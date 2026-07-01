# Qwen3.6 INT8 N-Gram Speculative Startup Failure

Date: 2026-06-10

## Context

I tested vLLM n-gram speculative decoding on the accepted Qwen3.6 INT8
no-prefix runtime.

The goal was to check a quality-preserving speculation path that does not use a
separate draft model. N-gram speculation proposes tokens from prompt lookup and
the target model verifies them, so it should preserve target-model output when
the implementation is working correctly.

Everything else stayed aligned with the accepted runtime:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- runtime dtype: BF16
- quantization: Quark W8A8 INT8
- tensor parallelism: TP4
- context cap: 32K
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce collectives
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`

Candidate speculation config:

```json
{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_min":2,"prompt_lookup_max":5}
```

## Startup Behavior

The runtime accepted the config and began startup. The log showed:

- async scheduling was disabled because n-gram speculation does not support it
- model load succeeded
- KV cache profiling succeeded
- graph capture expanded from the accepted runtime's 15 capture sizes to 51
  capture sizes, up to 512
- graph capture reached `47/51`

After that, the log stopped updating. The endpoint never reached `/health`, the
tmux session disappeared, and the vLLM worker PIDs were gone. There was no
explicit Python traceback or `EXIT` line in the captured log.

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-ngram5-startup-fail-20260610.json`

Log:

- `/tmp/qwen36-quark-int8-tp4-piecewise-graph-ngram5-32k-noprefix.log`

## Decision

Reject n-gram speculative decoding for the current Qwen3.6 INT8 XPU runtime.
This candidate did not reach the health gate, so no speed or quality benchmark
is valid.

Even before the failure, the startup log showed two practical concerns for this
runtime:

- n-gram speculation disables async scheduling, which already regressed
  single-request decode in the separate sync-scheduling screen
- graph capture expands to many more sizes, increasing startup and reliability
  risk for the current XPU graph recipe

## Restore

I restored the accepted no-prefix runtime after the failed startup screen:

- session: `qwen36-tp4-noprefix-32k`
- backend `/health`: pass
- backend `/v1/completions`: pass, returned `OK` after the raw thinking wrapper
- frontdoor `/v1/chat/completions`: pass, returned exactly `OK`

Keep the accepted runtime on the no-prefix TP4 32K profile.
