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

        stream = torch.xpu.Stream(device=self.device)
        stream.wait_stream(torch.xpu.current_stream(self.device))
        with torch.xpu.stream(stream), torch.no_grad():
            for _ in range(WARMUP_ITERATIONS):
                self.original(*static_args, **static_kwargs)
        torch.xpu.current_stream(self.device).wait_stream(stream)
        torch.xpu.synchronize(self.device)
        restore()

        graph = torch.xpu.XPUGraph()
        # An explicit per-device capture stream is required: torch.xpu.graph
        # otherwise reuses one class-level stream bound to the first device it
        # saw, which records an EMPTY graph on any other device.
        with torch.no_grad(), torch.xpu.graph(graph, stream=torch.xpu.Stream(device=self.device)):
            output = self.original(*static_args, **static_kwargs)
        torch.xpu.synchronize(self.device)
        require(isinstance(output, torch.Tensor), self.name + ' capture did not produce a tensor')

        # Non-inert: perturb a static input and require the replayed output to move.
        require(flat, self.name + ' has no tensor inputs to perturb')
        restore()
        flat[0].add_(1.0)
        graph.replay()
        torch.xpu.synchronize(self.device)
        perturbed = output.clone()
        restore()
        graph.replay()
        torch.xpu.synchronize(self.device)
        require(not torch.equal(output.view(torch.int16) if output.dtype == torch.bfloat16 else output,
                                perturbed.view(torch.int16) if output.dtype == torch.bfloat16 else perturbed),
                self.name + ' captured an inert graph; replay ignored its input')

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
            entry.graph.replay()
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

    def record(self, name, key, tensor_count, out_shape, out_dtype):
        self.captures.append({'method': name, 'mirrored_tensors': tensor_count,
                              'output_shape': list(out_shape), 'output_dtype': out_dtype,
                              'signature_sha256': hashlib.sha256(repr(key).encode()).hexdigest()})

    def summary(self):
        return {'captured_graphs': len(self.captures), 'replays': self.replays,
                'methods': sorted({c['method'] for c in self.captures}),
                'captures': self.captures}


def decoder_of(vae):
    decoder = vae.first_stage_model.decoder
    require(type(decoder).__name__ == 'NADiffusionDecoder',
            'Expected the native neighbourhood-attention diffusion decoder')
    for name in METHODS:
        require(callable(getattr(decoder, name, None)), 'Decoder is missing ' + name)
    require(int(decoder.default_inference_timesteps.shape[0]) == 1,
            'Capture assumes the single-step decoder configuration')
    state = tuple(decoder.parameters()) + tuple(decoder.buffers())
    require(state and len({t.device for t in state}) == 1, 'Decoder state spans devices')
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
