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

## Thermal / Hardware Fairness

The current Gemma 26B Q8 record family has several-percent run-to-run variance.
For promoted record repeats and close A/B decisions, capture XPU telemetry
alongside the benchmark so temperature and throttling are not guessed after the
fact.

Recommended telemetry on this host:

```bash
sudo -S -p '' xpu-smi dump -d <gpu> -m 0,1,2,3,4,5,17,18,35 -i 1 \
  < /home/steve/SUDOPASSWORD.txt
```

Never print or copy the sudo password. Record only the resulting telemetry
file and summarize active core temperature start/max/end, memory temperature
start/max/end, power mean/max, frequency mean/min/max, and throttle reasons.
Flag real thermal-throttle samples. `Burst Power Excursion` should still be
recorded, but do not treat it as equivalent to sustained thermal throttling
without supporting frequency/power evidence.

The 2026-07-01 same-GPU thermal sweep did not find temperature to be the main
driver of current final-postnorm variance: four exact GPU0 full512 repeats
spanned `114.520-120.202 tok/s` while active core max stayed `77-78 C`, memory
max stayed `86-90 C`, frequency remained near max, and no thermal-throttle
samples appeared. See
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md`.

Do not compare a hot run against a cold historical outlier without telemetry,
same-recipe repeats, or a same-window control lane. Small deltas near the
frontier should be treated as variance until repeated under the fixed
realistic gate with `cached_tokens=0` and the exact same canary scale.

## Micro-Improvement / A/B Reliability Gate

Near the current Gemma record, single-run medians are too noisy for
micro-change decisions. The same-GPU thermal repeatability check measured
`2.324%` run-median CV and `4.409%` p90 pairwise absolute run-median delta for
the exact same recipe.

For source or config changes expected to move the short metric by only a few
percent, use paired same-window A/B blocks and analyze per-prompt ratios with:

```bash
scripts/analyze-gemma-realistic-ab.py \
  --control data/<control-1>/summary.json \
  --control data/<control-2>/summary.json \
  --candidate data/<candidate-1>/summary.json \
  --candidate data/<candidate-2>/summary.json
```

The candidate is a micro-win only if the paired bootstrap 95% lower bound of
the median candidate/control prompt ratio is above `+1.0%`, all candidate runs
pass the realistic final gate, and p10/full512/wall/TTFT/canary/telemetry do
not materially regress. Positive raw medians with a CI crossing zero are
`inconclusive_positive`, not promotable. See
`results/gemma4-26b-a4b-q8-b70/reliability-protocol.md`.

When the patch or config should only affect the target-side runtime, and not
MTP/speculation behavior, add the no-spec calibration check before deciding a
small delta:

- run the same fixed realistic suite with MTP/speculation disabled;
- keep `cached_tokens=0`, one cold response per prompt, no context checkpoints,
  no cache reuse, and no history/n-gram acceleration;
- compare control and candidate with the paired analyzer;
- use the result as diagnostic evidence for whether the target-side change is
  real;
- still rerun the normal MTP realistic final gate before promotion or
  LocalMaxxing submission.

The current no-spec calibration lane measured `0.330%` run-median CV and
`0.577%` p90 pairwise same-recipe delta, much tighter than the `4.409%` MTP
noise band. Use it to resolve target-side changes that are otherwise lost in
MTP variance. Do not use it for draft quality, verifier, acceptance-policy,
handoff, or p-min/n-min/n-max changes.

## Long-Context Service Gate

Prompt-processing and long-context service changes are useful only if they do
not weaken the short decode record or hide behind cache reuse. Use the fixed
long-context suite at
`repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json` and the harness
`scripts/bench-openai-long-context-suite.py`.

A long-context/prefill result may be promoted as a service candidate only when:

- each selected suite prompt is sent once as a cold first response;
- `cached_tokens=0` for every request;
- prompt hashes are unique across measured requests;
- the response is exact JSON and all case-specific fields match:
  `case_id`, `project_code`, `answer_phrase`, `sort_order`, and
  `arithmetic_result`;
- deterministic text canaries pass in the same launcher run;
- the target model, target quantization, draft model, and verification mode are
  unchanged from the declared recipe;
- a paired short fixed-suite guard is rerun afterward, and no short-decode
  regression is accepted for the promoted short-record recipe.

Report long-context/prefill results separately from the short decode record.
Use approximate prefill throughput (`prompt_tokens / TTFT`) only as a service
diagnostic, alongside TTFT, generated-token throughput after TTFT,
wall-clock throughput, prompt/output hashes, model identity, runtime commit,
env vars, flags, and logs. Do not submit long-context service diagnostics to
LocalMaxxing as the one-B70 short-decode headline unless the separate realistic
final gate also beats the current record.

Run the paired service gate with
`repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`; run the
paired short guard with
`repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh`.

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
