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

No device call is added and no tensor is read or written (the per-request view is read from numpy arrays on the host),
so no output can change. The four events are wrapped in a proxy that forwards everything, as b70-host-step-clock does.
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


def stamp(t):
    return time.strftime('%H:%M:%S', time.localtime(t)) + '.%03d' % int((t % 1) * 1000)


class Crumbs:
    def __init__(self, log, keep=32, stall_s=20.0, one_launch=False, clock=time.time):
        self.log, self.stall_s, self.one_launch, self.clock = log, stall_s, one_launch, clock
        self.steps = deque(maxlen=keep)
        self.index, self.rank, self.busy, self.reported = 0, '?', {}, set()
        self.lock = threading.Lock()
        self.watcher, self.dumped, self.stalled = None, None, None

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
                'preempted': len(getattr(out, 'preempted_req_ids', None) or ()), 'reqs': reqs, 'events': []}
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
        for s in steps:
            reqs = ' '.join('[%s sched %d draft %d comp %s | w comp %s tok %s acc %s]' % (
                r['id'], r['sched'], r['draft'], r['computed'], r.get('w_computed'), r.get('w_tokens'),
                r.get('w_accepted')) for r in s['reqs'])
            ev = ' '.join('%s.%s+%.1fms' % (n, w, (t - s['t']) * 1e3) for n, w, t in s['events'])
            lines.append('  #%d %s tokens %d fin %d pre %d%s %s | %s%s' % (
                s['i'], stamp(s['t']), s['tokens'], s['finished'], s['preempted'],
                ' ONE-LAUNCH' if s.get('one_launch') else '', reqs, ev, ' ' + s['view_error'] if 'view_error' in s else ''))
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


def install(cls, log, keep=32, stall_s=20.0, one_launch=False, watch=True):
    if getattr(cls, '_b70_step_breadcrumbs', False):
        return False
    init, execute, sample, draft = cls.__init__, cls.execute_model, cls.sample_tokens, cls.propose_draft_token_ids

    def crumbs_of(self):
        c = self.__dict__.get('_b70_crumbs')
        if c is None:
            c = self.__dict__['_b70_crumbs'] = Crumbs(log, keep, stall_s, one_launch)
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
    if install(module.GPUModelRunner, logger.warning, keep, stall_s, one_launch):
        logger.warning('b70_step_breadcrumbs 0.1.0: installed on GPUModelRunner (last %d steps kept in memory, written '
                       'on a stall over %.0f s or a failure; host only, no device call)', keep, stall_s)
