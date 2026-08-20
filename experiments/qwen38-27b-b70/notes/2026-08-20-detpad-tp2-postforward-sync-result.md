# Qwen3.8 sealed TP2 post-forward synchronization result

Date: 2026-08-20

Status: **negative boundary result; S2 forbidden**

The preregistered S1 arm passed every sealed model, runtime, cache, freshness,
and cleanup gate with the rank-local target/verifier post-forward
synchronization enabled. It did not satisfy the primary endpoint. Prompt 24
did not produce A2/C1's catastrophic all-zero stream, but it was not token-identical to
the sane B2 peer: it first split at zero-based generated token 469 and produced
a third long-rollover family. Per the preregistered stop rule, S2 must not run.

## Result

| Comparison | Exact token arrays | Mismatching prompts |
| --- | ---: | --- |
| S1 versus sane B2 | 22/25 | 6, 11, 24 |
| S1 versus corrupt A2 | 22/25 | 6, 11, 24 |
| S1 versus corrupt C1 | 22/25 | 6, 11, 24 |

The three unstable endpoints were:

- `selection--sql-debugging`: S1 produced a fourth family across A2/B2/C1/S1,
  first splitting at generated token 35 with token `63541` versus A2 `13`, B2
  `1058`, and C1 `3152`.
- `holdout--factual-protocol`: S1 produced a fourth family across A2/B2/C1/S1.
  It first split from B2 at token 486 (`82` versus `25344`), from C1 at token
  465, and from A2 at token 343. This family had occurred in earlier full-25
  margin-free arms, so it is not globally new.
- `holdout--long-rollover-repository-audit`: S1 began with the sane B2 prefix
  `71093,13102,198` and matched B2 through token 468, then selected `9345`
  rather than `3669` at token 469. Its complete output SHA is `471a54e8...`,
  a previously observed family that exactly matches the earlier post-recovery
  speculative B arm. It is neither B2's `c923f52f...` family nor A2/C1's
  `aeb1da71...` all-zero family.

S1's preferred 99-interval median was `100.252977 tok/s`; its legacy median
was `101.265633 tok/s`. These are diagnostic-only and non-promotable because
the synchronization deliberately changes execution ordering and the token
endpoint failed.

## Integrity

S1 exited zero. The arm-level sealed checker passed with no errors. The run
dual-view verified the model, resolved the complete `4dd33601...` composite
runtime with graph-safe FA `33938cdd...`, recorded both effective and expected
post-forward sync as one, emitted one oneDNN INT4 pad marker from each TP rank,
directly loaded two b991 outer graphs and four AOT artifacts, emitted no
graph/AOT compile or save marker, and left the cache byte-identical at manifest
`f3582440...`, tree `723c1599...`, 3,795 entries, 3,246 files, and 395,855,113
bytes. Smoke, fresh-response, cached-zero, and clean process-group teardown
gates passed; quality was skipped by preregistration.

Artifact checksums:

- benchmark JSON: `ef58255251c5e2462d8dc51da19fe9ec9e737e531116acb4b406cddc99ec61fb`;
- sealed-gate JSON: `0a8d719fc2cece3fe583d4a2cdf49f8fe74d5d52bce74e109bfd5b59620ed80a`;
- checksum manifest: `d1311d452416f5a3cdc8c9da7b39574d20f70a50d9c3e93156c469dd8c6c78a9`.

Artifact root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-marginfree-mtp5-25-postforward-sync-s1-20260820`

## Decision

Do not run S2 and do not interpret the absence of the all-zero family in one
synchronized arm as a fix. S1 observed a different, previously seen family
with the intervention active, but the untreated lane already emitted multiple
families; this is consistent with, but does not establish, a synchronization-
caused ordering effect. The broad boundary does not restore exactness or
determinism and does not isolate a root cause. The next diagnostic is the
bounded prompt-24 replay microscope,
retaining all 24 predecessor requests. If the trace heals or wedges the
response, classify it as scheduling-sensitive and inconclusive; if the corrupt
token survives, use the six stage records to bracket the first bad value
between model input, hidden state, logits, and sampler output.

Structured evidence:
[`../data/2026-08-20-int4-detpad-tp2-postforward-sync-result.json`](../data/2026-08-20-int4-detpad-tp2-postforward-sync-result.json)

Preregistration:
[`2026-08-20-detpad-tp2-postforward-sync-prereg.md`](2026-08-20-detpad-tp2-postforward-sync-prereg.md)
