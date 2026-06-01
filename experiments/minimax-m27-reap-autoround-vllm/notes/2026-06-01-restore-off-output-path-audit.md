# 2026-06-01 Restore-Off Output Path Audit

Goal: explain the `82.7078` OpenAI endpoint result, verify whether the
`89.49922316987691 output tok/s` path still works under quality-safe settings,
and avoid promoting a regression.

## Summary

`82.7078 output tok/s` is not a meaningful improvement over the archived REAP
record. It is only a tiny OpenAI streaming-cadence change versus the
quality-safe qk-helper endpoint, and it remains well below the archived
LocalMaxxing result.

The important correction from this pass is that the direct benchmark wrapper was
not preserving `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT` overrides after sourcing the
older MiniMax promoted env. That means the earlier "restore-off" direct result
around `85.8 output tok/s` was actually still running with restore-weight on.

The wrapper now preserves:

- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS`

## Endpoint Follow-Up

Prompt shape and log-stat overhead did not explain the endpoint gap:

- artifact:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/openai-endpoint-qkhelper1-disablelogstats-vllmrandom-graph-p512n1536-r2-20260601T123011Z.json`
- prompt kind: vLLM `RandomDataset`, `512` prompt tokens, `1536` output tokens
- server: qk-helper on, restore-weight off, delayed attention allreduce on,
  `--disable-log-stats`
- corrected output throughput: `82.39036990907539 tok/s`
- total throughput: `107.49263424479153 tok/s`

This is worse than the earlier qk-helper endpoint result and far below the
archived offline `89.49922316987691 output tok/s` record.

Trying to serve the preserved fast `f728d2c0cf` cache also failed:

- preserved root:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-sweep-moe-full-forward0-20260531T193000Z`
- failure: `ValueError: not enough values to unpack (expected 811, got 749)`
- interpretation: that stale backbone and the current server/AOT argument layout
  are not compatible.

## Direct Restore-Off Check

After fixing the wrapper override preservation, a true restore-off direct run was
much slower on the first request after a fresh compile:

- artifact:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T124258Z.json`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-restore0-safe-20260601T124258Z`
- backbone key: `d4d78c1656`
- AOT key: `baed0971531a4824474916a783ca5bfc09780742bb50b650626b0864e2fa9c2f`
- elapsed: `28.89871882200532 s`
- total throughput: `70.86819359066267 tok/s`
- output throughput: `53.151145192997 tok/s`

A warmed repeat against the same cache root recovered to the low-80s band:

- artifact:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T124723Z.json`
- elapsed: `19.052092138008447 s`
- total throughput: `107.49475622754791 tok/s`
- output throughput: `80.62106717066092 tok/s`

This aligns with the OpenAI endpoint rather than the archived `89.5` result.

## Output-Kind Probe

The direct async output-kind helper was added to compare vLLM
`RequestOutputKind` modes in one process.

Diagnostic artifact:

`/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/direct-async-outputkind-qkhelper1-restore0-p512n1536-20260601T125504Z.json`

This run should be interpreted cautiously because it was launched from the older
promoted env and enabled the MiniMax logits-WS decode path. It is still useful
for the output-mode question:

| Output kind | Output tok/s | Chunks |
| --- | ---: | ---: |
| `FINAL_ONLY` | `81.75603118953512` | `1` |
| `CUMULATIVE` | `81.44655120219124` | `1536` |
| `DELTA` | `81.90052970625766` | `1536` |

Output-kind selection is not the dominant limiter for the restore-off path. The
quality-safe decode rate is bounded by the model/runtime path itself.

## Restore-Weight Graph Quality

Restore-weight remains graph-unsafe on the OpenAI server path.

I tested a targeted variant with:

- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=1`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`
- `VLLM_MINIMAX_QK_NORM_COMPILE_USE_PARAM=1`
- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`

Quality artifact:

`/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-param1-graph-ml32768-20260601T125336Z.json`

Result: failed. All three prompts generated `192` NUL characters. This rejects
the variant before benchmarking.

I also tested restore-weight with the qk-helper disabled at 2K compiled OpenAI
context:

- `VLLM_MINIMAX_QK_RMS_XPU_HELPER=0`
- `VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`
- `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=1`
- `VLLM_MAX_MODEL_LEN=2048`

Quality artifact:

`/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/openai-quality-smoke-restore1-qk0-graph-ml2048-20260601T130428Z.json`

Result: failed with the same all-NUL signature: all three prompts generated
`192` NUL characters. This narrows the failure to the restore-weight graph path
rather than the qk-helper custom op.

## Restore-Weight NaN Trace

I traced the failing restore-weight/qk-helper-off compiled 2K server with finite
checks around the final model layers:

- cache root:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-serve-restore1-qk0-ml2048-20260601T130024Z`
- first trace:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/restore1-qk0-finite-trace-20260601T130641Z.jsonl`
- layer-boundary trace:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/restore1-qk0-layer-boundary-trace-20260601T130915Z.jsonl`
- tiny request:
  `Say OK and nothing else.`, `max_tokens=8`
- observed response: eight NUL characters

The first trace showed that all `200064` logits were NaN and that NaNs were
already present in the final hidden state, so this is not a sampler or OpenAI
serialization problem.

The layer-boundary trace narrowed the failure further:

| Tag | Bad rows | Last row finite state |
| --- | ---: | --- |
| `minimax.layer58.input` | `0/16` | finite |
| `minimax.layer58.after_attn` | `0/16` | finite |
| `minimax.layer58.after_moe` | `0/16` | finite |
| `minimax.layer59.input` | `0/16` | finite |
| `minimax.layer59.after_attn` | `0/16` | finite |
| `minimax.layer59.after_moe` | `0/16` | finite |
| `minimax.layer60.input` | `0/16` | finite |
| `minimax.layer60.after_attn` | `0/16` | finite |
| `minimax.layer60.after_moe` | `0/16` | finite |
| `minimax.layer61.input` | `0/16` | finite |
| `minimax.layer61.after_attn` | `4/16` | all `135168` values NaN |
| `minimax.layer61.after_moe` | `4/16` | all `135168` values NaN |
| `minimax.model.final_hidden` | `4/16` | all `135168` values NaN |
| `gpu_model_runner.sample_hidden_states` | `32/32` | all `3072` values NaN |
| `gpu_model_runner.logits_after_compute` | `32/32` | all `200064` values NaN |

Interpretation: restore-weight graph mode is corrupting inside the final
attention block, not in the preceding MoE, final norm, logits processor, or
sampler. The next source-level target should be layer 61 attention under
`VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1`, especially the restore-weight
normalization path as captured by XPU graph with TP collectives.

## Decision

- Do not promote `82.7078`; it is a regression relative to the archived
  LocalMaxxing result and not a meaningful endpoint win.
- Keep the OpenAI serve path on qk-helper, restore-weight off, delayed attention
  allreduce on.
- Treat the archived `89.49922316987691 output tok/s` result as valid history,
  but not currently reproduced under the quality-safe runtime path.
- The next sizable improvement likely requires source work on the restore-weight
  graph-safety issue or another model-forward/MoE fusion path. Endpoint prompt
  shape, log stats, stream cadence, output-kind selection, and disabling the
  qk-helper around restore-weight are not enough.
- The concrete restore-weight bug target is now final-layer attention: layer 61
  enters attention finite and leaves attention all-NaN in compiled graph mode.
