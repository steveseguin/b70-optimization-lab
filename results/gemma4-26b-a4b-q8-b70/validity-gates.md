# Gemma 4 26B A4B Validity Gates

This lane optimizes speed without accepting an INT4-quality downgrade. A result
is not a record just because it is fast.

## Required Identity

Every run summary must include:

- model repo, filename, revision or commit where available;
- quantization and KV cache precision;
- runtime (`llama.cpp`, vLLM, Ollama, or other) and source commit;
- exact GPU layout: one process per GPU, TP, DP, RPC, or other;
- GPU index / `ONEAPI_DEVICE_SELECTOR`;
- prompt tokens, generated tokens, max context, batch/ubatch;
- relevant env vars (`GGML_SYCL_*`, `ONEAPI_DEVICE_SELECTOR`,
  `UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS`, vLLM graph flags, etc.);
- whether multimodal/image input was enabled.

## Quality Rules

- Default lane is Q8 / INT8-or-better. Do not promote INT4 AutoRound, Q4_K,
  IQ4, or lower-precision runs into this folder unless explicitly labeled as a
  lower-quality side experiment.
- A runtime result must pass deterministic text canaries before it is compared
  against other speed results.
- If using a different precision mix, document why it should be quality-neutral
  or quality-positive. Examples: int8 weight-only, Q8 GGUF, BF16, or FP16 KV.
- Multimodal support is optional for the initial speed lane. If claimed, add a
  separate image smoke result.

## Initial Text Canaries

Use temperature `0`, fixed seeds when supported, and repeat enough times to
catch nondeterministic runtime bugs:

- JSON canary: answer `42`, unit `widgets`.
- Sorting canary: output exactly `blue, green, orange, red`.
- Arithmetic canary: simple multi-step arithmetic with exact final answer.
- Code canary: small Python function with deterministic behavior.
- Repeat canary: run at least 32 repeats for early smoke, 96+ repeats before
  promoting a record.

The Qwen lane demonstrated that smoke passes can hide 1-in-30 or 1-in-100
runtime corruptions. Full promotion needs repeat depth, not a single lucky run.

## Speed Metrics

Report at least:

- output tokens per second after TTFT, per request;
- wall-clock output tokens per second, per request;
- aggregate output tokens per second across four replicas, if running all GPUs;
- TTFT and wall time;
- prompt and completion token counts.

For LocalMaxxing or cross-model comparison, prefer corrected/generated output
throughput rather than total client throughput. Label total-token throughput
separately.

## Promotion Thresholds

The first baseline can be promoted if it is quality-valid and reproducible, even
if slow. Later "best" claims require:

- same model and precision, or a clearly justified higher-quality precision;
- same prompt/output shape;
- at least two independent repeat runs or one deep repeat run plus a matching
  reproduction command;
- no unresolved correctness failures in the same runtime/config family.
