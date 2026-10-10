"""Control-plane-only replacement of two certified timeout escalation paths.

Keep waiting after recording a 300s failure. Returning with live mp children
would permit interpreter finalizers to kill them. No retries or forced exits.
"""
import os
from pathlib import Path
import signal
import time

from window_driver import write

_sent = set()


def wait_only(procs, timeout=None, *, request=False):
    root = Path(os.environ['PACKET4_WINDOW'])
    if request:
        for proc in procs:
            if proc.is_alive() and proc.pid not in _sent:
                _sent.add(proc.pid)
                os.kill(proc.pid, signal.SIGINT)
    start = time.monotonic()
    recorded = False
    while any(p.is_alive() for p in procs):
        if time.monotonic() - start >= 300 and not recorded:
            write(root / f'shutdown-wait-{os.getpid()}.json', {
                'status': 'MANUAL-RECOVERY', 'pids': [p.pid for p in procs if p.is_alive()],
                'reason': '300s elapsed; waiting without terminate/kill; no next launch'})
            write(root / 'STOP.json', {'reason': 'cooperative shutdown over budget'})
            recorded = True
        for proc in procs:
            proc.join(.25)


def request_and_wait(procs, timeout=None):
    return wait_only(procs, timeout, request=True)


def install():
    import vllm.v1.utils as utils
    # Imported before any process manager or its weakref.finalize is created.
    utils.shutdown = request_and_wait
    import vllm.v1.engine.utils as engine_utils
    engine_utils.shutdown = request_and_wait
    from vllm.v1.executor.multiproc_executor import MultiprocExecutor
    MultiprocExecutor._ensure_worker_termination = staticmethod(wait_only)
    write(Path(os.environ['PACKET4_WINDOW']) / f'shutdown-guard-{os.getpid()}.json', {
        'pid': os.getpid(), 'installed': True, 'scope': 'process cleanup only'})
