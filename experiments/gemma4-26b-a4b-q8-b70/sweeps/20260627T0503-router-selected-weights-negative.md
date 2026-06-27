# Gemma 4 26B Q8 Router Selected-Weights Fusion

Date: 2026-06-27

## Result

Valid screen, but **not a record**.

- run:
  `data/gemma4-q8-gpu1-routerselectedweights-screen-20260627T050319Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-routerselectedweights-screen-20260627T050319Z.server.log`
- canary: `64/64` rows pass
- fresh-response headline: `101.52715106143687 tok/s` after TTFT
- wall headline: `88.29327310635769 tok/s`
- cached tokens: all `0`
- prompt mode: `filled-long`, `512` requested prompt tokens, `512` max output tokens
- quality lane: Q8 target/verifier, Q4_0 MTP draft

Current promoted record at the time of this screen:

- `data/gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z/summary.json`
- fresh-response headline: `104.22626983476746 tok/s` after TTFT
- canary: `6144/6144` rows pass
- LocalMaxxing: `cmqvv3kop0309qr013ekr8apu`

This screen is about `2.7 tok/s` below the valid record and was **not**
submitted to LocalMaxxing.

## Patch Tested

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260627T0503-llamacpp-gemma4-router-selected-weights-negative-current-stack.patch`

The patch adds a default-off Gemma verifier path behind:

```text
LLAMA_GEMMA4_MOE_FUSED_ROUTER_SELECTED_WEIGHTS=1
```

It introduces a narrow ggml/SYCL op:

```text
GGML_OP_MOE_ROUTER_SELECTED_WEIGHTS
```

for Gemma4 verifier shapes (`n_expert=128`, `n_expert_used=8`,
small decode-token batches). The op fuses router top-k with selected softmax
weight materialization and returns an F32 tensor with two planes:

- selected softmax weights;
- F32-encoded selected expert IDs, cast back to I32 for the existing MoE path.

Implementation fixes made before the valid screen:

- fixed `GGML_OP_NAME` alignment for the new op;
- added SYCL `F32 -> I32` copy/cast support so the selected expert ID cast
  does not fall back to CPU;
- kept the path narrow and default-off.

## Command Shape

The screen used the current promoted scalar stack plus the new env flag:

```bash
cd /home/steve/qwen36-results-main
LABEL=gemma4-q8-gpu1-routerselectedweights-screen-$(date -u +%Y%m%dT%H%M%SZ) \
GPU_INDEX=1 PORT=18261 CTX_SIZE=8192 BATCH_SIZE=1024 UBATCH_SIZE=768 \
THREADS=8 POLL=100 FLASH_ATTN=off \
CANARY_REPEATS=16 BENCH_REPEATS=1 PROMPT_TOKENS=512 BENCH_PROMPT_MODE=filled-long \
MAX_TOKENS=512 \
MTP_N_MAX=7 MTP_N_MIN=3 MTP_P_MIN=0.10 \
MTP_BACKEND_SAMPLING=0 MTP_DRAFT_THREADS=32 MTP_DRAFT_THREADS_BATCH=32 \
MTP_EXTRA_ARGS='--ctx-checkpoints 0' \
LLAMA_MTP_DRAFT_FAST_ARGMAX=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 \
LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1 \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1 \
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1 \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1 \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1 \
LLAMA_GEMMA4_MOE_FUSED_ROUTER_SELECTED_WEIGHTS=1 \
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 GGML_SYCL_ENABLE_VMM=0 \
scripts/run-gemma4-26b-mtp-candidate.sh
```

## Interpretation

The router selected-weights fusion is correct enough for the screen, but it is
not beneficial on the current record stack. The likely reason is that the
existing `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1` plus route-cache path has
already made this boundary cheap; the new op adds packing, an F32-encoded ID
plane, and an F32-to-I32 cast that outweigh the saved materialization work.

Do not promote this path or spend more time on this exact design unless a
profile later proves router selection has become hot again after a larger MoE
or verifier rewrite.

## Next Actions

This result removes the first item from the 2026-06-27 source roadmap as a
promising near-term lever. The next Gemma work should move to one of:

- narrow Q8 verifier gate/up kernel for the current route-cache shapes;
- exact verifier candidate-vs-max acceptance;
- direct-unroll confidence score/gap so `MTP_P_MIN` or gap gating can actually
  reduce verifier rows on fresh requests;
- true graph-level multi-token assistant unroll.

Small p-min/UBATCH/selected-softmax-router sweeps are unlikely to move the
fresh-response headline materially beyond the current `104.226 tok/s` record.
