# Qwen3.8 Flash-Next FP8 TP4 MTP0 greedy-decision trace A8 preregistration

Date: 2026-08-28
Status: closed; host stopped during worker initialization before model load

## Question and source control

A7 changed `VLLM_XPU_USE_SAMPLER_KERNEL`, but the frozen requests use
`temperature=0`. Current vLLM computes greedy argmax and returns from the
`all_greedy` branch before the selected top-k/top-p implementation is called.
A7 therefore supplied no active treatment. Its exact-4K repeat still produced
two different token arrays, so the next question is where the greedy decision
first differs.

A8 adds a report-only trace at current overlay commit
`5d5081b2b1e145067bce6ec99492eac7ce042e23`. The feature is absent from the
normal path unless all three of these conditions hold: a trace directory is
configured, this process is the global first rank, and a non-discarded fully
greedy request ID matches the configured prefix. It records the top eight raw
logit IDs and exact float hex values, top-one/top-two margin, and selected token.
It refuses an existing trace file and stops after 256 records. Enabling it adds
a synchronization per decision, so no traced rate is eligible for performance
comparison or credit.

The source patch passed three focused unit tests, Ruff check/format, Python
compilation, and diff validation. Its preserved format-patch SHA-256 is
`84dfc547f0d985775d1803e9d62582f105079eb9d0f48eb5fde88559bf842847`.
Normal behavior remains unchanged when the trace directory is absent.

## Frozen identity and order

Start one TP4/EP4/eager/MTP0 server with the A7 model, kernel stage, 12.25-GiB
selective UVA offload, 33-block cache, 64-token scheduler, and 16,512 configured
capacity. Restore the accepted `VLLM_XPU_USE_SAMPLER_KERNEL=1`; it remains inert
for these greedy requests. The only active material change is the report-only
trace. Use a fresh run/cache/compile root, short IPC path, port 19680, and
attempt 8. The unchanged launcher base still performs source/model/runtime,
four-card idle, and four-rank XCCL gates before load.

After health, send exactly two identical cache-zero exact-4K/128-token requests
on the same server. Do not run the quality battery, MTP, 16K, 24K, or 32K in
this arm. Require both transport receipts to pass and require exactly two
128-record trace occurrences whose selected IDs exactly match the returned
token arrays and whose selected token always equals raw top one.

Frozen artifacts:

- launcher SHA-256:
  `8b9828a5280cc8c83850c72b75bfb019d51e773528b9f13dc71cd53d53a8e280`;
- generated launcher SHA-256:
  `ded085ed13530ba198cd2bbca24a2eeab09c17df62da77ff53ca398ddf0c3f7b`;
- ordered client/analyzer SHA-256:
  `8f3323d19c76b53ac8c87079a133503c36c9b7a54080d0189ec78ea63f5a8601`;
- exact-depth fixture SHA-256:
  `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`;
- exact-depth harness SHA-256:
  `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`.

## Frozen interpretations

- If both token arrays match, classify the arm as repeat-stable under this
  timing-changing trace. That is mechanism evidence only, not deployment proof.
- If the first different returned token has different raw top-one IDs and each
  selected token equals its own top one, classify raw greedy-logit divergence.
- If a selected token ever differs from recorded raw top one, fail the trace
  integrity gate; do not infer model causality.
- Record the earliest top-eight ID and exact-value differences even when top one
  stays stable. They are diagnostic drift evidence, not correctness failures.
- Any request timeout, incomplete trace, owned residue, or new B70 event closes
  A8 without retry. No historical throughput or public coverage cell changes.

## Closeout

A8 passed preflight but the host stopped after only worker ranks 0 and 1
reported distributed initialization. No shard load, health pass, trace record,
or request occurred. The opt-in trace was removed from the active runtime by a
normal revert commit, while its patch remains preserved. See the
[A8 closeout](2026-08-29-tp4-mtp0-greedy-trace-a8-worker-init-freeze.md).
