# Qwen27 EAGLE Corpus V2 Followups Closed

Date: 2026-07-04

Status: **closed diagnostic-only, no endpoint candidate**.

## Context

The four-GPU v2 corpus collection was mechanically clean:

- `96` chat prompts;
- `15360` hidden rows;
- `96` dataset samples;
- metadata on `96/96` samples;
- `0` continuity breaks.

The first compact draft trained directly on shards `0-2` and evaluated on
heldout shard `3` reached only `0.489` mean accepted over `1024` offline starts.
That was too weak for endpoint testing, but the split was also harsh: shard `3`
contained entire unseen prompt families. These followups tested whether the
weak score was just a curriculum or split artifact.

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260704T102338Z
```

Compact summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-corpus-v2-followups-20260704T104229Z-summary.json
```

## Results

| Experiment | Eval split | Mean accepted | Histogram | Decision |
|---|---:|---:|---|---|
| Direct r3 baseline | shard 3 OOD families | `0.489` | `{0:707,1:189,2:72,3:56}` | no endpoint |
| Staged r1->r2->r3 curriculum | shard 3 OOD families | `0.616` | `{0:655,1:196,2:84,3:89}` | no endpoint |
| Old strong v1 draft transfer | shard 3 OOD families | `0.201` | `{0:846,1:154,2:20,3:4}` | no transfer |
| Balanced task holdout staged | review/test-plan across families | `0.601` | `{0:633,1:223,2:112,3:56}` | no endpoint |
| All 96 v2 samples staged | separate calibration suite | `0.438` | `{0:720,1:202,2:60,3:42}` | no endpoint |

The staged curriculum helped slightly versus direct r3 training, but it did not
move the draft into a useful range. The balanced task split disproves the idea
that OOD-family heldout was the only problem. The older `2.1016` offline draft
does not transfer to v2 chat heldout (`0.201`). Training on all v2 data still
generalizes poorly to the separate calibration-suite corpus (`0.438`).

For comparison, the earlier old-corpus draft reached `2.1016` offline and still
failed endpoint quality/speed, so `0.4-0.6` offline mean accepted is nowhere
near an endpoint candidate.

## Decision

Do **not** endpoint-test the current compact v2 drafts. Do **not** submit any of
these diagnostic scores to LocalMaxxing.

The current EAGLE v2 branch is closed until there is a materially different
reason to expect draft quality:

- much larger/diverse non-final corpus;
- stronger initialization that actually transfers to chat distributions;
- larger/deeper draft architecture with acceptable service cost;
- or source/runtime changes that explain and fix the prior endpoint corruption.

Near-term Qwen27 optimization should return to non-EAGLE bottlenecks: reducing
LM-head/verifier cost, improving accepted tokens per verified target step, or
finding a graph/runtime path that preserves strict fresh-response quality.
