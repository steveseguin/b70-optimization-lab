"""XPU graph capture for the LTX neighbourhood-attention video decoder.

The decoder's own `forward` is NOT captured: it draws `x_t` from a generator, and
baking one sample of that into a graph would be wrong. Its two components are
pure functions of their arguments and are captured instead:

- `forward_pre_diffusion(z, ...)` -- the deterministic stages 1-4 NA upsample;
- `forward_diff_step(context, x_t, t)` -- one diffusion step.

The decoder is configured with `default_num_inference_steps = 1`, so each runs
once per decode. Both are installed as instance attributes that shadow the class
methods, and removed on restore; the module, its registration and its weights are
untouched. All buffer, signature and proof machinery is imported from the
qualified `ltx_graph_capture` rather than reimplemented.
"""
import hashlib
from pathlib import Path

import torch

from ltx_graph_capture import (MAX_SIGNATURES_PER_BLOCK, WARMUP_ITERATIONS, describe,
                               fill_static, mirror, require, static_like, walk)

METHODS = ('forward_pre_diffusion', 'forward_diff_step')
DECODER_SOURCE_SHA256 = None  # set by the node from the sealed manifest


class Captured:
    def __init__(self, key, graph, static_args, static_kwargs, flat, output):
        self.key = key
        self.graph = graph
        self.static_args = static_args
        self.static_kwargs = static_kwargs
        self.flat = flat
        self.output = output
        self.replays = 0


class GraphedMethod:
    """Graph-backed stand-in for one pure decoder method."""

    def __init__(self, owner, name, original, report):
        self.owner = owner
        self.name = name
        self.original = original
        self.report = report
        self.device = next(owner.parameters()).device
        self.entries = {}

    def _replay(self, graph):
        with torch.xpu.device(self.device):
            graph.replay()
            torch.xpu.synchronize(self.device)

    # -- helpers ------------------------------------------------------------
    def _signature(self, args, kwargs):
        return (self.name, describe(args, self.name + '.args'),
                describe(kwargs, self.name + '.kwargs'))

    def _flatten(self, args, kwargs):
        found = []
        walk(args, found, self.name + '.args')
        walk(kwargs, found, self.name + '.kwargs')
        return found

    def _capture(self, args, kwargs, key):
        static_args = mirror(args, static_like)
        static_kwargs = mirror(kwargs, static_like)
        flat = self._flatten(static_args, static_kwargs)
        require(len(flat) == len(self._flatten(args, kwargs)),
                'Static mirror lost or gained a tensor for ' + self.name)
        snapshot = [t.clone() for t in flat]

        def restore():
            for buffer, value in zip(flat, snapshot):
                fill_static(buffer, value)

        # Reference: a fresh eager call of the original method on the same bits.
        with torch.no_grad():
            reference = self.original(*mirror(args, lambda t: t.clone()),
                                      **mirror(kwargs, lambda t: t.clone()))
        require(isinstance(reference, torch.Tensor),
                self.name + ' did not return a single tensor; capture assumes it does')
        reference = reference.clone()

        # The decoder lives on xpu:3 while the current device is xpu:0. Setting
        # only the stream is not enough: torch.xpu.graph synchronises and
        # empty_caches the *current* device, and capture then records nothing.
        # An empty graph replays as a no-op and would silently return stale
        # output, so the device context is set explicitly around every capture,
        # warm-up and replay. The non-inertness proof below is what caught this.
        with torch.xpu.device(self.device):
            stream = torch.xpu.Stream(device=self.device)
            stream.wait_stream(torch.xpu.current_stream(self.device))
            with torch.xpu.stream(stream), torch.no_grad():
                for _ in range(WARMUP_ITERATIONS):
                    self.original(*static_args, **static_kwargs)
            torch.xpu.current_stream(self.device).wait_stream(stream)
            torch.xpu.synchronize(self.device)
        restore()

        # The captured region must land its result in a buffer allocated OUTSIDE
        # the capture. A tensor the capture allocates itself is only valid for
        # the call that produced it: the bitwise check right after capture passes
        # on it, and then every replay leaves it stale -- which is exactly what
        # three attempts saw as "an inert graph no input moves", with a non-empty
        # graph and no driver warning. Copying into a stable buffer inside the
        # captured region makes replay land somewhere this code still owns.
        static_output = torch.empty_like(reference)

        graph = torch.xpu.XPUGraph()
        # An explicit per-device capture stream is required: torch.xpu.graph
        # otherwise reuses one class-level stream bound to the first device it
        # saw, which records an EMPTY graph on any other device.
        try:
            with torch.xpu.device(self.device), torch.no_grad(), \
                    torch.xpu.graph(graph, stream=torch.xpu.Stream(device=self.device)):
                produced = self.original(*static_args, **static_kwargs)
                static_output.copy_(produced)
            output = static_output
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
        require(isinstance(produced, torch.Tensor),
                self.name + ' capture did not produce a tensor')
        require(produced.shape == reference.shape and produced.dtype == reference.dtype,
                self.name + ' capture changed the output shape or dtype')

        # Non-inert: the replayed output must move when an input moves. Earlier
        # attempts perturbed only flat[0] and reported a bare "inert graph",
        # which said nothing about WHY. Perturb each input in turn and record
        # which ones the output follows, so a failure is a diagnosis.
        require(flat, self.name + ' has no tensor inputs to perturb')
        restore()
        self._replay(graph)
        baseline = output.clone()
        sensitivity = []
        for position, buffer in enumerate(flat):
            if not buffer.is_floating_point():
                sensitivity.append({'input': position, 'dtype': str(buffer.dtype),
                                    'shape': list(buffer.shape), 'moved': None,
                                    'note': 'not perturbed: non-floating input'})
                continue
            restore()
            buffer.add_(1.0)
            self._replay(graph)
            moved = not bitwise_equal(output, baseline)
            sensitivity.append({'input': position, 'dtype': str(buffer.dtype),
                                'shape': list(buffer.shape), 'moved': moved})
        restore()
        self._replay(graph)
        require(bitwise_equal(output, baseline),
                self.name + ' replay is not reproducible after restoring its inputs')
        self.report.sensitivity[self.name] = sensitivity
        require(any(row['moved'] for row in sensitivity),
                self.name + ' captured a graph no input moves; sensitivity=' + repr(sensitivity))

        # Bitwise proof against the eager reference.
        require(output.dtype == reference.dtype and output.shape == reference.shape,
                self.name + ' replay changed output dtype or shape')
        require(bitwise_equal(output, reference),
                self.name + ' graph replay differs from eager execution; refuse graph mode')

        entry = Captured(key, graph, static_args, static_kwargs, flat, output)
        self.entries[key] = entry
        self.report.record(self.name, key, len(flat), tuple(output.shape), str(output.dtype))
        return entry

    def __call__(self, *args, **kwargs):
        key = self._signature(args, kwargs)
        entry = self.entries.get(key)
        if entry is None:
            require(len(self.entries) < MAX_SIGNATURES_PER_BLOCK,
                    f'{self.name} reached {len(self.entries)} distinct argument signatures; '
                    'the signature is tracking something that is not a real input')
            entry = self._capture(args, kwargs, key)
        else:
            incoming = self._flatten(args, kwargs)
            require(len(incoming) == len(entry.flat),
                    'Argument tensor count changed for a captured ' + self.name + ' signature')
            for buffer, value in zip(entry.flat, incoming):
                if buffer is not value:
                    fill_static(buffer, value)
            self._replay(entry.graph)
        entry.replays += 1
        self.report.replays += 1
        # The captured output lives in this graph's private pool and the next
        # replay overwrites it, so hand the caller its own copy.
        return entry.output.clone()


def bitwise_equal(a, b):
    if a.dtype in (torch.bfloat16, torch.float16):
        return torch.equal(a.view(torch.int16), b.view(torch.int16))
    if a.dtype == torch.float32:
        return torch.equal(a.view(torch.int32), b.view(torch.int32))
    return torch.equal(a, b)


class Report:
    def __init__(self):
        self.captures = []
        self.replays = 0
        self.sensitivity = {}

    def record(self, name, key, tensor_count, out_shape, out_dtype):
        self.captures.append({'method': name, 'mirrored_tensors': tensor_count,
                              'output_shape': list(out_shape), 'output_dtype': out_dtype,
                              'signature_sha256': hashlib.sha256(repr(key).encode()).hexdigest()})

    def summary(self):
        return {'captured_graphs': len(self.captures), 'replays': self.replays,
                'input_sensitivity': self.sensitivity,
                'methods': sorted({c['method'] for c in self.captures}),
                'captures': self.captures}


def placement_of(decoder):
    """Per-device tensor counts of the decoder's parameters and buffers, with a few names."""
    rows = {}
    for name, t in list(decoder.named_parameters()) + list(decoder.named_buffers()):
        row = rows.setdefault(str(t.device), {'count': 0, 'examples': []})
        row['count'] += 1
        if len(row['examples']) < 4:
            row['examples'].append(name)
    return rows


def decoder_of(vae, strict_placement=True):
    """The native decoder. `strict_placement` (needed for graph capture and its
    proofs) requires every parameter and buffer on one device; the original and
    restored modes only observe placement (the native decode handles its own)."""
    decoder = vae.first_stage_model.decoder
    require(type(decoder).__name__ == 'NADiffusionDecoder',
            'Expected the native neighbourhood-attention diffusion decoder')
    for name in METHODS:
        require(callable(getattr(decoder, name, None)), 'Decoder is missing ' + name)
    require(int(decoder.default_inference_timesteps.shape[0]) == 1,
            'Capture assumes the single-step decoder configuration')
    state = tuple(decoder.parameters()) + tuple(decoder.buffers())
    require(bool(state), 'Decoder has no state')
    if strict_placement:
        require(len({t.device for t in state}) == 1,
                'Decoder state spans devices: ' + repr(placement_of(decoder)))
    for module in decoder.modules():
        require(not (module._forward_hooks or module._forward_pre_hooks or module._backward_hooks),
                'VAE graph capture does not support additional module hooks')
    return decoder


def install(vae):
    """Shadow the two pure decoder methods with graph-backed stand-ins."""
    decoder = decoder_of(vae)
    for name in METHODS:
        require(name not in vars(decoder), 'Decoder method is already shadowed: ' + name)
    report = Report()
    originals = {}
    for name in METHODS:
        bound = getattr(decoder, name)
        originals[name] = bound
        setattr(decoder, name, GraphedMethod(decoder, name, bound, report))
    return report, originals


def restore(vae, originals):
    """Remove the stand-ins so the class methods take over again."""
    decoder = vae.first_stage_model.decoder
    for name in METHODS:
        current = vars(decoder).get(name)
        require(isinstance(current, GraphedMethod) and current.original is originals[name],
                'Unexpected decoder method while restoring ' + name)
        current.entries.clear()
        delattr(decoder, name)
    for name in METHODS:
        require(name not in vars(decoder), 'Decoder method stayed shadowed: ' + name)
        require(callable(getattr(decoder, name, None)), 'Decoder lost its original ' + name)
    decoder_of(vae)
