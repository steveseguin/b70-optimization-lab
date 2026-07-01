# Qwen3.6 INT8 N-Gram No-Chunk MBT32768 Rejected

Date: 2026-06-10

## Context

The earlier n-gram speculative candidate showed a single-request speed win, but
failed c2 reliability when chunked prefill mixed a waiting prefill with a
running speculative decode. This screen tested the same no-draft-model n-gram
idea with chunked prefill disabled at a valid 32K setting:

- `--no-enable-chunked-prefill`
- `--max-num-batched-tokens 32768`
- `--max-num-seqs 48`
- prefix caching disabled
- TP4, 32K context, Quark W8A8 INT8, BF16 runtime
- XPU PIECEWISE graph capture, max capture size `128`
- speculative config:

```json
{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_min":2,"prompt_lookup_max":5}
```

This should preserve target-model quality in principle because the target model
verifies prompt-lookup draft tokens. The purpose here was first to see whether
removing chunked prefill kept the earlier speed win without the c2 crash.

## Startup

The runtime started successfully.

Important startup facts:

- vLLM warned that this model does not officially support disabling chunked
  prefill.
- Async scheduling was disabled because n-gram speculative decoding does not
  support it.
- compile range: `(1, 32768)`
- graph capture sizes: 19 sizes, through `128`
- model load memory: `8.58 GiB`
- available KV cache memory: `18.37 GiB`
- GPU KV cache size: `1,459,705 tokens`
- reported maximum concurrency for 32K requests: `44.55x`
- graph capture: `14 s`, `1.60 GiB`

Log:

- `/tmp/qwen36-quark-int8-tp4-ngram5-cg128-nochunk-mbt32768-20260610.log`

## Single-Request Speed Gate

Artifact:

- `data/qwen36-quark-int8-tp4-ngram5-cg128-nochunk-mbt32768-single-20260610.json`

p512/n512, stream mode, eight measured repeats:

- corrected output tok/s after first streamed chunk mean: `98.10297085386148`
- output tok/s end-to-end mean: `94.25329296832349`
- client TTFT mean: `75.39676626038272 ms`

Current accepted no-prefix control from the refreshed gate:

- corrected output tok/s after first streamed chunk mean: `98.7741`
- output tok/s end-to-end mean: `97.5295`
- client TTFT mean: `76.28 ms`

This candidate is not a speed win. Corrected decode speed is slightly lower than
control and end-to-end output speed is clearly lower.

## Speculation Behavior

The runtime reported low n-gram acceptance during the speed gate:

- mean acceptance length: about `2.47`, then `2.19`
- average draft acceptance rate: about `30.6%`, then `24.3%`

That acceptance rate is too low to compensate for disabled async scheduling and
speculation overhead on this non-repetitive single-request gate.

## Decision

Reject this no-chunk n-gram speculative candidate at the speed gate.

I did not run the full quality and reliability suites because the candidate
already failed the required no-quality-loss performance condition. No serving
change was accepted.

## Restore

After rejection, I restored the accepted backend:

- tmux session: `qwen36-tp4-noprefix-32k`
- endpoint: `http://127.0.0.1:18080`
- model name: `qwen36-35b-a3b-fp8`
- prefix caching disabled
- async scheduling enabled
- reported maximum concurrency for 32K requests: `62.65x`
- `/health`: pass
- `/v1/completions` smoke: pass, returned `qwen36 smoke ok` after the raw
  thinking wrapper

Keep the accepted runtime on the no-prefix TP4 32K profile while pursuing the
next no-quality-loss speed path.
