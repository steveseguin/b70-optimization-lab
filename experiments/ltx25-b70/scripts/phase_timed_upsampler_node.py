"""Drop-in for LTXVLatentUpsampler that times each phase of the node.

Same calls in the same order as `comfy_extras/nodes_lt_upsampler.py`
(model-management load, copy to the model device, un_normalize, forward,
normalize, copy to the intermediate device), with a device sync and a
wall-clock read between phases. Numerically it is the sealed node; the four
raw oracles gate it like everything else. `original` calls the sealed node
itself; `timed` runs the phased copy and writes the per-phase seconds.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

import torch

from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MODES = ('original', 'timed')
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def _sync_all():
    for i in range(torch.xpu.device_count()):
        torch.xpu.synchronize(i)


def phased_upsample(samples, upscale_model, vae):
    """nodes_lt_upsampler.LTXVLatentUpsampler.execute, phase by phase."""
    import comfy.model_management as mm
    phases = []

    def mark(name, started):
        _sync_all()
        phases.append({'phase': name, 'seconds': round(time.perf_counter() - started, 5)})

    device = upscale_model.load_device
    model = upscale_model.model
    model_dtype = upscale_model.model_dtype()
    latents = samples['samples']
    input_dtype = latents.dtype
    _sync_all()
    t = time.perf_counter()
    memory_required = math.prod(latents.shape) * 3000.0
    mm.load_models_gpu([upscale_model], memory_required=memory_required)
    mark('load_models_gpu', t)
    t = time.perf_counter()
    latents = latents.to(dtype=model_dtype, device=device)
    mark('latent_to_model_device', t)
    t = time.perf_counter()
    latents = vae.first_stage_model.per_channel_statistics.un_normalize(latents)
    mark('un_normalize', t)
    t = time.perf_counter()
    upsampled = model(latents)
    mark('forward', t)
    t = time.perf_counter()
    upsampled = vae.first_stage_model.per_channel_statistics.normalize(upsampled)
    mark('normalize', t)
    t = time.perf_counter()
    upsampled = upsampled.to(dtype=input_dtype, device=mm.intermediate_device())
    mark('to_intermediate_device', t)
    out = samples.copy()
    out['samples'] = upsampled
    out.pop('noise_mask', None)
    return out, {'phases': phases, 'total_seconds': round(sum(p['seconds'] for p in phases), 5),
                 'latent_source_device': str(samples['samples'].device),
                 'model_device': str(device), 'model_dtype': str(model_dtype),
                 'vae_stats_device': str(vae.first_stage_model.per_channel_statistics.get_buffer('std-of-means').device),
                 'intermediate_device': str(mm.intermediate_device())}


class LTXPhaseTimedUpsampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'samples': ('LATENT',), 'upscale_model': ('LATENT_UPSCALE_MODEL',),
                             'vae': ('VAE',), 'mode': (list(MODES),),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('LATENT',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, samples, upscale_model, vae, mode, run_name):
        global _failed
        try:
            return self._apply(samples, upscale_model, vae, mode, run_name)
        except BaseException:
            _failed = True
            raise

    def _apply(self, samples, upscale_model, vae, mode, run_name):
        require(not _failed, 'Previous phase-timed upsampler failure; halt submissions and inspect evidence')
        require(mode in MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        actual = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        require(server['extension_sha256s']['phase_timed_upsampler_node.py'] == actual,
                'Sealed extension changed: phase_timed_upsampler_node.py')
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        report = {'schema': 'ltx.phase-timed-upsampler-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'extension_sha256s': {'phase_timed_upsampler_node.py': actual},
                  'claim': 'same calls as the sealed LTXVLatentUpsampler node in the same order; only '
                           'synchronised timers were added between phases', 'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                import nodes
                out = nodes.NODE_CLASS_MAPPINGS['LTXVLatentUpsampler'].execute(
                    samples=samples, upscale_model=upscale_model, vae=vae).result[0]
                report['detail'] = {'sealed_node': True}
            else:
                out, detail = phased_upsample(samples, upscale_model, vae)
                report['detail'] = detail
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('upsampler-phases-' + run_name + '.json'), report)
        return (out,)


NODE_CLASS_MAPPINGS = {'LTXPhaseTimedUpsampler': LTXPhaseTimedUpsampler}
