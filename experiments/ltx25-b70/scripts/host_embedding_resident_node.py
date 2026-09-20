"""Inactive successor: retain nonencoder components; replace only CLIP.

The five component outputs and all diffusion/VAE/upscaler loading operations
match packet10's split lane. Only the explicit CLIP ownership adapter changes.
No prompt encodings or generated outputs are retained here.
"""
import gc
import hashlib
import json
import time
import weakref

from host_embedding_transition_memory import checkpoint_geometry, admission, restore_allocation

import torch
import comfy.model_management
import comfy.sd
import comfy.utils
import folder_paths
import nodes
from comfy_extras.nodes_hunyuan import LatentUpscaleModelLoader

from ltx_layer_shard import DECLARED_SPLIT_INDEX, apply_layer_shard
from encoder_diagnostics import ROOT, _context, _exclusive_json
from host_embedding_clip import load_clip, MODES, require
from host_embedding_placement_node import NODE_CLASS_MAPPINGS as PLACEMENT_NODES

MODEL_SHA = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
_components = None
_shared = None
_mode = None
_generation = 0
_identity = None
_failure = None
_pending = []


def write_receipt(path, value):
    _exclusive_json(path, value, ROOT)


def retirement_refs(clip):
    group = clip._host_embedding
    objects = {'clip': clip, 'group': group, 'encoder_patcher': clip.patcher,
               'encoder_model': clip.cond_stage_model}
    if group.owner is not None:
        owner = group.owner
        objects.update(host_owner=owner, host_patcher=owner.host,
                       host_model=owner.host.model, host_weight=owner.weight)
    return {name: weakref.ref(value) for name, value in objects.items()}


def require_dead(refs):
    survivors = [name for name, ref in refs.items() if ref() is not None]
    require(not survivors, 'Retired CLIP owner survived; refuse replacement: ' + ', '.join(survivors))
    return {'all_retired_weakrefs_dead': True, 'checked': sorted(refs)}


def memory_gate(run_dir, prefix, stage, allocation):
    report = admission(stage, allocation)
    write_receipt(run_dir / (prefix + '-' + stage + '-memory.json'), report)
    require(report['passed'], 'Insufficient source-budgeted host RAM at ' + stage)
    return report


def shared_identity(shared):
    model, video, audio, upscaler = shared
    shard, = model.get_additional_models_with_key('ltx_layer_shard')
    return {'model_patcher': id(model), 'model': id(model.model), 'shard_patcher': id(shard),
            'shard_model': id(shard.model), 'video_vae': id(video), 'audio_vae': id(audio),
            'upscaler': id(upscaler)}


class LTXHostEmbeddingComponents:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'placement': (['split'],), 'encoder_mode': (list(MODES),)}}

    RETURN_TYPES = ('MODEL', 'CLIP', 'VAE', 'VAE', 'LATENT_UPSCALE_MODEL')
    RETURN_NAMES = ('model', 'clip', 'video_vae', 'audio_vae', 'upscaler')
    FUNCTION = 'load'
    CATEGORY = 'lab/validation'

    def load(self, placement, encoder_mode):
        global _components, _shared, _mode, _generation, _identity, _failure, _pending
        require(placement == 'split' and encoder_mode in MODES, 'Unsupported component configuration')
        require(_failure is None, 'Component transition failed; halt new requests and inspect evidence')
        run_dir, identity = _context(ROOT)
        require(identity['model_verification_sha256'] == MODEL_SHA, 'Original model identity required')
        if _identity is not None:
            require(identity == _identity, 'Server/model identity changed during component ownership')
        if _components is not None and _mode == encoder_mode:
            _components[1]._host_embedding.guard()
            return _components

        next_generation = _generation + 1
        prefix = f'host-components-{next_generation:02d}-{encoder_mode}'
        started = run_dir / (prefix + '-started.json')
        result_path = run_dir / (prefix + '-result.json')
        require(not result_path.exists() and not result_path.is_symlink(), 'Existing transition result')
        record = {'schema': 'ltx.host-embedding-components.v2', **identity,
                  'generation': next_generation, 'previous_generation': _generation,
                  'placement': placement, 'encoder_mode': encoder_mode, 'previous_mode': _mode,
                  'retained': 'nonencoder components across all generations; one current CLIP', 'prompt_encoding_cache': False,
                  'generated_output_cache': False, 'status': 'started'}
        write_receipt(started, record)
        start = time.monotonic()
        phase = 'retire-previous-components'
        try:
            clip_path = folder_paths.get_full_path_or_raise('text_encoders', 'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors')
            geometry = checkpoint_geometry(clip_path)
            record['memory_geometry'] = geometry
            if _components is not None:
                clip = _components[1]
                inspection = clip._host_embedding.inventory(clip)
                record['restore_memory'] = memory_gate(run_dir, prefix, 'before-restore', restore_allocation(inspection['encoder']))
                retired_patcher_ids = [id(clip.patcher)]
                if clip._host_embedding.owner is not None:
                    retired_patcher_ids.append(id(clip._host_embedding.owner.host))
                refs = retirement_refs(clip)
                retirement = clip._host_embedding.detach_restore(clip)
                write_receipt(run_dir / (prefix + '-unload.json'), {**identity, **retirement,
                    'old_generation': _generation, 'new_generation': next_generation,
                    'old_mode': _mode, 'new_mode': encoder_mode})
                # Keep nonencoder owners strongly resident. Remove old CLIP from
                # every component slot/local before collecting cycles. The native
                # LoadedModel registry is weak and its finalizer removes dead models.
                _components = None
                _mode = None
                del clip
                gc.collect()
                comfy.model_management.cleanup_models()
                death = require_dead(refs)
                live_registry_ids = {id(p) for p in comfy.model_management.loaded_models() if p is not None}
                require(not live_registry_ids.intersection(retired_patcher_ids), 'Retired CLIP remains in native registry')
                death['retired_patcher_ids_absent_from_registry'] = True
                write_receipt(run_dir / (prefix + '-retired-owner-release.json'), {**identity, **death,
                    'old_generation': _generation, 'new_generation': next_generation,
                    'shared_owner_ids': shared_identity(_shared),
                    'native_registry_cleanup': 'cleanup_models after weak-finalizer cleanup; no direct list mutation'})
                record['released_memory'] = memory_gate(run_dir, prefix, 'after-release', 0)

            _pending = []
            if _shared is None:
                phase = 'load-diffusion'
                model = nodes.UNETLoader().load_unet('ltx-2.5-22b-distilled-transformer-bf16.safetensors', 'default')[0]
                _pending.append(model)
            else:
                model, video, audio, upscaler = _shared
                vaes = [video, audio]
                record['shared_owner_ids_before'] = shared_identity(_shared)
            phase = 'admit-CPU-encoder-construction'
            record['construction_memory'] = memory_gate(run_dir, prefix, 'before-construction', geometry['construction_overlap_bytes'])
            phase = 'construct-CPU-encoder-ownership'
            clip = load_clip(ckpt_paths=[clip_path],
                embedding_directory=folder_paths.get_folder_paths('embeddings'), mode=encoder_mode,
                model_options={'load_device': torch.device('xpu:2'), 'offload_device': torch.device('cpu')})
            _pending.append(clip)
            record['constructed_memory'] = memory_gate(run_dir, prefix, 'after-construction', 0)
            initial_encoder = clip._host_embedding.inventory(clip)
            require(clip.patcher.loaded_size() == 0 and all(p.device.type == 'cpu'
                    for p in clip.cond_stage_model.parameters()), 'Encoder loaded before ownership receipt')

            if _shared is None:
                phase = 'load-VAEs'
                vaes = []
                for name in ['ltx-2.5-video-vae-bf16.safetensors', 'ltx-2.5-audio-vae-bf16.safetensors']:
                    path = folder_paths.get_full_path_or_raise('vae', name)
                    weights, metadata = comfy.utils.load_torch_file(path, return_metadata=True)
                    vae = comfy.sd.VAE(sd=weights, metadata=metadata, device=torch.device('xpu:3'))
                    vae.throw_exception_if_invalid()
                    del weights
                    vaes.append(vae)
                    _pending.append(vae)
                phase = 'load-upscaler-and-split'
                upscaler = LatentUpscaleModelLoader.execute('ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors')[0]
                _pending.append(upscaler)
                model = apply_layer_shard(model, secondary_device='xpu:1', split_index=DECLARED_SPLIT_INDEX)
                _shared = (model, *vaes, upscaler)
            record['shared_owner_ids'] = shared_identity(_shared)
            if 'shared_owner_ids_before' in record:
                require(record['shared_owner_ids'] == record['shared_owner_ids_before'], 'Nonencoder ownership changed')
            completed = (model, clip, *vaes, upscaler)
            record.update(status='completed', seconds=time.monotonic() - start,
                encoder_initial_ownership=initial_encoder,
                model_load_device=str(model.load_device),
                text_encoder_load_device=str(clip.patcher.load_device),
                vae_devices=[str(v.device) for v in vaes], shard=model.ltx_layer_shard_report)
            write_receipt(result_path, record)
            _components, _mode, _generation, _identity = completed, encoder_mode, next_generation, identity
            _pending = []
            return _components
        except BaseException as error:
            # Retain partial owners for inspection; never retry or cycle a server.
            _failure = {'phase': phase, 'error': repr(error), 'generation': next_generation}
            record.update(status='failed', seconds=time.monotonic() - start, failure=_failure,
                          retained_partial_owners=len(_pending), shared_components_retained=_shared is not None)
            if not result_path.exists() and not result_path.is_symlink():
                write_receipt(result_path, record)
            raise


NODE_CLASS_MAPPINGS = {'LTXHostEmbeddingComponents': LTXHostEmbeddingComponents, **PLACEMENT_NODES}
