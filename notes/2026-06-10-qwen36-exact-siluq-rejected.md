# Qwen3.6 Exact SiLU+INT8 MoE Fusion Rejection

Date: 2026-06-10

## Candidate

The earlier `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1` MoE epilogue candidate
was faster in isolation but failed quality because its fused SiLU+mul+INT8
quant path did not match the two-step baseline:

1. `fused_moe_activation(..., "silu")` writes a BF16 activation tensor.
2. `_xpu_C.per_token_quant_int8_xpu` quantizes that BF16 tensor.

I tested an exact version that rounds SiLU to the input dtype before multiply,
then rounds the product to the input dtype before INT8 quantization. Patch:

- `patches/vllm-xpu-kernels-qwen36-exact-siluq-rejected-20260610.patch`

Build helper added for repeatable `_xpu_C`-only iteration:

- `scripts/build-vllm-xpu-kernels-xpu-c-only.sh`

For endpoint testing, `_xpu_C` must be rebuilt with `GDN_KERNELS=ON`; a MoE-only
build imports but fails vLLM runtime with missing `_xpu_C.gdn_attention`.

## Kernel Exactness

Direct XPU equivalence test against `fused_moe_activation` plus
`per_token_quant_int8_xpu` on Qwen-shaped BF16 tensors:

- rows `1,2,4,8,16,32,64,128`
- tensor shape per row: `topk=8`, `2 * inter_size_per_tp = 256`
- result: `qdiff=0` and `scale_max=0.0` for every tested row

## Microbench

Artifacts:

- Baseline: `data/qwen36-quark-int8-moe-kernels-exactsiluq-baseline-20260610.json`
- Exact fused: `data/qwen36-quark-int8-moe-kernels-exactsiluq-fused-20260610.json`

`xpu_fused_moe` total mean, microseconds:

| rows | baseline | exact fused | result |
| ---: | ---: | ---: | --- |
| 1 | 248.297 | 236.940 | +4.6% |
| 2 | 245.540 | 289.851 | -18.0% |
| 4 | 244.441 | 273.610 | -11.9% |
| 8 | 263.686 | 295.624 | -12.1% |
| 16 | 340.592 | 366.446 | -7.6% |
| 32 | 502.354 | 504.935 | -0.5% |

The exact fused kernel computes SiLU twice, once for max-scale reduction and
once for quantization. That still helps the row-1 decode shape slightly, but it
is not a broad MoE win.

## Endpoint Speed

Endpoint candidate:

- `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1`
- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- TP4, no prefix caching, 32K context, `PIECEWISE` XPU graph
- cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-exactsiluq-gdnclone-32k-noprefix-20260610b`
- log: `/tmp/qwen36-quark-int8-tp4-exactsiluq-gdnclone-32k-noprefix-20260610b.log`

Speed artifact:

- `data/qwen36-quark-int8-tp4-noprefix-exactsiluq-gdnclone-single-r8-20260610.json`

Result:

- corrected after-first output: `99.7863 tok/s`
- e2e output: `98.5631 tok/s`
- total: `197.1261 tok/s`
- TTFT: `73.698 ms`

This beats the accepted stable speed artifact
`data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-envclean-single-r8-20260610.json`
(`99.3181 tok/s` corrected after-first), but only by about `0.47%`.

## Quality

Quality artifacts:

- `data/qwen36-quark-int8-tp4-noprefix-exactsiluq-gdnclone-frontdoor-quality-rerun32-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-exactsiluq-gdnclone-frontdoor-quality-rerun32-rerun2-20260610.json`

Both runs passed:

- exact canaries
- arithmetic
- compact JSON
- long-context recall
- baseline parity against the accepted quality artifact

Both runs failed repeat hash stability:

- run 1: `31/32` expected `blue, green, orange, red`; one outlier:
  `ntag is is ... whiskey ...`
- run 2: `31/32` expected `blue, green, orange, red`; one outlier:
  `blue whiskey whiskey green, orange, red`

## Decision

Reject. The exact fused kernel is isolated-kernel equivalent and improves the
single-request speed gate, but repeat-stability failed twice. The speed gain is
too small to justify promoting an endpoint that does not pass the reliability
gate.

The accepted backend was restored:

- tmux session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- active `_xpu_C.abi3.so` restored from backup
- frontdoor `/v1/models` smoke passed

## Next

Do not promote `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1`.

Future MoE work should focus on an exact fused implementation that avoids
recomputing SiLU twice, or on a broader decode profile target. Any new candidate
must pass repeat stability before promotion, even if exact canaries and baseline
parity pass.
