"""Experimental native LTXAV layer placement; no replacement model arithmetic.

Apply once to a fresh, exclusively owned CPU ModelPatcher before first use.
Registered ownership changes, so checkpoint saving, LoRA and replica creation
are deliberately unsupported. Normal ModelPatcher loading/offloading remains
responsible for each device. This is not a validated speed/quality result.
"""
from contextlib import nullcontext

import torch
from torch import nn

from comfy.model_patcher import ModelPatcher
from comfy.patcher_extension import CallbacksMP, WrappersMP
from comfy.ldm.lightricks.av_model import CompressedTimestep, LTXAVModel

KEY = "ltx_layer_shard"
CACHE_KEY = "_ltx_layer_shard_forward_transfers"
# Packet-declared transformer split (blocks 0..N-1 on the primary card, N..47
# on the secondary). 21/27 is the byte-balanced native split; packet 84 moves
# to 23/25, the time-balanced split for the two-clip sampler (xpu:0 carries
# the pre-glue glue work, so it should carry fewer blocks). Every node that
# hard-required 21 now requires this declared value instead.
DECLARED_SPLIT_INDEX = 23
# Packet 94: named multi-segment placements, selected per server (environment
# LTX_SAMPLER_PLACEMENT; default 'two-way' = the unchanged install() above with
# DECLARED_SPLIT_INDEX). Each entry is an ordered list of (device, first block,
# end block) covering 0..47 exactly once; the first segment is the primary
# card. Whole blocks only; no arithmetic changes, only where weights live.
PLACEMENTS = {
    'two-way': (('xpu:0', 0, 23), ('xpu:1', 23, 48)),
    'shard3-c': (('xpu:0', 0, 20), ('xpu:1', 20, 40), ('xpu:2', 40, 48)),
    'shard4-a': (('xpu:0', 0, 18), ('xpu:1', 18, 36), ('xpu:2', 36, 44), ('xpu:3', 44, 48)),
}
# Rough residency per block for planning: 0.720 GiB of bf16 weights (19.33 GB
# over 25 blocks on xpu:1) plus up to 0.25 GiB of graph statics and pool share
# for two sampler workers (90c: 24.24 GiB reserved vs 18.0 GiB of weights).
PLAN_GIB_PER_BLOCK = 0.97
MEMORY_FLOOR_GIB = 2.0


def segment_plan(segments, block_count=48, allow_same_device=False):
    """Validate a placement and return, per block, (device, primary, last)."""
    if not segments or not isinstance(segments, (tuple, list)):
        raise ValueError("A placement needs at least one segment")
    expected = 0
    devices = []
    for seg in segments:
        if len(seg) != 3:
            raise ValueError("Segments are (device, start, end)")
        device, start, end = seg
        if start != expected or not start < end:
            raise ValueError("Segments must be contiguous, ordered and non-empty")
        expected = end
        devices.append(str(device))
    if expected != block_count:
        raise ValueError("Segments must cover every block exactly once")
    if len(segments) < 2:
        raise ValueError("A placement needs at least two segments")
    if not allow_same_device and len(set(devices)) != len(devices):
        raise ValueError("Each segment needs its own device")
    primary = devices[0]
    plan = []
    for device, start, end in segments:
        for i in range(start, end):
            plan.append((str(device), primary, i == block_count - 1))
    return plan


def memory_plan(segments, free_gib, fixed_gib=None, per_block_gib=PLAN_GIB_PER_BLOCK,
                floor_gib=MEMORY_FLOOR_GIB):
    """Predicted free GiB per device after placing the blocks; raises below the floor.

    free_gib: {device: GiB free with everything else resident}; fixed_gib: extra
    per-device needs (e.g. activations). Blocks already counted in free_gib for
    the two-way layout must be removed by the caller."""
    out = {}
    for device, start, end in segments:
        left = free_gib[str(device)] - (end - start) * per_block_gib - (fixed_gib or {}).get(str(device), 0.0)
        out[str(device)] = round(left, 3)
    short = {d: v for d, v in out.items() if v < floor_gib}
    if short:
        raise RuntimeError("Placement leaves less than %.1f GiB free on %s" % (floor_gib, short))
    return out


def _tensors(module):
    return tuple(module.parameters()) + tuple(module.buffers())


def _bytes(module):
    return sum(t.numel() * t.element_size() for t in _tensors(module))


def _move(value, device, cache):
    """Keep dtype; retain source references until this forward returns."""
    if isinstance(value, torch.Tensor):
        if value.device == device:
            return value
        key = (id(value), device)
        if key not in cache:
            cache[key] = (value, value.to(device=device, non_blocking=False))
        return cache[key][1]
    if isinstance(value, CompressedTimestep):
        return CompressedTimestep(_move(value.data, device, cache),
                                  value.patches_per_frame, per_frame=True)
    if isinstance(value, tuple):
        return tuple(_move(v, device, cache) for v in value)
    if isinstance(value, list):
        return [_move(v, device, cache) for v in value]
    if isinstance(value, dict):
        return {k: (v if k == CACHE_KEY else _move(v, device, cache))
                for k, v in value.items()}
    return value


def _forward_transfers(executor, *args, **kwargs):
    # LTXBaseModel.forward supplies transformer_options at positional index 5.
    # The cache belongs solely to this invocation, never to a model or sampler.
    cache = {}
    args = list(args)
    if len(args) > 5:
        args[5] = {**args[5], CACHE_KEY: cache}
    else:
        kwargs["transformer_options"] = {
            **kwargs.get("transformer_options", {}), CACHE_KEY: cache}
    try:
        return executor(*args, **kwargs)
    finally:
        cache.clear()


class _BlockRoute:
    def __init__(self, device, primary, last):
        self.device = device
        self.primary = primary
        self.last = last

    def __call__(self, args, extra):
        cache = args["transformer_options"][CACHE_KEY]
        routed = {k: _move(v, self.device, {} if k == "img" else cache)
                  for k, v in args.items()}
        context = torch.xpu.device(self.device) if self.device.type == "xpu" else nullcontext()
        with context:
            result = extra["original_block"](routed)
        if self.last:
            result = {**result, "img": _move(result["img"], self.primary, {})}
        return result


class _Shard(nn.Module):
    def __init__(self, blocks, dtype):
        super().__init__()
        self.blocks = nn.ModuleList(blocks)
        self.dtype = dtype

    def get_dtype(self):
        return self.dtype


class LTXLayerShardedPatcher(ModelPatcher):
    """Placement policy owner; original model implementation stays unchanged."""

    @property
    def ltx_layer_shard_report(self):
        return dict(self.model.diffusion_model._ltx_layer_shard_identity)

    def deepclone_multigpu(self, *args, **kwargs):
        raise RuntimeError("Layer-sharded LTX does not support full-model replicas")

    def clone(self, disable_dynamic=False, model_override=None, force_deepcopy=False):
        if model_override is not None or force_deepcopy:
            raise RuntimeError("Layer-sharded LTX supports shared-weight clones only")
        return super().clone(disable_dynamic=disable_dynamic)

    def add_patches(self, *args, **kwargs):
        raise RuntimeError("Layer-sharded native LTX does not support weight patches")

    def model_state_dict(self, *args, **kwargs):
        raise RuntimeError("Layer-sharded LTX registration is not a checkpoint format")

    def model_state_dict_for_saving(self, *args, **kwargs):
        raise RuntimeError("Layer-sharded LTX registration is not a checkpoint format")

    def verify_placement(self):
        # Packet 94: one shard patcher per non-primary segment (exactly one for
        # the two-way placement, as before).
        shards = self.get_additional_models_with_key(KEY)
        if not shards:
            raise RuntimeError("LTX shard registration is missing")
        for patcher in (self, *shards):
            misplaced = [str(t.device) for t in _tensors(patcher.model)
                         if t.device != patcher.load_device]
            if misplaced:
                raise RuntimeError(f"LTX shard is not fully resident on {patcher.load_device}: {set(misplaced)}")
        if self.patches or self.hook_patches or self.forced_hooks:
            raise RuntimeError("Native LTX shard acquired unsupported weight/hooks patches")

    @classmethod
    def install(cls, patcher, primary, secondary, split_index=None):
        model = patcher.model
        diffusion = model.diffusion_model
        if getattr(diffusion, "_ltx_layer_shard_applied", False):
            raise RuntimeError("LTX layer sharding was already applied to this model")
        if type(patcher) is not ModelPatcher or patcher.is_dynamic():
            raise TypeError("LTX layer sharding requires the standard non-dynamic ModelPatcher")
        if patcher.loaded_size() or any(t.device.type != "cpu" for t in _tensors(model)):
            raise RuntimeError("Apply LTX layer sharding before first model placement")
        if (patcher.patches or patcher.object_patches or patcher.hook_patches
                or patcher.weight_wrapper_patches or patcher.forced_hooks
                or patcher.additional_models or patcher.backup
                or patcher.callbacks or patcher.wrappers or patcher.injections
                or patcher.model_options != {"transformer_options": {}}):
            raise RuntimeError("LTX layer sharding requires an unpatched native loader output")
        blocks = diffusion.transformer_blocks
        if not isinstance(blocks, nn.ModuleList) or len(blocks) < 2:
            raise TypeError("Expected the native LTXAV transformer ModuleList")

        before = {id(t): (t.dtype, tuple(t.shape)) for t in _tensors(model)}
        block_bytes = [_bytes(block) for block in blocks]
        total = _bytes(model)
        non_block = total - sum(block_bytes)
        if split_index is None:
            split_index = min(range(1, len(blocks)),
                              key=lambda n: abs(non_block + 2 * sum(block_bytes[:n]) - sum(block_bytes)))
        if not 0 < split_index < len(blocks):
            raise ValueError("split_index must leave at least one block on each device")
        original_blocks = blocks
        shard_module = _Shard(list(blocks)[split_index:], patcher.model_dtype())
        shard = ModelPatcher(shard_module, secondary, patcher.offload_device)
        old_class, old_size, old_device = type(patcher), patcher.size, patcher.load_device
        # No tensor/device mutation below. Roll back registration if setup fails.
        try:
            del diffusion.transformer_blocks
            object.__setattr__(diffusion, "transformer_blocks", tuple(original_blocks))
            diffusion.add_module("_ltx_primary_blocks", nn.ModuleList(list(original_blocks)[:split_index]))
            primary_tensors, secondary_tensors = _tensors(model), _tensors(shard_module)
            if {id(t) for t in primary_tensors} & {id(t) for t in secondary_tensors}:
                raise RuntimeError("LTX partitions contain shared tensor ownership")
            after = {id(t): (t.dtype, tuple(t.shape)) for t in primary_tensors + secondary_tensors}
            if before != after:
                raise RuntimeError("LTX partitioning changed tensor identity, dtype or shape")
            patcher.__class__ = cls
            patcher.size = 0
            patcher.load_device = primary
            patcher.set_additional_models(KEY, [shard])
            patcher.add_wrapper_with_key(WrappersMP.DIFFUSION_MODEL, KEY, _forward_transfers)
            for i in range(len(original_blocks)):
                device = primary if i < split_index else secondary
                patcher.set_model_patch_replace(_BlockRoute(device, primary, i == len(original_blocks) - 1),
                                                "dit", "double_block", i)
            patcher.add_callback_with_key(CallbacksMP.ON_PRE_RUN, KEY, _verify_placement)
            diffusion._ltx_layer_shard_applied = True
            diffusion._ltx_layer_shard_identity = {
                "split_index": split_index, "block_count": len(original_blocks),
                "primary": str(primary), "secondary": str(secondary),
                "primary_bytes": patcher.model_size(), "secondary_bytes": shard.model_size(),
                "original_bytes": total, "numerical_validation": "pending",
            }
        except Exception:
            if hasattr(diffusion, "_ltx_primary_blocks"):
                del diffusion._ltx_primary_blocks
            if not isinstance(diffusion.transformer_blocks, nn.ModuleList):
                del diffusion.transformer_blocks
                diffusion.add_module("transformer_blocks", original_blocks)
            patcher.__class__, patcher.size, patcher.load_device = old_class, old_size, old_device
            patcher.additional_models = {}
            patcher.model_options = {"transformer_options": {}}
            patcher.wrappers.pop(WrappersMP.DIFFUSION_MODEL, None)
            patcher.callbacks.pop(CallbacksMP.ON_PRE_RUN, None)
            for name in ("_ltx_layer_shard_applied", "_ltx_layer_shard_identity"):
                if hasattr(diffusion, name):
                    delattr(diffusion, name)
            raise
        return patcher


def _install_segments(cls, patcher, segments, allow_same_device=False):
    """Packet 94: install a multi-segment placement. Same ownership rules as
    install(); one shard ModelPatcher per non-primary segment, and per block the
    same _BlockRoute (its device, the primary, last-block move back)."""
    model = patcher.model
    diffusion = model.diffusion_model
    if getattr(diffusion, "_ltx_layer_shard_applied", False):
        raise RuntimeError("LTX layer sharding was already applied to this model")
    if type(patcher) is not ModelPatcher or patcher.is_dynamic():
        raise TypeError("LTX layer sharding requires the standard non-dynamic ModelPatcher")
    if patcher.loaded_size() or any(t.device.type != "cpu" for t in _tensors(model)):
        raise RuntimeError("Apply LTX layer sharding before first model placement")
    if (patcher.patches or patcher.object_patches or patcher.hook_patches
            or patcher.weight_wrapper_patches or patcher.forced_hooks
            or patcher.additional_models or patcher.backup
            or patcher.callbacks or patcher.wrappers or patcher.injections
            or patcher.model_options != {"transformer_options": {}}):
        raise RuntimeError("LTX layer sharding requires an unpatched native loader output")
    blocks = diffusion.transformer_blocks
    if not isinstance(blocks, nn.ModuleList) or len(blocks) < 2:
        raise TypeError("Expected the native LTXAV transformer ModuleList")
    plan = segment_plan(segments, len(blocks), allow_same_device)
    devices = [torch.device(seg[0]) for seg in segments]
    primary = devices[0]
    before = {id(t): (t.dtype, tuple(t.shape)) for t in _tensors(model)}
    total = _bytes(model)
    original_blocks = blocks
    shards = [ModelPatcher(_Shard(list(blocks)[start:end], patcher.model_dtype()), torch.device(device),
                           patcher.offload_device) for device, start, end in segments[1:]]
    old_class, old_size, old_device = type(patcher), patcher.size, patcher.load_device
    try:
        del diffusion.transformer_blocks
        object.__setattr__(diffusion, "transformer_blocks", tuple(original_blocks))
        diffusion.add_module("_ltx_primary_blocks", nn.ModuleList(list(original_blocks)[:segments[0][2]]))
        owned = [_tensors(model)] + [_tensors(s.model) for s in shards]
        ids = [id(t) for group in owned for t in group]
        if len(ids) != len(set(ids)):
            raise RuntimeError("LTX partitions contain shared tensor ownership")
        after = {id(t): (t.dtype, tuple(t.shape)) for group in owned for t in group}
        if before != after:
            raise RuntimeError("LTX partitioning changed tensor identity, dtype or shape")
        patcher.__class__ = cls
        patcher.size = 0
        patcher.load_device = primary
        patcher.set_additional_models(KEY, shards)
        patcher.add_wrapper_with_key(WrappersMP.DIFFUSION_MODEL, KEY, _forward_transfers)
        for i, (device, prim, last) in enumerate(plan):
            patcher.set_model_patch_replace(_BlockRoute(torch.device(device), torch.device(prim), last),
                                            "dit", "double_block", i)
        patcher.add_callback_with_key(CallbacksMP.ON_PRE_RUN, KEY, _verify_placement)
        diffusion._ltx_layer_shard_applied = True
        diffusion._ltx_layer_shard_identity = {
            "split_index": None, "segments": [[str(d), a, b] for d, a, b in segments],
            "block_count": len(original_blocks), "primary": str(primary),
            "devices": [str(d) for d in devices],
            "segment_bytes": [patcher.model_size()] + [s.model_size() for s in shards],
            "original_bytes": total, "numerical_validation": "pending",
        }
    except Exception:
        if hasattr(diffusion, "_ltx_primary_blocks"):
            del diffusion._ltx_primary_blocks
        if not isinstance(diffusion.transformer_blocks, nn.ModuleList):
            del diffusion.transformer_blocks
            diffusion.add_module("transformer_blocks", original_blocks)
        patcher.__class__, patcher.size, patcher.load_device = old_class, old_size, old_device
        patcher.additional_models = {}
        patcher.model_options = {"transformer_options": {}}
        patcher.wrappers.pop(WrappersMP.DIFFUSION_MODEL, None)
        patcher.callbacks.pop(CallbacksMP.ON_PRE_RUN, None)
        for name in ("_ltx_layer_shard_applied", "_ltx_layer_shard_identity"):
            if hasattr(diffusion, name):
                delattr(diffusion, name)
        raise
    return patcher


def _verify_placement(patcher):
    patcher.verify_placement()


def apply_layer_shard(model_patcher, secondary_device="xpu:1", primary_device="xpu:0", split_index=None):
    """Consume an exclusively owned fresh patcher and return its sharded form.

    No GPU allocation happens here. Normal sampling preparation loads both
    registered partitions; ON_PRE_RUN rejects any residual CPU offload.
    """
    primary, secondary = torch.device(primary_device), torch.device(secondary_device)
    if primary.type != "xpu" or secondary.type != "xpu" or primary == secondary:
        raise ValueError("Choose two distinct explicitly indexed XPU devices")
    if primary.index is None or secondary.index is None:
        raise ValueError("Explicit XPU device indices are required")
    if not isinstance(model_patcher.model.diffusion_model, LTXAVModel):
        raise TypeError("This placement experiment supports native LTXAV only")
    if model_patcher.model_dtype() != torch.bfloat16:
        raise TypeError("This placement experiment requires native BF16 weights")
    return LTXLayerShardedPatcher.install(model_patcher, primary, secondary, split_index)


def apply_layer_segments(model_patcher, placement):
    """Packet 94: consume a fresh patcher and install a named multi-segment placement."""
    if placement not in PLACEMENTS or placement == 'two-way':
        raise ValueError("Unknown multi-segment placement: %r" % (placement,))
    segments = PLACEMENTS[placement]
    for device, _start, _end in segments:
        d = torch.device(device)
        if d.type != "xpu" or d.index is None:
            raise ValueError("Explicit XPU device indices are required")
    if segments[0][0] != 'xpu:0':
        raise ValueError("The primary segment stays on xpu:0")
    if not isinstance(model_patcher.model.diffusion_model, LTXAVModel):
        raise TypeError("This placement experiment supports native LTXAV only")
    if model_patcher.model_dtype() != torch.bfloat16:
        raise TypeError("This placement experiment requires native BF16 weights")
    return _install_segments(LTXLayerShardedPatcher, model_patcher, segments)
