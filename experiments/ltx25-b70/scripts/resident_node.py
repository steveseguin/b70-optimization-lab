"""Retain verified model components, never prompt encodings or generated outputs."""
import gc
import hashlib
import json
import logging
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

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
_components = None
_placement = None
_generation = 0
_verification_sha256 = None


class LTXResidentComponents:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'placement': (['single', 'separate', 'split'],)}}

    RETURN_TYPES = ('MODEL', 'CLIP', 'VAE', 'VAE', 'LATENT_UPSCALE_MODEL')
    RETURN_NAMES = ('model', 'clip', 'video_vae', 'audio_vae', 'upscaler')
    FUNCTION = 'load'
    CATEGORY = 'lab/validation'

    def load(self, placement):
        global _components, _placement, _generation, _verification_sha256
        assert placement in ['single', 'separate', 'split']
        assert not (ROOT / 'FAULT.json').exists(), 'device fault recorded'
        verification_bytes = (ROOT / 'model-verification.json').read_bytes()
        verification = json.loads(verification_bytes)
        verification_sha256 = hashlib.sha256(verification_bytes).hexdigest()
        assert verification['status'] == 'passed'
        if _components is not None and placement == _placement:
            assert verification_sha256 == _verification_sha256, 'model verification changed; refuse stale components'
            logging.info('LTX resident component reuse: %s; no prompt/output reuse', placement)
            return _components
        if _components is not None:
            # A deliberate graph configuration change releases the previous model set.
            comfy.model_management.unload_all_models()
            _components = None
            _placement = None
            gc.collect()
            comfy.model_management.cleanup_models_gc()
        start = time.monotonic()
        model = nodes.UNETLoader().load_unet('ltx-2.5-22b-distilled-transformer-bf16.safetensors', 'default')[0]
        clip_path = folder_paths.get_full_path_or_raise('text_encoders', 'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors')
        clip_options = {} if placement == 'single' else {'load_device': torch.device('xpu:2'),
                                                         'offload_device': torch.device('cpu')}
        clip = comfy.sd.load_clip(ckpt_paths=[clip_path],
                                  embedding_directory=folder_paths.get_folder_paths('embeddings'),
                                  clip_type=comfy.sd.CLIPType.LTXV, model_options=clip_options)
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
        if placement == 'split':
            model = apply_layer_shard(model, secondary_device='xpu:1')
        _components = (model, clip, *vaes, upscaler)
        _placement = placement
        _verification_sha256 = verification_sha256
        _generation += 1
        receipt = {'placement': placement, 'seconds': time.monotonic() - start,
                   'generation': _generation, 'retained': 'model components only',
                   'model_verification_sha256': verification_sha256,
                   'prompt_encoding_cache': False, 'generated_output_cache': False,
                   'model_load_device': str(model.load_device),
                   'text_encoder_load_device': str(clip.patcher.load_device),
                   'vae_devices': [str(v.device) for v in vaes]}
        if placement == 'split':
            receipt['shard'] = model.ltx_layer_shard_report
        (ROOT / 'speed-server' / f'components-{_generation:02d}-{placement}.json').write_text(json.dumps(receipt, indent=2) + '\n')
        logging.info('LTX resident components initialized: %s', receipt)
        return _components


NODE_CLASS_MAPPINGS = {'LTXResidentComponents': LTXResidentComponents}
