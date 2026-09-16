"""Sample clip N while clips N-1 and N-2 are still moving through the pipeline.

The transformer's 48 blocks are split 21/27 across xpu:0 and xpu:1, so a single
clip's forward uses one card at a time and leaves the other idle. Diffusion is
sequential *within* a clip but not *between* clips, so two clips sampling at
once let one occupy xpu:1's blocks while the other occupies xpu:0's. The GPU
serialises each card by itself, so two workers settle into a two-stage pipeline.

This is run-behind, not run-ahead: the sampler needs THIS clip's conditioning,
which only exists once this prompt has it. So the prompt submits its own clip's
sampling and emits the clip sampled `depth` prompts earlier. Every clip is
sampled exactly once, by its own sampler, from its own conditioning and its own
noise; nothing is cached or shared between clips. Only the overlap changes.

Each worker thread gets its own static buffers and captured graphs
(`ltx_graph_capture.GroupRegistry` keys them by (device, thread)), which is what
makes two concurrent forwards safe.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_pipeline as pipeline
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def _node(name):
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get(name)
    require(cls is not None, 'Missing node class: ' + name)
    return cls


def sample_clip(noise_a, guider_a, sampler_a, sigmas_a,
                noise_b, guider_b, sampler_b, sigmas_b,
                video_latent, audio_latent, upscale_model, vae):
    """Exactly the sealed chain 377 -> 344 -> 367 -> 348 -> 340 -> 368 -> 369."""
    concat = _node('LTXVConcatAVLatent')
    separate = _node('LTXVSeparateAVLatent')
    upsampler = _node('LTXVLatentUpsampler')
    sampler_node = _node('SamplerCustomAdvanced')

    av = concat.execute(video_latent=video_latent, audio_latent=audio_latent).result[0]
    stage_a = sampler_node.execute(noise=noise_a, guider=guider_a, sampler=sampler_a,
                                   sigmas=sigmas_a, latent_image=av).result[0]
    video_a, audio_a = separate.execute(av_latent=stage_a).result[:2]
    upscaled = upsampler.execute(samples=video_a, upscale_model=upscale_model, vae=vae).result[0]
    av2 = concat.execute(video_latent=upscaled, audio_latent=audio_a).result[0]
    stage_b = sampler_node.execute(noise=noise_b, guider=guider_b, sampler=sampler_b,
                                   sigmas=sigmas_b, latent_image=av2).result[0]
    video_b, audio_b = separate.execute(av_latent=stage_b).result[:2]
    return video_b, audio_b


class LTXPipelineSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'noise_a': ('NOISE',), 'guider_a': ('GUIDER',), 'sampler_a': ('SAMPLER',),
            'sigmas_a': ('SIGMAS',),
            'noise_b': ('NOISE',), 'guider_b': ('GUIDER',), 'sampler_b': ('SAMPLER',),
            'sigmas_b': ('SIGMAS',),
            'video_latent': ('LATENT',), 'audio_latent': ('LATENT',),
            'upscale_model': ('UPSCALE_MODEL',), 'vae': ('VAE',),
            'mode': (list(pipeline.MODES),),
            'clip_index': ('INT', {'default': 0, 'min': 0, 'max': 1000000}),
            'depth': ('INT', {'default': 2, 'min': 1, 'max': pipeline.MAX_PENDING}),
            'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('LATENT', 'LATENT')
    RETURN_NAMES = ('video_latent', 'audio_latent')
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, **kwargs):
        global _failed
        try:
            return self._apply(**kwargs)
        except BaseException:
            _failed = True
            pipeline.clear()
            raise

    def _apply(self, mode, clip_index, depth, run_name, **chain):
        require(not _failed, 'Previous pipeline failure; halt submissions and inspect evidence')
        require(mode in pipeline.MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        actual = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        require(server['extension_sha256s']['pipeline_sampler_node.py'] == actual,
                'Sealed extension changed: pipeline_sampler_node.py')
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(),
                'Strict determinism required')

        report = {'schema': 'ltx.pipeline-sampler-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'clip_index': clip_index, 'depth': depth,
                  'extension_sha256s': {'pipeline_sampler_node.py': actual},
                  'claim': 'every clip is sampled exactly once by its own sampler, from its own '
                           'conditioning and its own noise; nothing is cached or shared between '
                           'clips. Two clips sample at once so one occupies xpu:1 while the other '
                           'occupies xpu:0. Each worker has its own static buffers and graphs.',
                  'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                with torch.inference_mode():
                    out = sample_clip(**chain)
                report['detail'] = {'emitted_index': clip_index, 'primed': True}
            else:
                out, detail = pipeline.run_behind(
                    'sample', clip_index, depth, lambda: sample_clip(**chain))
                report['detail'] = detail
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('pipeline-sampler-' + run_name + '.json'), report)
        return out


NODE_CLASS_MAPPINGS = {'LTXPipelineSampler': LTXPipelineSampler}
