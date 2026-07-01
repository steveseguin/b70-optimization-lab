# 2026-07-01 SWA left-bound balanced service profile

## Purpose

Profile the current balanced long-context service recipe before making another
prompt-processing source change. This is diagnostic only; profiling overhead
changes throughput and the result is not a LocalMaxxing or headline decode
claim.

## Command

```bash
cd /home/steve/llm-optimizations
source /opt/intel/oneapi/setvars.sh --force
STAMP=20260701Tprofile-swalb-service-canon1 \
GGML_SYCL_NODE_PROFILE=1 GGML_SYCL_NODE_PROFILE_DETAIL=1 \
GGML_SYCL_NODE_PROFILE_EVERY=24 \
LLAMA_SERVER_SPEC_PROFILE=1 LLAMA_MTP_DRAFT_PROFILE=1 \
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_PREFILL_UBATCH_SIZE=2048 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048 \
LONG_CONTEXT_CASE_IDS="lc-22000-middle" \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=1 MAX_TOKENS=96 BASE_PORT=18680 READINESS_TIMEOUT_S=900 \
LANE_SPECS="0:2048:1024:swalb-profile:2048" \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

## Artifacts

- Summary: `data/gemma4-long-context-service-gate-20260701Tprofile-swalb-service-canon1.json`
- Run dir: `data/gemma4-q8-gpu0-longctx-swalb-profile-ctx32768-o96-20260701Tprofile-swalb-service-canon1`
- Server/profile log: `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-longctx-swalb-profile-ctx32768-o96-20260701Tprofile-swalb-service-canon1.server.log`

The long-context gate passed, the canary passed, and `cached_tokens=0`.

## Diagnostic Metrics

Because profiling is enabled, the measured rates are not comparable to normal
record/service runs:

- median prefill: `1003.320 tok/s`;
- median decode after TTFT: `84.631 tok/s`;
- TTFT for `lc-22000-middle`: `30.299 s`.

Server phase profile:

- target decode total: `31936.981 ms`, `30679` tokens, `1.041 ms/token`;
- target prompt: `30854.568 ms`, `30555` tokens, `1.010 ms/token`;
- target generation: `1082.413 ms`, `124` tokens, `8.729 ms/token`;
- draft MTP: `221.048 ms` total, `93` draft tokens;
- sample/accept/common accept overhead: about `0.4 ms` total, negligible.

## Hot Nodes

The dominant long-context prompt-processing cost is global attention, not the
SWA left-bound scanner or sampler/MTP overhead. The final profile top nodes are
global `FLASH_ATTN_EXT` calls:

- `FLASH_ATTN_EXT:__fattn__-5`: `2205.397 ms`, `55` calls,
  `40.098 ms/call`;
- `FLASH_ATTN_EXT:__fattn__-11`: `2192.540 ms`, `55` calls,
  `39.864 ms/call`;
- `FLASH_ATTN_EXT:__fattn__-17`: `2192.530 ms`, `55` calls,
  `39.864 ms/call`;
- `FLASH_ATTN_EXT:__fattn__-23`: `2192.499 ms`, `55` calls,
  `39.864 ms/call`;
- `FLASH_ATTN_EXT:__fattn__-29`: `2187.210 ms`, `55` calls,
  `39.767 ms/call`.

The next tier is local/SWA attention and final MoE:

- early `FLASH_ATTN_EXT` nodes around `1.8-1.9 ms/call`;
- `MUL_MAT_ID:ffn_moe_gate_up-29`: `256.053 ms`, `55` calls,
  `4.656 ms/call`;
- `MUL_MAT_ID:ffn_moe_gate_up-0`: `245.836 ms`, `55` calls,
  `4.470 ms/call`.

## Decision

No prompt-processing source patch is selected from this profile yet. The
profile says the easy host SWA-left-bound and phase-prefill knobs have mostly
done their job; remaining TTFT cost is global `FLASH_ATTN_EXT` for the global
attention layers.

Do not revive the closed host left-bound fast builder or broad phase-prefill
roulette. If prompt-processing work continues, it should target global
attention tile/scheduling behavior with a same-window long-context A/B and then
a short-decode guard. For headline throughput, return to decode-side verifier
economics because the short-context record remains target/verifier-bound.
