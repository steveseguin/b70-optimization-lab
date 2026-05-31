# 2026-05-31 State And Next Steps

## Current Best

- Model: `MJPansa/MiniMax-M2.7-REAP-172B-A10B-AutoRound-W4A16`
- Revision: `31271b30ff048a128772a744ee6d998a2fb648cb`
- Local path: `/mnt/fast-ai/llm-models/minimax-m2.7-reap-autoround-w4a16`
- Quantization: AutoRound INT4 W4A16, `bits=4`, `group_size=128`, symmetric
- Runtime: local vLLM/XPU TP4 on 4x Intel Arc Pro B70 32 GB
- Best quality-gated decode result:
  - shape: `p512/n1536`, `max_model_len=2048`, `max_num_batched_tokens=512`, `max_num_seqs=1`
  - output throughput: `89.49922316987691 tok/s`
  - total throughput: `119.3322975598359 tok/s`
  - elapsed: `17.16216013500525 s`
  - benchmark JSON: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.json`
  - benchmark log: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.log`
- Post-patch quality gate:
  - file: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260531T231727Z.json`
  - result: `passed=true`
  - generated tokens: `1473`
  - deterministic: true
  - NUL/control/degenerate output: none

## Promoted Settings

Keep the conservative graph path:

```bash
VLLM_BENCH_TEMPERATURE=0 \
/home/steve/llm-optimizations/experiments/minimax-m27-reap-autoround-vllm/scripts/bench-decode.sh
```

Effective important settings:

- `TP=4`
- `DTYPE=float16`
- `MAX_MODEL_LEN=2048`
- `MAX_BATCHED_TOKENS=512`
- `MAX_NUM_SEQS=1`
- `INPUT_LEN=512`
- `OUTPUT_LEN=1536`
- `XPU_GRAPH=1`
- `CCL_IPC=pidfd`
- `CCL_ZE_IPC_EXCHANGE=pidfd`
- `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`
- `VLLM_XPU_USE_LLM_SCALER_MOE=1`
- `VLLM_XPU_USE_LLM_SCALER_MOE_WS=1`
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=0`
- `VLLM_XPU_SKIP_COMPILED_PREFILL=1`
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`
- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`
- vLLM args: `--async-engine --block-size 256 --no-enable-prefix-caching --compilation-config {"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}`

## What Changed

- Production is paused by `/home/steve/llm-optimizations/.pause-minimax-production`.
- Added REAP `E=192,N=384` B70 MoE configs to the local vLLM tree.
- Patched and rebuilt the llm-scaler INT4 MiniMax logits kernel to dispatch `192` experts as well as `256`.
- Patched the REAP benchmark wrapper to preserve targeted env overrides after sourcing the promoted MiniMax env.
- Patched vLLM `piecewise_backend.py` so fresh-cache PIECEWISE runs with static-shape subgraphs choose the unique single-size compiled entry when both `(1, 1)` and `(1, 512)` entries exist.

## Tried And Rejected

- `--block-size 128`: `84.86304386171942 output tok/s`
- `--block-size 512`: `85.20690854846342 output tok/s`
- `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=0`: `72.84487671422855 output tok/s`
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=0`: `85.34403336996918 output tok/s`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`: `88.17025570432432 output tok/s`, neutral
- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1`: `75.13077860553253 output tok/s`, reject
- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1 VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER_REUSE=1`: `75.34188608324035 output tok/s`, reject
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS=1`: `72.44384428157205 output tok/s`, reject
- `CCL_IPC=sockets`: `88.90492979756878 output tok/s`, reject
- default IPC same-window control after the `pidfd` screen: `89.27580338562741 output tok/s`, lower than the promoted `pidfd` run
- `FULL_DECODE_ONLY`: compile-range assertion path
- `FULL_AND_PIECEWISE`: unsupported SYCL graph scratch-memory behavior in XPU FlashAttention
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`: repaired enough to load in some paths, but graph integration is still too slow/fragile for promotion

## Future Work

- Investigate why the original warmed cache remains faster than fresh-cache warm reruns.
- Keep graph-cache experiments isolated with `VLLM_CACHE_ROOT`; never overwrite the best warmed cache while testing.
- Return to the MiniMax logits fused path only after solving the graph compile-range and no-auto-ranges slowdown.
- Consider deeper source-level fusion around attention/KV, Q/K RMS collectives, and graph boundaries; the simple flag sweep is exhausted.
- LocalMaxxing corrected greedy payload was submitted and approved as
  `cmpuc7tkq00qamq01z61pnb3c`.
- New `pidfd` CCL easy-win payload supersedes that local best at
  `89.49922316987691 output tok/s`; see
  `notes/2026-05-31-pidfd-ccl-easy-win.md`.
- LocalMaxxing update submitted and approved as
  `cmpuesbma00r5mq01yk0zdcjx`.

## Archived Repro State

- Internal repro guide:
  `experiments/minimax-m27-reap-autoround-vllm/REPRO.md`
- vLLM patch artifact:
  `patches/vllm-reap-piecewise-static-range-and-b70-e192-configs-20260531.patch`
- llm-scaler patch artifact:
  `patches/llm-scaler-minimax-reap-e192-router-ws-20260531.patch`
- REAP versus non-REAP gap analysis:
  `notes/2026-05-31-reap-vs-nonreap-gap.md`
