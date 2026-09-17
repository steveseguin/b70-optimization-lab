"""Run the dual-CFG guider's two model forwards concurrently.

`Guider_LTXAVDualCFG` sets `disable_cfg1_optimization`, so every sampler step
evaluates the model twice -- once conditional, once unconditional -- and the two
are independent: `dual_cfg` only combines their results arithmetically. The
captured block shapes are batch 1, so ComfyUI already runs them as two separate
forwards, one after the other.

The transformer's blocks are split 21/27 across xpu:0 and xpu:1, so a single
forward uses one card at a time and leaves the other idle. Running the two
forwards on two threads lets one occupy xpu:1's blocks while the other occupies
xpu:0's. The GPU serialises each card's work by itself, so the two threads
naturally settle into a two-stage pipeline.

Nothing is cached and no arithmetic changes: each forward computes exactly what
it computed before, on its own static buffers and its own captured graphs
(`GroupRegistry` keys them per thread). Only the two forwards' *overlap*
changes. If they raced, the sampler's input would change and the four raw
oracles would catch it.

This uses ComfyUI's own CALC_COND_BATCH wrapper point rather than patching.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

import torch

import comfy.patcher_extension
from comfy.patcher_extension import WrappersMP
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MODES = ('original', 'concurrent', 'timed', 'restored')
KEY = 'ltx_concurrent_cfg'
TIMER_KEY = 'ltx_forward_timer'
_installed = None
_installed_mode = None
_failed = False
_stats = {'splits': 0, 'passthrough': 0, 'errors': 0}
_forward_seconds = []      # diagnostic: synchronised wall time of each diffusion forward


def timed_diffusion_model(executor, *args, **kwargs):
    """Diagnostic only: sync every card, run the forward, sync again, record the wall.

    Numerically the original call. The syncs add a little latency per step, so
    this arm's interval is not a speed result; its receipt separates the model
    forward (blocks plus glue) from the sampler loop around it.
    """
    for i in range(torch.xpu.device_count()):
        torch.xpu.synchronize(i)
    started = time.perf_counter()
    try:
        return executor(*args, **kwargs)
    finally:
        for i in range(torch.xpu.device_count()):
            torch.xpu.synchronize(i)
        _forward_seconds.append(round(time.perf_counter() - started, 5))


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def concurrent_calc_cond_batch(executor, model, conds, x_in, timestep, model_options):
    """Compute each cond on its own thread, then return them in order.

    Falls back to the native path for anything that is not exactly two present
    conds, so an unexpected shape is never silently reinterpreted.
    """
    present = [i for i, c in enumerate(conds) if c is not None]
    if len(conds) != 2 or len(present) != 2:
        _stats['passthrough'] += 1
        return executor(model, conds, x_in, timestep, model_options)

    results = [None, None]
    errors = [None, None]

    def run(index):
        try:
            isolated = [None, None]
            isolated[index] = conds[index]
            with torch.inference_mode():
                out = executor(model, isolated, x_in, timestep, model_options)
            results[index] = out[index]
        except BaseException as exc:                     # noqa: BLE001
            import traceback
            errors[index] = ''.join(
                traceback.format_exception(type(exc), exc, exc.__traceback__))

    threads = [threading.Thread(target=run, args=(i,), name=f'ltx-cfg-{i}')
               for i in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if any(errors):
        _stats['errors'] += 1
        raise RuntimeError('Concurrent CFG forward failed:\n' + '\n'.join(e for e in errors if e))
    require(all(r is not None for r in results), 'Concurrent CFG produced no result')
    _stats['splits'] += 1
    return results


def _uninstall(model):
    global _installed, _installed_mode
    if _installed_mode == 'concurrent':
        model.remove_wrappers_with_key(WrappersMP.CALC_COND_BATCH, KEY)
    else:
        model.remove_wrappers_with_key(WrappersMP.DIFFUSION_MODEL, TIMER_KEY)
    _installed = None
    _installed_mode = None


class LTXConcurrentCFG:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'mode': (list(MODES),),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('MODEL',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, model, mode, run_name):
        global _failed
        try:
            return self._apply(model, mode, run_name)
        except BaseException:
            _failed = True
            raise

    def _apply(self, model, mode, run_name):
        global _installed, _installed_mode
        require(not _failed, 'Previous concurrent-CFG failure; halt and inspect evidence')
        require(mode in MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        actual = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        require(server['extension_sha256s']['concurrent_cfg_node.py'] == actual,
                'Sealed extension changed: concurrent_cfg_node.py')
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(),
                'Strict determinism required')

        report = {'schema': 'ltx.concurrent-cfg-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'extension_sha256s': {'concurrent_cfg_node.py': actual},
                  'claim': 'the dual-CFG guider already runs two independent batch-1 forwards per '
                           'step; this runs them on two threads so one occupies xpu:1 while the '
                           'other occupies xpu:0. Same arithmetic, same per-forward inputs, '
                           'separate static buffers per thread. Nothing is cached.',
                  'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                if _installed is not None:
                    require(_installed is model, 'A different model has the wrapper')
                    report['restored_from'] = _installed_mode
                    _uninstall(model)
            elif mode in ('concurrent', 'timed'):
                if _installed is not None and _installed_mode != mode:
                    require(_installed is model, 'A different model already has the wrapper')
                    _uninstall(model)
                    report['switched_from'] = _installed_mode
                if _installed is None:
                    if mode == 'concurrent':
                        model.add_wrapper_with_key(
                            WrappersMP.CALC_COND_BATCH, KEY, concurrent_calc_cond_batch)
                    else:
                        model.add_wrapper_with_key(
                            WrappersMP.DIFFUSION_MODEL, TIMER_KEY, timed_diffusion_model)
                    _installed = model
                    _installed_mode = mode
                    report['installed_now'] = True
                else:
                    require(_installed is model, 'A different model already has the wrapper')
                    report['installed_now'] = False
            else:
                if _installed is None:
                    report['was_installed'] = False
                else:
                    require(_installed is model, 'Restore target is not the wrapped model')
                    report['restored_mode'] = _installed_mode
                    _uninstall(model)
                    report['was_installed'] = True
            # The forward timer accumulates across a prompt; the receipt of the
            # NEXT gate call (or the restore) carries the previous prompt's rows.
            report['forward_seconds_before_this_prompt'] = list(_forward_seconds)
            del _forward_seconds[:]
            report['stats'] = dict(_stats)
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            report['stats_at_exit'] = dict(_stats)
            write_json(run / ('concurrent-cfg-' + run_name + '.json'), report)
        return (model,)


NODE_CLASS_MAPPINGS = {'LTXConcurrentCFG': LTXConcurrentCFG}
