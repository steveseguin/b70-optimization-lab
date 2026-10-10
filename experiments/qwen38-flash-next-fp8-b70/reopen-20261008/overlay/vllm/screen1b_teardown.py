"""Cooperative Screen 1b teardown. Stdlib import; runtime is injected by caller.

Receipts attest completed Python release calls, NOT a zero-USM/queue census.
No signal callback enters this module. Failed drains preserve the live process.
"""
import datetime
import gc
import json
import os
import threading
import time

_timestamps = {}
_complete = False
_releasing = False


def mark(phase):
    _timestamps[phase] = dict(
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        unix_ns=time.time_ns(), monotonic_ns=time.monotonic_ns())


def _parameters(guard, runner):
    roots = list(guard._models) + list(guard._tables.values()) + list(guard._owned_modules)
    if getattr(runner, 'model', None) is not None:
        roots.append(runner.model)
    speculator = getattr(runner, 'speculator', None)
    if getattr(speculator, 'model', None) is not None:
        roots.append(speculator.model)
    modules, params = {}, {}
    for root in roots:
        for module in root.modules():
            modules[id(module)] = module
            for param in module.parameters(recurse=False):
                params[id(param)] = param
            # Postprocessing retains the old Parameter outside _parameters.
            for key, param in vars(module).items():
                if key.startswith('_q38_placed_'):
                    params[id(param)] = param
    return list(modules.values()), list(params.values())


def release_runner(runner, guard, torch, release_runtime=lambda: None):
    """Services have stopped; current RPC has returned; synchronous scheduler only."""
    if getattr(runner, '_screen1b_released', False):
        return
    # Drain ALL streams on this rank before changing graph/pointer ownership.
    torch.xpu.synchronize()
    mark('drained')
    runner.cudagraph_manager = None
    runner.fast_prefill = None
    gc.collect()
    mark('graphs_released')
    modules, params = _parameters(guard, runner)
    release_runtime()  # workspace, rotary/global forward-context owners
    # Hold every CPU owner explicitly through pointer-table/UVA destruction.
    owners = []
    for param in params:
        for key in ('_q38_host_cpu', '_screen1b_host_storage'):
            owner = getattr(param, key, None)
            if owner is not None:
                owners.append(owner)
    owner = None
    for param in params:
        if hasattr(param, '_q38_base_table'):
            del param._q38_base_table
    gc.collect()
    mark('expert_tables_released')
    for param in params:
        if hasattr(param, '_q38_host_storage'):
            del param._q38_host_storage
        if hasattr(param, '_screen1b_host_storage'):
            # Generic UVA is p.data, not merely a Python metadata attribute.
            param.data = torch.empty(0, dtype=param.dtype, device='cpu')
    gc.collect()
    torch.xpu.synchronize()
    mark('uva_released')
    for module in modules:
        cache = getattr(module, '_screen1b_cache', None)
        if cache is not None:
            cache.close()  # memoryview -> mmap -> metadata, before pinned slab
            del module._screen1b_cache
        if hasattr(module, '_screen1b_step_device'):
            del module._screen1b_step_device
    cache = None
    mark('ple_closed')
    for param in params:
        for key in ('_q38_host_cpu', '_screen1b_host_storage'):
            if hasattr(param, key):
                delattr(param, key)
    for module in modules:
        for key in ('_screen1b_cache_slab', '_screen1b_step_host'):
            if hasattr(module, key):
                delattr(module, key)
        for key in tuple(vars(module)):
            if key.startswith('_q38_placed_'):
                delattr(module, key)
    owners.clear()
    gc.collect()
    mark('pinned_released')
    guard._tables.clear()
    guard._models.clear()
    guard._owned_modules.clear()
    # Drop every runner field, including request buffers, graph input/output
    # aliases and speculator. Services have already stopped in GPUWorker.
    # Keep only the idempotence marker; no runtime code may use this runner again.
    vars(runner).clear()
    runner._screen1b_released = True
    modules.clear()
    params.clear()
    module = param = None
    gc.collect()
    torch.xpu.synchronize()
    mark('registries_cleared')


def preserve_failure(guard, rank, error):
    """Do not exit a GPU-owning process when release failed; no automatic retry."""
    try:
        guard.request_stop('rank teardown failed; owner intervention required')
        guard.receipt('rank_teardown_failed', schema='screen1b.teardown.v1',
                      rank=rank, status='failed', timestamps=dict(_timestamps),
                      error_type=type(error).__name__, error=str(error))
    finally:
        # Even failed logging/STOP persistence must never bypass preservation.
        # No automatic retry, exit, or escalation; handlers remain intent-only.
        threading.Event().wait()



def shutdown_rank(proc, guard, torch, destroy_model_parallel,
                  destroy_distributed_environment, *, on_failure=preserve_failure):
    global _complete, _releasing
    if _complete or _releasing:
        return
    _releasing = True
    rank = proc.rank  # retained before worker/communicators disappear
    try:
        if not torch.xpu.is_initialized():
            # No device-side state was ever created. This is not a successful
            # native release and cannot qualify calibrate-load.
            guard.receipt('rank_teardown_uninitialized', rank=rank, status='uninitialized')
            _complete = True
            return
        guard.request_stop('ordered rank release')
        mark('submissions_stopped')
        if getattr(proc, 'use_async_scheduling', False):
            raise RuntimeError('unqualified async output worker; preserve process')
        mark('async_output_drained')  # disabled by mandatory launch/init guard
        for key in ('rpc_broadcast_mq', 'worker_response_mq'):
            queue = getattr(proc, key, None)
            if queue is not None:
                queue.shutdown()
                setattr(proc, key, None)
        queue = None
        mark('queues_closed')
        if proc.worker is not None:
            proc.worker.shutdown()  # services -> runner -> XPU pools
            # Wrapper may otherwise retain worker/runner buffers until exit.
            proc.worker.worker = None
            proc.worker = None
        # If init failed before a runner existed, release registered partial
        # modules using the identical ownership path.
        if 'registries_cleared' not in _timestamps:
            class PartialRunner:
                pass
            release_runner(PartialRunner(), guard, torch)
        gc.collect()
        mark('worker_released')
        destroy_model_parallel()
        destroy_distributed_environment()
        gc.collect()
        mark('distributed_released')
        # Do not initialize a device just to clean up failed CPU-side init.
        if not torch.xpu.is_initialized():
            raise RuntimeError('rank never initialized XPU; no native teardown receipt')
        torch.xpu.synchronize()
        mark('final_sync')
        torch.xpu.empty_cache()
        mark('device_cache_empty')
        # Required public API in this pinned Torch 2.13 image. No fallback to
        # undocumented native calls, no success receipt if unavailable/failing.
        torch.accelerator.empty_host_cache()
        mark('host_cache_empty')
        torch.xpu.synchronize()
        mark('post_cache_sync')
        mark('complete')
        row = dict(schema='screen1b.teardown.v1', rank=rank, pid=os.getpid(),
                   status='complete', timestamps=dict(_timestamps),
                   native_queue_destruction_verified=False)
        guard.receipt('rank_teardown_complete', **row)
        print('SCREEN1B_TEARDOWN ' + json.dumps(
            dict(event='rank_teardown_complete', **row), sort_keys=True), flush=True)
        _complete = True
    except BaseException as error:
        on_failure(guard, rank, error)


def shutdown_executor(executor, guard, *, on_failure=preserve_failure):
    """Concurrent main/monitor callers both wait for all children to exit."""
    with executor._screen1b_shutdown_lock:
        if executor._screen1b_shutdown_complete:
            return
        try:
            executor.shutting_down = True
            guard.request_stop('executor shutdown')
            workers = getattr(executor, 'workers', None) or []
            for worker in workers:
                pipe = worker.death_writer
                if pipe is not None:
                    try:
                        pipe.close()
                    except Exception:
                        # STOP also wakes the child's monitor, even on bad pipe.
                        pass
                    worker.death_writer = None
            guard.wait_processes([worker.proc for worker in workers])
            for worker in workers:
                queue = worker.worker_response_mq
                if queue is not None:
                    queue.shutdown()
                    worker.worker_response_mq = None
            queue = getattr(executor, 'rpc_broadcast_mq', None)
            if queue is not None:
                queue.shutdown()
                executor.rpc_broadcast_mq = None
            for queue in getattr(executor, 'response_mqs', None) or []:
                queue.shutdown()
            executor.response_mqs = []
            executor._screen1b_shutdown_complete = True
        except BaseException as error:
            on_failure(guard, -1, error)  # a parent must not orphan its children
