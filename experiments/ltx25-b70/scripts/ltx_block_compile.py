"""Inactive one-block Inductor experiment; preserve native registration/routing."""
import hashlib
from pathlib import Path

import torch
from comfy.ldm.lightricks import av_model
from ltx_layer_shard import LTXLayerShardedPatcher, _BlockRoute

AV_SOURCE_SHA256 = '6582ee5c9fe1119b0dfa85a7c5e4f6d94a899f3b551b1886546fd787c3799e7d'
OPTIONS = {'compile_threads': 1, 'emulate_precision_casts': True,
           'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
           'max_autotune': False, 'max_autotune_gemm': False}


def check_source():
    if hashlib.sha256(Path(av_model.__file__).read_bytes()).hexdigest() != AV_SOURCE_SHA256:
        raise RuntimeError('Native LTXAV call mapping changed; re-audit compiler adapter')


class CompiledBlockRoute:
    """Clone-local callback; its module remains owned by the original shard."""
    def __init__(self, block, original_route, *, compiler=torch.compile):
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
        # This callable is never assigned to an nn.Module registration or forward.
        self.compiled = compiler(block, backend='inductor', fullgraph=True, dynamic=False,
                                 options=dict(OPTIONS))

    def _call_native(self, args):
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
        return self.original_route(args, {**extra, 'original_block': self._call_native})


def _routes(patcher):
    if type(patcher) is not LTXLayerShardedPatcher or patcher.is_dynamic():
        raise TypeError('One-block compilation requires the native static layer-sharded patcher')
    if patcher.patches or patcher.hook_patches or patcher.forced_hooks or patcher.object_patches:
        raise RuntimeError('Unsupported model patches/hooks for the compiler screen')
    diffusion = patcher.model.diffusion_model
    if not isinstance(diffusion, av_model.LTXAVModel) or len(diffusion.transformer_blocks) != 48:
        raise TypeError('Expected native 48-block LTXAV model')
    return diffusion, patcher.model_options['transformer_options']['patches_replace']['dit']


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
    candidate.set_model_patch_replace(CompiledBlockRoute(block, route), 'dit', 'double_block', index)
    return candidate


def remove_block_compile(patcher):
    diffusion, routes = _routes(patcher)
    selected = [(key, route) for key, route in routes.items() if isinstance(route, CompiledBlockRoute)]
    if len(selected) != 1:
        raise RuntimeError('Expected exactly one compiler callback to restore')
    key, route = selected[0]
    if key[0] != 'double_block' or diffusion.transformer_blocks[key[1]] is not route.block:
        raise RuntimeError('Compiled callback no longer names its original registered block')
    restored = patcher.clone()
    restored.set_model_patch_replace(route.original_route, 'dit', 'double_block', key[1])
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
