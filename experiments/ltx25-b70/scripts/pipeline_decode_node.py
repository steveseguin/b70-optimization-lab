"""Decode clip N while clip N+1 samples.

The decode depends on this clip's sampler output, so it cannot run ahead. It can
run *behind*: clip N's decode is started on a worker thread bound to the VAE's
card (xpu:3) and this prompt emits the clip that was decoded `depth` prompts
ago, while the sampler moves on to clip N+1 on xpu:0/1.

Every clip is decoded exactly once, by its own decode, and emitted once in
steady state. Nothing is cached or reused; only the moment the work runs
changes. The one exception is the pipeline fill: the first prompt has nothing
decoded `depth` prompts ago, so it waits for its own clip and emits it without
consuming it, and the next prompt emits that same clip. Every receipt records
`emitted_index`, so which clip a prompt emitted is never in doubt.

Video and audio are decoded and emitted together, with their latents, so a
prompt's four oracle inputs always describe the same clip.
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


def decode_clip(vae, audio_vae, video_latent, audio_latent):
    """Exactly what VAEDecode and LTXVAudioVAEDecode do, and nothing else."""
    import nodes
    from comfy_extras.nodes_lt_audio import LTXVAudioVAEDecode
    decoded = nodes.VAEDecode().decode(vae, video_latent)
    require(isinstance(decoded, tuple) and len(decoded) == 1,
            'VAEDecode no longer returns a single image batch')
    images = decoded[0]
    audio = LTXVAudioVAEDecode.execute(samples=audio_latent, audio_vae=audio_vae).result[0]
    return images, audio, video_latent, audio_latent


class LTXPipelineDecode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'vae': ('VAE',), 'audio_vae': ('VAE',),
                             'video_latent': ('LATENT',), 'audio_latent': ('LATENT',),
                             'mode': (list(pipeline.MODES),),
                             'clip_index': ('INT', {'default': 0, 'min': 0, 'max': 1000000}),
                             'depth': ('INT', {'default': 1, 'min': 1,
                                               'max': pipeline.MAX_PENDING}),
                             # How many prompts the latents arriving here already
                             # lag by, when an upstream stage runs behind too.
                             # Keeps `emitted_index` naming the clip it really is.
                             'upstream_depth': ('INT', {'default': 0, 'min': 0,
                                                        'max': pipeline.MAX_PENDING}),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('IMAGE', 'AUDIO', 'LATENT', 'LATENT')
    RETURN_NAMES = ('images', 'audio', 'video_latent', 'audio_latent')
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, vae, audio_vae, video_latent, audio_latent, mode, clip_index, depth,
              run_name, upstream_depth=0):
        global _failed
        try:
            return self._apply(vae, audio_vae, video_latent, audio_latent,
                               mode, clip_index, depth, run_name, upstream_depth)
        except BaseException:
            _failed = True
            pipeline.clear()
            raise

    def _apply(self, vae, audio_vae, video_latent, audio_latent, mode, clip_index, depth,
               run_name, upstream_depth=0):
        require(not _failed, 'Previous pipeline failure; halt submissions and inspect evidence')
        require(mode in pipeline.MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(pipeline.__file__), 'ltx_pipeline.py'),
                           (Path(__file__), 'pipeline_decode_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(),
                'Strict determinism required')

        report = {'schema': 'ltx.pipeline-decode-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'clip_index': clip_index, 'depth': depth,
                  'upstream_depth': upstream_depth,
                  'extension_sha256s': hashes,
                  'claim': 'every clip is decoded once by its own decode and emitted once in '
                           'steady state; nothing is cached or reused. Only the moment the work '
                           'runs changes, so it overlaps the next clip sampling on other cards.',
                  'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                out = decode_clip(vae, audio_vae, video_latent, audio_latent)
                report['detail'] = {'emitted_index': max(0, clip_index - upstream_depth),
                                    'primed': True}
            else:
                latents = (video_latent, audio_latent)
                # During the upstream stage's own fill it emits its own clip, so
                # the index this prompt is really carrying is clamped at zero.
                # Those first few prompts re-emit an early clip; every clip is
                # still decoded exactly once, and emitted_index records which.
                out, detail = pipeline.run_behind(
                    'decode', max(0, clip_index - upstream_depth), depth,
                    lambda: decode_clip(vae, audio_vae, *latents))
                report['detail'] = detail
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('pipeline-decode-' + run_name + '.json'), report)
        return out


NODE_CLASS_MAPPINGS = {'LTXPipelineDecode': LTXPipelineDecode}
