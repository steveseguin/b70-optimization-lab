"""Layer shard for the Gemma4 text encoder: layers [split, 48) live on a second card.

The text encoder is the stream's wall after packet 74: one 1.59 s fp32 encode
per clip on one card caps the pipeline at 15.7 fps. A second replica does not
fit beside the VAEs, so the 48 layers are split across xpu:2 (primary) and
xpu:3 (secondary), and two encode workers keep both cards busy, exactly as
the sampler does with the transformer's blocks.

Construction mirrors ltx_layer_shard for the transformer: the upper layers
move into a `_TextShard` module owned by its own ModelPatcher on the secondary
device, registered as an additional model of the CLIP patcher; the stack's
`layers` attribute becomes a tuple so the parent patcher neither counts nor
moves the sharded layers, while the forward loop (which only enumerates) is
untouched. The per-layer forward shadows in ltx_graph_text_encoder route the
hidden state to the secondary card and back through pinned host memory.
Numerically nothing changes: same weights, same kernels, same order.
"""
import torch
from torch import nn

from comfy.model_patcher import ModelPatcher

KEY = 'ltx_text_layer_shard'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def _tensors(module):
    return list(module.parameters()) + list(module.buffers())


class _TextShard(nn.Module):
    def __init__(self, layers, dtype):
        super().__init__()
        self.layers = nn.ModuleList(layers)
        self.dtype = dtype

    def get_dtype(self):
        return self.dtype


def install(clip, stack, layers, primary, secondary, split_index):
    """Move layers[split_index:] under a shard patcher on `secondary`. Call before
    the CLIP is first placed (its weights still on the CPU)."""
    patcher = clip.patcher
    require(not getattr(stack, '_ltx_text_shard_applied', False), 'Text encoder is already sharded')
    require(type(patcher) is ModelPatcher and not patcher.is_dynamic(),
            'Text shard requires the standard non-dynamic ModelPatcher')
    require(patcher.loaded_size() == 0 and all(t.device.type == 'cpu' for t in _tensors(patcher.model)),
            'Apply the text shard before the encoder is first placed')
    require(0 < split_index < len(layers), 'split_index must leave layers on both cards')
    require(isinstance(getattr(stack, 'layers', None), nn.ModuleList), 'Expected a ModuleList of Gemma layers')
    original = stack.layers
    before = {id(t): (t.dtype, tuple(t.shape)) for t in _tensors(patcher.model)}
    shard_module = _TextShard(list(layers)[split_index:], patcher.model_dtype())
    shard = ModelPatcher(shard_module, secondary, patcher.offload_device)
    old_size, old_device = patcher.size, patcher.load_device
    try:
        del stack.layers
        object.__setattr__(stack, 'layers', tuple(layers))
        stack.add_module('_ltx_primary_layers', nn.ModuleList(list(layers)[:split_index]))
        primary_tensors, secondary_tensors = _tensors(patcher.model), _tensors(shard_module)
        require(not ({id(t) for t in primary_tensors} & {id(t) for t in secondary_tensors}),
                'Text partitions share tensor ownership')
        after = {id(t): (t.dtype, tuple(t.shape)) for t in primary_tensors + secondary_tensors}
        require(before == after, 'Text partitioning changed tensor identity, dtype or shape')
        patcher.size = 0
        patcher.load_device = primary
        patcher.set_additional_models(KEY, [shard])
        stack._ltx_text_shard_applied = True
        stack._ltx_text_shard_identity = {'split_index': split_index, 'layer_count': len(layers),
                                          'primary': str(primary), 'secondary': str(secondary),
                                          'primary_bytes': patcher.model_size(),
                                          'secondary_bytes': shard.model_size()}
    except Exception:
        if hasattr(stack, '_ltx_primary_layers'):
            del stack._ltx_primary_layers
        if not isinstance(getattr(stack, 'layers', None), nn.ModuleList):
            try:
                del stack.layers
            except AttributeError:
                pass
            stack.add_module('layers', original)
        patcher.size, patcher.load_device = old_size, old_device
        patcher.additional_models.pop(KEY, None)
        for name in ('_ltx_text_shard_applied', '_ltx_text_shard_identity'):
            if hasattr(stack, name):
                delattr(stack, name)
        raise
    return shard


def verify_placement(clip, stack):
    """Every primary tensor on the primary card, every shard tensor on the secondary."""
    patcher = clip.patcher
    shard, = patcher.get_additional_models_with_key(KEY)
    for p in (patcher, shard):
        misplaced = {str(t.device) for t in _tensors(p.model) if t.device != p.load_device}
        require(not misplaced, f'Text shard is not fully resident on {p.load_device}: {sorted(misplaced)}')
    return stack._ltx_text_shard_identity
