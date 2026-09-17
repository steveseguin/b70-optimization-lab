"""Skip ComfyUI's model-management bookkeeping for models that are already fully resident.

`comfy.model_management.load_models_gpu` is called by every sampler pass and by
the latent upsampler node. For a model that is already completely on its
device it still detaches and re-runs `model_load`, walks the module list,
queries allocator statistics and may empty the cache: measured at 0.068 s per
call for the 1 GB upsampler in packet 62, and called three times per clip.

`timed` wraps the function and records each call's wall time and whether the
fast path WOULD have applied. `fast` returns immediately when every requested
model is a live entry of `current_loaded_models`, fully loaded
(`loaded_size() == model_size()`), not dynamic, and carries no additional
patch models; otherwise it defers to the original. No tensor is touched and no
arithmetic changes; the four raw oracles gate the arm like every other.
`restored` puts the original function back.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import comfy.model_management as mm
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MODES = ('original', 'timed', 'fast', 'restored')
_original = mm.load_models_gpu
_installed_mode = None
_failed = False
_calls = []          # per call: {'seconds', 'resident', 'skipped', 'models'}
# ComfyUI's loader moves weights with module.to() and is not thread-safe. Two
# sampler workers whose first clips both fall through to it segfaulted the
# server on 2026-09-17 (packet 74b, endurance prompt 4). Every fall-through
# runs under this lock, and the residency check is re-read under it, so the
# second thread sees the first thread's completed load and skips.
_LOAD_LOCK = __import__('threading').Lock()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def _resident(models):
    """True only when every requested model is fully loaded and live in the registry."""
    if not models:
        return False
    for m in models:
        if m.is_dynamic() or m.model_patches_models():
            return False
        entry = None
        for loaded in mm.current_loaded_models:
            if loaded.model is m:
                entry = loaded
                break
        if entry is None or entry.is_dead():
            return False
        if m.loaded_size() != m.model_size() or m.model_size() <= 0:
            return False
        if m.current_loaded_device() != m.load_device:
            return False
    return True


def _describe(models):
    return [type(getattr(m, 'model', None)).__name__ for m in models]


def timed_load_models_gpu(models, *args, **kwargs):
    models = list(models)
    with _LOAD_LOCK:
        resident = _resident(models)
        started = time.perf_counter()
        try:
            return _original(models, *args, **kwargs)
        finally:
            _calls.append({'seconds': round(time.perf_counter() - started, 5), 'resident': resident,
                           'skipped': False, 'models': _describe(models)})


def fast_load_models_gpu(models, *args, **kwargs):
    models = list(models)
    if kwargs.get('force_patch_weights') or kwargs.get('force_full_load'):
        return timed_load_models_gpu(models, *args, **kwargs)
    with _LOAD_LOCK:
        resident = _resident(models)
        if resident:
            for m in models:
                for loaded in mm.current_loaded_models:
                    if loaded.model is m:
                        loaded.currently_used = True
            _calls.append({'seconds': 0.0, 'resident': True, 'skipped': True, 'models': _describe(models)})
            return None
        started = time.perf_counter()
        try:
            return _original(models, *args, **kwargs)
        finally:
            _calls.append({'seconds': round(time.perf_counter() - started, 5), 'resident': False,
                           'skipped': False, 'models': _describe(models)})


class LTXResidentFastPath:
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
        global _installed_mode
        require(not _failed, 'Previous fast-path gate failure; halt submissions and inspect evidence')
        require(mode in MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        actual = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        require(server['extension_sha256s']['resident_fastpath_node.py'] == actual,
                'Sealed extension changed: resident_fastpath_node.py')
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        report = {'schema': 'ltx.resident-fastpath-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'extension_sha256s': {'resident_fastpath_node.py': actual},
                  'claim': 'model-management bookkeeping is skipped only when every requested model is '
                           'already fully resident and live; no tensor is touched and no arithmetic '
                           'changes. timed mode changes nothing and records each call.',
                  'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                # 'original' means "ensure the original function"; an arm that
                # follows a fast/timed arm restores it here and says so.
                if _installed_mode is not None:
                    report['restored_from'] = _installed_mode
                    mm.load_models_gpu = _original
                    _installed_mode = None
            elif mode in ('timed', 'fast'):
                if _installed_mode != mode:
                    report['switched_from'] = _installed_mode
                    mm.load_models_gpu = timed_load_models_gpu if mode == 'timed' else fast_load_models_gpu
                    _installed_mode = mode
                    report['installed_now'] = True
                else:
                    report['installed_now'] = False
            else:
                report['was_installed'] = _installed_mode is not None
                mm.load_models_gpu = _original
                _installed_mode = None
            require(mm.load_models_gpu is (_original if _installed_mode is None else
                    (timed_load_models_gpu if _installed_mode == 'timed' else fast_load_models_gpu)),
                    'load_models_gpu is not the expected function')
            # Calls accumulate across a prompt; this receipt carries the previous prompt's rows.
            report['calls_before_this_prompt'] = list(_calls)
            report['calls_summary'] = {'count': len(_calls),
                                       'seconds_total': round(sum(c['seconds'] for c in _calls), 5),
                                       'resident': sum(1 for c in _calls if c['resident']),
                                       'skipped': sum(1 for c in _calls if c['skipped'])}
            del _calls[:]
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('resident-fastpath-' + run_name + '.json'), report)
        return (model,)


NODE_CLASS_MAPPINGS = {'LTXResidentFastPath': LTXResidentFastPath}
