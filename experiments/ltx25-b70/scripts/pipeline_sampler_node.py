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

One more shared thing: the initial noise. `comfy.sample.prepare_noise` seeds
the GLOBAL CPU generator (`torch.manual_seed(seed)`) and then draws from it.
Two sampler threads interleaving seed and draw would hand one clip the other
clip's noise. With equal seeds that is invisible; with distinct seeds it
corrupts a clip. Every `Noise` handed to the sampler here is wrapped so
`generate_noise` runs under one process-wide lock. Same generator sequence,
never interleaved: bit-identical by construction.
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


_ACTIVE = [0]
_ACTIVE_LOCK = __import__('threading').Lock()
_PINNED = {}
_NOISE_LOCK = __import__('threading').Lock()


class _SerialisedNoise:
    """A Noise whose generate_noise cannot interleave with another thread's."""

    def __init__(self, inner):
        self.inner = inner
        self.seed = getattr(inner, 'seed', 0)

    def generate_noise(self, input_latent):
        with _NOISE_LOCK:
            return self.inner.generate_noise(input_latent)


def pin_current_patcher(base_model):
    """Stop a finishing sampler from clearing `current_patcher` under a running one.

    `comfy.model_base.BaseModel.current_patcher` is a plain attribute on the ONE
    shared model object, set at the start of a sample and set back to None at the
    end (model_patcher.py:1394). With two clips sampling at once, the first to
    finish clears it while the second is mid-forward, which fails as
    "'NoneType' object has no attribute 'prepare_state'".

    Both concurrent samplers use the same patcher -- there is one model in the
    graph -- so holding the attribute at that patcher while any sampler is active
    is inert: every read that mattered already returned this value. Assignments
    of a real patcher are honoured as normal; only the None clear is deferred
    until the last sampler leaves. Asserted on every entry, and the four raw
    oracles gate the result either way.
    """
    cls = type(base_model)
    if cls in _PINNED:
        return
    store = {}
    previous = base_model.__dict__.pop('current_patcher', None)
    if previous is not None:
        store[id(base_model)] = previous

    def getter(self):
        return store.get(id(self))

    def setter(self, value):
        if value is None and _ACTIVE[0] > 0:
            return
        store[id(self)] = value

    cls.current_patcher = property(getter, setter)
    _PINNED[cls] = store


class _Active:
    """Counts samplers in flight, so the pin knows when the last one leaves."""

    def __enter__(self):
        with _ACTIVE_LOCK:
            _ACTIVE[0] += 1
        return self

    def __exit__(self, *exc):
        with _ACTIVE_LOCK:
            _ACTIVE[0] -= 1
        return False


def _node(name):
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get(name)
    require(cls is not None, 'Missing node class: ' + name)
    return cls


def sample_clip_original(noise_a, guider_a, sampler_a, sigmas_a,
                         noise_b, guider_b, sampler_b, sigmas_b,
                         video_latent, audio_latent, upscale_model, vae):
    """The sealed chain on the prompt thread, default streams, no staging."""
    return _sample_chain(_node('LTXVConcatAVLatent'), _node('LTXVSeparateAVLatent'),
                         _node('LTXVLatentUpsampler'), _node('SamplerCustomAdvanced'),
                         noise_a, guider_a, sampler_a, sigmas_a,
                         noise_b, guider_b, sampler_b, sigmas_b,
                         video_latent, audio_latent, upscale_model, vae)


def sample_clip(noise_a, guider_a, sampler_a, sigmas_a,
                noise_b, guider_b, sampler_b, sigmas_b,
                video_latent, audio_latent, upscale_model, vae):
    """Exactly the sealed chain 377 -> 344 -> 367 -> 348 -> 340 -> 368 -> 369."""
    concat = _node('LTXVConcatAVLatent')
    separate = _node('LTXVSeparateAVLatent')
    upsampler = _node('LTXVLatentUpsampler')
    sampler_node = _node('SamplerCustomAdvanced')

    import ltx_graph_capture as capture
    capture.set_pipelined(True)
    # This thread owns one clip: everything it issues goes to its own streams
    # on both shard cards (probe 5: the overlap needs per-clip streams and
    # staged cross-card moves; shared default streams fence the clips).
    streams = [capture.thread_stream(torch.device('xpu', i)) for i in range(2)]
    try:
        with _Active(), torch.xpu.stream(streams[0]):
            torch.xpu.set_stream(streams[1])
            return _sample_chain(concat, separate, upsampler, sampler_node,
                                 _SerialisedNoise(noise_a), guider_a, sampler_a, sigmas_a,
                                 _SerialisedNoise(noise_b), guider_b, sampler_b, sigmas_b,
                                 video_latent, audio_latent, upscale_model, vae)
    finally:
        for st in streams:
            st.synchronize()
        capture.set_pipelined(False)


def _sample_chain(concat, separate, upsampler, sampler_node,
                  noise_a, guider_a, sampler_a, sigmas_a,
                  noise_b, guider_b, sampler_b, sigmas_b,
                  video_latent, audio_latent, upscale_model, vae):
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
            'upscale_model': ('LATENT_UPSCALE_MODEL',), 'vae': ('VAE',),
            'mode': (list(pipeline.MODES),),
            'clip_index': ('INT', {'default': 0, 'min': 0, 'max': 1000000}),
            'depth': ('INT', {'default': 2, 'min': 1, 'max': pipeline.MAX_PENDING}),
            'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('LATENT', 'LATENT', 'INT')
    RETURN_NAMES = ('video_latent', 'audio_latent', 'emitted_index')
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
                           'occupies xpu:0. Each worker has its own static buffers and graphs; '
                           'initial-noise generation is serialised so the global CPU generator '
                           'cannot interleave between clips.',
                  'passed': False}
        started = time.monotonic()
        try:
            if mode != 'original':
                patcher = getattr(chain['guider_a'], 'model_patcher', None)
                require(patcher is not None, 'Guider has no model patcher to pin')
                require(getattr(chain['guider_b'], 'model_patcher', None) is patcher,
                        'The two sampler stages use different patchers; pinning would be unsound')
                pin_current_patcher(patcher.model)
            if mode == 'original':
                with torch.inference_mode():
                    out = sample_clip_original(**chain)
                report['detail'] = {'emitted_index': clip_index, 'primed': True}
                emitted = clip_index
            else:
                out, detail = pipeline.run_behind(
                    'sample', clip_index, depth, lambda: sample_clip(**chain))
                report['detail'] = detail
                emitted = detail['emitted_index']
                if out is None:
                    # Fill: nothing to emit yet. Placeholder latents of the
                    # input shapes; the decode stage treats index -1 as a fill.
                    out = ({**chain['video_latent'], 'samples': torch.zeros_like(chain['video_latent']['samples'])},
                           {**chain['audio_latent'], 'samples': torch.zeros_like(chain['audio_latent']['samples'])})
            report['memory'] = {f'xpu:{i}': {'allocated_bytes': int(torch.xpu.memory_allocated(i)),
                                           'reserved_bytes': int(torch.xpu.memory_reserved(i))}
                                for i in range(torch.xpu.device_count())}
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('pipeline-sampler-' + run_name + '.json'), report)
        return (out[0], out[1], emitted)


NODE_CLASS_MAPPINGS = {'LTXPipelineSampler': LTXPipelineSampler}
