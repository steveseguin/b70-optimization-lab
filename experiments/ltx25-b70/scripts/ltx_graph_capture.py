"""Per-block XPU graph capture for the native layer-sharded LTXAV transformer.

The native block code, its registration and the shard's routing are unchanged.
Each route keeps delegating to the original `_BlockRoute`, which still owns
device transfers, the device context and the last-block return. Only the
`original_block` callable is replaced: instead of re-issuing every operation
from Python on each of the 48 blocks x 11 steps, the first call for a given
argument signature records the block's work into a `torch.xpu.XPUGraph`, and
later calls copy inputs into that graph's static buffers and replay it.

Replay executes the recorded command list: the same kernels, in the same order,
over the same memory. It is bit-exact by construction, and an explicit
capture-time proof (replay vs a fresh eager execution of the same block on the
same inputs, compared as raw bits) is required before any graph is used.

This module allocates no model state and moves no weights.
"""
import copy
import hashlib
import time
import types as _types
import json
import weakref
from pathlib import Path

import torch

from comfy.ldm.lightricks import av_model
from comfy.patcher_extension import CallbacksMP, WrappersMP
from ltx_layer_shard import (CACHE_KEY, KEY, LTXLayerShardedPatcher, _BlockRoute,
                             _forward_transfers, _verify_placement)

AV_SOURCE_SHA256 = '6582ee5c9fe1119b0dfa85a7c5e4f6d94a899f3b551b1886546fd787c3799e7d'
SHARD_SOURCE_SHA256 = '0c836c2c19ef678360c4e5dddb09173d60e0fd011e44430370485abd63336d3b'
WARMUP_ITERATIONS = 3
# Two shapes per block (the 128x128 and 256x256 sampler stages) are expected.
# Anything more means the signature is tracking something that is not a real
# input, and unbounded capture exhausts device memory and evicts the model.
MAX_SIGNATURES_PER_BLOCK = 4
# Exact keyword translation from the pinned LTXAVModel.block_wrap.
KEYWORDS = ('v_context', 'a_context', 'attention_mask', 'v_timestep', 'a_timestep', 'v_pe', 'a_pe',
            'v_cross_pe', 'a_cross_pe', 'v_cross_scale_shift_timestep', 'a_cross_scale_shift_timestep',
            'v_cross_gate_timestep', 'a_cross_gate_timestep', 'self_attention_mask',
            'v_prompt_timestep', 'a_prompt_timestep')
SCALARS = (bool, int, float, str, bytes, type(None), torch.dtype, torch.device, torch.Size)
# `transformer_options` is ComfyUI's options bag, not a numerical argument. At
# runtime it also carries the sampler's infrastructure: the block route registry,
# ON_PRE_RUN callbacks and DIFFUSION_MODEL wrappers, all of which are Python
# callables and modules. Those are passed through untouched and pinned by
# identity, while any tensor the bag carries is still mirrored strictly.
OPTION_INFRASTRUCTURE = ('patches_replace', 'callbacks', 'wrappers', 'patches')
# Functions, methods, modules and classes all carry a __dict__, so the generic
# attribute walk would accept them while missing tensors held in a closure or on
# a class. Anything callable is refused instead.
OPAQUE = (_types.FunctionType, _types.BuiltinFunctionType, _types.MethodType,
          _types.ModuleType, _types.LambdaType, type)


def attribute_names(value):
    """Attribute names of a plain instance, covering __slots__ and __dict__.

    The native LTXAV arguments CompressedTimestep and GuideAttentionMask both
    declare __slots__ and therefore have no __dict__ at all, so a __dict__-only
    walk would refuse them (or, worse, see them as empty).
    """
    names = []
    for klass in type(value).__mro__:
        slots = getattr(klass, '__slots__', ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots or ():
            # __weakref__ and __dict__ appear in __slots__ but are not writable
            # data attributes (uuid.UUID is one such argument seen at runtime).
            if name.startswith('__') and name.endswith('__'):
                continue
            if name not in names and hasattr(value, name):
                names.append(name)
    names.extend(k for k in getattr(value, '__dict__', {}) if k not in names)
    return sorted(names)


def _has_attributes(value):
    return hasattr(value, '__dict__') or any(
        getattr(klass, '__slots__', None) for klass in type(value).__mro__)


def _is_plain_instance(value):
    return (_has_attributes(value) and not isinstance(value, OPAQUE)
            and not callable(value) and not isinstance(value, torch.nn.Module))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_source():
    import ltx_layer_shard
    if hashlib.sha256(Path(av_model.__file__).read_bytes()).hexdigest() != AV_SOURCE_SHA256:
        raise RuntimeError('Native LTXAV call mapping changed; re-audit the graph adapter')
    if hashlib.sha256(Path(ltx_layer_shard.__file__).read_bytes()).hexdigest() != SHARD_SOURCE_SHA256:
        raise RuntimeError('Native shard routing changed; re-audit the graph adapter')


# --- generic structure walk -------------------------------------------------
# Every tensor an argument can reach must be mirrored into a static buffer. A
# tensor missed here would be baked into the graph as a constant and silently
# stop tracking its source, so the walk refuses any container it cannot explain.

def walk(value, tensors, path='arg', opaque='refuse'):
    """Append every reachable tensor to `tensors`; refuse unexplained objects.

    `opaque='skip'` is used only for the non-infrastructure part of the options
    bag, where a stray callable carries no numerical input. `mirror` applies the
    identical rule, so the two always produce the same tensors in the same order.
    """
    if isinstance(value, torch.Tensor):
        tensors.append(value)
    elif isinstance(value, SCALARS):
        pass
    elif isinstance(value, (tuple, list)):
        for i, child in enumerate(value):
            walk(child, tensors, f'{path}[{i}]', opaque)
    elif isinstance(value, dict):
        for k in sorted(value, key=repr):
            walk(value[k], tensors, f'{path}[{k!r}]', opaque)
    elif _is_plain_instance(value):
        for k in attribute_names(value):
            walk(getattr(value, k), tensors, f'{path}.{k}', opaque)
    elif opaque == 'skip':
        pass
    else:
        raise RuntimeError(f'Graph capture cannot mirror {type(value).__module__}.'
                           f'{type(value).__name__} at {path}')


def mirror(value, make, opaque='refuse'):
    """Rebuild `value` with every tensor replaced by `make(tensor)`."""
    if isinstance(value, torch.Tensor):
        return make(value)
    if isinstance(value, SCALARS):
        return value
    if isinstance(value, tuple):
        return tuple(mirror(v, make, opaque) for v in value)
    if isinstance(value, list):
        return [mirror(v, make, opaque) for v in value]
    if isinstance(value, dict):
        return {k: mirror(v, make, opaque) for k, v in value.items()}
    if _is_plain_instance(value):
        # Only objects that actually hold a tensor are rebuilt. Reconstructing
        # arbitrary immutable values (uuid.UUID and friends) is both pointless
        # and fragile, and leaving them alone keeps walk() and mirror() aligned.
        if not contains_tensor(value):
            return value
        clone = copy.copy(value)
        for k in attribute_names(value):
            object.__setattr__(clone, k, mirror(getattr(value, k), make, opaque))
        return clone
    if opaque == 'skip':
        return value
    raise RuntimeError('Graph capture cannot mirror ' + type(value).__module__ + '.'
                       + type(value).__name__)


def describe(value, path='arg'):
    """Signature that must match for a captured graph to remain valid."""
    if isinstance(value, torch.Tensor):
        return ('T', tuple(value.shape), str(value.dtype), str(value.device),
                tuple(value.stride()), bool(value.is_contiguous()), bool(value.requires_grad))
    if isinstance(value, (bool, int, float, str, bytes, type(None))):
        return ('S', repr(value))
    if isinstance(value, (torch.dtype, torch.device, torch.Size)):
        return ('S', str(value))
    if isinstance(value, tuple):
        return ('tuple', tuple(describe(v, f'{path}[{i}]') for i, v in enumerate(value)))
    if isinstance(value, list):
        return ('list', tuple(describe(v, f'{path}[{i}]') for i, v in enumerate(value)))
    if isinstance(value, dict):
        return ('dict', tuple((repr(k), describe(value[k], f'{path}[{k!r}]'))
                              for k in sorted(value, key=repr)))
    if _is_plain_instance(value):
        return (type(value).__module__ + '.' + type(value).__name__,
                tuple((k, describe(getattr(value, k), f'{path}.{k}')) for k in attribute_names(value)))
    raise RuntimeError(f'Graph capture cannot describe {type(value).__module__}.'
                       f'{type(value).__name__} at {path}')


def contains_tensor(value):
    probe = []
    walk(value, probe, 'probe', 'skip')
    return bool(probe)


def describe_infrastructure(value, path='infrastructure'):
    """Identity pin for the sampler's own machinery inside the options bag.

    Containers are recursed; everything else is pinned by module, qualified name
    and object identity. Attributes are deliberately NOT followed: the route
    registry reaches the model's parameters and each route's own captured static
    buffers, so recursing would be both enormous and self-referential. These
    objects are owned by the patcher for the life of the process, so a changed
    identity means the sampler's infrastructure changed and every captured graph
    must be refused.
    """
    if isinstance(value, (bool, int, float, str, bytes, type(None))):
        return ('S', repr(value))
    if isinstance(value, (torch.dtype, torch.device, torch.Size)):
        return ('S', str(value))
    if isinstance(value, tuple):
        return ('tuple', tuple(describe_infrastructure(v, f'{path}[{i}]') for i, v in enumerate(value)))
    if isinstance(value, list):
        return ('list', tuple(describe_infrastructure(v, f'{path}[{i}]') for i, v in enumerate(value)))
    if isinstance(value, dict):
        return ('dict', tuple((repr(k), describe_infrastructure(value[k], f'{path}[{k!r}]'))
                              for k in sorted(value, key=repr)))
    return ('identity', getattr(value, '__module__', type(value).__module__),
            getattr(value, '__qualname__', type(value).__qualname__), id(value))


def describe_option_data(value, path='options'):
    """Signature for the numerical part of the options bag.

    Tensors and scalars are described exactly, because the block reads flags such
    as run_vx/run_ax from here and a captured graph bakes those decisions in.
    An object that holds no tensor is described by type only: ComfyUI puts
    per-request identity tokens (uuid.UUID) in this bag, and including their
    values would invalidate every captured graph on every request while changing
    nothing the block computes.
    """
    if isinstance(value, torch.Tensor):
        return describe(value, path)
    if isinstance(value, (bool, int, float, str, bytes, type(None))):
        return ('S', repr(value))
    if isinstance(value, (torch.dtype, torch.device, torch.Size)):
        return ('S', str(value))
    if isinstance(value, tuple):
        return ('tuple', tuple(describe_option_data(v, f'{path}[{i}]') for i, v in enumerate(value)))
    if isinstance(value, list):
        return ('list', tuple(describe_option_data(v, f'{path}[{i}]') for i, v in enumerate(value)))
    if isinstance(value, dict):
        return ('dict', tuple((repr(k), describe_option_data(value[k], f'{path}[{k!r}]'))
                              for k in sorted(value, key=repr)))
    if _is_plain_instance(value) and contains_tensor(value):
        return (type(value).__module__ + '.' + type(value).__name__,
                tuple((k, describe_option_data(getattr(value, k), f'{path}.{k}'))
                      for k in attribute_names(value)))
    return ('valueless', getattr(value, '__module__', type(value).__module__),
            getattr(value, '__qualname__', type(value).__qualname__))


def option_census(options):
    """What the options bag actually contained, for the request receipt."""
    rows = {}
    for key in sorted(options, key=repr):
        value = options[key]
        row = {'type': type(value).__module__ + '.' + type(value).__name__}
        if isinstance(value, torch.Tensor):
            row.update(shape=list(value.shape), dtype=str(value.dtype), device=str(value.device))
        elif isinstance(value, dict):
            row['keys'] = [repr(k) for k in sorted(value, key=repr)]
        elif isinstance(value, (bool, int, float, str, type(None))):
            row['value'] = repr(value)[:120]
        elif isinstance(value, (tuple, list)):
            row['length'] = len(value)
        rows[repr(key)] = row
    return rows


def split_options(options):
    """Separate the numerical part of the options bag from its infrastructure.

    The shard's own per-forward transfer cache (CACHE_KEY) is passed through but
    deliberately excluded from the signature. It is scratch owned by the routing
    wrapper, keyed by `(id(tensor), device)`, so on the secondary device -- where
    `_move` actually copies -- its contents change every single forward. Signing
    it made every block past the split re-capture on every step: 339 graphs
    instead of 96, which exhausted device memory and evicted the shard to CPU.
    """
    infra, data = {}, {}
    for key, value in options.items():
        if key == CACHE_KEY or key in OPTION_INFRASTRUCTURE:
            infra[key] = value
        else:
            data[key] = value
    return infra, data


def signed_infrastructure(infra):
    return {k: v for k, v in infra.items() if k != CACHE_KEY}


def static_like(tensor):
    """An owned buffer with the same layout, outside any graph memory pool.

    The layout is reproduced exactly rather than normalized to contiguous: a
    different stride can select a different kernel and so change output bits.
    A tensor whose elements alias each other (an expanded view) cannot be a
    copy target, so it is refused rather than silently reshaped.
    """
    require(not tensor.requires_grad, 'Graph capture requires inference tensors')
    shape, strides = tuple(tensor.shape), tuple(tensor.stride())
    broadcast = [size > 1 and stride == 0 for size, stride in zip(shape, strides)]
    if not any(broadcast):
        buffer = torch.empty_strided(shape, strides, dtype=tensor.dtype,
                                     device=tensor.device, requires_grad=False)
        buffer.copy_(tensor)
        return buffer
    # An expanded view aliases one element across a dimension, so it cannot be a
    # copy target. Own the unique elements, then re-expose exactly the original
    # shape and strides so the captured kernels see the identical layout.
    core_shape = tuple(1 if b else size for size, b in zip(shape, broadcast))
    owned = torch.empty_strided(core_shape, strides, dtype=tensor.dtype,
                                device=tensor.device, requires_grad=False)
    owned.copy_(tensor.as_strided(core_shape, strides, tensor.storage_offset()))
    view = owned.as_strided(shape, strides)
    view._graph_fill_target = owned
    view._graph_core_shape = core_shape
    return view


def fill_static(buffer, value):
    """Copy `value` into `buffer`, honouring an expanded buffer's owned core."""
    target = getattr(buffer, '_graph_fill_target', None)
    if target is None:
        buffer.copy_(value)
        return
    core = getattr(buffer, '_graph_core_shape')
    target.copy_(value.as_strided(core, value.stride(), value.storage_offset()))


class Slot:
    """Static buffers shared by every block on one device for one argument shape.

    All 48 blocks in a forward receive the *same* context, positional-embedding
    and timestep tensors, and each block mutates its video/audio activations in
    place and returns them. So one buffer set per device is enough: the first
    block on a device fills it, the rest see their inputs are already the very
    buffers they would copy into, and the captured graphs chain through shared
    memory with no copy between blocks at all.
    """

    def __init__(self, static_img, static_kw, flat):
        self.img = static_img
        self.kw = static_kw
        self.flat = flat
        self.sources = [None] * len(flat)


class DeviceGroup:
    """Per-device shared state: buffers, and a cached argument signature.

    Describing eighteen arguments per block per step was itself measurable, and
    the description is identical for every block on a device within one forward.
    It is computed once per forward and reused, keyed on the identity of the
    incoming objects (strong references are held so an id cannot be recycled).
    """

    def __init__(self, device):
        self.device = device
        self.slots = {}
        self._ids = None
        self._refs = None
        self._key = None
        self.fresh_forward = False

    def key_for(self, routed, options):
        vx, ax = routed['img']
        values = [vx, ax] + [routed.get(name) for name in KEYWORDS] + [options]
        ids = tuple(id(v) for v in values)
        if ids == self._ids:
            self.fresh_forward = False
            return self._key
        infra, data = split_options(options)
        key = (describe(routed['img'], 'img'),
               tuple(describe(routed.get(name), name) for name in KEYWORDS),
               describe_option_data(data, 'transformer_options'),
               describe_infrastructure(signed_infrastructure(infra),
                                       'transformer_options.infrastructure'))
        self._ids, self._refs, self._key = ids, values, key
        self.fresh_forward = True
        return key

    def slot_for(self, key, routed, options):
        slot = self.slots.get(key)
        if slot is not None:
            return slot
        require(len(self.slots) < MAX_SIGNATURES_PER_BLOCK,
                f'Device {self.device} reached {len(self.slots)} distinct argument shapes; '
                'the signature is tracking something that is not a real input')
        infra, data = split_options(options)
        expected = []
        for name in ('img',) + KEYWORDS:
            walk(routed.get(name), expected, name)
        walk(data, expected, 'transformer_options', 'skip')
        static_img = mirror(routed['img'], static_like)
        static_kw = {name: mirror(routed.get(name), static_like) for name in KEYWORDS}
        static_data = mirror(data, static_like, 'skip')
        static_kw['transformer_options'] = {**static_data, **infra}
        flat = []
        walk(static_img, flat, 'img')
        for name in KEYWORDS:
            walk(static_kw[name], flat, name)
        walk(static_data, flat, 'transformer_options', 'skip')
        require(len(flat) == len(expected), 'Static mirror lost or gained a tensor')
        slot = Slot(static_img, static_kw, flat)
        self.slots[key] = slot
        return slot

    def fill(self, slot, routed, options):
        """Copy only what actually changed since this slot was last filled."""
        incoming = []
        walk(routed['img'], incoming, 'img')
        for name in KEYWORDS:
            walk(routed.get(name), incoming, name)
        walk(split_options(options)[1], incoming, 'transformer_options', 'skip')
        require(len(incoming) == len(slot.flat), 'Argument tensor count changed for a captured shape')
        copied = 0
        for i, (buffer, value) in enumerate(zip(slot.flat, incoming)):
            if buffer is value or slot.sources[i] is value:
                slot.sources[i] = value
                continue
            fill_static(buffer, value)
            slot.sources[i] = value
            copied += 1
        return copied


class Entry:
    """One captured graph. Its buffers belong to the device's shared slot."""

    def __init__(self, index, key, graph, out_vx, out_ax):
        self.index = index
        self.key = key
        self.graph = graph
        self.out_vx, self.out_ax = out_vx, out_ax
        self.replays = 0


class GraphBlockRoute:
    """Replaces only the block callable; the original route is still in charge."""

    def __init__(self, block, original_route, index, report, group):
        check_source()
        require(type(block) is av_model.BasicAVTransformerBlock, 'Expected the native LTXAV block')
        require(type(original_route) is _BlockRoute, 'Expected the native shard route')
        for module in block.modules():
            require(not (module._forward_hooks or module._forward_pre_hooks or module._backward_hooks),
                    'Graph capture does not support additional module hooks')
        state = tuple(block.parameters()) + tuple(block.buffers())
        require(state and all(t.dtype == torch.bfloat16 for t in state), 'Native BF16 block state required')
        self.block = block
        self.original_route = original_route
        self.index = index
        self.device = original_route.device
        require(group.device == self.device, 'Route and device group disagree')
        self.group = group
        self._route_identity = (original_route.device, original_route.primary, original_route.last)
        self.report = report
        self.entries = {}

    # -- validation ---------------------------------------------------------
    def _validate_fast(self):
        """Per-call identity check. Cheap on purpose: the expensive registration
        and residency walk runs once per forward, and Comfy's own ON_PRE_RUN
        callback already verifies full shard residency before every sampling run."""
        require(type(self.block) is av_model.BasicAVTransformerBlock, 'Captured block class changed')
        require(type(self.original_route) is _BlockRoute and
                (self.original_route.device, self.original_route.primary,
                 self.original_route.last) == self._route_identity, 'Original route placement changed')

    def _validate(self):
        self._validate_fast()
        module_api = torch.nn.modules.module
        for name in ('_global_forward_hooks', '_global_forward_pre_hooks',
                     '_global_backward_hooks', '_global_backward_pre_hooks'):
            require(not getattr(module_api, name, {}), 'Global module hooks are unsupported')
        for module in self.block.modules():
            for name in ('_forward_hooks', '_forward_pre_hooks', '_backward_hooks', '_backward_pre_hooks'):
                require(not getattr(module, name, {}), 'Block acquired unsupported module hooks')
        state = tuple(self.block.parameters()) + tuple(self.block.buffers())
        require(state and all(t.dtype == torch.bfloat16 for t in state), 'Block state is no longer native BF16')
        require(all(t.device == self.device for t in state), 'Block state is on the wrong route device')

    # -- native execution ---------------------------------------------------
    def _invoke(self, img, kwargs):
        # Pass the prepared mapping through whole: building a second key list
        # here once silently dropped transformer_options, so the block saw None.
        require(set(kwargs) == set(KEYWORDS) | {'transformer_options'},
                'Block keyword translation lost or gained an argument')
        return self.block(img, **kwargs)

    def _capture(self, routed, slot, key):
        """Record one graph for this shape and prove it matches eager bits."""
        self._validate()
        options = routed['transformer_options']
        snapshot = [t.clone() for t in slot.flat]

        def restore():
            for buffer, value in zip(slot.flat, snapshot):
                fill_static(buffer, value)

        # Reference: a fresh eager execution of the same block on the same bits.
        eager_img = mirror(routed['img'], lambda t: t.clone())
        eager_kw = {name: mirror(routed.get(name), lambda t: t.clone()) for name in KEYWORDS}
        eager_kw['transformer_options'] = options
        with torch.no_grad():
            eager_vx, eager_ax = self._invoke(eager_img, eager_kw)
        eager_vx, eager_ax = eager_vx.clone(), eager_ax.clone()

        stream = torch.xpu.Stream(device=self.device)
        stream.wait_stream(torch.xpu.current_stream(self.device))
        with torch.xpu.stream(stream), torch.no_grad():
            for _ in range(WARMUP_ITERATIONS):
                self._invoke(mirror(slot.img, lambda t: t.clone()), slot.kw)
        torch.xpu.current_stream(self.device).wait_stream(stream)
        torch.xpu.synchronize(self.device)
        restore()

        graph = torch.xpu.XPUGraph()
        # An explicit per-device capture stream is required: torch.xpu.graph
        # otherwise reuses one class-level stream bound to the first device it
        # saw, which records an EMPTY graph on any other device.
        capture_stream = torch.xpu.Stream(device=self.device)
        try:
            with torch.no_grad(), torch.xpu.graph(graph, stream=capture_stream):
                out_vx, out_ax = self._invoke(slot.img, slot.kw)
        except BaseException:
            # A capture abandoned part-way leaves the device recording. On
            # 2026-09-15 an exception inside capture (a host read of tensor
            # contents returning garbage, which asked the allocator for a
            # petabyte) was followed by a GPU CAT error and an engine reset.
            # Tear the partial graph down and drain before re-raising.
            try:
                graph.reset()
            except BaseException:
                pass
            torch.xpu.synchronize(self.device)
            raise
        torch.xpu.synchronize(self.device)

        static_vx, static_ax = slot.img
        require(out_vx is static_vx and out_ax is static_ax,
                f'Block {self.index} did not update its activations in place; the shared-buffer '
                'chain between blocks assumes it does')

        # Non-emptiness: a graph that ignores its input would replay unchanged.
        restore()
        static_vx.add_(1.0)
        graph.replay()
        torch.xpu.synchronize(self.device)
        perturbed = out_vx.clone()
        restore()
        graph.replay()
        torch.xpu.synchronize(self.device)
        require(not torch.equal(out_vx.view(torch.int16), perturbed.view(torch.int16)),
                f'Block {self.index} captured an inert graph; replay ignored its input')

        # Bitwise proof against the eager reference.
        require(torch.equal(out_vx.view(torch.int16), eager_vx.view(torch.int16)) and
                torch.equal(out_ax.view(torch.int16), eager_ax.view(torch.int16)),
                f'Block {self.index} graph replay differs from eager execution; refuse graph mode')

        entry = Entry(self.index, key, graph, out_vx, out_ax)
        self.entries[key] = entry
        self.report.record_capture(self.index, key, len(slot.flat), True,
                                   describe_types(routed), option_census(options),
                                   sorted(split_options(options)[0], key=repr),
                                   sorted(split_options(options)[1], key=repr))
        return entry

    def _call_native(self, routed):
        self._validate_fast()
        options = routed['transformer_options']
        require(CACHE_KEY in options, 'Graph capture requires the shard forward wrapper')
        key = self.group.key_for(routed, options)
        if self.group.fresh_forward:
            self._validate()
        if self.report.first_options is None:
            self.report.first_options = {'block_index': self.index,
                                         'argument_types': describe_types(routed),
                                         'options': option_census(options)}
        slot = self.group.slot_for(key, routed, options)
        self.report.copies += self.group.fill(slot, routed, options)
        entry = self.entries.get(key)
        if entry is None:
            require(len(self.entries) < MAX_SIGNATURES_PER_BLOCK,
                    f'Block {self.index} reached {len(self.entries)} distinct argument signatures; '
                    'the signature is tracking something that is not a real input')
            entry = self._capture(routed, slot, key)
        else:
            entry.graph.replay()
        entry.replays += 1
        self.report.replays += 1
        return {'img': (entry.out_vx, entry.out_ax)}

    def __call__(self, args, extra):
        return self.original_route(args, {**extra, 'original_block': self._call_native})


def describe_types(routed):
    return {name: type(routed.get(name)).__module__ + '.' + type(routed.get(name)).__name__
            for name in ('img',) + KEYWORDS}


class Report:
    """Census plus capture/replay accounting for one installed generation."""

    def __init__(self):
        self.captures = []
        self.devices = []
        self.replays = 0
        self.copies = 0
        self.first_options = None
        self.option_key_sets = []

    def record_capture(self, index, signature, tensor_count, inplace, types, census, infra, data):
        self.captures.append({'block_index': index, 'mirrored_tensors': tensor_count,
                              'output_is_input_buffer': inplace,
                              'argument_types': types,
                              'signature_sha256': hashlib.sha256(repr(signature).encode()).hexdigest()})
        keys = {'infrastructure': infra, 'mirrored': data}
        if keys not in self.option_key_sets:
            self.option_key_sets.append(keys)
            self.captures[-1]['option_census'] = census

    def summary(self):
        return {'captured_graphs': len(self.captures), 'replays': self.replays,
                'static_buffer_copies': self.copies,
                'copies_per_replay': round(self.copies / self.replays, 3) if self.replays else None,
                'blocks_captured': sorted({c['block_index'] for c in self.captures}),
                'signatures_per_block': sorted({sum(1 for c in self.captures if c['block_index'] == i)
                                                for i in {c['block_index'] for c in self.captures}}),
                'all_outputs_are_input_buffers': all(c['output_is_input_buffer'] for c in self.captures),
                'mirrored_tensor_counts': sorted({c['mirrored_tensors'] for c in self.captures}),
                'argument_types': (self.captures[0]['argument_types'] if self.captures else {}),
                'devices': self.devices,
                'transformer_options_key_sets': self.option_key_sets,
                'first_call_options': self.first_options,
                'captures': self.captures}


def validate_patcher(patcher):
    """Reject anything but the untouched native sharded registration."""
    check_source()
    require(type(patcher) is LTXLayerShardedPatcher and not patcher.is_dynamic(),
            'Graph capture requires the native static layer-sharded patcher')
    require(not (patcher.patches or patcher.hook_patches or patcher.forced_hooks or
                 patcher.object_patches or patcher.weight_wrapper_patches or patcher.injections),
            'Unsupported model patches or hooks for graph capture')
    diffusion = patcher.model.diffusion_model
    require(isinstance(diffusion, av_model.LTXAVModel) and len(diffusion.transformer_blocks) == 48,
            'Expected the native 48-block LTXAV model')
    registry = patcher.model_options.get('transformer_options', {}).get('patches_replace', {}).get('dit', {})
    require(set(registry) == {('double_block', i) for i in range(48)}, 'Unexpected block route registry')
    require(patcher.wrappers == {WrappersMP.DIFFUSION_MODEL: {KEY: [_forward_transfers]}},
            'Foreign model wrappers are unsupported')
    require(patcher.callbacks == {CallbacksMP.ON_PRE_RUN: {KEY: [_verify_placement]}},
            'Foreign model callbacks are unsupported')
    options = patcher.model_options.get('transformer_options', {})
    require(not any(options.get(key) for key in ('wrappers', 'callbacks', 'patches')),
            'Inline transformer callbacks, wrappers or patches are unsupported')
    return diffusion, registry


def install(patcher, indices):
    """Replace the selected block callables with graph-backed ones."""
    diffusion, registry = validate_patcher(patcher)
    require(all(type(registry[('double_block', i)]) is _BlockRoute for i in range(48)),
            'Blocks already carry a non-original route')
    report = Report()
    originals, groups = {}, {}
    for i in indices:
        original = registry[('double_block', i)]
        originals[i] = original
        group = groups.setdefault(original.device, DeviceGroup(original.device))
        patcher.set_model_patch_replace(
            GraphBlockRoute(diffusion.transformer_blocks[i], original, i, report, group),
            'dit', 'double_block', i)
    report.devices = sorted(str(d) for d in groups)
    validate_patcher(patcher)
    return report, originals


def measure(patcher, originals, iterations=20):
    """Time every captured graph's replay, on the real blocks.

    This is the only way to learn what the 48 blocks actually cost: XPU graph
    events cannot be profiled, and a synthetic stand-in only approximates the
    real block. Replaying outside a forward is harmless -- it recomputes into the
    shared static buffers, and the next forward refills them (block 0 refills the
    activations because their source changed, and the invariants refill because
    the forward token changed).
    """
    diffusion, registry = validate_patcher(patcher)
    rows = []
    for index in sorted(originals):
        route = registry[('double_block', index)]
        require(type(route) is GraphBlockRoute, 'Expected a graph route at block ' + str(index))
        for entry in route.entries.values():
            device = route.device
            with torch.xpu.device(device):
                for _ in range(3):
                    entry.graph.replay()
                torch.xpu.synchronize(device)
                start = time.perf_counter()
                for _ in range(iterations):
                    entry.graph.replay()
                torch.xpu.synchronize(device)
            seconds = (time.perf_counter() - start) / iterations
            rows.append({'block_index': index, 'device': str(device),
                         'video_tokens': int(entry.out_vx.shape[1]),
                         'audio_tokens': int(entry.out_ax.shape[1]),
                         'replay_ms': round(seconds * 1e3, 4)})
    stages = {}
    for row in rows:
        stages.setdefault(row['video_tokens'], []).append(row['replay_ms'])
    summary = {'iterations': iterations, 'timed_graphs': len(rows),
               'per_stage': {str(tok): {'blocks': len(v), 'sum_ms': round(sum(v), 3),
                                        'mean_block_ms': round(sum(v) / len(v), 4)}
                             for tok, v in sorted(stages.items())},
               'rows': rows}
    return summary


def attribute(patcher, originals, iterations=15, probe_blocks=(0, 24)):
    """Attribute a REAL block's GPU time using the model's own stream switches.

    BasicAVTransformerBlock.forward already reads run_vx, run_ax, a2v_cross_attn
    and v2a_cross_attn from transformer_options, so a variant can be captured and
    timed without touching numerical source. Outputs are meaningless; only the
    timing is. Run at restore time, when corrupting the shared buffers is safe.
    """
    diffusion, registry = validate_patcher(patcher)
    variants = (('baseline', {}), ('no_audio_stream', {'run_ax': False}),
                ('no_a2v', {'a2v_cross_attn': False}), ('no_v2a', {'v2a_cross_attn': False}),
                ('no_video_stream', {'run_vx': False}))
    rows = []
    for index in sorted(originals):
        if index not in probe_blocks:
            continue
        route = registry[('double_block', index)]
        require(type(route) is GraphBlockRoute, 'Expected a graph route at block ' + str(index))
        for key in list(route.entries):
            slot = route.group.slots[key]
            snapshot = [t.clone() for t in slot.flat]

            def reset():
                for buffer, value in zip(slot.flat, snapshot):
                    fill_static(buffer, value)

            tokens = int(slot.img[0].shape[1])
            for name, override in variants:
                options = {**slot.kw['transformer_options'], **override}
                kwargs = {**slot.kw, 'transformer_options': options}
                try:
                    reset()
                    graph = torch.xpu.XPUGraph()
                    with torch.xpu.device(route.device):
                        stream = torch.xpu.Stream(device=route.device)
                        stream.wait_stream(torch.xpu.current_stream(route.device))
                        with torch.xpu.stream(stream), torch.no_grad():
                            for _ in range(2):
                                route._invoke(mirror(slot.img, lambda t: t.clone()), kwargs)
                        torch.xpu.current_stream(route.device).wait_stream(stream)
                        torch.xpu.synchronize(route.device)
                        reset()
                        with torch.no_grad(), torch.xpu.graph(
                                graph, stream=torch.xpu.Stream(device=route.device)):
                            route._invoke(slot.img, kwargs)
                        torch.xpu.synchronize(route.device)
                        for _ in range(3):
                            graph.replay()
                        torch.xpu.synchronize(route.device)
                        start = time.perf_counter()
                        for _ in range(iterations):
                            graph.replay()
                        torch.xpu.synchronize(route.device)
                    rows.append({'block_index': index, 'video_tokens': tokens, 'variant': name,
                                 'ms': round((time.perf_counter() - start) / iterations * 1e3, 4)})
                    graph.reset()
                except BaseException as error:
                    rows.append({'block_index': index, 'video_tokens': tokens, 'variant': name,
                                 'error': repr(error)[:160]})
                    try:
                        graph.reset()
                    except BaseException:
                        pass
                    torch.xpu.synchronize(route.device)
            reset()
    # difference each variant against its own baseline
    summary = {}
    for row in rows:
        if 'ms' not in row:
            continue
        cell = summary.setdefault((row['block_index'], row['video_tokens']), {})
        cell[row['variant']] = row['ms']
    attribution = []
    for (index, tokens), cell in sorted(summary.items()):
        base = cell.get('baseline')
        if base is None:
            continue
        attribution.append({'block_index': index, 'video_tokens': tokens, 'baseline_ms': base,
                            'audio_stream_ms': round(base - cell['no_audio_stream'], 4)
                                               if 'no_audio_stream' in cell else None,
                            'a2v_ms': round(base - cell['no_a2v'], 4) if 'no_a2v' in cell else None,
                            'v2a_ms': round(base - cell['no_v2a'], 4) if 'no_v2a' in cell else None,
                            'video_stream_ms': round(base - cell['no_video_stream'], 4)
                                               if 'no_video_stream' in cell else None})
    return {'iterations': iterations, 'probe_blocks': list(probe_blocks),
            'method': "the model's own run_vx / run_ax / a2v_cross_attn / v2a_cross_attn switches; "
                      'outputs are meaningless, only timing is',
            'attribution': attribution, 'rows': rows}


def restore(patcher, originals):
    """Put the original native routes back and drop every captured graph."""
    diffusion, registry = validate_patcher(patcher)
    for i, original in originals.items():
        current = registry[('double_block', i)]
        require(type(current) is GraphBlockRoute and current.original_route is original,
                'Unexpected route while restoring block ' + str(i))
        current.entries.clear()
        current.group.slots.clear()
        patcher.set_model_patch_replace(original, 'dit', 'double_block', i)
    diffusion, registry = validate_patcher(patcher)
    require(all(type(registry[('double_block', i)]) is _BlockRoute for i in range(48)),
            'Original routes were not fully restored')
