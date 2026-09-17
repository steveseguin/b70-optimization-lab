#!/usr/bin/env python3
"""Does a strict baton hand-off between two clip threads keep both shard cards busy?

Design B premise (two-clip-sampler-design.md): clip A and clip B each run on
their own thread, but only the thread holding the baton issues GPU work, and
the baton changes hands at the shard boundary (after a clip's xpu:0 segment
and its cross-card copy have been issued) and at the end of the forward. No
two threads ever issue at once, and no capture overlaps a replay: both clips'
graphs are captured in a serial warm-up first.

Each "forward" is segment 0 on xpu:0 (21 block-sized GEMMs, captured as one
graph) -> copy of the activation to xpu:1 -> segment 1 on xpu:1 (27 GEMMs).
Outputs are compared bit for bit against the serial run of the same clips.
Exclusive cards; no server may be running.
"""
import threading, time, sys
import torch

STEPS = 11
WARM = 2
BLOCKS0, BLOCKS1 = 21, 27
D = 4096
M = 256


H = 16384   # each block: three (D->H, H->D) pairs = six 128 MB weights = 768 MB, like a real 737 MB block


def make_weights(dev, n):
    g = torch.Generator(device='cpu'); g.manual_seed(7 + n)
    out = []
    for _ in range(n):
        out.append([(torch.randn(D, H, generator=g).to(dtype=torch.bfloat16, device=dev),
                     torch.randn(H, D, generator=g).to(dtype=torch.bfloat16, device=dev)) for _ in range(3)])
    return out


torch.xpu.set_device(0)
W0 = make_weights('xpu:0', BLOCKS0)
W1 = make_weights('xpu:1', BLOCKS1)


class Clip:
    """One clip: static input, captured graphs per segment, its own state."""

    def __init__(self, name, seed):
        self.name = name
        g = torch.Generator(device='cpu'); g.manual_seed(seed)
        self.x0 = torch.randn(M, D, generator=g).to(dtype=torch.bfloat16, device='xpu:0')
        self.in0 = torch.empty_like(self.x0)          # static input of segment 0
        self.out0 = torch.empty_like(self.x0)         # static output of segment 0
        self.in1 = torch.empty(M, D, dtype=torch.bfloat16, device='xpu:1')
        self.out1 = torch.empty_like(self.in1)
        self.g0 = self.g1 = None

    @staticmethod
    def block(x, pairs):
        for w_up, w_down in pairs:
            x = (torch.nn.functional.silu(x @ w_up) @ w_down) * 0.5 + x
        return x

    def eager0(self, x):
        for pairs in W0:
            x = self.block(x, pairs)
        return x

    def eager1(self, x):
        for pairs in W1:
            x = self.block(x, pairs)
        return x

    def capture(self):
        with torch.xpu.device(0):
            self.in0.copy_(self.x0)
            s = torch.xpu.Stream(device='xpu:0'); s.wait_stream(torch.xpu.current_stream(0))
            with torch.xpu.stream(s):
                for _ in range(3): self.eager0(self.in0)
            torch.xpu.current_stream(0).wait_stream(s); torch.xpu.synchronize(0)
            self.g0 = torch.xpu.XPUGraph()
            with torch.xpu.graph(self.g0, stream=torch.xpu.Stream(device='xpu:0')):
                self.out0.copy_(self.eager0(self.in0))
        with torch.xpu.device(1):
            self.in1.copy_(self.out0.to('xpu:1'))
            s = torch.xpu.Stream(device='xpu:1'); s.wait_stream(torch.xpu.current_stream(1))
            with torch.xpu.stream(s):
                for _ in range(3): self.eager1(self.in1)
            torch.xpu.current_stream(1).wait_stream(s); torch.xpu.synchronize(1)
            self.g1 = torch.xpu.XPUGraph()
            with torch.xpu.graph(self.g1, stream=torch.xpu.Stream(device='xpu:1')):
                self.out1.copy_(self.eager1(self.in1))
        torch.xpu.synchronize(0); torch.xpu.synchronize(1)

    def serial_forward(self, x):
        """Reference: segment 0, blocking copy, segment 1, blocking copy back."""
        self.in0.copy_(x); self.g0.replay()
        self.in1.copy_(self.out0.to('xpu:1', non_blocking=False))
        self.g1.replay()
        return self.out1.to('xpu:0', non_blocking=False).clone()


def run_serial(clips):
    xs = [c.x0.clone() for c in clips]
    torch.xpu.synchronize(0); torch.xpu.synchronize(1)
    t = time.perf_counter()
    for _ in range(STEPS):
        xs = [c.serial_forward(x) for c, x in zip(clips, xs)]
    torch.xpu.synchronize(0); torch.xpu.synchronize(1)
    return xs, time.perf_counter() - t


class Baton:
    def __init__(self, order):
        self.order = order; self.holder = order[0]
        self.cv = threading.Condition()

    def acquire(self, who):
        with self.cv:
            while self.holder != who:
                self.cv.wait()

    def pass_on(self, who):
        with self.cv:
            i = self.order.index(who); self.holder = self.order[(i + 1) % len(self.order)]
            self.cv.notify_all()


def run_baton(clips):
    """Each clip thread: [acquire] issue seg0 + non-blocking copy + event [pass] [acquire] issue seg1 + copy back [pass] ..."""
    baton = Baton([c.name for c in clips])
    results = {}
    errors = {}

    def worker(c):
        try:
            x = c.x0.clone()
            for _ in range(STEPS):
                baton.acquire(c.name)
                with torch.xpu.device(0):
                    c.in0.copy_(x); c.g0.replay()
                    # cross-card copy, stream-ordered after seg0 on xpu:0's current stream
                    c.in1.copy_(c.out0, non_blocking=True)
                    ev = torch.xpu.Event(); ev.record(torch.xpu.current_stream(0))
                baton.pass_on(c.name)
                baton.acquire(c.name)
                with torch.xpu.device(1):
                    torch.xpu.current_stream(1).wait_event(ev)
                    c.g1.replay()
                    x = torch.empty_like(c.out1, device='xpu:0')
                    x.copy_(c.out1, non_blocking=True)
                    ev2 = torch.xpu.Event(); ev2.record(torch.xpu.current_stream(1))
                with torch.xpu.device(0):
                    torch.xpu.current_stream(0).wait_event(ev2)
                baton.pass_on(c.name)
            results[c.name] = x
        except BaseException as e:  # noqa
            errors[c.name] = repr(e); baton.pass_on(c.name)

    ths = [threading.Thread(target=worker, args=(c,)) for c in clips]
    torch.xpu.synchronize(0); torch.xpu.synchronize(1)
    t = time.perf_counter()
    for th in ths: th.start()
    for th in ths: th.join()
    torch.xpu.synchronize(0); torch.xpu.synchronize(1)
    return [results.get(c.name) for c in clips], time.perf_counter() - t, errors


def run_free(clips):
    """Two threads, no baton: each clip issues freely on its own; graphs were captured serially first."""
    results, errors = {}, {}

    def worker(c):
        try:
            x = c.x0.clone()
            for _ in range(STEPS):
                x = c.serial_forward(x)
            results[c.name] = x
        except BaseException as e:  # noqa
            errors[c.name] = repr(e)

    ths = [threading.Thread(target=worker, args=(c,)) for c in clips]
    torch.xpu.synchronize(0); torch.xpu.synchronize(1)
    t = time.perf_counter()
    for th in ths: th.start()
    for th in ths: th.join()
    torch.xpu.synchronize(0); torch.xpu.synchronize(1)
    return [results.get(c.name) for c in clips], time.perf_counter() - t, errors


def run_free_streams(clips):
    """Two threads, each with its OWN stream on each card, so one clip's copies and
    waits are never queued behind the other clip's replays on a shared default stream."""
    results, errors = {}, {}

    def worker(c):
        try:
            s0 = torch.xpu.Stream(device='xpu:0'); s1 = torch.xpu.Stream(device='xpu:1')
            x = c.x0.clone()
            for _ in range(STEPS):
                with torch.xpu.device(0), torch.xpu.stream(s0):
                    c.in0.copy_(x); c.g0.replay()
                    c.in1.copy_(c.out0, non_blocking=True)
                    ev = torch.xpu.Event(); ev.record(s0)
                with torch.xpu.device(1), torch.xpu.stream(s1):
                    s1.wait_event(ev)
                    c.g1.replay()
                    x = torch.empty_like(c.out1, device='xpu:0')
                    x.copy_(c.out1, non_blocking=True)
                    ev2 = torch.xpu.Event(); ev2.record(s1)
                with torch.xpu.device(0), torch.xpu.stream(s0):
                    s0.wait_event(ev2)
            s0.synchronize(); s1.synchronize()
            results[c.name] = x
        except BaseException as e:  # noqa
            errors[c.name] = repr(e)

    ths = [threading.Thread(target=worker, args=(c,)) for c in clips]
    torch.xpu.synchronize(0); torch.xpu.synchronize(1)
    t = time.perf_counter()
    for th in ths: th.start()
    for th in ths: th.join()
    torch.xpu.synchronize(0); torch.xpu.synchronize(1)
    return [results.get(c.name) for c in clips], time.perf_counter() - t, errors


clips = [Clip('A', 1), Clip('B', 2)]
for c in clips: c.capture()
# Does replay() return before the work completes?
c0 = clips[0]; c0.in0.copy_(c0.x0); torch.xpu.synchronize(0)
t = time.perf_counter(); c0.g0.replay(); t_issue = time.perf_counter() - t
torch.xpu.synchronize(0); t_done = time.perf_counter() - t
print({'replay_issue_ms': round(t_issue * 1e3, 2), 'replay_done_ms': round(t_done * 1e3, 2),
       'replay_is_async': t_issue < 0.3 * t_done}, flush=True)
# Does a cross-card copy block the issuing thread?
t = time.perf_counter(); c0.g0.replay(); c0.in1.copy_(c0.out0, non_blocking=True); t_copy_issue = time.perf_counter() - t
torch.xpu.synchronize(0); torch.xpu.synchronize(1); t_copy_done = time.perf_counter() - t
print({'replay_plus_copy_issue_ms': round(t_copy_issue * 1e3, 2), 'done_ms': round(t_copy_done * 1e3, 2)}, flush=True)
ref, t_serial = run_serial(clips)
ref2, t_serial2 = run_serial(clips)
print('weights per card: xpu:0 %.1f GB, xpu:1 %.1f GB' % (BLOCKS0 * 6 * D * H * 2 / 1e9, BLOCKS1 * 6 * D * H * 2 / 1e9), flush=True)
same_serial = all(torch.equal(a.view(torch.int16), b.view(torch.int16)) for a, b in zip(ref, ref2))
outs, t_baton, errors = run_baton(clips)
outs2, t_baton2, errors2 = run_baton(clips)
equal = [o is not None and torch.equal(o.view(torch.int16), r.view(torch.int16)) for o, r in zip(outs, ref)]
free, t_free, ferr = run_free(clips)
free2, t_free2, ferr2 = run_free(clips)
fequal = [o is not None and torch.equal(o.view(torch.int16), r.view(torch.int16)) for o, r in zip(free2, ref)]
print({'free_threads_s': round(t_free2, 4), 'free_speedup_vs_serial': round(t_serial2 / t_free2, 3),
       'free_bitwise_equal_to_serial': fequal, 'free_errors': ferr or ferr2}, flush=True)
fs, t_fs, fserr = run_free_streams(clips)
fs2, t_fs2, fserr2 = run_free_streams(clips)
fsequal = [o is not None and torch.equal(o.view(torch.int16), r.view(torch.int16)) for o, r in zip(fs2, ref)]
print({'free_streams_s': round(t_fs2, 4), 'free_streams_speedup_vs_serial': round(t_serial2 / t_fs2, 3),
       'free_streams_bitwise_equal_to_serial': fsequal, 'errors': fserr or fserr2}, flush=True)
print({'serial_s': round(t_serial2, 4), 'baton_s': round(t_baton2, 4), 'speedup': round(t_serial2 / t_baton2, 3),
       'serial_reproducible': same_serial, 'baton_bitwise_equal_to_serial': equal, 'errors': errors or errors2,
       'per_clip_serial_ms': round(t_serial2 / STEPS / 2 * 1e3, 1), 'per_clip_baton_ms': round(t_baton2 / STEPS / 2 * 1e3, 1),
       'ideal_bound': 'xpu:1 segment is 27/48 of a forward, so the best case is 48/27 = 1.78x'})
