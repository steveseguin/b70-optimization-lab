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
MODES = ('original', 'concurrent', 'timed', 'batchproof', 'restored')
KEY = 'ltx_concurrent_cfg'
TIMER_KEY = 'ltx_forward_timer'
_installed = None
_installed_mode = None
_failed = False
_stats = {'splits': 0, 'passthrough': 0, 'errors': 0}
_forward_seconds = []      # diagnostic: synchronised wall time of each diffusion forward
_batch_proofs = []         # diagnostic: batch-2 vs batch-1 row equality per forward
PROOF_KEY = 'ltx_batch_proof'


def _bits_equal(a, b):
    if a.dtype in (torch.bfloat16, torch.float16):
        return bool(torch.equal(a.view(torch.int16), b.view(torch.int16)))
    if a.dtype == torch.float32:
        return bool(torch.equal(a.view(torch.int32), b.view(torch.int32)))
    return bool(torch.equal(a, b))


def _perturb(t, generator):
    """A second clip's worth of values: same dtype/shape, different content."""
    if not t.is_floating_point():
        return t
    noise = torch.randn(t.shape, generator=generator, device='cpu').to(dtype=t.dtype, device=t.device)
    return t + noise * 0.05


def _compressed_timestep_class():
    try:
        from comfy.ldm.lightricks.av_model import CompressedTimestep
        return CompressedTimestep
    except Exception:  # noqa: BLE001
        return None


def _stack_rows(value, second):
    """Batch-2 argument from two batch-1 arguments, recursively.

    Dicts (transformer_options and its caches) are shared, not walked. LTX's
    CompressedTimestep carries its batch in `.data` and is rebuilt.
    """
    CT = _compressed_timestep_class()
    if isinstance(value, torch.Tensor):
        if value.dim() >= 1 and value.shape[0] == 1:
            return torch.cat([value, second], dim=0)
        return value
    if CT is not None and isinstance(value, CT):
        return CT(_stack_rows(value.data, second.data), value.patches_per_frame, per_frame=True)
    if isinstance(value, (list, tuple)):
        out = [_stack_rows(v, s) for v, s in zip(value, second)]
        return type(value)(out) if isinstance(value, tuple) else out
    return value


def _map_rows(value, fn):
    CT = _compressed_timestep_class()
    if isinstance(value, torch.Tensor):
        return fn(value) if value.dim() >= 1 and value.shape[0] == 1 else value
    if CT is not None and isinstance(value, CT):
        return CT(_map_rows(value.data, fn), value.patches_per_frame, per_frame=True)
    if isinstance(value, (list, tuple)):
        out = [_map_rows(v, fn) for v in value]
        return type(value)(out) if isinstance(value, tuple) else out
    return value


def _census(value, path='arg'):
    """Shapes of every tensor in an argument tree, for the receipt."""
    out = {}
    if isinstance(value, torch.Tensor):
        out[path] = list(value.shape) + [str(value.dtype)]
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            out.update(_census(v, f'{path}[{i}]'))
    elif isinstance(value, dict):
        for k, v in value.items():
            if k == 'patches_replace' or k == '_ltx_layer_shard_forward_transfers':
                continue
            out.update(_census(v, f'{path}.{k}'))
    else:
        CT = _compressed_timestep_class()
        if CT is not None and isinstance(value, CT):
            out[path + '<CT>'] = list(value.data.shape)
    return out


def _double_batch_lists(options, second_options=None):
    """ComfyUI keys the batch in transformer_options too: cond_or_uncond, uuids, sigmas."""
    out = dict(options)
    for key in ('cond_or_uncond', 'uuids'):
        if isinstance(out.get(key), list) and len(out[key]) == 1:
            out[key] = out[key] * 2
    sig = out.get('sigmas')
    if isinstance(sig, torch.Tensor) and sig.dim() >= 1 and sig.shape[0] == 1:
        other = (second_options or {}).get('sigmas', sig)
        out['sigmas'] = torch.cat([sig, other], dim=0)
    return out


def _perturb_options(options, generator):
    out = dict(options)
    sig = out.get('sigmas')
    if isinstance(sig, torch.Tensor) and sig.dim() >= 1 and sig.shape[0] == 1:
        out['sigmas'] = _perturb(sig, generator)
    return out


def _rows(value, index):
    if isinstance(value, torch.Tensor):
        return value[index:index + 1] if value.dim() >= 1 and value.shape[0] == 2 else value
    if isinstance(value, (list, tuple)):
        out = [_rows(v, index) for v in value]
        return type(value)(out) if isinstance(value, tuple) else out
    return value


def batch_proof_diffusion_model(executor, *args, **kwargs):
    """Diagnostic: is a batch-2 forward bitwise equal, row by row, to two batch-1 forwards?

    Returns the ORIGINAL batch-1 result for the clip, so the clip stays exact.
    The second row is a perturbed copy of every batch-1 tensor argument (x,
    context, timesteps alike), so the two rows differ everywhere a real second
    clip would. Only tensors with a leading batch dimension of 1 are stacked;
    scalars, ints and unbatched tensors pass through unchanged.
    """
    original_out = executor(*args, **kwargs)
    generator = torch.Generator(device='cpu')
    generator.manual_seed(20260917)
    # LOCKSTEP variant (packet 72): a second clip differs in its latent
    # (args[0]) and its conditioning (args[2]) but samples at the same sigma,
    # so only those two are perturbed. Timesteps, option sigmas and every
    # other input stay identical (still stacked to batch 2 with equal rows).
    # Packet 71 perturbed the timesteps too and found rows differing by up to
    # 2.2, which a cross-row timestep interaction would explain.
    second_args = list(args)
    for i in (0, 2):
        if len(second_args) > i:
            second_args[i] = _map_rows(second_args[i], lambda t: _perturb(t, generator))
    second_kwargs = dict(kwargs)
    stage = 'second'
    try:
        second_out = executor(*second_args, **second_kwargs)
        stage = 'stacked'
        stacked_args = _stack_rows(list(args), second_args)
        stacked_kwargs = {k: _stack_rows(v, second_kwargs[k]) for k, v in kwargs.items()}
        if len(stacked_args) > 5 and isinstance(stacked_args[5], dict):
            stacked_args[5] = _double_batch_lists(args[5], second_args[5])
        if isinstance(stacked_kwargs.get('transformer_options'), dict):
            stacked_kwargs['transformer_options'] = _double_batch_lists(
                kwargs['transformer_options'], second_kwargs['transformer_options'])
        stacked_out = executor(*stacked_args, **stacked_kwargs)
        # Identical-rows control: cat(x, x) must reproduce the original in both rows.
        stage = 'identical-rows control'
        same_args = _stack_rows(list(args), list(args))
        same_kwargs = {k: _stack_rows(v, kwargs[k]) for k, v in kwargs.items()}
        if len(same_args) > 5 and isinstance(same_args[5], dict):
            same_args[5] = _double_batch_lists(args[5], args[5])
        if isinstance(same_kwargs.get('transformer_options'), dict):
            same_kwargs['transformer_options'] = _double_batch_lists(
                kwargs['transformer_options'], kwargs['transformer_options'])
        same_out = executor(*same_args, **same_kwargs)
        outsI = list(same_out) if isinstance(same_out, (list, tuple)) else [same_out]
        # The LTXAV model returns [video_out, audio_out]; compare every component.
        outs1 = list(original_out) if isinstance(original_out, (list, tuple)) else [original_out]
        outs2 = list(second_out) if isinstance(second_out, (list, tuple)) else [second_out]
        outsS = list(stacked_out) if isinstance(stacked_out, (list, tuple)) else [stacked_out]
        rec = {'output_shape_batch1': [list(t.shape) for t in outs1],
               'output_shape_batch2': [list(t.shape) for t in outsS], 'components': len(outsS)}
        if len(outsS) == len(outs1) and all(s.shape[0] == 2 and s.shape[1:] == o.shape[1:] for s, o in zip(outsS, outs1)):
            rec['row0_equals_batch1'] = all(_bits_equal(s[0:1], o) for s, o in zip(outsS, outs1))
            rec['row1_equals_batch1'] = all(_bits_equal(s[1:2], o) for s, o in zip(outsS, outs2))
            rec['row0_max_abs_diff'] = max(float((s[0:1].float() - o.float()).abs().max()) for s, o in zip(outsS, outs1))
            rec['row1_max_abs_diff'] = max(float((s[1:2].float() - o.float()).abs().max()) for s, o in zip(outsS, outs2))
            rec['per_component'] = [{'row0': _bits_equal(s[0:1], o), 'row1': _bits_equal(s[1:2], p)}
                                    for s, o, p in zip(outsS, outs1, outs2)]
            rec['identical_rows_control'] = {
                'row0_equals_batch1': all(_bits_equal(s[0:1], o) for s, o in zip(outsI, outs1)),
                'row1_equals_batch1': all(_bits_equal(s[1:2], o) for s, o in zip(outsI, outs1)),
                'max_abs_diff': max(float((s.float() - torch.cat([o, o]).float()).abs().max()) for s, o in zip(outsI, outs1))}
        else:
            rec['row0_equals_batch1'] = rec['row1_equals_batch1'] = None
            rec['note'] = 'batch-2 output shape does not split into two batch-1 rows'
    except BaseException as error:  # noqa: BLE001
        import traceback
        rec = {'error': repr(error)[:400], 'stage': stage,
               'traceback_tail': traceback.format_exc()[-2500:]}
    if len(_batch_proofs) == 0:
        rec['census_batch1'] = {**_census(list(args), 'args'), **_census(dict(kwargs), 'kwargs')}
        try:
            rec['census_stacked'] = {**_census(_stack_rows(list(args), second_args), 'args'),
                                     **_census({k: _stack_rows(v, second_kwargs[k]) for k, v in kwargs.items()}, 'kwargs')}
        except BaseException as error:  # noqa: BLE001
            rec['census_stacked_error'] = repr(error)[:200]
    _batch_proofs.append(rec)
    return original_out


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
    elif _installed_mode == 'timed':
        model.remove_wrappers_with_key(WrappersMP.DIFFUSION_MODEL, TIMER_KEY)
    else:
        model.remove_wrappers_with_key(WrappersMP.DIFFUSION_MODEL, PROOF_KEY)
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
            elif mode in ('concurrent', 'timed', 'batchproof'):
                if _installed is not None and _installed_mode != mode:
                    require(_installed is model, 'A different model already has the wrapper')
                    _uninstall(model)
                    report['switched_from'] = _installed_mode
                if _installed is None:
                    if mode == 'concurrent':
                        model.add_wrapper_with_key(
                            WrappersMP.CALC_COND_BATCH, KEY, concurrent_calc_cond_batch)
                    elif mode == 'timed':
                        model.add_wrapper_with_key(
                            WrappersMP.DIFFUSION_MODEL, TIMER_KEY, timed_diffusion_model)
                    else:
                        model.add_wrapper_with_key(
                            WrappersMP.DIFFUSION_MODEL, PROOF_KEY, batch_proof_diffusion_model)
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
            report['batch_proofs_before_this_prompt'] = list(_batch_proofs)
            if _batch_proofs:
                rows = [r for r in _batch_proofs if 'row0_equals_batch1' in r]
                report['batch_proof_summary'] = {
                    'forwards': len(_batch_proofs), 'errors': sum(1 for r in _batch_proofs if 'error' in r),
                    'row0_all_equal': all(r['row0_equals_batch1'] for r in rows) if rows else None,
                    'row1_all_equal': all(r['row1_equals_batch1'] for r in rows) if rows else None}
            del _batch_proofs[:]
            report['stats'] = dict(_stats)
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            report['stats_at_exit'] = dict(_stats)
            write_json(run / ('concurrent-cfg-' + run_name + '.json'), report)
        return (model,)


NODE_CLASS_MAPPINGS = {'LTXConcurrentCFG': LTXConcurrentCFG}
