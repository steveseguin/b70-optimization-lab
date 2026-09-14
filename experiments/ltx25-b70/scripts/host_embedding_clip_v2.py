"""Inactive per-component CLIP integration for the qualified CPU gather prototype.

No global CLIP/model patch, installer, launcher, or runtime action. Both modes
construct on CPU; the native loader keeps its estimator/reserve/budget policy.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace
import weakref

import torch
import comfy.sd
import comfy.model_management as model_management

from ltx_host_embedding_candidate import HostEmbeddingOwner, require, unmodified
from encoder_diagnostics import inspect_encoder

MODES = ('control', 'host-table')


class ClipOwnership:
    def __init__(self, clip, mode):
        require(mode in MODES, 'Unknown host embedding mode')
        self.mode = mode
        self.encoder_model = clip.cond_stage_model
        self.owner = None
        self.retired = False
        self.failed = False
        self.clips = []
        self.hooks = []
        self.encodes = 0
        self.last_checked_encode = 0
        self.embedding_observations = []
        self.observation_active = False
        self.observation_limit = 4
        self.internal_state = ContextVar('ltx-host-embedding-state-accounting', default=False)
        self.last_load = None
        self.original_bytes = clip.patcher.model_size()
        if mode == 'host-table':
            parent = clip.cond_stage_model.gemma3_12b.transformer.model
            self.owner = HostEmbeddingOwner(clip.patcher, parent)
            try:
                # Root state dictionaries otherwise silently omit the extracted
                # table. The private loader context permits size accounting only.
                for root in (self.encoder_model, self.owner.host.model):
                    self.hooks.append(root.register_state_dict_pre_hook(self.block_state_dict))
                    for module in root.modules():
                        self.hooks.append(module.register_load_state_dict_pre_hook(self.block_state_load))
            except BaseException:
                for hook in self.hooks:
                    hook.remove()
                self.owner.restore()
                self.owner.host.model._modules.pop('embedding')
                self.owner.host.size = 0
                raise
        embedding = self.encoder_model.gemma3_12b.transformer.model.embed_tokens
        self.embedding_observer_handle = embedding.register_forward_hook(self.observe_embedding, with_kwargs=True)

    def observe_embedding(self, module, args, kwargs, output):
        require(self.observation_active and len(self.embedding_observations) < self.observation_limit,
                'Embedding observation outside active bounded encode')
        require(len(args) == 1 and torch.is_tensor(args[0]) and torch.is_tensor(output),
                'Unexpected embedding call signature')
        indices = args[0]
        require(indices.dtype == torch.long and indices.ndim == 2
                and kwargs.get('out_dtype') == torch.float32,
                'Expected original int64 IDs and F32 embedding output request')
        require(output.dtype == torch.float32 and output.device == indices.device
                and output.ndim == 3 and tuple(output.shape[:2]) == tuple(indices.shape),
                'Scaled embedding metadata differs from input geometry/device/dtype')
        metadata = lambda value: {'shape': list(value.shape), 'dtype': str(value.dtype), 'device': str(value.device)}
        self.embedding_observations.append({'ordinal': len(self.embedding_observations) + 1,
            'input_ids': metadata(indices), 'scaled_embedding': metadata(output),
            'scope': 'Observed module input and final scaled output only; internal BF16 gather is not separately observed'})
        # Returning None preserves the original output object unchanged.

    def consume_observations(self):
        require(not self.observation_active and self.encodes == self.last_checked_encode + 1
                and 0 < len(self.embedding_observations) <= self.observation_limit,
                'Expected exactly one completed unconsumed encoding')
        self.last_checked_encode = self.encodes
        self.embedding_observations.clear()

    def active(self):
        return self.owner is not None and self.owner.active

    @contextmanager
    def loader_state_access(self):
        token = self.internal_state.set(True)
        try:
            yield
        finally:
            self.internal_state.reset(token)

    def block_state_dict(self, *args):
        require(not self.active() or self.internal_state.get(),
                'CPU table is separately owned; detach and restore before serializing')

    def block_state_load(self, *args):
        require(not self.active(), 'Detach and restore CPU table ownership before loading state')

    def bind(self, clip):
        require(clip.cond_stage_model is self.encoder_model and clip.patcher.model is self.encoder_model,
                'Different CLIP/model owner is unsupported')
        self.clips.append(weakref.ref(clip))

    def guard(self, *, cleanup=False):
        require(not self.retired and (cleanup or not self.failed), 'Retired/failed CLIP component cannot encode')
        for ref in self.clips:
            clip = ref()
            if clip is None:
                continue
            require(clip._host_embedding is self and clip.cond_stage_model is self.encoder_model
                    and clip.patcher.model is self.encoder_model, 'CLIP clone ownership changed')
            require(clip.layer_idx is None and not clip.use_clip_schedule,
                    'Layer selection and scheduled CLIP hooks are unsupported')
            unmodified(clip.patcher)
        if self.owner is not None:
            with self.loader_state_access():
                self.owner.guard()

    def inventory(self, clip, *, require_loaded=False, cleanup=False):
        self.guard(cleanup=cleanup)
        encoder = inspect_encoder(clip)
        result = {'schema': 'ltx.host-embedding-placement.v1', 'mode': self.mode,
                  'encodes_completed': self.encodes, 'original_combined_bytes': self.original_bytes,
                  'encoder': encoder, 'host': None, 'owner': None, 'last_load': self.last_load,
                  'embedding_observations': [dict(row) for row in self.embedding_observations],
                  'embedding_observation_limit': self.observation_limit,
                  'quality_qualified': False, 'speed_qualified': False}
        if self.owner is not None:
            owner = self.owner
            with self.loader_state_access():
                owner.guard(require_resident=require_loaded)
                owner.host.model_size()
            host = inspect_encoder(SimpleNamespace(patcher=owner.host, cond_stage_model=owner.host.model))
            require(host['parameters']['count'] == 1 and host['buffers']['count'] == 0,
                    'Unexpected CPU table owner inventory')
            table = host['parameters']['records'][0]
            require(table['name'] == 'embedding.weight' and table['device'] == 'cpu'
                    and table['dtype'] == 'torch.bfloat16', 'CPU table placement changed')
            require(encoder['parameters']['bytes'] + sum(x['bytes'] for x in encoder['buffers']['records']
                    if x['persistent']) + table['bytes'] == self.original_bytes,
                    'Registered combined model byte count changed')
            if require_loaded:
                require(owner.host.loaded_size() == owner.host_bytes,
                        'CPU owner is missing from native loaded-model accounting')
                accounting = encoder['accounting']
                actual = accounting['registered_parameter_bytes_on_load_device'] + accounting['registered_persistent_buffer_bytes_on_load_device']
                require(actual == clip.patcher.loaded_size() == clip.patcher.model_size(),
                        'Actual remaining encoder residency/accounting mismatch')
            result.update(host=host, owner=owner.metadata())
        return result

    def detach_restore(self, clip):
        """Retire one shared component group; surviving clones cannot encode."""
        self.guard(cleanup=True)
        before = self.inventory(clip, cleanup=True)
        clip.patcher.detach()
        if self.owner is not None:
            with self.loader_state_access():
                self.owner.restore()  # Also detaches the host patcher.
            # The prototype retained this module for its standalone inspection.
            # Integration must retire the CPU registration after restoration.
            self.owner.host.model._modules.pop('embedding')
            self.owner.host.size = 0
            require(not list(self.owner.host.model.parameters()) and self.owner.host.loaded_size() == 0,
                    'Retired CPU owner still registers loaded state')
        for hook in self.hooks:
            hook.remove()
        self.hooks.clear()
        self.embedding_observer_handle.remove()
        self.embedding_observations.clear()
        require(clip.patcher.loaded_size() == 0 and all(p.device.type == 'cpu'
                for p in self.encoder_model.parameters()), 'Encoder detach incomplete')
        require(clip.patcher.model_size() == self.original_bytes, 'Original ownership was not restored')
        self.retired = True
        return {'schema': 'ltx.host-embedding-unload.v1', 'before': before,
                'after_encoder': inspect_encoder(clip), 'after_host_registered_bytes': 0,
                'original_ownership_restored': True, 'all_shared_clones_retired': True}


class HostEmbeddingCLIP(comfy.sd.CLIP):
    @classmethod
    def adopt(cls, clip, group):
        require(type(clip) is comfy.sd.CLIP, 'Only original CLIP instances can be adapted')
        result = cls(no_init=True)
        result.__dict__.update(clip.__dict__)
        result._host_embedding = group
        group.bind(result)
        return result

    def clone(self, disable_dynamic=False):
        self._host_embedding.guard()
        clone = super().clone(disable_dynamic=disable_dynamic)
        return type(self).adopt(clone, self._host_embedding)

    def load_model(self, tokens={}):
        group = self._host_embedding
        group.guard()
        # Same estimator and same memory_required argument as original CLIP.
        memory_used = 0
        if hasattr(self.cond_stage_model, 'memory_estimation_function'):
            memory_used = self.cond_stage_model.memory_estimation_function(tokens, device=self.patcher.load_device)
        patchers = [self.patcher]
        if group.owner is not None:
            # Native loader reverses the list: load the CPU owner first.
            patchers.append(group.owner.host)
        with group.loader_state_access():
            model_management.load_models_gpu(patchers, memory_required=memory_used)
        group.last_load = {'memory_required': memory_used, 'patcher_ids': [id(p) for p in patchers],
                           'force_full_load': False, 'reserve_override': False}
        if group.owner is not None:
            group.owner.guard(require_resident=True)
            require(group.owner.host.loaded_size() == group.owner.host_bytes,
                    'CPU owner is missing from native loaded-model accounting')
        return self.patcher

    def encode_from_tokens(self, *args, **kwargs):
        group = self._host_embedding
        group.guard()
        require(group.encodes == group.last_checked_encode and not group.observation_active
                and not group.embedding_observations, 'Previous embedding observations were not consumed')
        group.observation_active = True
        try:
            result = super().encode_from_tokens(*args, **kwargs)
            if group.owner is not None:
                group.owner.guard(require_resident=True)
            require(0 < len(group.embedding_observations) <= group.observation_limit,
                    'Completed encode did not observe bounded embedding calls')
            group.encodes += 1
            return result
        except BaseException:
            group.failed = True
            raise
        finally:
            group.observation_active = False

    def _state_api(self):
        require(not self._host_embedding.active(), 'Detach and restore CPU table before CLIP state APIs')

    def get_sd(self):
        self._state_api()
        return super().get_sd()

    def state_dict_for_saving(self):
        self._state_api()
        return super().state_dict_for_saving()

    def load_sd(self, *args, **kwargs):
        self._state_api()
        return super().load_sd(*args, **kwargs)

    def get_key_patches(self):
        self._state_api()
        return super().get_key_patches()

    def add_patches(self, *args, **kwargs):
        self._state_api()
        return super().add_patches(*args, **kwargs)


def load_clip(*, ckpt_paths, embedding_directory, mode, model_options):
    require(mode in MODES, 'Unknown host embedding mode')
    options = dict(model_options)
    require(options.get('load_device') == torch.device('xpu:2')
            and options.get('offload_device') == torch.device('cpu'),
            'This integration requires the original XPU2/CPU encoder placement')
    require(not options.get('ltx_small_state_residency') and not options.get('ltx_crop_before_cpu'),
            'Do not combine prior encoder experiments')
    options['initial_device'] = torch.device('cpu')
    original = comfy.sd.load_clip(ckpt_paths=ckpt_paths, embedding_directory=embedding_directory,
                                 clip_type=comfy.sd.CLIPType.LTXV, model_options=options)
    require(not original.patcher.is_dynamic() and original.patcher.loaded_size() == 0,
            'CLIP must remain static/unloaded until ownership installation')
    group = ClipOwnership(original, mode)
    return HostEmbeddingCLIP.adopt(original, group)
