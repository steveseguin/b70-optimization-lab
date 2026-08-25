# b2dd TP1 eager-MTP2 full r1 closeout

Date: 2026-08-25. Classification: **terminally quarantined by the frozen
cross-boot exact-oracle gate; no MTP corruption attribution.**

The frozen b2dd/1e90 Qwen 3.8 AutoRound INT4 TP1 eager MTP2/F16 stage booted
cleanly and completed its full 25-prompt natural-EOS benchmark. The canary,
benchmark, cache-zero, immutable identity, complete quality battery, draft
acceptance, cleanup, and local-Git gates all passed. Speculation was active:
`7,391 / 10,040` drafted tokens were accepted (`73.6155%`).

The preregistered all-prompt target oracle matched `23/25` complete output
hashes and token sequences rather than the required `25/25`. The two coherent
differences were:

- `selection--customer-email`, first divergence at generated token 129;
- `selection--performance-hypotheses`, first divergence at generated token 50.

Neither output contained garbling, NaNs, a canary failure, or a runtime error.
The separate quality battery passed seven exact cases, all eight repeat checks,
the 8K needle, all 24 baseline comparisons, and all 16 cache-zero checks.

This result must not be called MTP corruption. The MTP2 candidate and its MTP0
oracle came from separate fresh boots and caches. Existing target-only evidence
already shows cross-compile output variability as low as `19/25` exact, so this
`23/25` cross-process comparison cannot isolate MTP as the cause. The exact
oracle was still a valid conservative promotion gate and correctly prevented
promotion.

The preferred interval median was `10.90171641629769 tok/s`, but the row is a
quarantined short-suite observation, not a speed candidate and not a
replacement for any protected eager or graph result. It fills zero numeric
active-context cells; configured max length is not active context.

Because E1 did not pass its exact frozen prerequisite, E2—the one authorized
eager-MTP4 actual—remains blocked and was not run. Preserve this attempt, do
not retry it under the same campaign, and advance another independent matrix
packet. A future causality study, only if it becomes coverage-critical, would
need a paired target/MTP diagnostic with controlled compile identity or
verifier logits and top-1 margins.

The terminal receipt SHA-256 is
`6decc3ad2624634054949fec4b37591b13f19f8b8324933e0c006bab9dde01ff`.
The structured closeout is
[`2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp2-full-r1.json`](../data/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp2-full-r1.json).
Complete evidence remains under
`/home/steve/qwen38-current-main-runs/tp1-eager-mtp-expansion-b2dd9ce73d-20260825-r1/01-mtp2-full`.
