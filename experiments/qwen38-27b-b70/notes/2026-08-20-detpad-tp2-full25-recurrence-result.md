# Qwen3.8 pad-on TP2 full-25 recurrence result

Date: 2026-08-20

Status: **recurrence established; stop untraced arms**

The preregistered C1 arm completed under the exact sealed A2/B2 identity and
failed only the mandatory token-array comparison. It reproduced A2's
catastrophic final response exactly: prompt 24 returned 512 copies of token ID
zero, output SHA `aeb1da71...`. This closes the hypothesis that the A2 stream
was a one-off artifact failure.

## Result

| Comparison | Exact token arrays | Mismatching prompts |
|---|---:|---|
| C1 versus sane B2 | 22/25 | 6, 11, 24 |
| C1 versus corrupt A2 | 23/25 | 6, 11 |

C1's preferred 99-interval median was `101.059105 tok/s`; its legacy median
was `102.079904 tok/s`. Both are descriptive only and non-promotable.

The three unstable endpoints now classify as follows:

- `selection--sql-debugging`: three families, all first splitting at generated
  token 35. C1 selected token `3152` versus A2 `13` and B2 `1058`, then ended
  at 239 token IDs rather than 512.
- `holdout--factual-protocol`: three families. C1 follows B2 through token 464,
  then selects `1946` versus B2 `2972`; A2 had already split at token 343.
- `holdout--long-rollover-repository-audit`: two families. C1 and A2 are
  byte-identical 512-zero streams; B2 is the sane family beginning
  `71093,13102,198`.

## Integrity

C1's runner exit `14` is the intended schema-proven parity rejection, not an
infrastructure or server failure. The arm-level sealed gate passed with no
errors. It dual-view verified the model, resolved the complete composite
runtime, emitted one pad marker from each TP rank, directly loaded two b991
outer graphs and four AOT artifacts, emitted no graph/AOT compile or save
marker, and left the cache byte-identical at manifest `f3582440...`, tree
`723c1599...`, 3,795 entries, 3,246 files, and 395,855,113 bytes. Smoke,
fresh-response, cached-zero, and clean process-group teardown gates passed;
quality was skipped by preregistration.

Artifact checksums:

- benchmark JSON: `8ff7a2e9ce7c41997e41747c1a35b71b8a06d0920030ecdc71d3305e7c08408e`;
- parity JSON: `31eb782113cb8a36fff940f660d1f5b732bbb9110cdcc273ec0a2705a5580e73`;
- sealed-gate JSON: `d3bfc6f26fe9c49c902bd9a635498ccec0072a0835c8a98606d42b8dd60f8ef0`;
- checksum manifest: `4037f0fee4ada9e47eab90bd560986724be589d6facf96890cf2bff8b93acc49`.

Artifact root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-c1-20260820`

## Decision

Do not run the preregistered D arm and do not resume speed-flag sweeps. The
next diagnostic must retain the complete 25-request order and treat throughput
as non-comparable. Localize the repeatedly corrupt prompt-24 path with a
request-filtered diagnostic or completion-boundary intervention, then use the
earlier SQL/factual families as secondary endpoints. Any instrumentation that
repairs the response is scheduling-sensitivity evidence, not a determinism
proof.

Structured evidence:
[`../data/2026-08-20-int4-detpad-tp2-recurrence-result.json`](../data/2026-08-20-int4-detpad-tp2-recurrence-result.json)

Preregistration:
[`2026-08-20-detpad-tp2-full25-recurrence-prereg.md`](2026-08-20-detpad-tp2-full25-recurrence-prereg.md)
