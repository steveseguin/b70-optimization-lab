"""In-worker decode-step profiler (research overlay). Enabled with B70_PROFILE_DIR=<dir>.

Wraps GPUModelRunner.execute_model: after B70_PROFILE_SKIP calls (default 40) it starts torch.profiler with CPU and
XPU activities, records B70_PROFILE_STEPS calls (default 60), exports a Chrome trace to
<dir>/worker-rank<r>-pid<pid>.json and never profiles again. No HTTP endpoint is involved, so the trace is written
even if the API server drops a connection. Each tensor-parallel worker writes its own file. Timing under the profiler
is not a speed measurement; the trace is for kernel time versus idle gaps and launch counts.

B70_PROFILE_RANKS (e.g. "0", or "0,1") restricts profiling to those tensor-parallel ranks; unset means every rank
profiles. The rank is resolved **lazily, on the first execute_model call**, and the choice is logged once. It used to
be resolved in register(), which runs before the tensor-parallel group exists: get_tensor_model_parallel_rank() raised
there and the fallback to RANK/LOCAL_RANK -- unset in vLLM's spawned XPU workers -- made every worker resolve to rank
0, so both ranks profiled and each step carried the other process's profiling overhead. Traces taken before
2026-09-18 therefore contain both ranks and their step times are inflated (see
notes/2026-09-18-two-card-exchange-fusion-memo.md). Resolution order on that first call: the tensor-parallel group,
then the runner's own rank/local_rank attribute, then $RANK/$LOCAL_RANK, then 0.
"""
import os
import time


def _resolve_rank(runner):
    """Return (rank, source). Call this only once the tensor-parallel group exists (i.e. inside execute_model)."""
    try:
        from vllm.distributed.parallel_state import get_tensor_model_parallel_rank
        return int(get_tensor_model_parallel_rank()), 'tp-group'
    except Exception:
        pass
    for attribute in ('rank', 'local_rank'):
        value = getattr(runner, attribute, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return int(value), f'runner.{attribute}'
    for name in ('RANK', 'LOCAL_RANK'):
        value = os.environ.get(name, '').strip()
        if value:
            try:
                return int(value), f'${name}'
            except ValueError:
                pass
    return 0, 'default'


def register():
    directory = os.environ.get('B70_PROFILE_DIR', '').strip()
    if not directory:
        return
    import torch
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as runner_module

    logger = init_logger('b70_step_profiler')
    cls = runner_module.GPUModelRunner
    if getattr(cls, '_b70_step_profiler', False):
        return
    skip = int(os.environ.get('B70_PROFILE_SKIP', '40'))
    steps = int(os.environ.get('B70_PROFILE_STEPS', '60'))
    ranks = os.environ.get('B70_PROFILE_RANKS', '').strip()  # e.g. "0": only that tensor-parallel rank profiles
    selected = [item.strip() for item in ranks.split(',') if item.strip()]
    state = {'calls': 0, 'profiler': None, 'done': False, 'started': None, 'pending': 0, 'label': None,
             'window_calls': 0, 'rank': None, 'enabled': None}
    original = cls.execute_model
    # B70_PROFILE_BY_PREFILL=1: instead of one window after `skip` calls, open a window of `steps` decode calls after
    # every prefill of at least B70_PROFILE_MIN_PREFILL tokens (default 8192), named by the prefilled token count, so
    # one server can be profiled at several context lengths.
    by_prefill = os.environ.get('B70_PROFILE_BY_PREFILL', '').strip() == '1'
    min_prefill = int(os.environ.get('B70_PROFILE_MIN_PREFILL', '8192'))

    def enabled_for(runner):
        """Resolve this worker's rank on the first call and decide, once, whether it profiles."""
        if state['enabled'] is None:
            rank, source = _resolve_rank(runner)
            state['rank'] = rank
            state['enabled'] = not selected or str(rank) in selected
            if state['enabled']:
                logger.warning('b70_step_profiler: rank %d (via %s) is profiling (B70_PROFILE_RANKS=%s)',
                               rank, source, ranks or '<all>')
            else:
                logger.warning('b70_step_profiler: rank %d (via %s) not selected (%s); not profiling',
                               rank, source, ranks)
        return state['enabled']

    def export(label, elapsed, n_steps):
        rank = state['rank']
        path = os.path.join(directory, f'worker-rank{rank}-{label}.json')
        state['profiler'].export_chrome_trace(path)
        with open(os.path.join(directory, f'worker-rank{rank}-{label}.meta.json'), 'w') as handle:
            handle.write('{"steps": %d, "wall_seconds": %.6f, "label": "%s"}\n' % (n_steps, elapsed, label))
        logger.warning('b70_step_profiler: wrote %s (%d steps, %.2f s wall)', path, n_steps, elapsed)
        state['profiler'] = None

    def execute_model(self, *args, **kwargs):
        if not enabled_for(self):
            return original(self, *args, **kwargs)
        if by_prefill:
            scheduled = getattr(args[0] if args else kwargs.get('scheduler_output'), 'total_num_scheduled_tokens', 0) or 0
            if scheduled >= 1024:
                state['pending'] += int(scheduled)
                if state['profiler'] is not None:  # a new prefill interrupts a window: drop it
                    state['profiler'].__exit__(None, None, None); state['profiler'] = None
                return original(self, *args, **kwargs)
            if state['profiler'] is None and state['pending'] >= min_prefill:
                activities = [torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.XPU]
                state['profiler'] = torch.profiler.profile(activities=activities, record_shapes=False, with_stack=False)
                state['profiler'].__enter__()
                state['started'] = time.perf_counter()
                state['label'] = f'ctx{state["pending"]}'
                state['window_calls'] = 0
                state['pending'] = 0
                logger.warning('b70_step_profiler: window %s: %d decode calls', state['label'], steps)
            elif state['profiler'] is None:
                state['pending'] = 0
            result = original(self, *args, **kwargs)
            if state['profiler'] is not None:
                state['window_calls'] += 1
                if state['window_calls'] >= steps:
                    torch.xpu.synchronize()
                    elapsed = time.perf_counter() - state['started']
                    state['profiler'].__exit__(None, None, None)
                    export(state['label'], elapsed, steps)
            return result
        if state['done']:
            return original(self, *args, **kwargs)
        state['calls'] += 1
        if state['profiler'] is None and state['calls'] > skip:
            activities = [torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.XPU]
            state['profiler'] = torch.profiler.profile(activities=activities, record_shapes=False, with_stack=False)
            state['profiler'].__enter__()
            state['started'] = time.perf_counter()
            logger.warning('b70_step_profiler: profiling %d execute_model calls starting at call %d', steps, state['calls'])
        result = original(self, *args, **kwargs)
        if state['profiler'] is not None and state['calls'] >= skip + steps:
            torch.xpu.synchronize()
            elapsed = time.perf_counter() - state['started']
            state['profiler'].__exit__(None, None, None)
            rank = state['rank']
            path = os.path.join(directory, f'worker-rank{rank}-pid{os.getpid()}.json')
            state['profiler'].export_chrome_trace(path)
            with open(os.path.join(directory, f'worker-rank{rank}-pid{os.getpid()}.meta.json'), 'w') as handle:
                handle.write('{"steps": %d, "skipped": %d, "wall_seconds": %.6f}\n' % (steps, skip, elapsed))
            logger.warning('b70_step_profiler: wrote %s (%d steps, %.2f s wall)', path, steps, elapsed)
            state['profiler'] = None
            state['done'] = True
        return result

    cls.execute_model = execute_model
    cls._b70_step_profiler = True
    logger.warning('b70_step_profiler: enabled (skip %d, steps %d, dir %s, ranks %s)', skip, steps, directory,
                   ranks or '<all>')
