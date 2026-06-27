# Gemma 4 26B A4B Validity Gates

This lane optimizes speed without accepting an INT4-quality downgrade. A result
is not a record just because it is fast.

## Required Identity

Every run summary must include:

- model repo, filename, exact byte size, and revision or commit where
  available;
- quantization, weight file flavor, and KV cache precision;
- runtime (`llama.cpp`, vLLM, Ollama, or other) and source commit;
- exact GPU layout: one process per GPU, TP, DP, RPC, or other;
- GPU index / `ONEAPI_DEVICE_SELECTOR`;
- prompt tokens, generated tokens, max context, batch, ubatch, and `--poll`;
- API path (`chat/completions` or raw `completions`) and seed;
- flash attention / `-fa` state;
- reasoning / thinking mode;
- llama.cpp device mapping (`-dev`, `--n-gpu-layers`) or vLLM device/env
  mapping;
- relevant env vars (`GGML_SYCL_*`, `ONEAPI_DEVICE_SELECTOR`,
  `UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS`, vLLM graph flags, etc.);
- server log path and benchmark JSON path;
- whether multimodal/image input was enabled.

## Quality Rules

- Default lane is Q8 / INT8-or-better. Do not promote INT4 AutoRound, Q4_K,
  IQ4, or lower-precision runs into this folder unless explicitly labeled as a
  lower-quality side experiment.
- A runtime result must pass deterministic **chat** text canaries before it is
  compared against other speed results. Raw-completion probes are diagnostic
  unless explicitly labeled.
- If using a different precision mix, document why it should be quality-neutral
  or quality-positive. Examples: int8 weight-only, Q8 GGUF, BF16, or FP16 KV.
- Multimodal support is optional for the initial speed lane. If claimed, add a
  separate image smoke result.

## Initial Text Canaries

Use temperature `0`, fixed seeds when supported, and repeat enough times to
catch nondeterministic runtime bugs. The repo harness defaults to
`/v1/chat/completions` and `seed=1`:

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
- repeat statistics when repeats are available: mean, median, min, max,
  standard deviation, and coefficient of variation.

Promoted throughput requires non-null server `usage.completion_tokens`.
Diagnostic runs may use `--allow-missing-usage`, but those are not record
evidence until token counting is fixed.

For LocalMaxxing or cross-model comparison, prefer corrected/generated output
throughput rather than total client throughput. Label total-token throughput
separately.

## Realistic Final Gate For Promotion

Diagnostic benchmarks may use synthetic or repetitive prompts while searching
for optimization ideas. A result may be confirmed, promoted, or submitted only
if it passes the realistic final gate:

- Use the fixed prompt suite at
  `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`.
- Run each prompt exactly once as a cold first response.
- Require `cached_tokens=0` for every request.
- Disable prompt/KV cache reuse, context checkpoints, response reuse,
  n-gram/history acceleration, and warmed repeated prompts.
- Keep the target model and quantization unchanged.
- Allow speculative decoding/MTP only when accepted tokens are verified by the
  declared target model.
- Primary metric: median tok/s for generated tokens 1-100 after TTFT across the
  suite.
- Also report p10, mean, TTFT, wall-clock tok/s, full 512-token tok/s,
  prompt/output hashes, model identity, runtime commit, env vars, flags, and
  logs.

Run it with the Gemma harness by setting `REALISTIC_GATE=1`; this writes
`realistic-suite.json` and embeds `realistic_final_gate` in `summary.json`.

## Fresh-Response Vs Warmed/History Throughput

Headline throughput must apply to the realistic final gate above. A single
synthetic first row may be useful for diagnosis, but it is not enough for
promotion or LocalMaxxing submission.

Speculation is allowed, including MTP, draft-model speculation, n-gram
speculation, and verifier-based multi-token acceptance. The validity question
is whether the draft source could operate on a fresh request without already
having seen the target response.

Separate every speculative result into:

- **Fresh-response throughput**: no prior identical or highly similar generated
  continuation is available. Draft-MTP with an independent draft model belongs
  here when `cached_tokens=0` and the canaries pass.
- **Warmed/history throughput**: prior benchmark requests, repeated prompts,
  repeated outputs, context checkpoints, response reuse, prefix/KV reuse, or
  n-gram history make the same continuation predictable. These runs are useful
  artifacts, but they are not valid fresh-response headline records.

If a benchmark mixes a cold first request with warmed repeated requests, report
the first-request throughput separately and do not average warmed repeats into
the fresh-response number. A draftless n-gram/history run that becomes fast only
after the first identical output must be labeled history-accelerated and must
not be submitted or promoted as fresh-response throughput.

The older benchmark harness supports `BENCH_PROMPT_MODE=filled-long-unique` and
`filled-fixed-line-unique` for fresh-response aggregate checks. These modes
generate a deterministic different prompt per repeat and store each row's
`prompt_sha256`. For those modes, the repeated-row mean may be treated as a
fresh-response mean only when:

- `fresh_response_validity.prompts_are_unique` is true;
- every row has a distinct prompt hash;
- every reported `cached_tokens` value is `0`;
- the same canary and model-identity gates pass.

For historical `filled-long` and `filled-fixed-line` runs, keep the conservative
policy: all rows are diagnostic unless the fixed realistic suite passes. Earlier
"row0 fresh" labels in the repo should be read as pre-final-gate terminology,
not as publishable real-world throughput.

Single-GPU records and four-replica aggregate capacity are different modes.
Record and submit them separately: one full model on one B70 is the primary
single-session decode record; four independent servers are an aggregate service
capacity result only after each replica passes the same canary gate.

## Promotion Thresholds

The first baseline can be promoted if it is quality-valid and reproducible, even
if slow. Later "best" claims require:

- same model and precision, or a clearly justified higher-quality precision;
- same prompt/output shape;
- at least two independent repeat runs or one deep repeat run plus a matching
  reproduction command;
- no unresolved correctness failures in the same runtime/config family.
- LocalMaxxing payload dry-run passes, and the payload links back to this repo's
  result packet or supporting artifacts.
