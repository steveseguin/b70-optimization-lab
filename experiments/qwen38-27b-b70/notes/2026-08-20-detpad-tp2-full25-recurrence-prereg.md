# Qwen3.8 pad-on TP2 full-25 recurrence preregistration

Date: 2026-08-20

Status: preregistered; C1 has not launched.

## Question

The sealed pad-on A2/B2 pair agreed on only 22/25 prompts. A2's final
long-rollover response was 512 copies of token ID zero, while B2 produced the
sane response. Does one more untraced fresh-server arm reproduce A2, reproduce
B2, or create a third output family when the complete 25-prompt history is
retained?

This is recurrence triage, not a stability proof or speed arm. It precedes any
synchronizing trace because tracing can suppress or move the race being
observed.

## Frozen identity

C1 uses the exact A2/B2 runtime identity and request order:

- [`../scripts/run-20260820-detpad-tp2-recurrence.sh`](../scripts/run-20260820-detpad-tp2-recurrence.sh), action `c`;
- GPUs 2,3, TP2, native MTP5, FP16, seed 0, both margins zero;
- composite `_xpu_C` `4dd33601...` plus graph-safe FA `33938cdd...`;
- global oneDNN W4A16 determinism pad on with one marker required per rank;
- native GDN on, ReplaySSM speculative path off, persistent scratch and GDN
  capture on;
- PIECEWISE partition capture size 6 and the sealed b991 outer/AOT cache;
- cache manifest `f3582440...`, tree `723c1599...`, 3,795 entries, 3,246
  files, 395,855,113 bytes;
- frozen 25-prompt suite SHA `292dea6a...`, smoke and fresh-response gates on,
  quality skipped, no trace or explicit synchronization hook.

The driver revalidates both completed arms and pins their checksum-manifest
files (`a9a162c9...` / `e7726d02...`) before checking their contents. B2's
sane benchmark SHA `96933a82...` is the mandatory peer. A2's corrupt benchmark
SHA `865ab22e...` is the report-only reference. Runner exit 0 means C1 is
25/25 exact against B2. Exit 14 is interpreted as recurrence only when
`token-parity.json` has schema `qwen38-token-array-parity-v1`, status `failed`,
and at least one actual C1/B2 token difference; otherwise it is an invalid
checker/infrastructure result.

## Frozen endpoints and stop rules

Primary endpoint, prompt 24 `holdout--long-rollover-repository-audit`:

- A2: 512 zero token IDs, output SHA `aeb1da71...`;
- B2: sane response beginning `71093,13102,198`, output SHA `c923f52f...`.

Secondary endpoints:

- prompt 6 `selection--sql-debugging`: A2/B2 first differ at token 35;
- prompt 11 `holdout--factual-protocol`: A2/B2 first differ at token 343.

Stop immediately on any model, staged-runtime, pad-marker, direct-load,
sealed-cache, freshness, cleanup, or server failure.

- Any schema-validated C1/B2 token mismatch (runner exit 14) stops untraced
  runs and localizes the earliest difference, even if prompt 24 itself is sane.
- If C1 repeats the all-zero stream or produces any new corrupt prompt-24
  family, recurrence is established; retain all 24 predecessor requests in
  the localization trace.
- Only C1 exit 0, meaning 25/25 exact against sane B2, authorizes one later,
  separately preregistered D recurrence arm before instrumentation.
- If future C1/D differ anywhere, stop and localize the earliest recurring
  endpoint.
- Even if C1/D are 25/25 exact and sane, classify the fault as intermittent
  and not reproduced. Do not promote from this recurrence sample.
- Any runner status other than 0 or mismatch-proven 14 is an invalid arm and
  stops the campaign without a causal interpretation.

The later causal screen, if recurrence is active, may use the already-existing
post-forward XPU synchronization hook. That hook is a rank-local completion
barrier, not a distributed barrier, and needs its own explicit identity and
engagement contract before use.

Parent result:
[`2026-08-20-detpad-composite-tp2-full25-result.md`](2026-08-20-detpad-composite-tp2-full25-result.md)
