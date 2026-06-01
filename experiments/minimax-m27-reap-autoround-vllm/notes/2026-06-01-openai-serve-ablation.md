# 2026-06-01 OpenAI Serve Ablation

Goal: recover REAP decode rate on the vLLM OpenAI-compatible server without
reintroducing the NaN/NUL output failure found in the stale promoted-env bundle.

## Baseline

Quality-safe compiled OpenAI server, 32K context, parsers disabled, vLLM
generation config:

- quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-qualityenv-graph-ml32768-20260601T050633Z.json`
- endpoint benchmark:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qualityenv-graph-p512n1536-r2-20260601T050839Z.json`
- mean output throughput after first chunk: `82.0487 tok/s`
- mean total throughput: `107.148 tok/s`

## Results

All throughput rows use the OpenAI `/v1/completions` streaming endpoint with
`512` prompt tokens, `1536` output tokens, TP4, 32K context unless noted.

| Setting | Quality | Output tok/s | Total tok/s | Decision |
| --- | --- | ---: | ---: | --- |
| quality-safe baseline | pass | `82.0487` | `107.148` | old serve default |
| `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1` | pass | `82.6854` | `107.899` | promote |
| `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`, eager 2K | pass | not benchmarked | not benchmarked | graph required |
| `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`, graph 32K | fail: all NUL output | n/a | n/a | reject |
| `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=0` | pass | `82.3183` | `107.420` | reject |
| qk-helper plus `ATTN_DELAY_ALLREDUCE=0` | pass | `82.4583` | `107.585` | reject |
| qk-helper, graph 2K context | pass | `82.1484` | `107.006` | reject |
| qk-helper plus `--stream-interval 8` | pass | `82.7617` old, `82.7078` corrected | `107.996` | optional |
| qk-helper plus `--stream-interval 16` | pass | `82.6700` old, `82.6162` corrected | `107.871` | reject |
| qk-helper, vLLM-random prompt, `--disable-log-stats` | not rerun; same safe env | `82.3904` corrected | `107.493` | reject |
| restore-weight plus `VLLM_MINIMAX_QK_NORM_COMPILE_USE_PARAM=1`, graph 32K | fail: all NUL output | n/a | n/a | reject |
| restore-weight, qk-helper disabled, graph 2K | fail: all NUL output | n/a | n/a | reject |

## Artifacts

- qk-helper quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-qkhelper1-graph-ml32768-20260601T051709Z.json`
- qk-helper endpoint:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-graph-p512n1536-r2-20260601T051723Z.json`
- restore-weight eager quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-eager-ml2048-20260601T052041Z.json`
- restore-weight graph failure:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-graph-ml32768-20260601T052241Z.json`
- attention-delay-off quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-attndelay0-graph-ml32768-20260601T052432Z.json`
- attention-delay-off endpoint:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-attndelay0-graph-p512n1536-r2-20260601T052446Z.json`
- qk-helper plus attention-delay-off endpoint:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-attndelay0-graph-p512n1536-r2-20260601T052801Z.json`
- qk-helper 2K endpoint:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-graph-ml2048-p512n1536-r2-20260601T053411Z.json`
- stream interval 8 endpoint:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-streamint8-graph-p512n1536-r2-20260601T053846Z.json`
- stream interval 16 endpoint:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-streamint16-graph-p512n1536-r2-20260601T054153Z.json`
- vLLM-random prompt plus `--disable-log-stats` endpoint:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-disablelogstats-vllmrandom-graph-p512n1536-r2-20260601T123011Z.json`
- restore-weight plus compile-param graph failure:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-param1-graph-ml32768-20260601T125336Z.json`
- restore-weight plus qk-helper-disabled graph failure:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-qk0-graph-ml2048-20260601T130428Z.json`

## Decisions

- Promote `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1` as the REAP OpenAI serve default.
  It is the only tested math-equivalent toggle with a repeatable positive
  endpoint result and no NUL/NaN symptom.
- Keep `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=0`. It is graph-unsafe on this
  lane even though the eager 2K smoke is clean.
- Keep `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`. Disabling delayed attention
  allreduce is quality-clean but slower here.
- Add `VLLM_STREAM_INTERVAL` to the serve wrapper for easy streaming cadence
  screens. `VLLM_STREAM_INTERVAL=8` is a small endpoint win and cuts streaming
  text chunks from about `1536` to `193`, but it changes client-visible cadence,
  so leave it opt-in.
- Do not treat `82.7078` as a meaningful improvement. It is only a tiny
  endpoint-cadence delta versus qk-helper and remains far below the archived
  `89.49922316987691 output tok/s` LocalMaxxing result.

## Next Work

- The OpenAI endpoint is still far below the archived offline `89.499 tok/s`
  record. The remaining gap is not explained by `max_model_len` alone; a 2K
  OpenAI server remained around `82.15 tok/s`.
- The next meaningful source-level target remains the E=192 MiniMax logits
  workspace path: make it graph-safe from a fresh cache, quality-clean, and
  faster than the current no-logits OpenAI server path.
- Add stricter task-adherence checks to the OpenAI quality smoke. The current
  smoke catches corruption and NUL/NaN symptoms but still accepts reasoning-style
  prompt restatement.
- Source-level work on restore-weight graph safety is the main remaining path
  for a sizable quality-preserving win. Prompt shape, log-stat overhead, stream
  cadence, and output-kind selection did not explain the gap.
- The restore-weight failure reproduces even with qk-helper disabled at 2K
  context, so do not focus only on the qk-helper custom op.
