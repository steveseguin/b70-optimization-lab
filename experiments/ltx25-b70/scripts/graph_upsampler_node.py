"""Bounded XPU graph-capture gate for the LTX latent spatial upsampler.

`original` leaves the model untouched; `timed` records the eager forward's
synchronised wall time per call and changes nothing numerically; `graph`
shadows `forward` with a graph-backed stand-in proven bit-identical to eager;
`restored` puts the class method back. The module, its registration and its
weights are never modified.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_graph_upsampler as adapter
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MODES = ('original', 'timed', 'graph', 'restored')
_installed = None      # (upscale_model, original, stand_in, report, mode)
_original_model = None
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


class LTXUpsamplerGraphGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'upscale_model': ('LATENT_UPSCALE_MODEL',), 'mode': (list(MODES),),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('LATENT_UPSCALE_MODEL',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, upscale_model, mode, run_name):
        global _failed
        try:
            return self._apply(upscale_model, mode, run_name)
        except BaseException:
            _failed = True
            raise

    def _apply(self, upscale_model, mode, run_name):
        global _installed, _original_model
        require(not _failed, 'Previous upsampler gate failure; halt submissions and inspect evidence')
        require(mode in MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(adapter.__file__), 'ltx_graph_upsampler.py'),
                           (Path(__file__), 'graph_upsampler_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        require(_original_model is None or upscale_model is _original_model,
                'Resident upscale model generation changed')
        _original_model = upscale_model
        model = adapter.upsampler_of(upscale_model)

        report = {'schema': 'ltx.upsampler-graph-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'extension_sha256s': hashes,
                  'model_class': type(model).__name__,
                  'capture_proof': 'the captured graph must replay bit-identically to a fresh eager call of '
                                   'LatentUpsampler.forward on the same input, be proven non-inert by '
                                   'perturbing the input, and weight addresses are checked on every replay',
                  'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                require(_installed is None, 'Upsampler forward is shadowed; run the restored mode first')
            elif mode in ('timed', 'graph'):
                if _installed is None:
                    # The stand-in binds to the weights' device, so they must be
                    # resident first. This is the same load the node itself does.
                    import comfy.model_management
                    comfy.model_management.load_models_gpu([upscale_model])
                    report['device'] = str(adapter.resident_on_xpu(model))
                    captures, original, stand_in = adapter.install(upscale_model, timed=(mode == 'timed'))
                    _installed = (upscale_model, original, stand_in, captures, mode)
                    report['installed_now'] = True
                else:
                    resident, _original, _stand_in, _captures, installed_mode = _installed
                    require(resident is upscale_model, 'A different upscale model is already shadowed')
                    require(installed_mode == mode, 'Upsampler is shadowed in mode ' + installed_mode +
                            '; run the restored mode before switching')
                    report['installed_now'] = False
            else:
                if _installed is None:
                    report['was_shadowed'] = False
                else:
                    resident, original, stand_in, captures, installed_mode = _installed
                    require(resident is upscale_model, 'Restore target is not the shadowed model')
                    adapter.restore(upscale_model, original)
                    report['was_shadowed'] = True
                    report['restored_mode'] = installed_mode
                    if installed_mode == 'timed':
                        report['eager_forward_seconds_at_restore'] = list(stand_in.seconds)
                    else:
                        report['capture_summary_at_restore'] = captures.summary()
                    _installed = None
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            if _installed is not None and mode != 'restored':
                _resident, _original, stand_in, captures, installed_mode = _installed
                if installed_mode == 'timed':
                    report['eager_forward_seconds'] = list(stand_in.seconds)
                else:
                    report['capture_summary'] = captures.summary()
                    report['calls'] = stand_in.calls
            write_json(run / ('upsampler-graph-' + run_name + '.json'), report)
        return (upscale_model,)


NODE_CLASS_MAPPINGS = {'LTXUpsamplerGraphGate': LTXUpsamplerGraphGate}
