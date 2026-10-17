"""Each worker's last steps, written to the server log when the worker stalls or fails (research overlay, diagnostic
only). Enabled with B70_STEP_BREADCRUMBS=1.

Why (notes/2026-10-17-context-lane-public-remeasure.md, campaign 28e): at 06:23 on 2026-10-17 a step on card 03:00.0
never finished. The worker only noticed when the next request arrived, 40 s after the last step it had been given, and
died with DEVICE_LOST; the engine's dump shows the new step, not the one that hung, and nothing shows whether the two
cards had been given the same step. The next occurrence has to say which step each card was given last and what its
shape was.

What it keeps, per worker, in memory: the last B70_STEP_BREADCRUMBS_KEEP (default 32) execute_model calls, each with
its wall time, scheduled tokens, finished/preempted counts and, per request (last 8 characters of its id): scheduled
tokens, draft tokens, the computed tokens the scheduler sent, and, after the call, this worker's own view (computed
tokens, tokens without drafts and accepted count from its CPU arrays) and whether the one-launch verify path applies
(one request, 2-8 rows, more than 1,536 keys); plus when each of the runner's four events was recorded and waited on.

When it writes them (one block per incident, prefixed `b70_step_breadcrumbs rank R`): a wait on one of the four events,
or a call of execute_model, sample_tokens or propose_draft_token_ids, has lasted longer than B70_STEP_BREADCRUMBS_STALL_S
seconds (default 20; a watcher thread compares host timestamps only), or one of them raised. The block is the kept
steps, oldest first, then the Python stacks of all threads.

0.2.0 (2026-10-17, notes/2026-10-17-hang-repro.md): each step also counts the torch.distributed calls this worker
issued from the start of its execute_model to the start of the next one, with a running signature of their names and
element counts. The two ranks must issue the same collectives in the same order; if a hang is a cross-card exchange
that one card never joined, the two ranks' blocks show different counts or signatures for the same step. Counting is
host arithmetic on the call's arguments (`numel()` of the tensors passed), nothing is read from the device.

No device call is added and no tensor is read or written (the per-request view is read from numpy arrays on the host),
so no output can change. The four events are wrapped in a proxy that forwards everything, as b70-host-step-clock does.

0.3.0 (2026-10-17, notes/2026-10-17-hang-repro.md), only with B70_STEP_BREADCRUMBS_DEVICE_MARKS=1 (off by default):
the host counts say what each card was given, not what its GPU finished. With the switch on, after every collective
this worker issues on an XPU tensor, its queue copies the collective's running number (mod 65,536, from a table on
the device) into 4 bytes of pinned host memory. The copy is ordered after the collective, so on a stall the block
names, read from host memory without touching the stuck queue, how many collectives this card has completed and
which issued ones have not (number, name, elements, step). Two cards whose completed counts differ by one point at a
collective one card left early; equal counts with nothing pending point at a non-collective kernel. One 4-byte
device-to-host copy per collective; it writes only its own buffers, so outputs cannot change. Calls with async_op are
not marked (their copy would not be ordered after the collective).
"""
import faulthandler
import os
import sys
import threading
import time
from collections import deque

EVENTS = ('prepare_inputs_event', 'valid_sampled_token_count_event', 'draft_token_ids_event',
          'num_accepted_tokens_event')
SHORT = {'prepare_inputs_event': 'prep', 'valid_sampled_token_count_event': 'count',
         'draft_token_ids_event': 'drafts', 'num_accepted_tokens_event': 'accepted'}
ONE_LAUNCH_KEYS = 1536
COLLECTIVES = ('all_reduce', 'all_gather_into_tensor', 'all_gather', 'reduce_scatter_tensor', 'reduce_scatter',
               'broadcast', 'gather', 'scatter', 'reduce', 'all_to_all_single', 'all_to_all', 'barrier', 'send', 'recv',
               'isend', 'irecv', 'broadcast_object_list', 'all_gather_object')
CURRENT = []          # this process's Crumbs (one model runner per worker); the collective wrappers count into it


def stamp(t):
    return time.strftime('%H:%M:%S', time.localtime(t)) + '.%03d' % int((t % 1) * 1000)


def first_device(args):
    for a in args:
        for b in (a if isinstance(a, (list, tuple)) else (a,)):
            dev = getattr(b, 'device', None)
            if dev is not None and hasattr(b, 'numel'):
                return dev
    return None


class DeviceMarks:
    """Per worker: after each collective on its card, a 4-byte copy of the collective's running number into pinned
    host memory, ordered after the collective on the card's queue (B70_STEP_BREADCRUMBS_DEVICE_MARKS=1). The completed
    count is exact while fewer than R collectives are pending (a step issues about 140)."""
    R = 1 << 16

    def __init__(self, log, keep=256, make=None):
        self.log, self.make = log, make or self.make_torch
        self.issued, self.device, self.table, self.host, self.off = 0, None, None, None, False
        self.recent = deque(maxlen=keep)

    def make_torch(self, device):
        import torch
        return (torch.arange(self.R, dtype=torch.int32, device=device),
                torch.full((1,), -1, dtype=torch.int32).pin_memory())

    def after(self, index, args, elems, step):
        if self.off:
            return
        dev = first_device(args)
        if dev is None or getattr(dev, 'type', 'cpu') == 'cpu':
            return
        try:
            if self.device is None:
                self.table, self.host = self.make(dev)
                self.device = dev
            elif dev != self.device:
                return
            self.issued += 1
            n = self.issued % self.R
            self.host.copy_(self.table[n:n + 1], non_blocking=True)
            self.recent.append((self.issued, index, elems, step))
        except Exception as e:     # diagnostic only: never fail a collective
            self.off = True
            self.log('b70_step_breadcrumbs: device marks off after %r' % (e,))

    def completed(self):
        if self.host is None:
            return 0
        v = int(self.host[0])
        return 0 if v < 0 else self.issued - ((self.issued - v) % self.R)

    def report(self):
        if self.off or self.device is None:
            return 'device marks: %s' % ('off after an error' if self.off else 'no collective on a device yet')
        done = self.completed()
        pending = [r for r in self.recent if r[0] > done]
        text = 'device marks: %d collectives issued on %s, %d completed on this card' % (self.issued, self.device, done)
        if pending:
            n, index, elems, step = pending[0]
            text += '; first not completed #%d %s %d elems (step #%d); %d issued after it' % (
                n, COLLECTIVES[index], elems, step, len(pending) - 1)
        return text


class Crumbs:
    def __init__(self, log, keep=32, stall_s=20.0, one_launch=False, clock=time.time):
        self.log, self.stall_s, self.one_launch, self.clock = log, stall_s, one_launch, clock
        self.steps = deque(maxlen=keep)
        self.index, self.rank, self.busy, self.reported = 0, '?', {}, set()
        self.lock = threading.Lock()
        self.watcher, self.dumped, self.stalled = None, None, None
        self.marks = None

    # ---- what happened
    def begin_step(self, out):
        now = self.clock()
        reqs = []
        sched = getattr(out, 'num_scheduled_tokens', None) or {}
        spec = getattr(out, 'scheduled_spec_decode_tokens', None) or {}
        computed = {}
        for r in getattr(out, 'scheduled_new_reqs', None) or ():
            computed[getattr(r, 'req_id', '?')] = getattr(r, 'num_computed_tokens', None)
        cached = getattr(out, 'scheduled_cached_reqs', None)
        for rid, n in zip(getattr(cached, 'req_ids', None) or (), getattr(cached, 'num_computed_tokens', None) or ()):
            computed[rid] = n
        for rid, n in sched.items():
            reqs.append({'id': str(rid)[-8:], 'rid': rid, 'sched': int(n), 'draft': len(spec.get(rid, ()) or ()),
                         'computed': computed.get(rid)})
        step = {'i': self.index, 't': now, 'tokens': int(getattr(out, 'total_num_scheduled_tokens', 0) or 0),
                'finished': len(getattr(out, 'finished_req_ids', None) or ()),
                'preempted': len(getattr(out, 'preempted_req_ids', None) or ()), 'reqs': reqs, 'events': [],
                'coll': 0, 'sig': 0, 'elems': 0}
        self.index += 1
        with self.lock:
            self.steps.append(step)
        return step

    def view(self, step, runner):
        """This worker's own CPU view of the requests, after execute_model returned (host numpy arrays only)."""
        batch = getattr(runner, 'input_batch', None)
        if batch is None:
            return
        try:
            index = {rid: i for i, rid in enumerate(batch.req_ids)}
            accepted = getattr(getattr(runner, 'num_accepted_tokens', None), 'np', None)
            for r in step['reqs']:
                i = index.get(r['rid'])
                if i is None:
                    continue
                r['w_computed'] = int(batch.num_computed_tokens_cpu[i])
                r['w_tokens'] = int(batch.num_tokens_no_spec[i])
                if accepted is not None and i < len(accepted):
                    r['w_accepted'] = int(accepted[i])
        except Exception as e:     # diagnostic only: never fail a step
            step['view_error'] = repr(e)[:120]
        n = len(step['reqs'])
        if self.one_launch and n == 1:
            r = step['reqs'][0]
            keys = (r.get('w_computed', r['computed']) or 0) + r['sched']
            step['one_launch'] = 2 <= r['sched'] <= 8 and keys > ONE_LAUNCH_KEYS

    def collective(self, index, args):
        """One torch.distributed call issued by this worker: counted into the current step (host arithmetic only)."""
        n = 0
        for a in args:
            numel = getattr(a, 'numel', None)
            if numel is not None:
                try:
                    n += int(numel())
                except Exception:
                    pass
            elif isinstance(a, (list, tuple)):
                for b in a:
                    try:
                        n += int(b.numel())
                    except Exception:
                        pass
        steps = self.steps
        if steps:
            s = steps[-1]
            s['coll'] += 1
            s['elems'] += n
            s['sig'] = (s['sig'] * 1000003 + index * 7919 + n) & 0xffffffff
        return n

    def collective_done(self, index, args, n):
        """After the collective was issued: its device mark (B70_STEP_BREADCRUMBS_DEVICE_MARKS=1 only)."""
        if self.marks is not None:
            self.marks.after(index, args, n, self.steps[-1]['i'] if self.steps else -1)

    def event(self, name, what):
        with self.lock:
            if self.steps:
                self.steps[-1]['events'].append((SHORT.get(name, name), what, self.clock()))

    # ---- stalls and failures
    def enter(self, what):
        token = (what, self.clock())
        with self.lock:
            self.busy[id(token)] = token
        return id(token)

    def leave(self, key):
        with self.lock:
            entry = self.busy.pop(key, None)
            self.reported.discard(key)
            cleared = self.stalled is not None and not self.reported
            since, self.stalled = (self.stalled, None) if cleared else (None, self.stalled)
        if cleared and entry is not None:
            self.log('b70_step_breadcrumbs rank %s: stall cleared (%s ended after %.1f s)'
                     % (self.rank, entry[0], self.clock() - entry[1]))

    def check(self, now=None):
        """Called by the watcher: report each call or wait that has lasted longer than stall_s, once."""
        now = self.clock() if now is None else now
        with self.lock:
            late = [(k, w, t) for k, (w, t) in self.busy.items() if now - t > self.stall_s and k not in self.reported]
            self.reported.update(k for k, _, _ in late)
            first = bool(late) and self.stalled is None
            if first:
                self.stalled = now
        if first:          # one block per stall; the calls nested in it are named in the same block
            self.dump('STALL: ' + '; '.join('%s since %s, %.1f s' % (w, stamp(t), now - t)
                                             for _, w, t in sorted(late, key=lambda x: x[2])))

    def dump(self, reason):
        with self.lock:
            steps = list(self.steps)
        lines = ['b70_step_breadcrumbs rank %s %s; last %d steps, oldest first:' % (self.rank, reason, len(steps))]
        if self.marks is not None:
            try:
                lines.insert(0, 'b70_step_breadcrumbs rank %s %s' % (self.rank, self.marks.report()))
            except Exception as e:
                lines.insert(0, 'b70_step_breadcrumbs rank %s device marks unreadable: %r' % (self.rank, e))
        for s in steps:
            reqs = ' '.join('[%s sched %d draft %d comp %s | w comp %s tok %s acc %s]' % (
                r['id'], r['sched'], r['draft'], r['computed'], r.get('w_computed'), r.get('w_tokens'),
                r.get('w_accepted')) for r in s['reqs'])
            ev = ' '.join('%s.%s+%.1fms' % (n, w, (t - s['t']) * 1e3) for n, w, t in s['events'])
            lines.append('  #%d %s tokens %d fin %d pre %d%s %s | coll %d elems %d sig %08x | %s%s' % (
                s['i'], stamp(s['t']), s['tokens'], s['finished'], s['preempted'],
                ' ONE-LAUNCH' if s.get('one_launch') else '', reqs, s['coll'], s['elems'], s['sig'], ev,
                ' ' + s['view_error'] if 'view_error' in s else ''))
        self.log('\n'.join(lines))
        try:
            sys.stderr.flush()
            faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        except Exception as e:
            self.log('b70_step_breadcrumbs rank %s: stacks unavailable: %r' % (self.rank, e))

    def failed(self, what, e):
        """One block per exception, however many wrappers it passes through."""
        if self.dumped is not e:
            self.dumped = e
            self.dump('FAILED: %s raised %s' % (what, repr(e)[:200]))

    def start_watcher(self, period=1.0):
        if self.watcher is not None:
            return

        def run():
            while True:
                time.sleep(period)
                try:
                    self.check()
                except Exception:
                    pass
        self.watcher = threading.Thread(target=run, name='b70-step-breadcrumbs', daemon=True)
        self.watcher.start()


class CrumbEvent:
    __slots__ = ('_event', '_name', '_crumbs')

    def __init__(self, event, name, crumbs):
        self._event, self._name, self._crumbs = event, name, crumbs

    def record(self, *args, **kwargs):
        self._crumbs.event(self._name, 'rec')
        return self._event.record(*args, **kwargs)

    def synchronize(self):
        c = self._crumbs
        key = c.enter('wait on %s' % self._name)
        try:
            return self._event.synchronize()
        except BaseException as e:
            c.failed('wait on %s' % self._name, e)
            raise
        finally:
            c.leave(key)
            c.event(self._name, 'waited')

    def __getattr__(self, attr):
        return getattr(self._event, attr)


def compiling():
    try:
        import torch
        return torch.compiler.is_compiling()
    except Exception:
        return False


def count_collectives(module):
    """Wrap the torch.distributed functions in `module` so each call is counted into this process's Crumbs."""
    if getattr(module, '_b70_step_breadcrumbs', False):
        return False
    for index, name in enumerate(COLLECTIVES):
        original = getattr(module, name, None)
        if original is None:
            continue

        def wrapper(*args, _original=original, _index=index, **kwargs):
            c = CURRENT[0] if CURRENT and not compiling() else None   # under torch.compile tracing: the call only
            n = None
            if c is not None:
                try:
                    n = c.collective(_index, args)
                except Exception:
                    pass
            result = _original(*args, **kwargs)
            if c is not None and c.marks is not None and not kwargs.get('async_op'):
                c.collective_done(_index, args, n or 0)
            return result
        wrapper.__name__, wrapper.__doc__, wrapper.__wrapped__ = original.__name__, original.__doc__, original
        setattr(module, name, wrapper)
    module._b70_step_breadcrumbs = True
    return True


def install(cls, log, keep=32, stall_s=20.0, one_launch=False, watch=True, marks=False):
    if getattr(cls, '_b70_step_breadcrumbs', False):
        return False
    init, execute, sample, draft = cls.__init__, cls.execute_model, cls.sample_tokens, cls.propose_draft_token_ids

    def crumbs_of(self):
        c = self.__dict__.get('_b70_crumbs')
        if c is None:
            c = self.__dict__['_b70_crumbs'] = Crumbs(log, keep, stall_s, one_launch)
            if marks:
                c.marks = DeviceMarks(log)
            CURRENT[:] = [c]
        return c

    def __init__(self, *args, **kwargs):
        init(self, *args, **kwargs)
        c = crumbs_of(self)
        for name in EVENTS:
            event = getattr(self, name, None)
            if event is not None and not isinstance(event, CrumbEvent):
                setattr(self, name, CrumbEvent(event, name, c))

    def guarded(original, what):
        def wrapper(self, *args, **kwargs):
            c = crumbs_of(self)
            key = c.enter(what)
            try:
                return original(self, *args, **kwargs)
            except BaseException as e:
                c.failed(what, e)
                raise
            finally:
                c.leave(key)
        wrapper.__name__, wrapper.__doc__ = original.__name__, original.__doc__
        return wrapper

    guarded_execute = guarded(execute, 'execute_model')

    def execute_model(self, scheduler_output, *args, **kwargs):
        c = crumbs_of(self)
        if c.rank == '?':
            try:
                from vllm.distributed import get_tensor_model_parallel_rank
                c.rank = str(get_tensor_model_parallel_rank())
            except Exception:
                c.rank = 'unknown'
            if watch:
                c.start_watcher()
        step = c.begin_step(scheduler_output)
        try:
            return guarded_execute(self, scheduler_output, *args, **kwargs)
        finally:
            c.view(step, self)

    cls.__init__ = __init__
    cls.execute_model = execute_model
    cls.sample_tokens = guarded(sample, 'sample_tokens')
    cls.propose_draft_token_ids = guarded(draft, 'propose_draft_token_ids')
    cls._b70_step_breadcrumbs = True
    return True


def register():
    if os.environ.get('B70_STEP_BREADCRUMBS', '').strip() != '1':
        return
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as module

    logger = init_logger('b70_step_breadcrumbs')
    keep = int(os.environ.get('B70_STEP_BREADCRUMBS_KEEP', '32') or 32)
    stall_s = float(os.environ.get('B70_STEP_BREADCRUMBS_STALL_S', '20') or 20)
    one_launch = os.environ.get('B70_FA_VERIFY_ROWS_ONE_LAUNCH', '').strip() == '1'
    marks = os.environ.get('B70_STEP_BREADCRUMBS_DEVICE_MARKS', '').strip() == '1'
    import torch.distributed as dist
    counted = count_collectives(dist)
    if install(module.GPUModelRunner, logger.warning, keep, stall_s, one_launch, marks=marks):
        logger.warning('b70_step_breadcrumbs 0.3.0: installed on GPUModelRunner (last %d steps kept in memory, written '
                       'on a stall over %.0f s or a failure; torch.distributed calls counted per step: %s; %s)',
                       keep, stall_s, 'yes' if counted else 'already',
                       'device marks ON: a 4-byte copy to pinned host memory after each collective' if marks
                       else 'host only, no device call')
