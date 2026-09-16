"""XPU graph capture for the LTX latent spatial upsampler.

`LatentUpsampler.forward` is a pure function of its one input: convolutions,
group norms, SiLU, pixel shuffle. No host reads, no generator, no
data-dependent shapes. The node calls it once per clip on a [1, 128, 4, 8, 8]
bf16 latent and pays ~0.24 s for a model that reads under 1 GB, which is
dispatch, not arithmetic. Capturing it removes the dispatch and changes no
kernel.

The capture machinery is `ltx_graph_vae.GraphedMethod`, which proves each
graph bit-identical to a fresh eager call on the same inputs and non-inert by
perturbation, and lands the output in a buffer allocated outside the capture.
One addition here: the parameter addresses the graph recorded are checked on
every call, because ComfyUI's model management may offload and reload this
small model, and a replay against moved weights would read freed memory.

`timed` is a diagnostic mode: it leaves the eager forward in place and records
its synchronised wall time per call, so the receipt attributes the node's cost
before any capture is claimed.
"""
import time

import torch

from ltx_graph_vae import GraphedMethod, Report, require

METHOD = 'forward'


def upsampler_of(upscale_model):
    model = getattr(upscale_model, 'model', None)
    require(model is not None and type(model).__name__ == 'LatentUpsampler',
            'Expected a LatentUpsampler behind the upscale model')
    require(callable(getattr(model, METHOD, None)), 'Upsampler is missing forward')
    for module in model.modules():
        require(not (module._forward_hooks or module._forward_pre_hooks or module._backward_hooks),
                'Upsampler graph capture does not support additional module hooks')
    return model


def state_of(model):
    state = tuple(model.parameters()) + tuple(model.buffers())
    require(state and len({t.device for t in state}) == 1, 'Upsampler state spans devices')
    return state


def resident_on_xpu(model):
    device = state_of(model)[0].device
    require(device.type == 'xpu', 'Upsampler weights are not resident on an XPU: ' + str(device))
    return device


def param_fingerprint(model):
    return tuple((t.data_ptr(), tuple(t.shape), str(t.dtype)) for t in state_of(model))


class GraphedUpsamplerForward(GraphedMethod):
    """GraphedMethod plus a weight-address check on every call."""

    def __init__(self, owner, original, report):
        resident_on_xpu(owner)
        super().__init__(owner, METHOD, original, report)
        self.fingerprint = param_fingerprint(owner)
        self.calls = 0

    def __call__(self, *args, **kwargs):
        require(param_fingerprint(self.owner) == self.fingerprint,
                'Upsampler weights moved since capture; refuse to replay against moved memory')
        self.calls += 1
        return super().__call__(*args, **kwargs)


class TimedForward:
    """Eager forward with synchronised wall timing; numerically the original call."""

    def __init__(self, owner, original):
        self.owner = owner
        self.original = original
        self.device = resident_on_xpu(owner)
        self.seconds = []

    def __call__(self, *args, **kwargs):
        torch.xpu.synchronize(self.device)
        started = time.perf_counter()
        out = self.original(*args, **kwargs)
        torch.xpu.synchronize(self.device)
        self.seconds.append(round(time.perf_counter() - started, 5))
        return out


def install(upscale_model, timed=False):
    model = upsampler_of(upscale_model)
    require(METHOD not in vars(model), 'Upsampler forward is already shadowed')
    bound = getattr(model, METHOD)
    report = Report()
    stand_in = TimedForward(model, bound) if timed else GraphedUpsamplerForward(model, bound, report)
    setattr(model, METHOD, stand_in)
    return report, bound, stand_in


def restore(upscale_model, original):
    model = upsampler_of(upscale_model)
    current = vars(model).get(METHOD)
    require(isinstance(current, (GraphedUpsamplerForward, TimedForward)) and current.original is original,
            'Unexpected upsampler forward while restoring')
    if isinstance(current, GraphedUpsamplerForward):
        current.entries.clear()
    delattr(model, METHOD)
    require(METHOD not in vars(model) and callable(getattr(model, METHOD, None)),
            'Upsampler did not regain its original forward')
