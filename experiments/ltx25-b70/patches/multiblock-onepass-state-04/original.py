"""Inactive multi-block Inductor candidate; preserve native registration/routing."""
import hashlib
import weakref
from itertools import count
from pathlib import Path
from types import FunctionType, MappingProxyType

import torch
import ltx_native_activations_backend as activation_backend
from ltx_native_activations_backend import make_backend
from comfy.ldm.lightricks import av_model
from ltx_layer_shard import (LTXLayerShardedPatcher, _BlockRoute, _Shard,
                             _forward_transfers, _verify_placement, KEY)
from comfy.patcher_extension import CallbacksMP, WrappersMP

AV_SOURCE_SHA256 = '6582ee5c9fe1119b0dfa85a7c5e4f6d94a899f3b551b1886546fd787c3799e7d'
LIFECYCLE_KEY = 'ltx_multiblock_compile_lifecycle'
ACTIVATION_BACKEND_SHA256 = '62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a'
OPTIONS = {'compile_threads': 1, 'emulate_precision_casts': True,
           'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
           'max_autotune': False, 'max_autotune_gemm': False}
_ENTRY_IDS = count()


def check_source():
    if hashlib.sha256(Path(av_model.__file__).read_bytes()).hexdigest() != AV_SOURCE_SHA256:
        raise RuntimeError('Native LTXAV call mapping changed; re-audit compiler adapter')
    if hashlib.sha256(Path(activation_backend.__file__).read_bytes()).hexdigest() != ACTIVATION_BACKEND_SHA256:
        raise RuntimeError('Native activation backend source changed')


class CompiledBlockRoute:
    """Clone-local callback; its module remains owned by the original shard."""
    def __init__(self, block, original_route, *, receipt_directory, compiler=torch.compile, binding=None):
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
        self.index = binding[1] if binding is not None else None
        self.receipt_directory = Path(receipt_directory)
        self._lifecycle = None
        self._validate(check_device=False)
        # Each route owns an entry code object and its Dynamo cache. The shared
        # native forward is inlined; its registration and Python code stay intact.
        def invoke(x, **kwargs):
            return block(x, **kwargs)
        entry_name = f'ltx_private_block_{next(_ENTRY_IDS)}'
        self._compile_target = FunctionType(
            invoke.__code__.replace(co_name=entry_name, co_qualname=entry_name),
            invoke.__globals__, entry_name,
            invoke.__defaults__, invoke.__closure__)
        # Neither private callable is assigned to a module registration/forward.
        self.compiled = compiler(self._compile_target, backend=make_backend(
            OPTIONS, self.receipt_directory,
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
            self._lifecycle.validate_current_execution(self)
            return True
        return False

    def _call_native(self, args):
        if not self._validate_execution():
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
        if not self._validate_execution():
            self._validate(check_device=False)
        return self.original_route(args, {**extra, 'original_block': self._call_native})


def _indices(values):
    """Normalize a bounded iterable of distinct native zero-based indices."""
    try:
        iterator = iter(values)
    except TypeError as error:
        raise ValueError('Select 1..48 distinct native block indices from 0 through 47') from error
    selected = set()
    for value in iterator:
        if type(value) is not int or not 0 <= value < 48 or value in selected:
            raise ValueError('Block indices must be distinct exact integers from 0 through 47')
        selected.add(value)
        if len(selected) > 48:
            raise ValueError('Select at most 48 native blocks')
    if not selected:
        raise ValueError('Select at least one native block')
    return tuple(sorted(selected))


def _routes(patcher, *, binding_indices=None):
    """Validate all48 registrations once; optionally return selected bindings."""
    requested = None if binding_indices is None else _indices(binding_indices)
    if type(patcher) is not LTXLayerShardedPatcher or patcher.is_dynamic():
        raise TypeError('Multi-block compilation requires the native static layer-sharded patcher')
    if (patcher.patches or patcher.hook_patches or patcher.forced_hooks or patcher.object_patches
            or patcher.weight_wrapper_patches or patcher.injections):
        raise RuntimeError('Unsupported model patches/hooks for the compiler screen')
    diffusion = patcher.model.diffusion_model
    if not isinstance(diffusion, av_model.LTXAVModel) or len(diffusion.transformer_blocks) != 48:
        raise TypeError('Expected native 48-block LTXAV model')
    registry = patcher.model_options.get('transformer_options', {}).get('patches_replace', {}).get('dit', {})
    if set(registry) != {('double_block', i) for i in range(48)}:
        raise RuntimeError('Unexpected block route registry')
    selected = {i: registry[('double_block', i)] for i in range(48)
                if type(registry[('double_block', i)]) is CompiledBlockRoute}
    expected_callbacks = {CallbacksMP.ON_PRE_RUN: {KEY: [_verify_placement]}}
    expected_order = [_verify_placement]
    if selected:
        guard = next(iter(selected.values()))._lifecycle
        if type(guard) is not _CompilePreRun:
            raise RuntimeError('Expected one aggregate compiler lifecycle gate')
        guard._validate_selection()
        if tuple(selected.items()) != guard._route_items or any(
                route._lifecycle is not guard for route in selected.values()):
            raise RuntimeError('Compiler lifecycle route selection changed')
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
    bindings = _registered_bindings(patcher, diffusion, registry, (0,) if requested is None else requested)
    if requested is not None:
        return diffusion, registry, bindings
    return diffusion, registry


def _registered_bindings(patcher, diffusion, routes, indices):
    """One full registry/placement walk, then cheap selected owner bindings."""
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
        if type(callback) is CompiledBlockRoute and callback.block is not diffusion.transformer_blocks[i]:
            raise RuntimeError('Compiled route names a different registered block')
    bindings = {}
    for index in indices:
        if index < len(primary):
            bindings[index] = diffusion, index, diffusion, '_ltx_primary_blocks', primary, index
        else:
            bindings[index] = diffusion, index, secondary_owner, 'blocks', secondary, index - len(primary)
    return bindings


class _CompilePreRun:
    """One aggregate guard; model ownership is retained, executing patcher is weak."""
    def __init__(self, patcher, routes):
        if not hasattr(patcher.model, 'current_patcher'):
            raise RuntimeError('Native BaseModel.current_patcher is required')
        self.indices = _indices(routes)
        self._route_items = tuple((index, routes[index]) for index in self.indices)
        self.routes = MappingProxyType(dict(self._route_items))
        self.model = patcher.model
        self.diffusion = patcher.model.diffusion_model
        self.secondary_owner = patcher.get_additional_models_with_key(KEY)[0].model
        self._last_pre_run = None

    def _validate_selection(self):
        if (self.indices != tuple(index for index, route in self._route_items)
                or tuple(self.routes.items()) != self._route_items
                or any(type(route) is not CompiledBlockRoute or route.index != index
                       for index, route in self._route_items)):
            raise RuntimeError('Aggregate compiler selection changed')

    def _validate(self, patcher, route=None):
        if (not torch.are_deterministic_algorithms_enabled()
                or torch.is_deterministic_algorithms_warn_only_enabled()):
            raise RuntimeError('Compiler lifecycle requires strict deterministic mode')
        if (patcher.model is not self.model or patcher.model.diffusion_model is not self.diffusion):
            raise RuntimeError('Executing top-level diffusion owner changed')
        shards = patcher.get_additional_models_with_key(KEY)
        if len(shards) != 1 or shards[0].model is not self.secondary_owner:
            raise RuntimeError('Executing secondary shard owner changed')
        self._validate_selection()
        if route is not None and (type(route) is not CompiledBlockRoute
                                  or self.routes.get(route.index) is not route):
            raise RuntimeError('Executing route is outside the selected compiler set')
        diffusion, registry, bindings = _routes(patcher, binding_indices=self.indices)
        for index, selected in self._route_items:
            if registry[('double_block', index)] is not selected:
                raise RuntimeError('Executing compiler callback was replaced')
            current = bindings[index]
            if not isinstance(selected._binding, tuple) or len(selected._binding) != len(current):
                raise RuntimeError('Executing compiler registration binding changed')
            if any(a is not b if isinstance(a, torch.nn.Module) else a != b
                   for a, b in zip(current, selected._binding)):
                raise RuntimeError('Executing compiler registration binding changed')
        # Pre-run checks every selected block. Each later invocation scans only
        # its current block's parameters/buffers/hooks, plus the full registry.
        active = self.routes.values() if route is None else (route,)
        for selected in active:
            selected._validate(check_device=True)

    def __call__(self, patcher):
        self._last_pre_run = None
        if self.model.current_patcher is not patcher:
            raise RuntimeError('Lifecycle callback must run through native pre_run')
        self._validate(patcher)
        self._last_pre_run = weakref.ref(patcher)

    def validate_current_execution(self, route):
        patcher = self.model.current_patcher
        if (patcher is None or self._last_pre_run is None or self._last_pre_run() is not patcher):
            raise RuntimeError('Executing patcher has not passed native pre_run')
        # Callback removal and late registry changes remain checked at each
        # existing route-entry/native-call boundary; no per-request hoisting.
        self._validate(patcher, route)


def apply_blocks_compile(patcher, indices, *, receipt_root, compiler=torch.compile):
    check_source()
    indices = _indices(indices)
    if (not torch.are_deterministic_algorithms_enabled()
            or torch.is_deterministic_algorithms_warn_only_enabled()):
        raise RuntimeError('Strict deterministic mode is required for the compiler screen')
    diffusion, routes, bindings = _routes(patcher, binding_indices=indices)
    if any(isinstance(route, CompiledBlockRoute) for route in routes.values()):
        raise RuntimeError('Compilation is already applied; selections cannot be stacked')
    receipt_root = Path(receipt_root)
    if receipt_root.exists() and not receipt_root.is_dir():
        raise RuntimeError('Compiler receipt root is not a directory')
    if any(path.is_symlink() for path in (receipt_root, *receipt_root.parents)):
        raise RuntimeError('Compiler receipt root cannot contain symlinks')
    directories = {index: receipt_root / f'block-{index:02d}' for index in indices}
    if any(path.exists() or path.is_symlink() for path in directories.values()):
        raise RuntimeError('Compiler block receipt directory already exists; never overwrite')
    candidate = patcher.clone()
    selected = {}
    for index in indices:
        selected[index] = CompiledBlockRoute(diffusion.transformer_blocks[index], routes[('double_block', index)],
            receipt_directory=directories[index], compiler=compiler, binding=bindings[index])
    guard = _CompilePreRun(candidate, selected)
    for index, route in selected.items():
        route._lifecycle = guard
        candidate.set_model_patch_replace(route, 'dit', 'double_block', index)
    candidate.callbacks = {CallbacksMP.ON_PRE_RUN: {LIFECYCLE_KEY: [guard], KEY: [_verify_placement]}}
    return candidate


def remove_blocks_compile(patcher):
    diffusion, routes = _routes(patcher)
    selected = [(key, route) for key, route in routes.items() if type(route) is CompiledBlockRoute]
    if not selected:
        raise RuntimeError('Expected selected compiler callbacks to restore')
    for key, route in selected:
        route._validate(check_device=False)
        if key[0] != 'double_block' or diffusion.transformer_blocks[key[1]] is not route.block:
            raise RuntimeError('Compiled callback no longer names its original registered block')
    restored = patcher.clone()
    for key, route in selected:
        restored.set_model_patch_replace(route.original_route, 'dit', 'double_block', key[1])
    restored.callbacks = {CallbacksMP.ON_PRE_RUN: {KEY: [_verify_placement]}}
    return restored
