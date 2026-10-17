"""Host-side clock of decode steps (research overlay, diagnostic only). Enabled with B70_HOST_STEP_CLOCK=1.

The question (notes/2026-10-17-fp8-step-floor.md): is a drafting step's time set by the cards or by the host issuing
the step? With asynchronous scheduling the host runs at most one step ahead. When the cards are the slower side, the
host spends the difference waiting in one of the runner's event waits; when the host is the slower side, those waits
are near zero and the step takes as long as the host needs to issue it.

For each decode step (one whose scheduled tokens are 1 to B70_HOST_STEP_CLOCK_MAX_TOKENS, default 8) followed by
another decode step, on every worker:
  period   from this step's execute_model entry to the next step's
  execute  host time inside execute_model
  sample   host time inside sample_tokens (which includes `draft`)
  draft    host time inside propose_draft_token_ids (the drafter's passes, issued)
  wait     host time inside the runner's event waits (prepare_inputs, valid_sampled_token_count, draft_token_ids,
           num_accepted_tokens), wherever they are called in that period
One log line per run of at least 20 such steps (a run ends at any other step, so one line per answer), or every
B70_HOST_STEP_CLOCK_EVERY steps (default 400): means and medians in milliseconds.

No device synchronisation is added and no tensor is read or written, so no output can change. The four events are
wrapped in a proxy that forwards everything and times `synchronize()`; vLLM and the lab overlays only call `record()`
and `synchronize()` on them and test them against None (checked in the R314 tree, 2026-10-17).
"""
import os
import statistics
import time

EVENTS = ('prepare_inputs_event', 'valid_sampled_token_count_event', 'draft_token_ids_event',
          'num_accepted_tokens_event')
SHORT = {'prepare_inputs_event': 'prep', 'valid_sampled_token_count_event': 'count',
         'draft_token_ids_event': 'drafts', 'num_accepted_tokens_event': 'accepted'}
KEYS = ('period', 'execute', 'sample', 'draft', 'wait')


class TimedEvent:
    __slots__ = ('_event', '_name', '_clock')

    def __init__(self, event, name, clock):
        self._event, self._name, self._clock = event, name, clock

    def synchronize(self):
        t = time.perf_counter()
        try:
            return self._event.synchronize()
        finally:
            self._clock.waited(self._name, time.perf_counter() - t)

    def __getattr__(self, attr):
        return getattr(self._event, attr)


class Clock:
    def __init__(self, log, every=400, max_tokens=8, min_run=20):
        self.log, self.every, self.max_tokens, self.min_run = log, every, max_tokens, min_run
        self.rows, self.cur, self.t0, self.decode, self.lines = [], None, 0.0, False, 0
        self.rank = '?'

    def waited(self, name, dt):
        if self.cur is not None:
            self.cur['wait'] += dt
            self.cur[SHORT[name]] = self.cur.get(SHORT[name], 0.0) + dt

    def spent(self, key, dt):
        if self.cur is not None:
            self.cur[key] += dt

    def step(self, num_tokens, now=None):
        """Called at each execute_model entry."""
        now = time.perf_counter() if now is None else now
        decode = 1 <= num_tokens <= self.max_tokens
        if self.cur is not None and self.decode and decode:
            self.cur['period'] = now - self.t0
            self.rows.append(self.cur)
            if len(self.rows) >= self.every:
                self.flush('window')
        elif not decode and len(self.rows) >= self.min_run:
            self.flush('run')
        elif not decode:
            self.rows = []
        self.cur = {k: 0.0 for k in KEYS}
        self.t0, self.decode = now, decode

    def flush(self, why):
        rows, self.rows = self.rows, []
        if not rows:
            return
        self.lines += 1

        def ms(key):
            values = [r.get(key, 0.0) * 1e3 for r in rows]
            return statistics.fmean(values), statistics.median(values)

        parts = ['%s %.2f/%.2f' % ((k,) + ms(k)) for k in KEYS]
        parts.append('not waiting %.2f' % (ms('period')[0] - ms('wait')[0]))
        waits = ' '.join('%s %.2f' % (s, ms(s)[0]) for s in SHORT.values())
        self.log('b70_host_step_clock rank %s %s: %d decode steps, ms mean/median: %s; waits by event (mean): %s'
                 % (self.rank, why, len(rows), '; '.join(parts), waits))


def install(cls, log, every=400, max_tokens=8):
    if getattr(cls, '_b70_host_step_clock', False):
        return False
    init, execute, sample, draft = cls.__init__, cls.execute_model, cls.sample_tokens, cls.propose_draft_token_ids

    def clock_of(self):
        c = self.__dict__.get('_b70_clock')
        if c is None:
            c = self.__dict__['_b70_clock'] = Clock(log, every, max_tokens)
        return c

    def __init__(self, *args, **kwargs):
        init(self, *args, **kwargs)
        c = clock_of(self)
        for name in EVENTS:
            event = getattr(self, name, None)
            if event is not None and not isinstance(event, TimedEvent):
                setattr(self, name, TimedEvent(event, name, c))

    def timed(original, key):
        def wrapper(self, *args, **kwargs):
            c = clock_of(self)
            t = time.perf_counter()
            try:
                return original(self, *args, **kwargs)
            finally:
                c.spent(key, time.perf_counter() - t)
        wrapper.__name__, wrapper.__doc__ = original.__name__, original.__doc__
        return wrapper

    def execute_model(self, scheduler_output, *args, **kwargs):
        c = clock_of(self)
        if c.rank == '?':
            try:
                from vllm.distributed import get_tensor_model_parallel_rank
                c.rank = str(get_tensor_model_parallel_rank())
            except Exception:
                c.rank = 'unknown'
        t = time.perf_counter()
        c.step(int(getattr(scheduler_output, 'total_num_scheduled_tokens', 0) or 0), t)
        try:
            return execute(self, scheduler_output, *args, **kwargs)
        finally:
            c.spent('execute', time.perf_counter() - t)

    cls.__init__ = __init__
    cls.execute_model = execute_model
    cls.sample_tokens = timed(sample, 'sample')
    cls.propose_draft_token_ids = timed(draft, 'draft')
    cls._b70_host_step_clock = True
    return True


def register():
    if os.environ.get('B70_HOST_STEP_CLOCK', '').strip() != '1':
        return
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as module

    logger = init_logger('b70_host_step_clock')
    every = int(os.environ.get('B70_HOST_STEP_CLOCK_EVERY', '400') or 400)
    max_tokens = int(os.environ.get('B70_HOST_STEP_CLOCK_MAX_TOKENS', '8') or 8)
    if install(module.GPUModelRunner, logger.warning, every, max_tokens):
        logger.warning('b70_host_step_clock 0.1.0: installed on GPUModelRunner (decode steps of 1-%d tokens; '
                       'host time only, no device synchronisation)', max_tokens)
