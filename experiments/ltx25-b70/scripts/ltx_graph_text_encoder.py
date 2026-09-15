"""XPU graph capture for the Gemma4-12B text encoder stack.

Text encoding is the largest single node in the clip -- 1.81 s of 4.75 s, 38% --
and it runs the same 48 layers over the same `[1, 1024]` prompt on every clip.
The prompt is a sealed literal, so the work is bit-for-bit identical each time,
yet it is re-issued from Python each time.

It is also the worst-served component on the box. A Gemma layer holds 546 MB of
state, so one layer reads at 1.02 ms at the measured 537 GB/s copy roofline, and
48 layers should cost about 49 ms. They cost 1.81 s -- **37x the roofline**,
against 2.2x for the video transformer's blocks. That gap is operation-issue
overhead, which is exactly what graph replay removes.

Capture is per layer, not per stack. `Gemma4Transformer.forward` collects the
hidden state between layers (`all_intermediate.append(x.unsqueeze(1).clone())`,
gemma4.py:565-567) because LTX consumes all 49 of them, so folding layers
together would drop the collections. One graph per layer keeps every one.

`TransformerBlockGemma4.forward` writes its result into its own input buffer
(`output = x`, then `torch.mul(..., out=output)`), so a layer's static input IS
its static output, the same shape the video block route relies on.

Nothing here changes the checkpoint, precision, token count, layer count or
arithmetic. Replay issues the recorded command list: same kernels, same order,
same memory. Every capture is proven non-inert and bitwise-equal to a fresh
eager execution of the same layer on the same inputs before it is ever used.
"""
import hashlib
import sys
import time
from pathlib import Path

import torch

from ltx_graph_capture import (MAX_SIGNATURES_PER_BLOCK, WARMUP_ITERATIONS, describe,
                               fill_static, mirror, require, static_like, walk)

GEMMA_SOURCE_SHA256 = 'a0bec322e45e94e5c938c2b8bde0112d23805166a533612077915d594d18dbbc'
LAYER_CLASS = 'TransformerBlockGemma4'
STACK_CLASS = 'Gemma4Transformer'
LAYERS = 48


def check_source(module):
    actual = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
    require(actual == GEMMA_SOURCE_SHA256,
            'Native Gemma4 source changed; re-audit the text encoder graph adapter')


def bitwise_equal(a, b):
    if a.dtype in (torch.bfloat16, torch.float16):
        return torch.equal(a.view(torch.int16), b.view(torch.int16))
    if a.dtype == torch.float32:
        return torch.equal(a.view(torch.int32), b.view(torch.int32))
    return torch.equal(a, b)


class Entry:
    def __init__(self, key, graph, static_kwargs, flat, output):
        self.key = key
        self.graph = graph
        self.static_kwargs = static_kwargs
        self.flat = flat
        self.output = output
        self.replays = 0


class GraphedLayer:
    """Graph-backed stand-in for one Gemma4 transformer layer."""

    def __init__(self, layer, index, report):
        self.layer = layer
        self.index = index
        self.report = report
        self.original = layer.forward
        self.source = sys.modules[type(layer).__module__]
        check_source(self.source)
        require(tuple(layer.parameters()) or tuple(layer.buffers()),
                f'Gemma layer {index} carries no state')
        # The device is resolved at capture, not here. ComfyUI moves the text
        # encoder onto its load device lazily, inside the encode itself, so at
        # gate time these layers are still on the CPU; reading the device now
        # refuses a perfectly capturable encoder.
        self.device = None
        for module in layer.modules():
            require(not (module._forward_hooks or module._forward_pre_hooks or module._backward_hooks),
                    'Text encoder graph capture does not support additional module hooks')
        self.entries = {}

    # -- helpers ------------------------------------------------------------
    def _signature(self, kwargs):
        return (self.index, describe(kwargs, f'layer{self.index}.kwargs'))

    def _flatten(self, kwargs):
        found = []
        walk(kwargs, found, f'layer{self.index}.kwargs')
        return found

    def _resolve_device(self):
        state = tuple(self.layer.parameters()) + tuple(self.layer.buffers())
        devices = {t.device for t in state}
        require(len(devices) == 1,
                f'Gemma layer {self.index} state spans devices: {sorted(map(str, devices))}')
        device = devices.pop()
        require(device.type == 'xpu',
                f'Gemma layer {self.index} is on {device} at encode time; text encoder graph '
                'capture needs the encoder resident on an XPU')
        require(self.device is None or self.device == device,
                f'Gemma layer {self.index} moved from {self.device} to {device} after capture')
        self.device = device
        return device

    def _replay(self, graph):
        with torch.xpu.device(self.device):
            graph.replay()
            torch.xpu.synchronize(self.device)

    def _run(self, kwargs):
        # Prefill only, with no cache in and none out. A KV cache would make the
        # layer stateful, and a graph that baked one step's cache in would
        # silently serve stale keys forever after.
        require(kwargs.get('past_key_value') is None,
                f'Gemma layer {self.index} was given a KV cache; capture assumes stateless prefill')
        require(kwargs.get('shared_kv') is None,
                f'Gemma layer {self.index} was given a shared KV; capture assumes stateless prefill')
        out, present, shareable = self.original(**kwargs)
        # `present` and `shareable` are computed even on a cacheless prefill and
        # are both provably dead here -- see the contract asserted in stack_of().
        return out

    # -- capture ------------------------------------------------------------
    def _capture(self, kwargs, key):
        check_source(self.source)
        self._resolve_device()
        static_kwargs = mirror(kwargs, static_like)
        flat = self._flatten(static_kwargs)
        require(len(flat) == len(self._flatten(kwargs)),
                f'Static mirror lost or gained a tensor for Gemma layer {self.index}')
        snapshot = [t.clone() for t in flat]

        def restore():
            for buffer, value in zip(flat, snapshot):
                fill_static(buffer, value)

        # Reference: a fresh eager call of the same layer on the same bits.
        with torch.no_grad():
            reference = self._run(mirror(kwargs, lambda t: t.clone())).clone()

        with torch.xpu.device(self.device):
            stream = torch.xpu.Stream(device=self.device)
            stream.wait_stream(torch.xpu.current_stream(self.device))
            with torch.xpu.stream(stream), torch.no_grad():
                for _ in range(WARMUP_ITERATIONS):
                    self._run(mirror(static_kwargs, lambda t: t.clone()))
            torch.xpu.current_stream(self.device).wait_stream(stream)
            torch.xpu.synchronize(self.device)
        restore()

        graph = torch.xpu.XPUGraph()
        try:
            # The encoder lives on xpu:2 while the sampler's current device is
            # xpu:0. torch.xpu.graph synchronises and empty_caches the *current*
            # device, so without this context it records an EMPTY graph that
            # replays as a no-op and returns stale text conditioning.
            with torch.xpu.device(self.device), torch.no_grad(), \
                    torch.xpu.graph(graph, stream=torch.xpu.Stream(device=self.device)):
                output = self._run(static_kwargs)
        except BaseException:
            # A capture abandoned part-way leaves the device recording; tear the
            # partial graph down and drain before re-raising.
            try:
                graph.reset()
            except BaseException:
                pass
            torch.xpu.synchronize(self.device)
            raise
        torch.xpu.synchronize(self.device)

        static_x = static_kwargs['x']
        require(output is static_x,
                f'Gemma layer {self.index} did not write into its input buffer; capture assumes it does')

        # Non-inert: perturb a static input and require the replayed output to move.
        restore()
        static_x.add_(1.0)
        self._replay(graph)
        perturbed = output.clone()
        restore()
        self._replay(graph)
        require(not bitwise_equal(output, perturbed),
                f'Gemma layer {self.index} captured an inert graph; replay ignored its input')

        # Bitwise proof against the eager reference.
        require(output.dtype == reference.dtype and output.shape == reference.shape,
                f'Gemma layer {self.index} replay changed output dtype or shape')
        require(bitwise_equal(output, reference),
                f'Gemma layer {self.index} graph replay differs from eager execution; refuse graph mode')

        entry = Entry(key, graph, static_kwargs, flat, output)
        self.entries[key] = entry
        self.report.record(self.index, key, len(flat), tuple(output.shape), str(output.dtype))
        return entry

    def __call__(self, **kwargs):
        require(isinstance(kwargs.get('x'), torch.Tensor),
                f'Gemma layer {self.index} was called without a tensor hidden state')
        # ComfyUI may move the encoder between encodes; a graph whose static
        # buffers live on a device the weights have left would replay stale.
        self._resolve_device()
        key = self._signature(kwargs)
        entry = self.entries.get(key)
        if entry is None:
            require(len(self.entries) < MAX_SIGNATURES_PER_BLOCK,
                    f'Gemma layer {self.index} reached {len(self.entries)} distinct argument '
                    'signatures; the signature is tracking something that is not a real input')
            entry = self._capture(kwargs, key)
        else:
            incoming = self._flatten(kwargs)
            require(len(incoming) == len(entry.flat),
                    f'Argument tensor count changed for Gemma layer {self.index}')
            for buffer, value in zip(entry.flat, incoming):
                if buffer is not value:
                    fill_static(buffer, value)
            self._replay(entry.graph)
        entry.replays += 1
        self.report.replays += 1
        # The caller rebinds x to this buffer and the parent loop clones it into
        # all_intermediate before the next layer runs, so handing back the static
        # buffer is what the native in-place layer does too.
        return entry.output, None, None


class Report:
    def __init__(self):
        self.captures = []
        self.replays = 0

    def record(self, index, key, tensor_count, out_shape, out_dtype):
        self.captures.append({'layer_index': index, 'mirrored_tensors': tensor_count,
                              'output_shape': list(out_shape), 'output_dtype': out_dtype,
                              'signature_sha256': hashlib.sha256(repr(key).encode()).hexdigest()})

    def summary(self):
        return {'captured_graphs': len(self.captures), 'replays': self.replays,
                'layers_captured': sorted({c['layer_index'] for c in self.captures}),
                'signatures_per_layer': sorted({sum(1 for c in self.captures if c['layer_index'] == i)
                                                for i in {c['layer_index'] for c in self.captures}}),
                'output_shapes': sorted({tuple(c['output_shape']) for c in self.captures}),
                'captures': self.captures}


def stack_of(clip):
    """Locate the one Gemma4 text transformer under a loaded CLIP."""
    root = getattr(clip, 'cond_stage_model', None)
    require(root is not None, 'CLIP has no cond_stage_model')
    found = [m for m in root.modules() if type(m).__name__ == STACK_CLASS]
    require(len(found) == 1, f'Expected exactly one {STACK_CLASS}, found {len(found)}')
    stack = found[0]
    check_source(sys.modules[type(stack).__module__])
    layers = getattr(stack, 'layers', None)
    require(layers is not None and len(layers) == LAYERS,
            f'Expected {LAYERS} Gemma layers, found {0 if layers is None else len(layers)}')
    require(all(type(l).__name__ == LAYER_CLASS for l in layers),
            'Unexpected Gemma layer class')
    # Why a captured layer may return (output, None, None) instead of the KV
    # pair the native layer returns. Gemma4Transformer.forward consumes the two
    # KV outputs in exactly two places (gemma4.py:576-582 and 617-619), and both
    # are guarded by `num_kv_shared_layers > 0`. With that zero, the store at 617
    # is dead and `next_key_values` is returned only when `past_key_values is not
    # None` (gemma4.py:651-653), which a prompt encode never passes. So on this
    # configuration the KV outputs are discarded and dropping them is exact.
    # If the configuration ever changes, this refuses instead of guessing.
    config = getattr(stack, 'config', None)
    require(config is not None, 'Gemma stack has no config to check the KV contract against')
    require(getattr(config, 'num_kv_shared_layers', None) == 0,
            'Gemma layers share a KV cache; the captured layers may not drop their KV outputs')
    require(getattr(config, 'num_hidden_layers', None) == LAYERS,
            'Gemma layer count disagrees with the configuration')
    return stack, layers


def install(clip):
    """Shadow every Gemma layer's forward with a graph-backed stand-in."""
    stack, layers = stack_of(clip)
    for layer in layers:
        require('forward' not in vars(layer), 'Gemma layer forward is already shadowed')
    report = Report()
    originals = {}
    for index, layer in enumerate(layers):
        shadow = GraphedLayer(layer, index, report)
        originals[index] = shadow.original
        layer.forward = shadow
    return report, originals


def restore(clip, originals):
    """Remove the stand-ins so the class methods take over again."""
    stack, layers = stack_of(clip)
    for index, layer in enumerate(layers):
        current = vars(layer).get('forward')
        require(isinstance(current, GraphedLayer) and current.original is originals[index],
                f'Unexpected Gemma layer forward while restoring layer {index}')
        current.entries.clear()
        del layer.forward
    for layer in layers:
        require('forward' not in vars(layer), 'Gemma layer forward stayed shadowed')
        require(callable(getattr(layer, 'forward', None)), 'Gemma layer lost its forward')
    stack_of(clip)


def measure(clip, iterations=20):
    """Time every captured layer graph. XPU graph events cannot be profiled, so
    replaying each graph with a host sync is the only ground truth for what the
    48 layers actually cost."""
    stack, layers = stack_of(clip)
    rows = []
    for index, layer in enumerate(layers):
        shadow = vars(layer).get('forward')
        if not isinstance(shadow, GraphedLayer):
            continue
        if shadow.device is None:
            continue
        for entry in shadow.entries.values():
            with torch.xpu.device(shadow.device):
                for _ in range(3):
                    entry.graph.replay()
                torch.xpu.synchronize(shadow.device)
                start = time.perf_counter()
                for _ in range(iterations):
                    entry.graph.replay()
                torch.xpu.synchronize(shadow.device)
            seconds = (time.perf_counter() - start) / iterations
            rows.append({'layer_index': index, 'device': str(shadow.device),
                         'tokens': int(entry.output.shape[1]),
                         'replay_ms': round(seconds * 1e3, 4)})
    return {'iterations': iterations, 'timed_graphs': len(rows),
            'sum_ms': round(sum(r['replay_ms'] for r in rows), 3),
            'rows': rows}
