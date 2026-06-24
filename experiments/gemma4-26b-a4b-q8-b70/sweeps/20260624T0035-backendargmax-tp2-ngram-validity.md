# 2026-06-24T0035: backend argmax, TP=2, and fresh n-gram validity checks

Goal: keep pushing Gemma 4 26B A4B Q8 on B70 for **fresh-response**
single-session decode, while obeying the validity rule that warmed repeated
continuations and history-populated n-gram speedups are not headline fresh
throughput.

Current valid fresh record remains:

- `gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z`
- canary: `384/384`
- fresh first request after TTFT: `92.397 tok/s`
- mean after TTFT: `92.767 tok/s`
- cached prompt tokens: `0`
- prompt mode: `filled-long`

Post-cleanup sanity control after removing the losing backend-argmax hook from
live source:

- `gemma4-q8-gpu0-mtp-n7-cleanrebuild-control-20260624T0046Z`
- canary: `32/32`
- fresh first request after TTFT: `93.616 tok/s`
- wall: `80.215 tok/s`
- cached prompt tokens: `0`
- Same promoted MTP recipe as the record stack. Treat as a healthy smoke / noise
  range confirmation, not as a new strategic lane.

## Backend draft argmax smoke

Run:

- `gemma4-q8-gpu0-mtp-n7-backendargmax-smoke-20260624T0029Z`
- summary: `data/gemma4-q8-gpu0-mtp-n7-backendargmax-smoke-20260624T0029Z/summary.json`
- patch snapshot: `patches/gemma4-llamacpp-mtp-record-stack-plus-backendargmax-negative-20260624.patch`

Result:

- canary: `32/32`
- fresh first request after TTFT: `91.891 tok/s`
- wall: `78.837 tok/s`
- cached prompt tokens: `0`

Interpretation:

- This is valid, but **not a win** over the `92.397 tok/s` first-request record.
- The patch did remove the draft full-vocab host scan (`vocab_scanned=0`), but the
  draft decode path itself became slightly slower. Server profile for the measured
  request:
  - `draft_decode_ms=1408.049`
  - `sampler_ms=2.893`
  - `draft_decodes=910`
  - `draft_decode_tokens=910`
  - `vocab_scanned=0`
- Do not promote as the record path. Keep the patch as evidence because it proves
  the full-vocab draft scan is not the current dominant limiter once draft decode
  itself is serial.
- The live source and harness were cleaned back to the promoted MTP path after this
  run. The backend-argmax code/env hook exists only in the patch snapshot and run
  data, not in the active source.

## TP=2 startup checks

Tensor split run:

- `gemma4-q8-tp2-12-tensorsplit-faon-fitoff-mtpn7-smoke-20260624T0030Z`
- GPUs selected with `ONEAPI_DEVICE_SELECTOR=level_zero:1,2`
- `LLAMA_DEVICES=SYCL0,SYCL1`
- `LLAMA_SPLIT_MODE=tensor`
- `LLAMA_TENSOR_SPLIT=1,1`
- `FLASH_ATTN=on`
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0 --fit off'`

Outcome:

- Failed before readiness.
- Abort in `ggml_backend_sched_backend_id_from_cur`.
- Diagnostic:
  `pre-allocated tensor (cache_k_l28) in a buffer (Meta()) that cannot run the operation (NONE)`.

Row split run:

- `gemma4-q8-tp2-12-rowsplit-fitoff-mtpn7-smoke-20260624T0032Z`
- GPUs selected with `ONEAPI_DEVICE_SELECTOR=level_zero:1,2`
- `LLAMA_DEVICES=SYCL0,SYCL1`
- `LLAMA_SPLIT_MODE=row`
- `LLAMA_TENSOR_SPLIT=1,1`
- `FLASH_ATTN=off`
- `MTP_EXTRA_ARGS='--ctx-checkpoints 0 --fit off'`

Outcome:

- Failed before readiness.
- Segfault during server/model initialization.

Interpretation:

- TP=2 remains blocked by llama.cpp/Gemma4 shared-KV backend placement, not by
  benchmark quality or throughput.
- A previous cross-GPU target/draft attempt failed similarly:
  `pre-allocated tensor (cache_v_l28) in a buffer (SYCL0) that cannot run the operation (NONE)`.
- This should be reported as an Intel/llama.cpp scheduler-placement issue for
  Gemma4 shared KV / assistant contexts. It is not a usable optimization lane
  without source-level scheduler work.

## First-request-only n-gram validity control

Run:

- `gemma4-q8-gpu0-ngram-mod-20-32-64-firstonly-filledlong-20260624T0034Z`
- summary: `data/gemma4-q8-gpu0-ngram-mod-20-32-64-firstonly-filledlong-20260624T0034Z/summary.json`
- `--spec-type ngram-mod`
- `--spec-ngram-mod-n-match 20`
- `--spec-ngram-mod-n-min 32`
- `--spec-ngram-mod-n-max 64`
- `BENCH_REPEATS=1`
- prompt mode: `filled-long`

Result:

- canary: `32/32`
- fresh first request after TTFT: `41.407 tok/s`
- wall: `38.513 tok/s`
- cached prompt tokens: `0`

Interpretation:

- The old `>200 tok/s` n-gram averages should **not** be treated as fresh
  headline throughput for the promoted `filled-long` harness.
- On a single measured fresh request, n-gram-mod is far below MTP (`41.4` vs
  `92.4` tok/s). The old high numbers remain useful as history-accelerated /
  repeated-output evidence only.
- A control using old `filled-long-deep` failed because the current promoted
  benchmark script accepts only `default`, `long`, `filled-long`, and
  `filled-fixed-line`.

## Working conclusion

The current single-GPU Q8 path is limited by serial MTP draft decode:

- n=7 accepts well, but still performs one draft `llama_decode(ctx_dft)` per
  proposed token.
- Raising `n_max` above 7 was already tested and is slower.
- Backend argmax removes draft scan overhead, but does not reduce the serial
  draft-forward cost.
- TP=2 and cross-GPU draft/target split are blocked before benchmark by Gemma4
  shared-KV placement failures.
- First-only n-gram does not provide a fresh-response win on the promoted prompt.

Next useful engineering directions:

1. Fix llama.cpp Gemma4 shared-KV placement for TP=2/cross-GPU contexts.
2. Find or implement a MTP path that does not require serial full draft forwards
   for every proposed token.
3. Evaluate a different engine only if it supports Q8/INT8-quality Gemma4 on B70
   without falling back to a lower-quality quantization.

## Related upstream/current research

- vLLM GGUF support is documented as "highly experimental and under-optimized",
  with compatibility caveats:
  <https://docs.vllm.ai/en/stable/features/quantization/gguf/>.
- The same Unsloth Gemma4 GGUF family has a reported vLLM/Transformers GGUF
  startup failure:
  `ValueError: GGUF model with architecture gemma4 is not supported yet`
  (<https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/discussions/14>).
  This makes vLLM GGUF a poor near-term path for this exact Q8 artifact.
- llama.cpp issue `#21788` discusses split-mode tensor / meta-backend edge cases
  around KV cache quantization and has a small proposed implementation touching
  `ggml-backend-meta.cpp`, `llama-graph.cpp`, and `llama-kv-cache.cpp`:
  <https://github.com/ggml-org/llama.cpp/issues/21788>. It is not the same exact
  failure, but it is in the right subsystem for the TP=2 `Meta()/NONE` backend
  placement abort seen here.
- llama.cpp issue `#21468` documents Gemma4 shared-KV assumptions breaking cache
  reuse / prefix matching:
  <https://github.com/ggml-org/llama.cpp/issues/21468>. That aligns with our
  broader observation that Gemma4 shared KV is the fragile part when combining
  server cache behavior, assistants, and multi-device placement.
