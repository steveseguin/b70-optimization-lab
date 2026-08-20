# Qwen3.8 composite-runtime INT4-pad TP2 full-25 result

Date: 2026-08-20

Status: **negative determinism result; not promotion evidence**

The preregistered A2/B2 pair completed under the same pad-on composite
runtime, TP2/MTP5 topology, sealed b991 outer/AOT cache, model bytes, suite,
request order, and seed. Both arm-level identity and cache gates passed. The
campaign failed closed at the final token-array comparison: A2 and B2 agreed
on only **22/25** prompts.

## Result

| Arm | Preferred 99-interval median | Legacy median | Quality | Arm gate | Campaign exit |
|---|---:|---:|---|---|---:|
| A2 | 100.916265 tok/s | 101.935621 tok/s | pass, baseline matched | pass | 0 |
| B2 | 101.123643 tok/s | 102.145094 tok/s | skipped by design | pass | 14, parity NOGO |

The legacy arm medians were individually `+0.757%` and `+0.964%` versus the
`101.170` historical anchor. Do not average the arms into a campaign speed:
the token streams are not reproducible, and two mismatches occur inside the
first 100-token timing window.

The three A2/B2 mismatches were:

- `selection--sql-debugging`: first difference at generated token 35, with
  468/512 positions different;
- `holdout--factual-protocol`: first difference at token 343, with 168/512
  positions different;
- `holdout--long-rollover-repository-audit`: first difference at token 0 and
  all 512 positions different.

The final mismatch is not a near-tie continuation. A2 returned **512 token IDs
of zero**, rendered as 512 exclamation marks, output SHA `aeb1da71...`. B2
returned the sane diff response, SHA `c923f52f...`, and matched the historical
target through token 468 before the already-known token-469 split. This is a
catastrophic runtime-nondeterminism symptom. A2's separate semantic quality
suite passed, but that suite did not contain the corrupted full-25 response
and therefore cannot qualify this result.

## Integrity and engagement

Both arms:

- dual-view verified all 19 model files immediately before load;
- resolved the complete composite package under the strict staged path with
  `_xpu_C` SHA `4dd336013d15...` and graph-safe FA SHA `33938cdd2436...`;
- emitted exactly one determinism-pad marker from each TP rank;
- directly loaded two b991 outer graphs and four AOT artifacts;
- emitted no graph/AOT compile or save marker;
- left the sealed cache byte-identical: manifest `f3582440de9b...`, tree
  `723c1599060f...`, 3,795 entries, 3,246 files, 395,855,113 bytes;
- passed smoke, 25-prompt fresh-response, cache-zero, model, and process-group
  cleanup gates.

B2's exit code 14 is the intended fail-closed parity rejection, not a server
or benchmark failure. Both candidates matched the historical unpadded target
on 15/25 prompts, but that comparison remains report-only because the target
used a different runtime identity.

## Decision

Global in-band oneDNN W4A16 padding fixed the observed TP1
structured-extraction flip, but it is insufficient for full-25 TP2
determinism. Do not promote the measured speed and do not resume speed-flag
sweeps from this pair.

The narrowest recurrence test is one exact, untraced full-25 TP2 C arm that
preserves all 24 preceding requests and gates against complete sane-B2 token
parity. Any C/B mismatch stops untraced work and localizes the earliest
difference. If the all-zero stream repeats, trace only the final request's
prefill-to-first-target-logit/gather/GDN-state path while retaining the full
history. Only a 25/25 B2-exact C authorizes one later D recurrence arm. A
prompt-24-only test is not the first discriminator because it removes the
request-history position that may be causal.

Recurrence preregistration:
[`2026-08-20-detpad-tp2-full25-recurrence-prereg.md`](2026-08-20-detpad-tp2-full25-recurrence-prereg.md)

Structured evidence:
[`../data/2026-08-20-int4-detpad-tp2-full25-result.json`](../data/2026-08-20-int4-detpad-tp2-full25-result.json)

Preregistration and exact launch contract:
[`2026-08-20-detpad-composite-tp2-full25-prereg.md`](2026-08-20-detpad-composite-tp2-full25-prereg.md)
