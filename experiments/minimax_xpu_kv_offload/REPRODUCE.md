# Reproducing The XPU KV / Session-Cache Work

This guide assumes the baseline MiniMax B70 stack from
`../../repro/minimax-m27-b70-110tps-ubuntu24-20260523/` has already been built.

Production remains c1. Every experiment should end by restoring c1.

## Prerequisites

- Ubuntu 24.04 with Intel GPU userspace packages installed.
- 4x Intel Arc Pro B70 visible through `xpu-smi discovery`.
- The MiniMax AutoRound model available at:
  `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- vLLM, llm-scaler, and vllm-xpu-kernels built by the 110tps repro scripts.
- Current working directory:

```bash
cd /home/steve/llm-optimizations
```

## Profile Switcher

Start or restore production c1:

```bash
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c1
```

Start c2 session-cache mode:

```bash
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c2
```

Start c4 or c8 research modes:

```bash
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c4
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c8
```

Check status:

```bash
experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh
experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh --tail
```

The switcher stops old MiniMax vLLM processes, starts the selected profile,
waits for `/v1/models`, and writes:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/current-session-cache-profile.json`

## Known-Good C2 Operational Smoke

This is the current best way to reproduce RAM-backed session juggling.

```bash
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c2

ts=$(date -u +%Y%m%dT%H%M%SZ)
experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py \
  --prompt-mode fact-word \
  --prompt-lines 900 \
  --max-tokens 4 \
  --passes 2 \
  --concurrency 2 \
  --labels A,B \
  --stop-newline \
  --output-json "/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c2-ops-fact-900lines-${ts}.json"
```

Expected class:

- two concurrent sessions
- about `22540` prompt tokens per session
- expected words match for A/B
- exact output hashes match across passes
- second-pass reload TTFT is sub-second on the current host

After the test:

```bash
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c1
```

Reference result:

- file on originating host:
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c2-ops-fact-900lines-20260525T223527Z.json`
- summary:
  `notes-20260525-session-cache-operations.md`

## C4 And C8 Reproduction

The controlled ladder results are useful, but do not treat c4/c8 as production.

Reference notes:

- `notes-20260525-c4-c8-session-cache-ladder.md`
- `notes-20260525-sustained-concurrency-decode.md`
- `notes-20260525-session-cache-operations.md`

Known results:

- c4 correctness ladder passed four `22540`-token fact-word sessions in the
  earlier controlled ladder.
- c4 sustained warmed decode at four `9234`-token prompts and `128` requested
  output tokens measured about `109.76 tok/s` total wall output.
- c8 correctness ladder passed eight `17540`-token sessions.
- c8 sustained warmed decode at eight `9234`-token prompts measured about
  `110.34 tok/s` total wall output.

Known blockers:

- c4 live operations smoke later stalled on second-pass reload with
  waiting/deferred requests.
- c4 rerun hit `UR_RESULT_ERROR_DEVICE_LOST` while copying vLLM block-table
  state to GPU.
- c8 does not increase total decode throughput; it spreads similar throughput
  across more sessions.

Suggested next c4 debug:

```bash
VLLM_MAX_NUM_BATCHED_TOKENS=256 \
  experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c4
```

Then rerun smaller fact-word canaries before trying long sustained decode.

## TurboQuant Reproduction

TurboQuant requires the workspace fallback patch:

`../../patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`

Apply it to the vLLM source tree used by the repro build if it is not already
present:

```bash
cd /mnt/fast-ai/src/vllm
git apply /home/steve/llm-optimizations/patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch
```

Run the repro helper on a non-production port:

```bash
cd /home/steve/llm-optimizations
LOG_DIR=/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260525 \
KV_DTYPE=turboquant_k8v4 \
PORT=18080 \
scripts/repro-minimax-turboquant-xpu-workspace-bug.sh
```

Reference notes:

- `notes-20260525-c2-quality-and-turboquant.md`
- `notes-20260525-turboquant-active-context-boundary.md`

Expected class after the patch:

- server reaches `/v1/models`
- `turboquant_k8v4` at 32K can report around `80128` GPU KV tokens
- strict-word canaries can pass at 8K and 32.5K prompt sizes
- sustained decode is much slower than the normal FP16-family KV path

Do not promote TurboQuant as production until quality, stability, and decode
speed are acceptable for the target use.

## True 196K Active Context

CPU KV offload and TurboQuant do not yet provide one exact `196608` active
context. The active request still needs its working KV blocks in live GPU
memory.

The current full-context design path is CPU-paged attention:

- `notes-20260525-cpu-paged-attention-design.md`
- `notes-20260525-dense-staged-cpu-attention.md`
- `notes-20260525-stagea-gpu-split-attention.md`

Useful probes:

- `probes/split_attention_merge_probe.py`
- `probes/xpu_flash_attn_split_probe.py`
- `probes/xpu_cpu_dense_staged_attention_probe.py`

## Raw Artifacts

GitHub contains scripts, notes, patches, and summarized result files. Large raw
logs and result JSONs under `/mnt/fast-ai/bench-results` are local to the
originating machine unless copied into the repo.
