"""Packet117: the stage-A / stage-B anchor encodes run on the decode thread (LTX_PREP_AHEAD, LTX_BENCODE_OVERLAP).

Torch and the runtime's trusted callbacks are passed in; this module imports nothing device-related.

The frame anchor conditions both sampler stages through the native `LTXVImgToVideoInplace.execute`
(nodes_lt.py:152-177): `t = vae.encode(pixels)` of the anchor frame (stage A: bilinearly resized to 128x128;
stage B: 256x256 as is), then the slot-0 copy into a clone of the latent and the noise mask. The encode
depends only on the anchor frame and the latent's pixel size, so it can run before the stage's node does.

Packet117 runs it on the decode thread instead of the prompt thread:

- stage A (prep-ahead): right after the predecessor's receipt commits, beside the client's turnaround and
  the successor's admission;
- stage B (overlap): when the successor's sampler A starts, beside stage A on xpu:0/xpu:1.

How the native code still does all the arithmetic. The decode thread calls the native node itself with a
`CaptureVAE` (the real VAE's `downscale_index_formula`; `encode` calls the real `VAE.encode` and records
the pixels it was given and the latent it returned) on a zero latent of the stage's shape, and keeps `t`.
The stage's node later calls the native node again with a `ReplayVAE`, whose `encode` checks that it is
handed exactly the recorded pixels (shape, dtype and SHA-256 of the bytes) and returns a copy of `t`
(SHA-256 checked). The resize, the slot copy and the mask are the native code on the stage's own inputs.

The guard variant (`Xpu3Snapshot`): the encode runs on xpu:3 while the samplers run on xpu:0/xpu:1, so its
safety snapshots synchronise xpu:3 ONLY and check what the encode can touch:
  P1 the controller is not failed or closed; P2 the stream authority is healthy and in its qualification or
  stream phase; P3 the fault observer is clear; P4 torch.xpu.synchronize('xpu:3') (only xpu:3);
  P5 physical free memory of xpu:3 >= 9 GiB before / 2 GiB after (the 9/2 GiB floors of xpu:3);
  P6 xpu:3 allocation counters valid (reserved >= allocated, peak >= allocated); P7 the residence and
  ownership fingerprint of every xpu:3 role (text_secondary, video_vae, audio_vae) equals the admitted one;
  P8 both VAEs are still bound to this safety controller.
Plus, around the encode: E1 the encoder lock (no conditioning-guard call on the prompt thread runs at the
same time); E2 the anchor tensor's metadata and bytes (SHA-256, finite) before and after; E3 the encoder's
per-thread temporal cache is empty for this thread and holds no other thread's entry, before and after;
E4 the native bindings (registration, code objects, pinned sources) and settings.
Nothing is removed from the prompt thread: the request's before/after snapshots and the stage-A/B
conditioning snapshots still run there, on all four cards, with the 8/8/2/9 GiB and 2 GiB floors, around
the (now encode-free) native call; the four-card floor checks of xpu:0/1/2 stay exactly where they were.
A failure latches the server (the decode job raises) and the runtime writes LATCH_NAME, after which the
launcher refuses LTX_BENCODE_OVERLAP=1 and LTX_PREP_AHEAD=1.
"""
import hashlib
import threading
import time

SCHEMA = 'ltx.stream117.precompute.v1'
LATCH_NAME = 'precompute-117-refused.json'
GIB = 2 ** 30
XPU3 = 'xpu:3'
XPU3_ROLES = ('text_secondary', 'video_vae', 'audio_vae')     # native_safety.ROLES placed on xpu:3
PRE_FLOOR = 9 * GIB
POST_FLOOR = 2 * GIB
STAGES = ('A', 'B')
STATES = ('scheduled', 'running', 'done', 'failed', 'cancelled', 'superseded')
SAFETY_ATTRIBUTE = '_ltx_native_reference_safety'
CHECKS = {
    'P1': 'controller not failed or closed',
    'P2': 'stream authority healthy, phase stream_qualification or stream',
    'P3': 'fault observer clear',
    'P4': 'synchronize xpu:3 (only)',
    'P5': 'xpu:3 physical free >= 9 GiB before / 2 GiB after',
    'P6': 'xpu:3 allocation counters valid',
    'P7': 'residence/ownership fingerprints of text_secondary, video_vae, audio_vae unchanged',
    'P8': 'both VAEs bound to the safety controller',
    'E1': 'encoder lock held (no prompt-thread conditioning call at the same time)',
    'E2': 'anchor metadata, SHA-256 and finiteness before and after',
    'E3': 'encoder temporal cache: no own or foreign entry before and after',
    'E4': 'native bindings and settings checked'}


class PrecomputeRefusal(RuntimeError):
    pass


def require(ok, why):
    if not ok:
        raise PrecomputeRefusal(why)


def tensor_sha256(torch, tensor):
    t = tensor.detach().to('cpu').contiguous()
    return hashlib.sha256(t.view(torch.uint8).numpy()).hexdigest()


class Xpu3Snapshot:
    """The xpu:3-only safety snapshot of the decode thread's encode (checks P1-P8 of the module doc)."""

    def __init__(self, *, controller, phase_ok, fault, synchronize, free_bytes, counters, rows, fingerprint):
        for fn in (phase_ok, fault, synchronize, free_bytes, counters, rows, fingerprint):
            require(callable(fn), 'Trusted snapshot callbacks required')
        self.controller = controller
        self.phase_ok, self.fault, self.synchronize = phase_ok, fault, synchronize
        self.free_bytes, self.counters, self.rows, self.fingerprint = free_bytes, counters, rows, fingerprint
        self.synchronized = []           # every card this guard synchronised (tests: only ever xpu:3)

    @staticmethod
    def _bytes(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    def take(self, event, floor):
        c = self.controller
        require(c.failed is None and not c.closed, 'P1: safety controller failed or closed')     # P1
        require(self.phase_ok() is True, 'P2: stream authority is not healthy in a stream phase')  # P2
        require(self.fault() is False, 'P3: fault observer refused the encode')                    # P3
        self.synchronize(XPU3)                                                                    # P4
        self.synchronized.append(XPU3)
        free = self.free_bytes(XPU3)
        require(self._bytes(free) and free >= floor,                                              # P5
                'P5: xpu:3 physical free %r below the %d-byte floor (%s)' % (free, floor, event))
        counters = self.counters(XPU3)
        require(type(counters) is dict and set(counters) == {'allocated', 'reserved', 'peak'} and
                all(self._bytes(v) for v in counters.values()) and
                counters['reserved'] >= counters['allocated'] and counters['peak'] >= counters['allocated'],
                'P6: invalid xpu:3 allocation counters')                                          # P6
        residence = {}
        for role in XPU3_ROLES:                                                                   # P7
            value = self.fingerprint(self.rows(role))
            require(value == c.expected_residence[role], 'P7: residence/ownership changed: ' + role)
            residence[role] = value
        for role in ('video_vae', 'audio_vae'):                                                   # P8
            require(getattr(c.objects[role], SAFETY_ATTRIBUTE, None) is c, 'P8: VAE safety binding changed')
        return {'event': event, 'card': XPU3, 'synchronized': [XPU3], 'required_free_bytes': floor,
                'physical_free_bytes': free, 'counters': counters, 'residence': residence,
                'checks': ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8'], 'admitted': True,
                'time_ns': time.time_ns()}


class CaptureVAE:
    """Stands in for the VAE in the decode thread's native call: the real encode, recorded once."""

    def __init__(self, torch, vae):
        self.torch, self.vae = torch, vae
        self.downscale_index_formula = vae.downscale_index_formula
        self.calls = []

    def encode(self, pixels):
        require(not self.calls, 'The native node encoded twice')
        require(isinstance(pixels, self.torch.Tensor) and pixels.dtype is self.torch.float32 and
                str(pixels.device) == 'cpu', 'Unexpected encode pixels')
        record = {'pixels_shape': list(pixels.shape), 'pixels_sha256': tensor_sha256(self.torch, pixels)}
        t = self.vae.encode(pixels)
        record.update(t_shape=list(t.shape), t_dtype=str(t.dtype), t_sha256=tensor_sha256(self.torch, t))
        self.calls.append((record, t))
        return t


class ReplayVAE:
    """Stands in for the VAE in the stage's native call: hands back the precomputed encode, once, only for
    exactly the recorded pixels."""

    def __init__(self, torch, vae, entry):
        self.torch, self.entry = torch, entry
        self.downscale_index_formula = vae.downscale_index_formula
        self.used = False

    def encode(self, pixels):
        require(not self.used, 'The native node encoded twice')
        self.used = True
        rec = self.entry.record
        require(isinstance(pixels, self.torch.Tensor) and pixels.dtype is self.torch.float32 and
                str(pixels.device) == 'cpu' and list(pixels.shape) == rec['pixels_shape'] and
                tensor_sha256(self.torch, pixels) == rec['pixels_sha256'],
                'Stage pixels differ from the precomputed encode\'s pixels')
        t = self.entry.t.clone()
        require(tensor_sha256(self.torch, t) == rec['t_sha256'], 'Precomputed encode changed')
        return t


class Entry:
    def __init__(self, anchor_sha256, stage, source_run_name):
        self.anchor_sha256, self.stage, self.source_run_name = anchor_sha256, stage, source_run_name
        self.state = 'scheduled'
        self.event = threading.Event()
        self.t = None
        self.record = None
        self.error = None
        self.consumed_by = None
        self.timing = {'scheduled': time.time_ns(), 'start': None, 'done': None}

    def summary(self):
        return {'anchor_sha256': self.anchor_sha256, 'stage': self.stage, 'source_run_name': self.source_run_name,
                'state': self.state, 'consumed_by': self.consumed_by, 'error': self.error,
                'record': None if self.record is None else {k: v for k, v in self.record.items()
                                                            if k not in ('before', 'after')},
                'timing_ns': dict(self.timing)}


class PrecomputeStore:
    """The precomputed encodes of the NEWEST anchor only (a strict-predecessor chain consumes nothing older)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.anchor_sha256 = None
        self.entries = {}
        self.history = []          # summaries of finished entries (the newest 32)

    def reserve(self, anchor_sha256, stages, source_run_name):
        """Decode thread, before the anchor is handed to the chain: the stages that WILL be precomputed for
        the chunk that consumes this anchor. Older entries are superseded (their waiters released)."""
        with self.lock:
            for entry in self.entries.values():
                if entry.state in ('scheduled', 'running'):
                    entry.state = 'superseded'
                    entry.event.set()
                self.history.append(entry.summary())
            del self.history[:-32]
            self.anchor_sha256 = anchor_sha256
            self.entries = {stage: Entry(anchor_sha256, stage, source_run_name) for stage in stages}
            return [self.entries[s] for s in stages]

    def lookup(self, anchor_sha256, stage):
        with self.lock:
            entry = self.entries.get(stage)
            return entry if entry is not None and entry.anchor_sha256 == anchor_sha256 else None

    def start(self, entry):
        with self.lock:
            if entry.state != 'scheduled':
                return False
            entry.state = 'running'
            entry.timing['start'] = time.time_ns()
            return True

    def finish(self, entry, t, record):
        with self.lock:
            require(entry.state == 'running', 'Precompute finished from state ' + entry.state)
            entry.t, entry.record, entry.state = t, record, 'done'
            entry.timing['done'] = time.time_ns()
            entry.event.set()

    def fail(self, entry, error):
        with self.lock:
            entry.state, entry.error = 'failed', repr(error)[:1000]
            entry.timing['done'] = time.time_ns()
            entry.event.set()

    def cancel(self, entry, reason):
        with self.lock:
            if entry.state == 'scheduled':
                entry.state, entry.error = 'cancelled', reason
                entry.event.set()
                return True
            return False

    def take(self, entry, consumer, timeout_s):
        """Prompt thread, outside every lock: wait (bounded) for a reserved entry. Returns the entry when it is
        done (and marks it consumed), None when it was cancelled or superseded; raises on a failure or the
        bound."""
        started = time.monotonic()
        require(entry.event.wait(timeout_s), 'Precomputed stage-%s encode not ready within %.0f s'
                % (entry.stage, timeout_s))
        with self.lock:
            if entry.state == 'failed':
                raise PrecomputeRefusal('Precomputed stage-%s encode failed: %s' % (entry.stage, entry.error))
            if entry.state != 'done':
                return None, round(time.monotonic() - started, 6)
            require(entry.consumed_by is None, 'Precomputed encode consumed twice')
            entry.consumed_by = consumer
            return entry, round(time.monotonic() - started, 6)

    def summary(self):
        with self.lock:
            return {'anchor_sha256': self.anchor_sha256,
                    'entries': {s: e.summary() for s, e in self.entries.items()},
                    'history': list(self.history[-4:])}


def bitwise_equal(torch, a, b):
    return (a.dtype == b.dtype and a.shape == b.shape and
            torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8)))
