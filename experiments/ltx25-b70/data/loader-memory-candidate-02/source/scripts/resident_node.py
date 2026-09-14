"""Retain verified model components, never prompt encodings or generated outputs."""
import gc
import hashlib
import json
import logging
import os
from pathlib import Path
import time

import torch
import comfy.model_management
import comfy.sd
import comfy.utils
import folder_paths
import nodes
from comfy_extras.nodes_hunyuan import LatentUpscaleModelLoader

from ltx_layer_shard import apply_layer_shard
from encoder_diagnostics import (
    begin_encoder_unload, finish_encoder_unload,
    NODE_CLASS_MAPPINGS as ENCODER_DIAGNOSTIC_NODES,
)

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
_components = None
_placement = None
_encoder_variant = None
_loader_policy = None
_generation = 0
_verification_sha256 = None


class LTXResidentComponents:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'placement': (['single', 'separate', 'split'],)},
                'optional': {'encoder_variant': (['control', 'crop', 'small_state', 'combined'], {'default': 'control'}),
                             'loader_policy': (['baseline', 'assign', 'assign_preload'], {'default': 'baseline'})}}

    RETURN_TYPES = ('MODEL', 'CLIP', 'VAE', 'VAE', 'LATENT_UPSCALE_MODEL')
    RETURN_NAMES = ('model', 'clip', 'video_vae', 'audio_vae', 'upscaler')
    FUNCTION = 'load'
    CATEGORY = 'lab/validation'

    def load(self, placement, encoder_variant="control", loader_policy="baseline"):
        global _components, _placement, _encoder_variant, _loader_policy, _generation, _verification_sha256
        assert placement in ['single', 'separate', 'split']
        assert loader_policy in ['baseline', 'assign', 'assign_preload']
        assert loader_policy == 'baseline' or placement == 'split', 'loader candidate requires split placement'
        assert encoder_variant in ['control', 'crop', 'small_state', 'combined']
        assert not (ROOT / 'FAULT.json').exists(), 'device fault recorded'
        verification_bytes = (ROOT / 'model-verification.json').read_bytes()
        verification = json.loads(verification_bytes)
        verification_sha256 = hashlib.sha256(verification_bytes).hexdigest()
        assert verification['status'] == 'passed'
        run_value = os.environ.get('LTX_ENCODER_RUN_DIR', '')
        run_dir = Path(run_value)
        assert run_value and run_dir.is_absolute(), 'LTX_ENCODER_RUN_DIR must be explicit and absolute'
        assert run_dir.resolve().parent == ROOT.resolve() and run_dir.name.startswith('encoder-server-'), 'dedicated encoder receipt directory required'
        assert run_dir.is_dir() and not run_dir.is_symlink(), 'encoder receipt directory must already exist'
        if _components is not None and placement == _placement and encoder_variant == _encoder_variant and loader_policy == _loader_policy:
            assert verification_sha256 == _verification_sha256, 'model verification changed; refuse stale components'
            logging.info('LTX resident component reuse: %s/%s; no prompt/output reuse', placement, encoder_variant)
            return _components
        receipt_path = run_dir / f'components-{_generation + 1:02d}-{placement}-{encoder_variant}.json'
        if receipt_path.exists() or receipt_path.is_symlink():
            raise FileExistsError(f'Refuse existing component receipt: {receipt_path}')
        if _components is not None:
            # A deliberate graph configuration change releases the previous model set.
            unload_report = begin_encoder_unload(
                _components[1], _generation, _generation + 1,
                _encoder_variant, encoder_variant, root=ROOT)
            comfy.model_management.unload_all_models()
            finish_encoder_unload(_components[1], unload_report, root=ROOT)
            _components = None
            _placement = None
            _encoder_variant = None
            _loader_policy = None
            gc.collect()
            comfy.model_management.cleanup_models_gc()
        start = time.monotonic()
        if loader_policy == 'baseline':
            model = nodes.UNETLoader().load_unet('ltx-2.5-22b-distilled-transformer-bf16.safetensors', 'default')[0]
        else:
            model_path = folder_paths.get_full_path_or_raise(
                'diffusion_models', 'ltx-2.5-22b-distilled-transformer-bf16.safetensors')
            model = comfy.sd.load_diffusion_model(model_path,
                model_options={'ltx_native_bf16_assign': True}, disable_dynamic=True)
        if loader_policy == 'assign_preload':
            model = apply_layer_shard(model, secondary_device='xpu:1')
            # Free CPU transformer storage before constructing the large encoder.
            comfy.model_management.load_models_gpu(
                [model] + model.get_nested_additional_models(), force_full_load=True)
            model.verify_placement()
        clip_path = folder_paths.get_full_path_or_raise('text_encoders', 'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors')
        clip_options = {} if placement == 'single' else {'load_device': torch.device('xpu:2'),
                                                         'offload_device': torch.device('cpu')}
        encoder_options = {
            'ltx_crop_before_cpu': encoder_variant in ['crop', 'combined'],
            'ltx_small_state_residency': encoder_variant in ['small_state', 'combined'],
        }
        clip_options.update(encoder_options)
        clip = comfy.sd.load_clip(ckpt_paths=[clip_path],
                                  embedding_directory=folder_paths.get_folder_paths('embeddings'),
                                  clip_type=comfy.sd.CLIPType.LTXV, model_options=clip_options)
        assert getattr(clip.cond_stage_model, 'ltx_crop_before_cpu', False) == encoder_options['ltx_crop_before_cpu'], 'crop option not propagated'
        assert clip.patcher.model_options.get('ltx_small_state_residency', False) == encoder_options['ltx_small_state_residency'], 'small-state option not propagated'
        vaes = []
        for name in ['ltx-2.5-video-vae-bf16.safetensors', 'ltx-2.5-audio-vae-bf16.safetensors']:
            if placement == 'single':
                vae = nodes.VAELoader().load_vae(name)[0]
            else:
                path = folder_paths.get_full_path_or_raise('vae', name)
                weights, metadata = comfy.utils.load_torch_file(path, return_metadata=True)
                vae = comfy.sd.VAE(sd=weights, metadata=metadata, device=torch.device('xpu:3'))
                vae.throw_exception_if_invalid()
                del weights
            vaes.append(vae)
        upscaler = LatentUpscaleModelLoader.execute('ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors')[0]
        if placement == 'split' and loader_policy != 'assign_preload':
            model = apply_layer_shard(model, secondary_device='xpu:1')
        _components = (model, clip, *vaes, upscaler)
        _placement = placement
        _encoder_variant = encoder_variant
        _loader_policy = loader_policy
        _verification_sha256 = verification_sha256
        _generation += 1
        receipt = {'placement': placement, 'encoder_variant': encoder_variant,
                   'loader_policy': loader_policy,
                   'native_assign': getattr(model, '_ltx_native_assign_report', None),
                   'encoder_options': encoder_options, 'seconds': time.monotonic() - start,
                   'generation': _generation, 'retained': 'model components only',
                   'model_verification_sha256': verification_sha256,
                   'prompt_encoding_cache': False, 'generated_output_cache': False,
                   'model_load_device': str(model.load_device),
                   'text_encoder_load_device': str(clip.patcher.load_device),
                   'vae_devices': [str(v.device) for v in vaes]}
        if placement == 'split':
            receipt['shard'] = model.ltx_layer_shard_report
        with (run_dir / f'components-{_generation:02d}-{placement}-{encoder_variant}.json').open('x') as stream:
            stream.write(json.dumps(receipt, indent=2) + '\n')
        logging.info('LTX resident components initialized: %s', receipt)
        return _components


NODE_CLASS_MAPPINGS = {'LTXResidentComponents': LTXResidentComponents, **ENCODER_DIAGNOSTIC_NODES}
