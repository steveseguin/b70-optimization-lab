"""In-worker decode-step profiler (research overlay). Enabled with B70_PROFILE_DIR=<dir>.

Wraps GPUModelRunner.execute_model: after B70_PROFILE_SKIP calls (default 40) it starts torch.profiler with CPU and
XPU activities, records B70_PROFILE_STEPS calls (default 60), exports a Chrome trace to
<dir>/worker-rank<r>-pid<pid>.json and never profiles again. No HTTP endpoint is involved, so the trace is written
even if the API server drops a connection. Each tensor-parallel worker writes its own file. Timing under the profiler
is not a speed measurement; the trace is for kernel time versus idle gaps and launch counts.
"""
import os
import time


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
    if ranks:
        try:
            from vllm.distributed.parallel_state import get_tensor_model_parallel_rank
            my_rank = get_tensor_model_parallel_rank()
        except Exception:
            my_rank = int(os.environ.get('RANK', os.environ.get('LOCAL_RANK', '0')))
        if str(my_rank) not in ranks.split(','):
            logger.warning('b70_step_profiler: rank %d not selected (%s); not profiling', my_rank, ranks)
            return
    state = {'calls': 0, 'profiler': None, 'done': False, 'started': None, 'pending': 0, 'label': None, 'window_calls': 0}
    original = cls.execute_model
    # B70_PROFILE_BY_PREFILL=1: instead of one window after `skip` calls, open a window of `steps` decode calls after
    # every prefill of at least B70_PROFILE_MIN_PREFILL tokens (default 8192), named by the prefilled token count, so
    # one server can be profiled at several context lengths.
    by_prefill = os.environ.get('B70_PROFILE_BY_PREFILL', '').strip() == '1'
    min_prefill = int(os.environ.get('B70_PROFILE_MIN_PREFILL', '8192'))

    def export(label, elapsed, n_steps):
        rank = int(os.environ.get('RANK', os.environ.get('LOCAL_RANK', '0')))
        try:
            from vllm.distributed.parallel_state import get_tensor_model_parallel_rank
            rank = get_tensor_model_parallel_rank()
        except Exception:
            pass
        path = os.path.join(directory, f'worker-rank{rank}-{label}.json')
        state['profiler'].export_chrome_trace(path)
        with open(os.path.join(directory, f'worker-rank{rank}-{label}.meta.json'), 'w') as handle:
            handle.write('{"steps": %d, "wall_seconds": %.6f, "label": "%s"}\n' % (n_steps, elapsed, label))
        logger.warning('b70_step_profiler: wrote %s (%d steps, %.2f s wall)', path, n_steps, elapsed)
        state['profiler'] = None

    def execute_model(self, *args, **kwargs):
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
            rank = int(os.environ.get('RANK', os.environ.get('LOCAL_RANK', '0')))
            try:
                from vllm.distributed.parallel_state import get_tensor_model_parallel_rank
                rank = get_tensor_model_parallel_rank()
            except Exception:
                pass
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
    logger.warning('b70_step_profiler: enabled (skip %d, steps %d, dir %s)', skip, steps, directory)
