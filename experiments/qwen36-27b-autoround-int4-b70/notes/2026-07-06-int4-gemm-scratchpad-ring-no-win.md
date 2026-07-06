# 2026-07-06 - INT4 W4A16 oneDNN scratchpad ring screen - no win

## Goal

Test whether reusing oneDNN user scratchpad tensors for the target W4A16 INT4
GEMMs reduces per-step overhead for the current Qwen27 ReplaySSM draft-INT4
record recipe.

The current valid record recipe is still:

- `webhie/Qwen3.6-27B-int4-AutoRound` revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70 TP1, XPU graph PIECEWISE, MTP3/cg8;
- runtime INT8 target LM-head with BF16 scales;
- runtime INT4 draft LM-head with BF16 scales;
- ReplaySSM exact GDN state, commit-in-forward;
- `VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1`;
- strict fresh Qwen realistic suite, one cold request per prompt,
  `cached_tokens=0`, token-id timing.

Before testing, the same current recipe reconfirmed healthy:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-record-reconfirm-20260706T052643Z-candidate-summary-20260706T052643Z.json`;
- median: `68.29516426484548 tok/s`;
- p10: `62.61194966289658`;
- mean: `67.721871920058`;
- TTFT median: `488.70998341590166 ms`;
- strict fresh gate: pass, `cached_tokens=0` for all prompts;
- quality was skipped because this was an unchanged-recipe support run.

## Patch Tested

Patch artifact:

`patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-int4-gemm-scratchpad-ring-no-win-20260706.patch`

The patch added a default-off `VLLM_XPU_INT4_GEMM_SCRATCHPAD_RING_SIZE` knob to
`csrc/xpu/onednn/int4_gemm_w4a16.h`. When set to `1..16`, it reused a
thread-local per-device/per-scratchpad-size ring of byte tensors instead of
allocating a fresh scratchpad tensor for every W4A16 oneDNN matmul call.

The patch built successfully with oneAPI `2025.3` in:

`/home/steve/src/vllm-xpu-kernels/build/int4scratch-2025/_C.abi3.so`

The rebuilt extension imported cleanly. After testing, the live
`vllm_xpu_kernels/_C.abi3.so` was restored to the timestamped pre-experiment
backup, and the active source diff for `int4_gemm_w4a16.h` was removed. The
patch is preserved only as an experiment artifact.

## Four-GPU Same-Window Screen

All rows used `RUN_QUALITY=0` and passed the strict fresh gate with
`cached_tokens=0`; this was a speed screen, not a promoted result.

| Arm | GPU | Median tok/s | p10 | Mean | Summary |
| --- | --- | ---: | ---: | ---: | --- |
| ring0 control | 0 | `66.83323972876187` | `62.153055078588416` | `67.2231875747553` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4scratch-ring0-control-20260706T053231Z-candidate-summary-20260706T053231Z.json` |
| ring1 | 1 | `67.22604198954804` | `61.475321470086534` | `66.9406965265061` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4scratch-ring1-20260706T053231Z-candidate-summary-20260706T053231Z.json` |
| ring2 | 2 | `66.81736227917004` | `61.87416835678712` | `67.36920351455754` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4scratch-ring2-20260706T053231Z-candidate-summary-20260706T053231Z.json` |
| ring4 | 3 | `66.6382874621469` | `61.347502217852785` | `66.85339346830195` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4scratch-ring4-20260706T053231Z-candidate-summary-20260706T053231Z.json` |

Ring1 was nominally positive by `+0.59%` over the same-window control, but the
delta was inside the known variance band, so it required a crossover.

## Ring1 Crossover

| Arm | GPU | Median tok/s | p10 | Mean | Summary |
| --- | --- | ---: | ---: | ---: | --- |
| ring1 | 0 | `66.87934235526812` | `62.095834559702536` | `67.10660803614283` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4scratch-ring1-crossover-gpu0-20260706T053630Z-candidate-summary-20260706T053630Z.json` |
| ring0 control | 1 | `66.55031199933182` | `61.72662690252947` | `66.87583148920109` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4scratch-ring0-control-crossover-gpu1-20260706T053630Z-candidate-summary-20260706T053630Z.json` |
| ring1 | 2 | `66.95417669441979` | `62.063407349145` | `67.4849507775755` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4scratch-ring1-crossover-gpu2-20260706T053630Z-candidate-summary-20260706T053630Z.json` |
| ring0 control | 3 | `67.514906797444` | `61.812147322889166` | `67.05867131311722` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4scratch-ring0-control-crossover-gpu3-20260706T053630Z-candidate-summary-20260706T053630Z.json` |

Across all ring0/ring1 rows in the initial screen plus crossover:

- ring0 controls: `66.833`, `66.550`, `67.515` tok/s;
- ring1 candidates: `67.226`, `66.879`, `66.954` tok/s;
- ring1 minus ring0 mean delta: `+0.0537 tok/s`, `+0.080%`;
- ring1 minus ring0 median-of-runs delta: `+0.1209 tok/s`, `+0.181%`.

## Decision

Closed as **no win**. Scratchpad allocation/reuse for W4A16 INT4 GEMM is not a
measurable endpoint bottleneck for this recipe. Do not promote or carry
`VLLM_XPU_INT4_GEMM_SCRATCHPAD_RING_SIZE` in the Qwen27 record recipe.

The useful conclusion is negative: the current waste is not per-call oneDNN
scratchpad allocation. Continue with mechanisms that reduce target step cost or
increase target-verified accepted tokens per step, rather than more allocator
micro-knobs.
