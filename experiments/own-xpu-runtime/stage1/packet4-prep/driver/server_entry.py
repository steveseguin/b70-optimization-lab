"""Spawn-safe A367 CLI entry; no model computation implemented here.

multiprocessing spawn imports this as __mp_main__ BEFORE executing EngineCore
or WorkerProc. Thus each process installs cleanup guards before finalizers.
This file is never imported in the CPU preparation except with mocked vLLM.
"""
import os
from pathlib import Path

from window_driver import PREREG, read, require, sha


def bootstrap():
    root = Path(os.environ['PACKET4_SOURCE'])
    import vllm
    require(Path(vllm.__file__).resolve() == (root / 'vllm/__init__.py').resolve(),
            'venv editable mapping shadowed certified source')
    # Parent checked all files. Each spawned process also checks its injection,
    # scheduler and shutdown dependencies before constructing a worker/engine.
    for relative in (
        'vllm/v1/worker/worker_base.py', 'vllm/v1/worker/xpu_worker.py',
        'vllm/v1/worker/gpu_worker.py', 'vllm/v1/worker/gpu_model_runner.py',
        'vllm/v1/executor/multiproc_executor.py', 'vllm/v1/utils.py',
        'vllm/v1/engine/utils.py', 'vllm/platforms/xpu.py'):
        require(sha(root / relative) == read(PREREG)['source_pins'][relative], 'spawn source drift')
    from shutdown_guard import install
    install()


bootstrap()
if __name__ == '__main__':
    from vllm.entrypoints.cli.main import main
    main()
