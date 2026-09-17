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
    state = {'calls': 0, 'profiler': None, 'done': False, 'started': None}
    original = cls.execute_model

    def execute_model(self, *args, **kwargs):
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
