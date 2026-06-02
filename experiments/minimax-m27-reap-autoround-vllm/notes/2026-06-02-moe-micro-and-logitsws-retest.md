# 2026-06-02 MoE Microbench And Logits-WS Retest

Goal: look for low-risk REAP decode improvements after the current live-source
quality-safe lane settled around `83.52` output tok/s.

## Tooling

Added `scripts/bench-reap-moe-micro.py`, a synthetic XPU microbench for the
REAP per-rank MoE shape:

- hidden size: `3072`
- intermediate size: `384`
- routed experts: `192`
- top-k: `8`

It times the raw routed U4 path, routed workspace path, FP16 top-k-weight
variant, MiniMax logits path, and MiniMax logits workspace path without loading
the full checkpoint. Run one process per env setting because the llm-scaler
extension reads several knobs into static variables on first use.

Also extended the benchmark and quality wrappers to preserve/record:

- `VLLM_XPU_MOE_WS_UP_NTILE`
- `VLLM_XPU_MOE_WS_DOWN_HTILE`
- `VLLM_XPU_MINIMAX_WS_TOPK_WEIGHT_FP16`
- `VLLM_XPU_MINIMAX_WS_REUSE_DECODE_BUFFERS`
- `VLLM_XPU_MINIMAX_WS_REUSE_INTERMEDIATES`
- `VLLM_XPU_MINIMAX_WS_REUSE_TOPK_BUFFERS`

## Microbench Results

Default synthetic run:

- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/micro/moe-e192-default-20260602T032601Z.json`
- `tokens=1`: `routed_ws=0.0870 ms`, `minimax_logits_ws=0.0881 ms`,
  `routed_u4=0.1663 ms`
- `tokens=2`: `routed_ws=0.1084 ms`, `minimax_logits_ws=0.0827 ms`,
  `routed_u4=0.2652 ms`
- `tokens=4`: `routed_ws=0.1426 ms`, `minimax_logits_ws=0.1505 ms`,
  `routed_u4=0.3207 ms`

Tile sweep summary:

- default/default: `routed_ws=0.077606 ms`, `minimax_ws=0.078589 ms`
- default/down4: `routed_ws=0.070203 ms`, `minimax_ws=0.076725 ms`
- up2/default: `routed_ws=0.071335 ms`, `minimax_ws=0.094498 ms`
- larger up/down tiles were generally slower or noisy

FP16 top-k-weight screen:

- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/micro/moe-e192-topkfp16-tokens1-20260602T0402Z.json`
- `tokens=1`, `VLLM_XPU_MINIMAX_WS_TOPK_WEIGHT_FP16=1`
- `minimax_logits_ws=0.0627475 ms`
- synthetic max absolute diff vs routed U4: `3.814697265625e-06`

Decision from microbench: the workspace MiniMax logits path is worth full-model
testing. Tile and reuse screens are too noisy to trust without full decode.
FP16 top-k weights are a numerical relaxation, so they require separate quality
and speed gating.

## Full Decode Screens

Common settings unless noted:

- `VLLM_XPU_USE_LLM_SCALER_MOE=1`
- `VLLM_XPU_USE_LLM_SCALER_MOE_WS=1`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`
- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`
- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=0`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=0`
- `VLLM_XPU_SKIP_COMPILED_PREFILL=1`
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`
- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`
- `VLLM_BENCH_TEMPERATURE=0`
- `CCL_IPC=pidfd`
- `CCL_ZE_IPC_EXCHANGE=pidfd`
- `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`

### Regular WS, down tile 4

Settings:

- `VLLM_XPU_MOE_WS_DOWN_HTILE=4`
- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=0`

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-downhtile4-qk0-20260602T033150Z.json`
- passed, `384` generated tokens, `188` distinct generated token IDs, no
  NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T033622Z.log`
- `111.41` total tok/s
- `83.56` output tok/s

Decision: reject. It is quality-clean but effectively neutral versus the
`83.52` baseline.

### Logits WS, down tile 4

Settings:

- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`
- `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1`
- `VLLM_XPU_MOE_WS_DOWN_HTILE=4`

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-downhtile4-qk0-20260602T033827Z.json`
- passed, `384` generated tokens, `172` distinct generated token IDs, no
  NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T034250Z.log`
- `112.47` total tok/s
- `84.35` output tok/s

Decision: small improvement, but not enough to promote over the default-tile
logits-WS run.

### Logits WS, default tiles

Settings:

- `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`
- `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1`
- no explicit `VLLM_XPU_MOE_WS_DOWN_HTILE`
- no explicit `VLLM_XPU_MOE_WS_UP_NTILE`

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-default-qk0-20260602T034639Z.json`
- passed, `384` generated tokens, `180` distinct generated token IDs, no
  NUL/control output

Benchmarks:

- first:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T035058Z.log`,
  `112.65` total tok/s, `84.49` output tok/s
- repeat:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T035955Z.log`,
  `113.46` total tok/s, `85.10` output tok/s

Decision: best new quality-smoke-clean result from this pass. Keep as the
current live-source candidate, but do not submit or call it recovered: it is
still below the archived `89.49922316987691` output tok/s REAP record.

### Logits WS, reused intermediates

Settings:

- default logits-WS settings
- `VLLM_XPU_MINIMAX_WS_REUSE_INTERMEDIATES=1`

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-reuseinter-qk0-20260602T035326Z.json`
- passed, `384` generated tokens, `174` distinct generated token IDs, no
  NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T035758Z.log`
- `112.57` total tok/s
- `84.43` output tok/s

Decision: reject. It is quality-clean but slower than default logits-WS.

### Logits WS, FP16 top-k weights

Settings:

- default logits-WS settings
- `VLLM_XPU_MINIMAX_WS_TOPK_WEIGHT_FP16=1`

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-topkfp16-qk0-20260602T040231Z.json`
- passed, `384` generated tokens, `186` distinct generated token IDs, no
  NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T040656Z.log`
- `112.38` total tok/s
- `84.29` output tok/s

Decision: reject. The microbench win did not survive full decode, and this path
also changes top-k-weight precision.

## Current State

Current live-source quality-smoke-clean best from this pass:

- logits-WS default tiles
- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-logitsws-default-qk0-20260602T034639Z.json`
- best repeat:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T035955Z.log`
- `85.10` output tok/s
- `113.46` total tok/s

This improves the current low-83 live-source lane, but it does not recover the
archived `89.49922316987691` output tok/s result and is not a LocalMaxxing
submission candidate.

## Next Work

The easy env screens are not enough. Meaningful movement toward `90+` and
eventually `100+` output tok/s likely needs source-level work:

- inspect why the old fast `f728d2c0cf` cache shape was faster but corrupt when
  used without the clean-weight repair
- make the Q/K RMS restore path graph-safe without changing the code hash into
  the slower low-83/85 shape
- profile the default logits-WS candidate and compare kernel buckets against
  the archived f728 run
- investigate source-level MiniMax logits-WS fusion and IGC behavior rather
  than more tile/env sweeps
- keep top-k-buffer reuse disabled unless a dedicated aliasing proof and
  stricter quality gate are added
