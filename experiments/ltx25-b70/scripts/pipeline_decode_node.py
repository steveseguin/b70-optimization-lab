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

`pipeline-save` additionally assembles and writes the lossy MP4 preview on the
same worker, right after the decode, so the 0.13 s of container encoding leaves
the prompt thread too. The written file is what the sealed SaveVideo node
would write (same container, codec, fps, bit depth and colour space; no
embedded prompt metadata). The prompt emits its path through
LTXPipelineSaveRecord, an output node that records but does not encode.
"""
import os
import hashlib
import json
from pathlib import Path
import re
import time

import torch

import ltx_pipeline as pipeline
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
DECODE_MODES = pipeline.MODES + ('pipeline-save',)
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def decode_clip(vae, audio_vae, video_latent, audio_latent, save_prefix=None):
    """Exactly what VAEDecode and LTXVAudioVAEDecode do, then optionally the MP4 write."""
    import nodes
    from comfy_extras.nodes_lt_audio import LTXVAudioVAEDecode
    decoded = nodes.VAEDecode().decode(vae, video_latent)
    require(isinstance(decoded, tuple) and len(decoded) == 1,
            'VAEDecode no longer returns a single image batch')
    images = decoded[0]
    audio = LTXVAudioVAEDecode.execute(samples=audio_latent, audio_vae=audio_vae).result[0]
    saved = ''
    if save_prefix:
        saved = save_preview_guarded(images, audio, save_prefix)
    return images, audio, video_latent, audio_latent, saved


SAVE_FAILURES = []


def save_preview_guarded(images, audio, prefix):
    """The MP4 is a lossy preview; the raw tensors and their oracle are the product.
    A muxer/encoder failure therefore records diagnostics (and the waveform, for
    offline replay) instead of failing the clip, and returns a 'save-failed:' marker."""
    try:
        return save_preview(images, audio, prefix)
    except Exception as error:  # noqa: BLE001  (diagnostic capture, then continue)
        import folder_paths
        waveform = audio.get('waveform') if isinstance(audio, dict) else None
        row = {'prefix': prefix, 'error': repr(error)[:400],
               'images_shape': list(images.shape) if hasattr(images, 'shape') else None,
               'sample_rate': audio.get('sample_rate') if isinstance(audio, dict) else None}
        if waveform is not None:
            w = waveform.detach().float().cpu()
            row.update({'waveform_shape': list(w.shape), 'waveform_dtype': str(waveform.dtype),
                        'waveform_device': str(waveform.device), 'nan': int(torch.isnan(w).sum()),
                        'inf': int(torch.isinf(w).sum()), 'min': float(w.min()) if w.numel() else None,
                        'max': float(w.max()) if w.numel() else None})
            try:
                folder = folder_paths.get_output_directory()
                dump = os.path.join(folder, prefix.replace('/', '_') + '_audio_debug.pt')
                torch.save({'waveform': w, 'sample_rate': row['sample_rate']}, dump)
                row['dump'] = dump
            except Exception as dump_error:  # noqa: BLE001
                row['dump_error'] = repr(dump_error)[:200]
        SAVE_FAILURES.append(row)
        return 'save-failed:' + type(error).__name__


def save_preview(images, audio, prefix):
    """What the sealed CreateVideo(fps 24, 8-bit sRGB, codec none) + SaveVideo(mp4, auto) pair writes."""
    import folder_paths
    from comfy_api.latest import Types
    from comfy_extras.nodes_video import CreateVideo
    video = CreateVideo.execute(images=images, fps=24.0, audio=audio, bit_depth=8,
                                color_space='sRGB', codec='none').result[0]
    width, height = video.get_dimensions()
    folder, filename, counter, subfolder, _prefix = folder_paths.get_save_image_path(
        prefix, folder_paths.get_output_directory(), width, height)
    file = f"{filename}_{counter:05}_.mp4"
    video.save_to(os.path.join(folder, file), format=Types.VideoContainer('mp4'),
                  codec=Types.VideoCodec('auto'), metadata=None, crf=None)
    return os.path.join(subfolder, file)


class LTXPipelineDecode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'vae': ('VAE',), 'audio_vae': ('VAE',),
                             'video_latent': ('LATENT',), 'audio_latent': ('LATENT',),
                             'mode': (list(DECODE_MODES),),
                             'clip_index': ('INT', {'default': 0, 'min': -1, 'max': 1000000}),
                             'depth': ('INT', {'default': 1, 'min': 1,
                                               'max': pipeline.MAX_PENDING}),
                             # How many prompts the latents arriving here already
                             # lag by, when an upstream stage runs behind too.
                             # Keeps `emitted_index` naming the clip it really is.
                             'upstream_depth': ('INT', {'default': 0, 'min': 0,
                                                        'max': pipeline.MAX_PENDING}),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('IMAGE', 'AUDIO', 'LATENT', 'LATENT', 'STRING')
    RETURN_NAMES = ('images', 'audio', 'video_latent', 'audio_latent', 'saved_file')
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
        require(mode in DECODE_MODES, 'Only preregistered modes are admitted')
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
            elif clip_index < 0:
                # Upstream fill (the pipelined sampler emitted nothing): emit
                # nothing here either. Small placeholders; never decoded, never
                # saved, skipped by the driver.
                out = (torch.zeros(1, 8, 8, 3), {'waveform': torch.zeros(1, 2, 8), 'sample_rate': 48000},
                       video_latent, audio_latent, 'fill')
                report['detail'] = {'emitted_index': -1, 'fill': True, 'upstream_fill': True}
            else:
                latents = (video_latent, audio_latent)
                decode_index = max(0, clip_index - upstream_depth)
                # Packet 90: the latents submitted here must be byte-identical
                # to what the sampler's worker-side sentry recorded for this
                # clip. This is the last checkpoint before the clip leaves the
                # sampler's outputs for the decode stage (the f89 NaN bird's
                # passthrough latents were NaN at the capture node, which reads
                # this stage's inputs).
                sentry = pipeline.fingerprint(('sample-output', decode_index))
                require(sentry is not None and sentry['video_finite'] and sentry['audio_finite'],
                        'Decode input sentry missing or nonfinite for clip %d: %s' % (decode_index, sentry))
                for key, lat in (('video', video_latent), ('audio', audio_latent)):
                    tensor = lat['samples']
                    require(bool(torch.isfinite(tensor).all().item()),
                            'Nonfinite %s latents at decode submit for clip %d' % (key, decode_index))
                    sha = hashlib.sha256(tensor.detach().to('cpu', copy=True)
                                         .view(torch.uint8).numpy().tobytes()).hexdigest()
                    require(sha == sentry[key + '_sha256'],
                            'Decode-submit %s latents for clip %d differ from the sampler sentry: %s vs %s'
                            % (key, decode_index, sha[:12], sentry[key + '_sha256'][:12]))
                save_prefix = (run_name + '/preview') if mode == 'pipeline-save' else None
                # During the upstream stage's own fill it emits its own clip, so
                # the index this prompt is really carrying is clamped at zero.
                # Those first few prompts re-emit an early clip; every clip is
                # still decoded exactly once, and emitted_index records which.
                out, detail = pipeline.run_behind(
                    'decode', decode_index, depth,
                    lambda: decode_clip(vae, audio_vae, *latents, save_prefix=save_prefix))
                if out is None:
                    out = (torch.zeros(1, 8, 8, 3), {'waveform': torch.zeros(1, 2, 8), 'sample_rate': 48000},
                           video_latent, audio_latent, 'fill')
                detail['saved_file'] = out[4]
                report['detail'] = detail
            report['save_failures'] = [dict(row) for row in SAVE_FAILURES]
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('pipeline-decode-' + run_name + '.json'), report)
        return out


class LTXPipelineSaveRecord:
    """Output node: records the preview already written by the decode worker."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'saved_file': ('STRING', {'forceInput': True}),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, saved_file, run_name):
        require(isinstance(saved_file, str) and saved_file, 'The decode worker did not write a preview')
        if saved_file == 'fill':
            return {'ui': {'text': ['pipeline fill: nothing emitted']}}
        run, _identity = _context()
        write_json(run / ('pipeline-save-' + run_name + '.json'),
                   {'schema': 'ltx.pipeline-save-record.v1', 'run_name': run_name, 'saved_file': saved_file})
        subfolder, file = os.path.split(saved_file)
        return {'ui': {'images': [{'filename': file, 'subfolder': subfolder, 'type': 'output'}]}}


NODE_CLASS_MAPPINGS = {'LTXPipelineDecode': LTXPipelineDecode, 'LTXPipelineSaveRecord': LTXPipelineSaveRecord}
