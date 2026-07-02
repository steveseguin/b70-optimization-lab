# Research Workflow Playbook

This page captures the prompts and approaches that produced the best outcomes
across the MiniMax, Gemma, and Qwen36 B70 work. Use it when starting a new model
lane or when an experiment series starts losing structure.

For the full start-to-finish operating manual, use
`model-optimization-guide.md`. This playbook is the shorter prompt and workflow
companion.

## Start With A Clear Target

Good opening prompt for a model lane:

```text
Build a model-specific result packet for <model> on <hardware>. First identify
the best valid result, the fastest invalid result, and the exact validity gates.
Then propose the next three experiments ranked by expected value. Do not change
code until the benchmark identity and current best artifact are clear.
```

Use a numeric target, not a vague target. For Qwen36 the real target was
`>150 tok/s`; treating `75 tok/s` as enough wasted time because it was below the
reason spec decode was being investigated.

## Identity Lock Prompt

Use this before changing code or launch flags:

```text
Compare this candidate run to the last known-good run. Diff model path,
revision, quantization, TP/PP, prompt/output shape, COMPILATION_CONFIG,
XPU graph flags, GPU memory utilization, fallback flags, async scheduling,
diagnostic flags, launcher path, and server log identity. Report only real
behavior changes after identity differences are ruled out.
```

This avoids the Qwen36 mistake where graph-none runs were compared with
PIECEWISE forced-comm graph runs.

## Hypothesis Funnel Prompt

Useful when asking Codex or another agent to generate many ideas:

```text
List up to 100 hypotheses, but mark each as significant or not significant.
For significant hypotheses, include why it could move the target metric, what
artifact would validate it, what patch/config would test it, and the expected
failure signature. Stop expanding a branch once it is clearly dominated by a
cheaper or already-tested branch.
```

This keeps large idea lists useful. It is better to reach 20 well-ranked
significant ideas than to create 1000 undifferentiated tasks.

## Code-Audit Prompt

Use this when a bug is likely in runtime state handling:

```text
Read the exact functions that save, restore, advance, or commit model state for
this path. Identify every tensor/buffer that is read by graph replay or reused
across requests. Then list which state is covered by the current snapshot and
which state is blind to it. Do not propose a fix until the state ownership is
explicit.
```

This was useful in Qwen36 because ReplaySSM/GDN correctness depended on state
outside the normal KV cache.

## Validation Ladder

Use this ladder before promoting any speed result:

1. Smoke: tiny repeats to prove the harness starts and the config is coherent.
2. Canary scale-up: JSON and deterministic color/order canaries at high repeat
   count.
3. Quality suite: semantic, arithmetic, repeatability, and long-context checks
   relevant to the model.
4. Metrics repeat: output-token throughput, total throughput, TTFT, and
   context shape.
5. Lock run: repeat the full gate after the first pass if the prior bug was
   intermittent.

Never promote from a smoke if the failure mode is intermittent. The Qwen36
graph path passed several smokes and then failed full repeats.

Add a calibration step when the question is a small target-side speed change,
not an MTP/speculation change:

```text
If the candidate is expected to affect only target-side kernels/runtime and the
normal MTP result is within the known same-recipe variance band, rerun control
and candidate with MTP/speculation/cache/history disabled. Use the lower-variance
no-spec calibration lane to decide whether the target-side delta is real, then
return to the normal MTP realistic gate before promotion.
```

This is not a replacement for the headline benchmark. It removes pipeline parts
that the patch cannot affect, reducing variance and preventing a `+1-4%` MTP
movement from being mistaken for a source win. For the Gemma 26B Q8 lane, see
`results/gemma4-26b-a4b-q8-b70/reliability-protocol.md`.

## Negative Result Discipline

For every meaningful failed attempt, record:

- exact patch or env delta;
- run identity;
- throughput and correctness result;
- failure signature;
- why the idea was plausible;
- whether it is superseded or should remain a future lead.

Suggested note prompt:

```text
Summarize this failed experiment as a reusable negative result. Include the
reason we tried it, exact identity, artifacts, observed failure, whether it
rules out a class of fixes, and the next action it implies.
```

## Cross-Agent Use

When Claude/OpenCode has limited token budget, use Codex/GPT for bulky work:

```bash
codex exec --cd /home/steve/llm-optimizations \
  "Audit the <model> result packet for stale claims, missing artifacts, and false validity wording. Return exact file edits."
```

Good delegation boundaries:

- one agent audits docs and links;
- one agent classifies result artifacts;
- one agent audits patches and source diffs;
- the main agent owns final edits, commits, LocalMaxxing submissions, and
  protection of secrets.

## Gemma 4 Lane Prompt

Use this to start or resume the current Gemma 4 26B A4B work:

```text
Resume the Gemma 4 26B A4B Q8 B70 lane. Read
results/gemma4-26b-a4b-q8-b70/README.md, research-plan.md,
model-options.md, validity-gates.md, localmaxxing-and-targets.md, and the
latest notes. Keep the primary lane Q8/INT8-or-better. First verify the model
file identity and current best valid result. Then run or propose the next four
independent experiments that can occupy GPUs 0..3 without tensor parallelism.
Do not promote speed-only results; every claim needs canary status, run
identity, output tok/s, TTFT or another secondary metric, and a server log path.
```

Gemma-specific lessons from the Q8 run:

- Use four independent GPUs for coarse rejection and idea coverage, but do not
  rank near-record candidates from four-way screens alone. The current record
  neighborhood showed host/contention variance; promote only from a clean solo
  run.
- Treat synthetic `p512o512.rows[0].tok_s_after_ttft` as diagnostic only, even
  when `cached_tokens=0` and canaries pass. Current Gemma/Qwen promotion and
  LocalMaxxing submission require the fixed realistic prompt suite, one cold
  response per prompt, `cached_tokens=0` every row, no cache/history reuse, and
  `median_tok_s_1_100_after_ttft` as the primary metric.
- For target-side Gemma changes that do not touch MTP/speculation, use the
  no-spec calibration lane when the apparent MTP delta is inside the current
  noise band. It keeps fresh prompts and `cached_tokens=0`, but disables
  speculation, cache reuse, and history acceleration so target-kernel changes
  can be measured with much lower variance.
- Mine the existing result tree before new runs. The 125 tok/s strict
  cold-suite result came from a sequence of targeted changes, not generic flag
  roulette: Q8 reorder VDR2, selected-down fused weighted-sum, bulk sampled-ID
  verifier host read, FA-on 32K/VMM, and final post-norm residual fusion.
- Preserve the realistic-suite prompt hashes and output hashes for promoted
  runs. A speedup is not headline-worthy unless it remains a fresh response:
  each fixed-suite prompt once, no prompt/KV/context/response reuse, no
  n-gram/history acceleration, and `cached_tokens=0`.
- Use the 4-GPU host for same-window A/B and cross-over screens, then confirm
  promising candidates with a clean solo run. The measured no-spec calibration
  spread was about `4.4%` p90 pairwise absolute run-median delta, so sub-1%
  changes need paired analysis rather than single-run comparison.
- Capture thermal/frequency telemetry when investigating variance. The
  2026-07-01 Gemma sweep found no throttle explanation for the spread
  (`77-78 C` active core, `86-90 C` memory, near-max frequency), which is why
  the repo treats close single-run deltas as inconclusive.
