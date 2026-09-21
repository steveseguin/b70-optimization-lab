"""Inactive one-block Inductor experiment; preserve native registration/routing."""
import hashlib
import os
import weakref
from pathlib import Path

import torch
from ltx_native_activations_backend import make_backend
from comfy.ldm.lightricks import av_model
from ltx_layer_shard import (LTXLayerShardedPatcher, _BlockRoute, _Shard,
                             _forward_transfers, _verify_placement, KEY)
from comfy.patcher_extension import CallbacksMP, WrappersMP

AV_SOURCE_SHA256 = 'e880b29b1d6e2cefe807c53c26cf4733d90aaae13126d8652f5989de15d1f213'
LIFECYCLE_KEY = 'ltx_block_compile_lifecycle'
OPTIONS = {'compile_threads': 1, 'emulate_precision_casts': True,
           'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
           'max_autotune': False, 'max_autotune_gemm': False}


def check_source():
    if hashlib.sha256(Path(av_model.__file__).read_bytes()).hexdigest() != AV_SOURCE_SHA256:
        raise RuntimeError('Native LTXAV call mapping changed; re-audit compiler adapter')


class CompiledBlockRoute:
    """Clone-local callback; its module remains owned by the original shard."""
    def __init__(self, block, original_route, *, compiler=torch.compile, binding=None):
        check_source()
        if type(block) is not av_model.BasicAVTransformerBlock or type(original_route) is not _BlockRoute:
            raise TypeError('Expected original native LTXAV block and shard route')
        for module in block.modules():
            if module._forward_hooks or module._forward_pre_hooks or module._backward_hooks:
                raise RuntimeError('Block compiler does not support additional module hooks')
        tensors = tuple(block.parameters()) + tuple(block.buffers())
        if not tensors or any(t.dtype != torch.bfloat16 for t in tensors):
            raise TypeError('Native BF16 block state required')
        self.block = block
        self.original_route = original_route
        self._route_identity = (original_route.device, original_route.primary, original_route.last)
        self._binding = binding
        self._lifecycle = None
        self._validate(check_device=False)
        # This callable is never assigned to an nn.Module registration or forward.
        self.compiled = compiler(block, backend=make_backend(
            OPTIONS, Path(os.environ['LTX_ENCODER_RUN_DIR']) / 'native-activation-graphs',
            expected_count=15), fullgraph=True, dynamic=False)

    def _validate(self, *, check_device):
        if type(self.block) is not av_model.BasicAVTransformerBlock:
            raise RuntimeError('Compiled block class changed')
        if type(self.original_route) is not _BlockRoute or (
                self.original_route.device, self.original_route.primary, self.original_route.last) != self._route_identity:
            raise RuntimeError('Original route placement changed')
        if self._binding is not None:
            diffusion, index, owner, registration, container, slot = self._binding
            if (len(diffusion.transformer_blocks) != 48 or diffusion.transformer_blocks[index] is not self.block
                    or owner._modules.get(registration) is not container or container[slot] is not self.block):
                raise RuntimeError('Compiled block registered ownership changed')
        module_api = torch.nn.modules.module
        if any(getattr(module_api, name, {}) for name in (
                '_global_forward_hooks', '_global_forward_pre_hooks',
                '_global_backward_hooks', '_global_backward_pre_hooks')):
            raise RuntimeError('Global module hooks are unsupported')
        for module in self.block.modules():
            if any(getattr(module, name, {}) for name in (
                    '_forward_hooks', '_forward_pre_hooks', '_backward_hooks', '_backward_pre_hooks')):
                raise RuntimeError('Block acquired unsupported module hooks')
        state = tuple(self.block.parameters()) + tuple(self.block.buffers())
        if not state or any(t.dtype != torch.bfloat16 for t in state):
            raise RuntimeError('Compiled block state is no longer native BF16')
        if check_device and any(t.device != self._route_identity[0] for t in state):
            raise RuntimeError('Compiled block state is on the wrong route device')

    def _validate_execution(self):
        if self._binding is not None:
            if type(self._lifecycle) is not _CompilePreRun:
                raise RuntimeError('Bound compiler callback has no lifecycle gate')
            self._lifecycle.validate_current_execution()

    def _call_native(self, args):
        self._validate_execution()
        self._validate(check_device=True)
        def require_device(value):
            if isinstance(value, torch.Tensor) and value.device != self._route_identity[0]:
                raise RuntimeError('Routed numerical input is on the wrong device')
            if isinstance(value, av_model.CompressedTimestep):
                require_device(value.data)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    require_device(child)
        for key, value in args.items():
            # Infrastructure/cache tensors can intentionally retain source devices.
            if key != 'transformer_options':
                require_device(value)

        # Exact argument translation from pinned LTXAVModel.block_wrap. Keep all
        # options intact, including numerical flags; routing stays outside compile.
        return {'img': self.compiled(
            args['img'], v_context=args['v_context'], a_context=args['a_context'],
            attention_mask=args['attention_mask'], v_timestep=args['v_timestep'],
            a_timestep=args['a_timestep'], v_pe=args['v_pe'], a_pe=args['a_pe'],
            v_cross_pe=args['v_cross_pe'], a_cross_pe=args['a_cross_pe'],
            v_cross_scale_shift_timestep=args['v_cross_scale_shift_timestep'],
            a_cross_scale_shift_timestep=args['a_cross_scale_shift_timestep'],
            v_cross_gate_timestep=args['v_cross_gate_timestep'],
            a_cross_gate_timestep=args['a_cross_gate_timestep'],
            transformer_options=args['transformer_options'],
            self_attention_mask=args.get('self_attention_mask'),
            v_prompt_timestep=args.get('v_prompt_timestep'),
            a_prompt_timestep=args.get('a_prompt_timestep'))}

    def __call__(self, args, extra):
        # The original route owns transfers, device context and last-block return.
        self._validate_execution()
        self._validate(check_device=False)
        return self.original_route(args, {**extra, 'original_block': self._call_native})


def _routes(patcher):
    if type(patcher) is not LTXLayerShardedPatcher or patcher.is_dynamic():
        raise TypeError('One-block compilation requires the native static layer-sharded patcher')
    if (patcher.patches or patcher.hook_patches or patcher.forced_hooks or patcher.object_patches
            or patcher.weight_wrapper_patches or patcher.injections):
        raise RuntimeError('Unsupported model patches/hooks for the compiler screen')
    registry = patcher.model_options.get('transformer_options', {}).get('patches_replace', {}).get('dit', {})
    selected = [route for route in registry.values() if type(route) is CompiledBlockRoute]
    expected_callbacks = {CallbacksMP.ON_PRE_RUN: {KEY: [_verify_placement]}}
    expected_order = [_verify_placement]
    if selected:
        if len(selected) != 1 or type(selected[0]._lifecycle) is not _CompilePreRun:
            raise RuntimeError('Expected one bound compiler lifecycle gate')
        guard = selected[0]._lifecycle
        if guard.route is not selected[0]:
            raise RuntimeError('Compiler lifecycle route identity changed')
        expected_callbacks = {CallbacksMP.ON_PRE_RUN: {LIFECYCLE_KEY: [guard], KEY: [_verify_placement]}}
        expected_order = [guard, _verify_placement]
    if (patcher.callbacks != expected_callbacks
            or patcher.get_all_callbacks(CallbacksMP.ON_PRE_RUN) != expected_order):
        raise RuntimeError('Foreign or reordered model callbacks are unsupported')
    if patcher.wrappers != {WrappersMP.DIFFUSION_MODEL: {KEY: [_forward_transfers]}}:
        raise RuntimeError('Foreign model wrappers are unsupported')
    options = patcher.model_options.get('transformer_options', {})
    if any(options.get(key) for key in ('wrappers', 'callbacks', 'patches')):
        raise RuntimeError('Inline transformer callbacks/wrappers/patches are unsupported')
    diffusion = patcher.model.diffusion_model
    if not isinstance(diffusion, av_model.LTXAVModel) or len(diffusion.transformer_blocks) != 48:
        raise TypeError('Expected native 48-block LTXAV model')
    routes = patcher.model_options['transformer_options']['patches_replace']['dit']
    if set(routes) != {('double_block', i) for i in range(48)}:
        raise RuntimeError('Unexpected block route registry')
    _registered_binding(patcher, diffusion, routes, 0)
    return diffusion, routes


def _registered_binding(patcher, diffusion, routes, index):
    if set(patcher.additional_models) != {KEY}:
        raise RuntimeError('Unexpected additional model ownership')
    shards = patcher.get_additional_models_with_key(KEY)
    if len(shards) != 1 or type(shards[0].model) is not _Shard:
        raise RuntimeError('Expected the original registered secondary shard')
    primary = diffusion._modules.get('_ltx_primary_blocks')
    secondary_owner = shards[0].model
    secondary = secondary_owner._modules.get('blocks')
    if (not isinstance(primary, torch.nn.ModuleList) or not isinstance(secondary, torch.nn.ModuleList)
            or not 0 < len(primary) < 48 or len(primary) + len(secondary) != 48):
        raise RuntimeError('Shard module registration changed')
    if tuple(primary) + tuple(secondary) != tuple(diffusion.transformer_blocks):
        raise RuntimeError('Transformer tuple disagrees with registered shard blocks')
    for i, callback in ((i, routes[('double_block', i)]) for i in range(48)):
        route = callback.original_route if type(callback) is CompiledBlockRoute else callback
        expected_device = patcher.load_device if i < len(primary) else shards[0].load_device
        if type(route) is not _BlockRoute or (route.device, route.primary, route.last) != (
                expected_device, patcher.load_device, i == 47):
            raise RuntimeError('Block route disagrees with registered shard placement')
    if index < len(primary):
        return diffusion, index, diffusion, '_ltx_primary_blocks', primary, index
    return diffusion, index, secondary_owner, 'blocks', secondary, index - len(primary)




class _CompilePreRun:
    """Validate the actual executing patcher without owning a patcher reference."""
    def __init__(self, patcher, route, index):
        if not hasattr(patcher.model, 'current_patcher'):
            raise RuntimeError('Native BaseModel.current_patcher is required')
        self.model = patcher.model
        self.diffusion = patcher.model.diffusion_model
        self.secondary_owner = patcher.get_additional_models_with_key(KEY)[0].model
        self.route = route
        self.index = index
        self._last_pre_run = None

    def _validate(self, patcher):
        if (not torch.are_deterministic_algorithms_enabled()
                or torch.is_deterministic_algorithms_warn_only_enabled()):
            raise RuntimeError('Compiler lifecycle requires strict deterministic mode')
        if (patcher.model is not self.model
                or patcher.model.diffusion_model is not self.diffusion):
            raise RuntimeError('Executing top-level diffusion owner changed')
        shards = patcher.get_additional_models_with_key(KEY)
        if len(shards) != 1 or shards[0].model is not self.secondary_owner:
            raise RuntimeError('Executing secondary shard owner changed')
        diffusion, routes = _routes(patcher)
        if routes[('double_block', self.index)] is not self.route:
            raise RuntimeError('Executing compiler callback was replaced')
        current = _registered_binding(patcher, diffusion, routes, self.index)
        if any(a is not b if isinstance(a, torch.nn.Module) else a != b
               for a, b in zip(current, self.route._binding)):
            raise RuntimeError('Executing compiler registration binding changed')
        self.route._validate(check_device=True)

    def __call__(self, patcher):
        self._last_pre_run = None
        # ModelPatcher.pre_run assigns current_patcher before invoking callbacks.
        if self.model.current_patcher is not patcher:
            raise RuntimeError('Lifecycle callback must run through native pre_run')
        self._validate(patcher)
        self._last_pre_run = weakref.ref(patcher)

    def validate_current_execution(self):
        patcher = self.model.current_patcher
        if (patcher is None or self._last_pre_run is None
                or self._last_pre_run() is not patcher):
            raise RuntimeError('Executing patcher has not passed native pre_run')
        # Also closes callback removal and late changes after pre_run. Routing
        # metadata remains unmodified; this is outside the compiled callable.
        self._validate(patcher)


def apply_block_compile(patcher, index=0):
    check_source()
    if not torch.are_deterministic_algorithms_enabled() or torch.is_deterministic_algorithms_warn_only_enabled():
        raise RuntimeError('Strict deterministic mode is required for the compiler screen')
    diffusion, routes = _routes(patcher)
    if type(index) is not int or not 0 <= index < 48:
        raise ValueError('Select one native block index from 0 through 47')
    if any(isinstance(route, CompiledBlockRoute) for route in routes.values()):
        raise RuntimeError('This bounded screen allows only one compiled block')
    block = diffusion.transformer_blocks[index]
    route = routes[('double_block', index)]
    candidate = patcher.clone()
    compiled = CompiledBlockRoute(block, route,
        binding=_registered_binding(patcher, diffusion, routes, index))
    guard = _CompilePreRun(candidate, compiled, index)
    compiled._lifecycle = guard
    candidate.set_model_patch_replace(compiled, 'dit', 'double_block', index)
    # First under the native ordered callback traversal; original placement
    # validation follows. Loading/injection occurs earlier in native sampling.
    candidate.callbacks = {CallbacksMP.ON_PRE_RUN: {LIFECYCLE_KEY: [guard], KEY: [_verify_placement]}}
    return candidate


def remove_block_compile(patcher):
    diffusion, routes = _routes(patcher)
    selected = [(key, route) for key, route in routes.items() if isinstance(route, CompiledBlockRoute)]
    if len(selected) != 1:
        raise RuntimeError('Expected exactly one compiler callback to restore')
    key, route = selected[0]
    route._validate(check_device=False)
    if key[0] != 'double_block' or diffusion.transformer_blocks[key[1]] is not route.block:
        raise RuntimeError('Compiled callback no longer names its original registered block')
    restored = patcher.clone()
    restored.set_model_patch_replace(route.original_route, 'dit', 'double_block', key[1])
    restored.callbacks = {CallbacksMP.ON_PRE_RUN: {KEY: [_verify_placement]}}
    return restored


class LTXCompileOneBlock:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'block_index': ('INT', {'default': 0, 'min': 0, 'max': 47})}}

    RETURN_TYPES = ('MODEL',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, model, block_index):
        return (apply_block_compile(model, block_index),)


NODE_CLASS_MAPPINGS = {'LTXCompileOneBlock': LTXCompileOneBlock}
