# 2026-05-21 MiniMax llm-scaler INT4 prefill-op smoke

## Context

The current promoted MiniMax-M2.7 AutoRound path is decode-focused. While
looking for remaining non-quality-sacrificing optimizations, I checked the
upstream llm-scaler INT4 prefill sources. The source tree already had
`csrc/moe_prefill/moe_prefill_int4.sycl`, but the Python package did not have
`moe_int4_prefill_ops` built or importable.

## Build Attempt

Added an isolated setup entry point:

```bash
setup_moe_int4_prefill_only.py
```

First build failed because `icpx` was not on `PATH`. Re-running with the known
working oneAPI 2025.3 compiler environment succeeded:

```bash
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
source /home/steve/.venvs/vllm-xpu/bin/activate
cd /home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm
MAX_JOBS=1 \
CC=/opt/intel/oneapi/compiler/2025.3/bin/icx \
CXX=/opt/intel/oneapi/compiler/2025.3/bin/icpx \
python setup_moe_int4_prefill_only.py build_ext --inplace
```

Import and op registration passed:

```text
custom_esimd_kernels_vllm.moe_int4_prefill_ops
moe_prefill_full_int4
moe_prefill_gather_forward_v2
moe_prefill_up_forward_v2
moe_prefill_down_forward_v2
moe_prefill_accumulate_forward_v2
moe_topk_softmax
```

## Correctness Smoke

The prefill kernel consumes AutoRound/GPTQ-style int32 packed weights. A packed
zero is not all-zero bytes. For this path, the zero-pointed INT4 zero value is
the signed int32 bit pattern `0x88888888`, represented as `-0x77777778`.

With all weights filled as `0x88888888`, `moe_prefill_full_int4` returned exact
zero output for M in `[1, 4, 16, 64, 128, 256, 512]`.

## Timing Smoke

Zero-weight timing on one B70, MiniMax local shapes:

| Tokens | ms/layer | layer-equivalent tok/s |
| ---: | ---: | ---: |
| 1 | 2.256 | 443 |
| 4 | 5.089 | 786 |
| 16 | 12.194 | 1,312 |
| 64 | 24.841 | 2,576 |
| 128 | 27.120 | 4,720 |
| 256 | 26.649 | 9,606 |
| 512 | 25.972 | 19,714 |

This is not a decode win by itself. It may still be worth integrating as a
prefill-only candidate, but it needs real-weight equivalence against vLLM's
current prefill path before any throughput claim.

## Current Status

Not promoted. No LocalMaxxing submission. The build and smoke are useful
because they identify a viable prefill-op test surface and the required packed
zero representation.

Important semantic guardrail: `moe_prefill_full_int4` is not directly
MiniMax-correct as-is. Its all-in-one path calls `moe_topk_v2_host`, which is a
softmax TopK router. MiniMax M2 routing uses sigmoid scores plus
`e_score_correction_bias`, then top-k renormalization. To preserve quality, a
MiniMax integration must bypass the all-in-one router and use the lower-level
`moe_prefill_gather_forward_v2`, `moe_prefill_up_forward_v2`,
`moe_prefill_down_forward_v2`, and `moe_prefill_accumulate_forward_v2` ops with
the current vLLM MiniMax router outputs.

The promoted decode path was rechecked after the prefill-only extension build.
The raw145 n64 canary still passed exactly:

```text
combined_token_sha256=267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd
control_nonspace_text_chars=0
nul_token_count=0
```

## Next Gate

Preserve or reconstruct the original per-rank int32 AutoRound/GPTQ weights,
feed the lower-level prefill ops with MiniMax-correct router outputs, then
compare one MoE layer against the current vLLM prefill path with real weights.
Only after exact/tolerance layer equivalence should this be exposed behind a
runtime env flag.
