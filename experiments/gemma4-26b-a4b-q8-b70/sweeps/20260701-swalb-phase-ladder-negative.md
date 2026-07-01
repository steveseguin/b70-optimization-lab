# 2026-07-01 SWA left-bound phase-prefill ladder: prefill/decode tradeoff

## Purpose

Retest phase-prefill sizes under the current best long-context service stack:
GQA8, host SWA left-bound, 32K context, Q8 target/verifier, Q4_0 MTP draft,
VDR2 selected-down stack, and final postnorm fusion.

This was a targeted follow-up after worktree consolidation. The goal was prompt
processing improvement without lowering decode speed or changing quality.

## Command

```bash
cd /home/steve/llm-optimizations
source /opt/intel/oneapi/setvars.sh --force
STAMP=20260701Tswalb-phase-ladder-canon1 \
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048 \
LONG_CONTEXT_CASE_IDS="lc-12288-early lc-16384-late lc-22000-middle" \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=2 MAX_TOKENS=96 BASE_PORT=18690 READINESS_TIMEOUT_S=900 \
LANE_SPECS="0:2048:1024:phase2048:2048 1:2304:1024:phase2304:2304 2:2560:1024:phase2560:2560 3:2816:1024:phase2816:2816" \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

## Artifacts

- Summary: `data/gemma4-long-context-service-gate-20260701Tswalb-phase-ladder-canon1.json`

All lanes passed the long-context gate, exact validation/canary checks, and
`cached_tokens=0`.

## Results

| Batch / prefill ubatch | Median prefill tok/s | Delta vs 2048 | Median decode tok/s | Delta vs 2048 |
| ---: | ---: | ---: | ---: | ---: |
| 2048 | 1129.207 | baseline | 119.470 | baseline |
| 2304 | 1142.167 | +1.15% | 116.706 | -2.31% |
| 2560 | 1180.935 | +4.58% | 116.706 | -2.31% |
| 2816 | 1188.638 | +5.26% | 114.903 | -3.82% |

## Decision

Negative for promotion. Larger phase-prefill sizes improve long-context prefill
throughput, but they lower decode throughput in the same run. Because the
service goal is faster prompt processing without hurting decode, these are not
promoted and do not justify a short-decode guard.

The balanced service recipe remains:

```bash
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
LLAMA_PREFILL_UBATCH_SIZE=2048
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048
```

Next useful prompt-processing step is a profile of the balanced recipe to see
where TTFT remains after GQA8 + phase prefill + host SWA left-bound. Do not
repeat broad phase-prefill roulette unless a source change alters the kernel
mix.
