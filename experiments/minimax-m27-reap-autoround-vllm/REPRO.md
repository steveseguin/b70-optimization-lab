# REAP MiniMax M2.7 AutoRound Repro Guide

This is the current internal repro path for the REAP lane on a 4x Intel Arc Pro B70
32 GB host. It is not yet a public polished guide, but it captures the exact setup
that produced the 2026-05-31 best result.

## Hardware And Model

- GPUs: 4x Intel Arc Pro B70, 32 GB each
- Runtime: local vLLM/XPU TP4
- Model: `MJPansa/MiniMax-M2.7-REAP-172B-A10B-AutoRound-W4A16`
- Local model path: `/mnt/fast-ai/llm-models/minimax-m2.7-reap-autoround-w4a16`
- Model revision tested: `31271b30ff048a128772a744ee6d998a2fb648cb`
- Safetensors footprint: `91,512,175,232` bytes, about `85.23 GiB`

## Source Patches

Apply or reproduce the relevant local source changes before running quality or
benchmarks:

- vLLM patch artifact:
  `patches/vllm-reap-piecewise-static-range-and-b70-e192-configs-20260531.patch`
- llm-scaler patch artifact:
  `patches/llm-scaler-minimax-reap-e192-router-ws-20260531.patch`

The vLLM patch adds the REAP `E=192,N=384` B70 INT4 MoE configs and fixes the
fresh-cache PIECEWISE static-shape multiple-entry assertion. The llm-scaler patch
archives the current MiniMax INT4 kernel changes used in this lab tree. It is
larger than the REAP-specific diff because it includes the ongoing MiniMax kernel
work this lane depends on.

## Download

```bash
cd /home/steve/llm-optimizations/experiments/minimax-m27-reap-autoround-vllm
HF_HUB_DISABLE_XET=1 HF_DOWNLOAD_WORKERS=6 HF_DOWNLOAD_ATTEMPTS=0 \
  scripts/download-model.sh
```

Expected post-download checks:

- `23` safetensor shards
- No missing shards from `model.safetensors.index.json`
- No stale `.incomplete` or `.lock` files in the HF cache

## Quality Gate

```bash
cd /home/steve/llm-optimizations/experiments/minimax-m27-reap-autoround-vllm
scripts/quality-smoke.sh
```

Current passing smoke:

- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260531T231727Z.json`
- result: `passed=true`
- deterministic: true
- generated tokens: `1473`
- NUL/control/degenerate output: none

## Benchmark

Use true greedy decoding for LocalMaxxing-compatible results:

```bash
cd /home/steve/llm-optimizations/experiments/minimax-m27-reap-autoround-vllm
VLLM_BENCH_TEMPERATURE=0 scripts/bench-decode.sh
```

Current promoted settings live in `configs/reap.env`. Important settings:

- `TP=4`
- `MAX_MODEL_LEN=2048`
- `MAX_BATCHED_TOKENS=512`
- `MAX_NUM_SEQS=1`
- `INPUT_LEN=512`
- `OUTPUT_LEN=1536`
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

Archived best result:

- output throughput: `89.49922316987691 tok/s`
- total throughput: `119.3322975598359 tok/s`
- elapsed: `17.16216013500525 s`
- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.log`
- JSON:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.json`

Current caveat, added 2026-06-01:

- The `89.49922316987691` result is a historical, previously quality-gated
  artifact. It is not currently reproducible as a quality-valid runtime from
  the live source after later Q/K restore and cache-debug work.
- Current live-source quality-valid direct async REAP best is:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T223035Z.json`,
  `83.517837` output tok/s, with async quality pass
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-fullforward0-restore0-qksafe-20260601T1828.json`.
- The stale fast `f728d2c0cf` path can still produce `88.x` output tok/s in
  benchmark-only runs, but strict async quality catches all-zero/NUL output.
  Do not publish or promote it without a fresh quality pass.

## Known Rejected Settings

- `CCL_IPC=sockets`: slower than `pidfd`
- `--block-size 128` and `--block-size 512`: slower than `256`
- `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=0`: large regression
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=0`: slower
- `VLLM_XPU_LOCAL_ARGMAX_DECODE=1`: large regression
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS=1`: starts after repair but
  regresses throughput
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`: still too fragile/slow for
  promotion on REAP

## LocalMaxxing

Best submitted REAP result:

- LocalMaxxing ID: `cmpuesbma00r5mq01yk0zdcjx`
- Payload:
  `localmaxxing/reap-minimax-m27-autoround-greedy-pidfd-p512n1536-20260531.payload.json`
- Status: HTTP `201`, `APPROVED`

## OpenAI-Compatible Serve

For the vLLM OpenAI server path:

```bash
cd /home/steve/llm-optimizations
VLLM_ENABLE_AUTO_TOOL_CHOICE=0 \
VLLM_TOOL_CALL_PARSER=none \
VLLM_REASONING_PARSER=none \
VLLM_GENERATION_CONFIG=vllm \
  experiments/minimax-m27-reap-autoround-vllm/scripts/serve.sh
```

Current REAP serve defaults differ slightly from the offline LocalMaxxing
benchmark wrapper:

- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=0`
- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`
- `VLLM_STREAM_INTERVAL=1`

The qk-helper default is quality-clean on the compiled 32K OpenAI path and is
the best tested server default so far: `82.6854` mean output tok/s after first
chunk on p512/n1536. `VLLM_STREAM_INTERVAL=8` is an opt-in streaming profile that
reduces stream chunk count and reached `82.7078` corrected output tok/s, but it
is not a meaningful improvement versus the archived `89.49922316987691` offline
record. It changes client-visible streaming cadence and is not the default.

Current quality-safe restore-off direct checks also sit in the same low-80s
band after warmup:

- warmed direct restore-off:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T124723Z.json`
- output throughput: `80.62106717066092 tok/s`
- total throughput: `107.49475622754791 tok/s`

Do not use restore-weight for compiled OpenAI serve yet. It is faster in some
direct/offline paths, but compiled OpenAI quality currently fails with all-NUL
output, including the `VLLM_MINIMAX_QK_NORM_COMPILE_USE_PARAM=1` variant.
