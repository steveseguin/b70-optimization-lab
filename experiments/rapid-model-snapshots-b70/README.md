# Rapid Model Snapshots On B70

This lane is for quick, honest short-context decode snapshots across practical
models on the 4x Intel Arc Pro B70 system. The goal is not to deeply optimize
every model immediately. The goal is to get a reproducible, reasonably tuned
baseline for useful model families, publish only strict-valid final rows, and
leave enough notes that a future deeper lane can resume without rediscovery.

## Current Policy

- Use one model replica on one B70 whenever it fits. Use all four GPUs for
  parallel independent variants, same-window repeats, or variance checks.
- Prefer llama.cpp GGUF for fast first screens of Q4/Q6/Q8 variants. Use vLLM
  when a model has an Intel/AutoRound path or llama.cpp support is weak.
- Keep Gemma 4 26B Q8 on NVMe. It is a future production candidate and should
  not be archived unless a working symlink/hot replacement is made deliberately.
- Use `/mnt/usb-models` for inactive model archives and overflow downloads.
- Do not submit synthetic, warmed, repeated-output, n-gram-history, prefix-cache,
  slot-restore, or context-checkpoint speedups as headline throughput.
- Final publish candidates must pass the shared strict suite:
  `repro/rapid-model-snapshots-b70/realistic-suite-v1.json`.

## Final Gate

Headline results require:

- fixed realistic prompt suite;
- each prompt sent exactly once as a cold first response;
- `cached_tokens=0` for every request;
- prompt/KV/context/response reuse disabled;
- no n-gram/history acceleration based on earlier benchmark outputs;
- target model and quantization unchanged during the run;
- speculation/MTP only when accepted tokens are verified by the declared target;
- primary metric: median generated-token throughput for tokens 1-100 after TTFT;
- p10, mean, TTFT, wall-clock/full-output tok/s, prompt/output hashes, model
  identity, runtime commit, flags, and logs captured.

Diagnostic runs can be looser, but must be labeled diagnostic and never promoted
or submitted.

## Candidate Priority

1. Qwen3 30B-A3B / Qwen3-Coder 30B-A3B: best new vLLM/XPU target because the
   Intel/vLLM path is likely to support this MoE family directly. Start with
   GPTQ/INT4 or dynamic-FP8 style paths if available, then use GGUF as fallback.
2. Mistral Small 3.2 24B Instruct GGUF: first llama.cpp dense-model target,
   useful quality/performance reference, likely to fit one B70 at Q4/Q6/Q8.
3. Gemma 4 12B INT4/AutoRound or GGUF: small high-throughput production
   baseline and useful vLLM vs llama.cpp comparison.
4. Phi-4 family: smaller high-throughput reference; include if setup is quick.
5. DeepSeek-R1-Distill-Qwen 14B/32B: reasoning-family reference if the first
   three lanes are stable.

Do not spend rapid-lane time on Kimi K2.x, GLM 5.2, DeepSeek V4 Flash, or other
models whose local footprint clearly exceeds a clean one-B70 or practical TP
setup. Record them as skipped with the reason instead.

## Per-Model Workflow

1. Record model source, exact file/revision, quantization, size, and storage
   location.
2. Start from a conservative baseline: one GPU, no cache reuse, short context,
   deterministic sampling, no speculation unless the model/runtime has a proven
   verifier path.
3. Run a fast diagnostic decode screen to verify the endpoint and rough speed.
4. Try quick knobs that historically mattered:
   `ctx`, `batch`, `ubatch`, FlashAttention, VMM, graph/JIT/AOT build choice,
   polling, thread counts, KV dtype, MTP draft settings where available, and
   model-specific feature flags.
5. If a candidate appears within the noise band, run same-window repeats across
   multiple GPUs and compare to a control. Do not declare sub-1% wins from a
   single run.
6. Promote only after the strict realistic suite passes with all cached tokens
   zero.
7. Write a result packet under `results/rapid-model-snapshots-b70/<model>/`,
   a repro command/script when useful, and a LocalMaxxing queue entry only for
   strict-valid rows.

## Storage Rules

- Hot active models: `/mnt/fast-ai/llm-models`.
- Hugging Face cache: `/mnt/fast-ai/llm-cache/hf` when the model is actively
  being tested; `/mnt/usb-models/llm-cache/hf` or `/mnt/usb-models/models` for
  archival copies.
- Archive by copying first, verifying size/checksum where practical, then
  replacing the old source with a clear symlink only if a script expects that
  path.
- Never move Gemma 4 26B Q8 away from its known-good fast path without updating
  its production-service and repro docs.

## Result Ledger

Use `results/rapid-model-snapshots-b70/README.md` for promoted or useful final
snapshots. Use this experiment folder for active notes, failed ideas, and
diagnostic-only screens.

Current promoted rapid rows:

- `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF`
  `Qwen3-30B-A3B-Instruct-2507-UD-Q4_K_XL.gguf`, llama.cpp/SYCL on one B70:
  `107.48388363267362 tok/s` median tokens 1-100 after TTFT under the strict
  fresh-response gate. See
  `results/rapid-model-snapshots-b70/qwen3-30b-a3b-instruct-2507-udq4/README.md`.
  The key policy fix was disabling llama.cpp request prompt reuse with
  `{"cache_prompt":false}`; default `cache_prompt=true` produced
  `cached_tokens=3` and is invalid for headline fresh-response throughput.
- `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF`
  `Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf`, llama.cpp/SYCL on one B70:
  `108.1165394591524 tok/s` median tokens 1-100 after TTFT under the same
  strict fresh-response gate. See
  `results/rapid-model-snapshots-b70/qwen3-coder-30b-a3b-instruct-udq4/README.md`.
- `unsloth/GLM-4.7-Flash-GGUF`
  `GLM-4.7-Flash-UD-Q4_K_XL.gguf`, llama.cpp/SYCL on one B70:
  `40.7691297367011 tok/s` median tokens 1-100 after TTFT under the strict
  fresh-response gate. See
  `results/rapid-model-snapshots-b70/glm-4.7-flash-udq4/README.md`. This is a
  valid expected-performance snapshot, not a frontier row; faster concurrent
  four-GPU screen rows were not used as the headline.
- `bartowski/microsoft_Phi-4-mini-instruct-GGUF`
  `microsoft_Phi-4-mini-instruct-Q4_K_M.gguf`, llama.cpp/SYCL on one B70:
  `96.54834088986573 tok/s` median tokens 1-100 after TTFT under the strict
  fresh-response gate. The Q8_0 reference row is `72.24629337909391 tok/s`.
  See `results/rapid-model-snapshots-b70/phi4-mini-instruct-gguf/README.md`.
  This lane showed why small-model records must be confirmed standalone: the
  four-GPU concurrent screen underreported the same Q4 recipe at about
  `74.8 tok/s`.

## Helpers

- `scripts/run-rapid-llamacpp-realistic-candidate.sh` runs one strict
  llama.cpp/SYCL candidate with prompt cache disabled and writes compact JSON
  evidence plus raw logs.
- `scripts/run-rapid-llamacpp-fourway-screen.sh` launches up to four one-GPU
  strict candidate variants in parallel across the B70s. Use it for first-pass
  screens only; promote from a standalone confirmation row after reviewing the
  best variant.
