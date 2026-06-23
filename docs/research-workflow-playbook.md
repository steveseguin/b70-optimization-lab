# Research Workflow Playbook

This page captures the prompts and approaches that produced the best outcomes
across the MiniMax, Gemma, and Qwen36 B70 work. Use it when starting a new model
lane or when an experiment series starts losing structure.

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
