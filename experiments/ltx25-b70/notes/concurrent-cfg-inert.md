# Concurrent dual-CFG: correct, exact, and inert on this recipe

*2026-09-16, packet52, `pipe-ccfg` arm. Five clips, all bytewise exact.*

## The idea

`Guider_LTXAVDualCFG.predict_noise` sets `disable_cfg1_optimization`, so on the
dual-CFG path every sampler step evaluates the model twice -- conditional and
unconditional -- and the two are independent; `dual_cfg` only combines their
results arithmetically. The captured block shapes are batch 1, so ComfyUI runs
them as two separate sequential forwards. The transformer's blocks are split
21/27 across xpu:0 and xpu:1, so a single forward leaves one card idle. Running
the two forwards on two threads should let one occupy xpu:1 while the other
occupies xpu:0 -- a two-stage pipeline inside a single clip, with no cross-prompt
state and no change to any arithmetic.

## What was built, and it works

- `GroupRegistry` keys a `DeviceGroup` by **(device, thread)**, and the block
  route keys its captured graphs by thread, so two concurrent forwards never
  share static buffers. Without this they would overwrite each other's
  activations.
- `LTXConcurrentCFG` registers a wrapper at ComfyUI's own
  `WrappersMP.CALC_COND_BATCH` extension point -- no patching -- which runs each
  present cond on its own thread and returns them in order, falling back to the
  native path for anything that is not exactly two present conds.

Five clips ran through it, **all four raw outputs bytewise equal**, 96 graphs
captured, no errors.

## Why it does nothing here

The receipts say `splits: 0, passthrough: 44` -- eleven wrapper calls per clip,
each with a single cond, matching the eleven model forwards per clip measured
from the replay count. The reason is in the graph:

```json
"388": {"class_type": "LTXVDualCFGGuider",
        "inputs": {"video_cfg": 1.0, "audio_cfg": 1.0, ...}}
```

`video_cfg == audio_cfg`, so `predict_noise` takes its own early return to
standard single-CFG with `self.cfg = 1.0` -- and `disable_cfg1_optimization` is
set **only on the dual path**. At cfg 1.0 ComfyUI skips the unconditional pass.

**This distilled recipe runs exactly one model forward per step.** There is no
second forward to overlap, which is also why the sampler is as cheap as it is.
The lever is not slow, it is absent.

## What it leaves behind

The negative result is clean, but the per-thread capture state is not wasted:
**it is the piece inter-clip sampler pipelining needs.** Two clips sampling at
once require exactly what this built -- separate static buffers, separate
captured graphs and a separate signature cache per forward thread -- and that is
now implemented and proven exact on real clips. What remains for inter-clip
pipelining is a sampler that can run on a worker thread, so two clips can be in
flight at once.
