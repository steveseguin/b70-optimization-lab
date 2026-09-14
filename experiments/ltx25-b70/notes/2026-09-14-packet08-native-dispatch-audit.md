# Packet08 native wrapper dispatch audit — 2026-09-14

Read-only source/trace audit. No extension compilation, native imports, runtime changes, requests or profiler execution. The profiled compiled clip passed its four output comparisons; the parent reports the diagnostic client subsequently failed on a retention filename contract, so this is a **failed diagnostic campaign with a usable trace**, not a passed campaign or speed result. No restore/retry is implied.

## What the trace establishes

Selected exact worker: `Thread 66989 "Thread-2 (prompt_worker)"`. Its 1,341 samples have explicit 0.01-second weights. The actual profiler log says `Samples: 6705 Errors: 158`; 6,705 is the profiler's total across threads and must not replace the worker count. The existing analyzer reports 598 queue-idle samples. Fifty-eight worker samples lack an actual `prompt_worker` frame, demonstrating incomplete ancestry. Sample occupancy includes waits and sampling bias; none of these counts measures CPU utilization, Python overhead, or kernel duration.

Whole-stack membership, **nonadditive**:

| Frame path fragment | Worker samples containing it |
| --- | ---: |
| pinned `ltx_native_rms_backend.py` | 9 |
| pinned `ltx_native_activations_backend.py` | 2 |
| `torch/_library/custom_ops.py` | 65 |
| `torch/_ops.py` | 63 |

The union of these four memberships is 87 samples. Generic custom-op stacks also contain Comfy Kitchen rope, AdaLN and neighborhood attention. They cannot all be charged to the private RMS/activation operators. Private-wrapper stacks include time inside native operations or waiting for prior work; only one activation stack ends in `_layout`, for example. Generated-wrapper caller lines also identify some RMS invocations under generic `_ops.py`, but asynchronous/incomplete stack samples do not establish an exact dispatch-time total.

`_group_mask` is the leaf in 25 worker samples: **21 at na.py:74 (`torch.tensor(starts, device=device)`), 1 at :75 (ends tensor), and 3 at :76 (`torch.arange(int(en.max()), device=device)`)**. An early message incorrectly associated :74 with the extent read; these source-verified lines are the correction. This supports inspecting mask construction/upload and the already-prepared extent candidate, but does not establish the extent synchronization as dominant. Tensor creation can itself include allocation/copy/wait time.

## Concrete private-wrapper candidate

The current RMS helper saves `F.rms_norm` and calls it unchanged after `_layout`, then checks output shape/stride/dtype/device (`ltx_native_rms_backend.py:15–44`). The two activation implementations likewise call saved `torch.sigmoid` and `F.gelu(..., approximate='tanh')`, with layout/result checks (`ltx_native_activations_backend.py:26–63`). Each registered `custom_op` additionally enters Python `backend_impl`, calls the selected backend and checks aliasing (`torch/_library/custom_ops.py:441–484`); its selected backend is another disabled-Dynamo Python `wrapped_fn` (`:496–503`). These are real source-level dispatch layers, independent of their unmeasured cost.

A feasible successor uses **new private C++ dispatcher operators** whose implementations call only `at::rms_norm`, `at::sigmoid`, and `at::gelu(input, "tanh")`. Keep the same opaque FX boundaries, 15 RMS/6 sigmoid/2 GELU sites, arguments, fake output layout, original parameters, and compiler options. Move existing input/result metadata and nonalias checks into C++ rather than deleting them. Do not replace formulas, fuse reductions/activations, make weights contiguous by copying, or cache tensor results. Keep fake registrations in Python; they execute during graph construction rather than each warm invocation. Restrict the candidate to the existing inference contract.

Local headers expose the exact ATen dispatcher entry points: `ATen/ops/rms_norm.h:27–29`, `sigmoid.h:27–29`, `gelu.h:41–43`. `torch/nn/functional.py:2998–3012` directly forwards RMS to `torch.rms_norm`. The candidate avoids the Python implementation and generic custom-op wrapper on the hot path while preserving the underlying ATen operations. It needs an ABI/runtime-pinned compiled artifact and new private namespace; no installed operator registry/decomposition override or live monkey-patch is required. Registration of the new private operators is still a runtime integration change and needs a sealed successor.

This is feasibility, **not numerical proof or a demonstrated speedup**. Normal 48-block, 11-invocation source counts imply 7,920 RMS + 3,168 sigmoid + 1,056 GELU calls (12,144 total); that is a static call-count opportunity, not a measured cost estimate.

## Why decomposition removal alone is insufficient

`compile_fx(..., decompositions=...)` accepts a per-compilation table (`torch/_inductor/compile_fx.py:2901–2924`), but retaining an ATen node does not force native execution: sigmoid already has an Inductor lowering (`lowering.py:8472`). `make_fallback` registers lowerings/realized-input constraints globally (`:2903–2961`). Removing decompositions or calling global `make_fallback` therefore does not provide the same isolated, exact native-operation boundary. A lower-level Python `Library.impl` may remove some custom-op scaffolding but retains a Python dispatch callback and would require rebuilding its alias/autograd safeguards.

## Qualification and priority

First preserve current output/state/receipt evidence. The smaller prepared mask-extent candidate is a reasonable immediate exactness qualification because its arithmetic-preserving change is already narrowly defined; the trace gives only three direct extent-line samples and no speed promise. Do not silently broaden it to a mask cache or CPU mask computation.

If proceeding with private C++ wrappers, start with bounded CPU operator comparisons against the saved Python/native helpers: BF16/F32, weighted/unweighted RMS, explicit epsilon and `None`, current contiguous shapes, result strides/devices, no aliasing or input mutation, and rejection of unsupported metadata. Then actual tiny block compile/eager/repeat bitwise comparisons, two stage graphs with unchanged 15/6/2 census, source/binary/dependency identity gates, and both native XPU stage/full-clip four-output oracles. Matched retained compiled/restored timing is required only after exactness passes. Keep the original wrappers and failed candidate evidence intact. The present trace does not justify promoting or prioritizing a C++ rewrite solely on presumed dispatch savings.

## Pinned audit inputs

```json
{
  "/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_native_rms_backend.py": "09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb",
  "/home/steve/llm-optimizations/experiments/ltx25-b70/scripts/ltx_native_activations_backend.py": "62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/_library/custom_ops.py": "e86666f219071ce8fe966d8de7783cc0068040061c9c59a1279c617dafd8f710",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/nn/functional.py": "95ff403085bb179477a01df63acfddf59dfac0fb58829e99a9c8b5c2fe98899b",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/_inductor/compile_fx.py": "4e5b593e018c6bd6f69062483d524b64820ab272351fbf073b7ec118a66598f8",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/_inductor/lowering.py": "c2ea8692e9948b82175cf8fc3ad9fa67e98b04c9b9e1fba5ae2ac77902d18e0c",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/include/ATen/ops/rms_norm.h": "c4941b6b8a19060f8359eed6449d5fe235bf7ea81d0c69edbe66a9f81505f2b7",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/include/ATen/ops/sigmoid.h": "48fdf94b5fbc984eab7a594603adc3578ae569a463bc459c09963764c450239c",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/include/ATen/ops/gelu.h": "be5dd8db53179b527e75ffac9651f0707b4f03cdddf60b63d66b81f7b27c43b8",
  "/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen/backends/eager/na.py": "4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995",
  "/mnt/fast-ai/bench-results/ltx25-baseline-20260913/retained-multiblock-profile-01/stacks.json": "980376023bff0097b7079ff916e4ca20b0118b425cbf2c5fa160ab36d3a113b9",
  "/mnt/fast-ai/bench-results/ltx25-baseline-20260913/retained-multiblock-profile-01/profiler.log": "dcb2490c62e8e30c744401a6ce00c6c0081ed30213418a425997c3896e660453"
}
```
