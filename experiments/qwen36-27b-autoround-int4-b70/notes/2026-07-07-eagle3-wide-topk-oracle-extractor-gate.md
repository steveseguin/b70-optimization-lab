# 2026-07-07: EAGLE3 wide top-k oracle extractor gate

## Classification

Diagnostic only. No endpoint throughput claim, no quality claim, and no
LocalMaxxing submission.

## Why

The earlier top-k oracle stopped at `K=16`, where the impossible same-cost
oracle estimated only `91.65 tok/s`. That was below the `>100 tok/s` target,
so the candidate-list branch looked weak unless we changed the drafter itself.

I reran the oracle at larger candidate counts to answer one narrower question:
does the frozen v6b EAGLE draft contain enough target-token signal somewhere in
the top-k list to justify building a cheap extractor/ranker?

## Run Identity

Draft checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-allscope-20260707T075425Z/all-r5-lr3e-6-decay0p25/checkpoint
```

Heldout dataset:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z/shard-3/dataset
```

Raw root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-v6b-topk-wide-oracle-20260707T103008Z
```

Compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-v6b-wide-topk-oracle-summary-20260707.json
```

## Results

Current valid endpoint reference:

- strict fresh record: `68.23626314761921 tok/s`;
- inferred verifier step cost: `40.256513914139006 ms`;
- `100 tok/s` at that step cost requires just over `4.0` visible
  target-verified tokens/step.

| oracle | starts | accepted draft tokens/step | visible tokens/step | impossible same-cost tok/s |
| ---: | ---: | ---: | ---: | ---: |
| top-32 | `14715` | `2.886102616377846` | `3.886102616377846` | `96.5335106926126` |
| top-64 | `14715` | `3.1770302412504248` | `4.177030241250424` | `103.76035665083647` |
| top-128 | `14715` | `3.4775399252463473` | `4.477539925246347` | `111.2252276686515` |

This is still an oracle: it accepts when the verified target token appears
anywhere in the draft top-k list, then continues with the verified target
token. It assumes a magic free extractor/reranker and is not an endpoint path.

## Decision

The wider oracle changes the conclusion from "top-k cannot reach the target"
to "top-k is extractor-gated."

- `K=64` and `K=128` contain enough target-token signal to cross `100 tok/s`
  under an impossible same-cost magic extractor.
- Naive legal full-tree verification remains infeasible; the row explosion is
  worse than the extra accepted depth saves.
- Prior diagonal and small-MLP rerankers failed to extract this signal
  (`~1.1069` and `~1.1193` accepted tokens versus `1.1015` top-1 baseline).

## Next

Do not publish these oracle rows and do not build a full top-k tree verifier.
The credible next implementation lane is rank promotion / candidate extraction:

1. train the draft head/objective to promote these top-64/top-128 near misses
   into rank 1, using hard-negative/listwise losses instead of more endpoint
   config sweeps; or
2. build a genuinely cheap selected-candidate scorer that can choose among
   top-k candidates without invoking target verifier rows for the whole tree.

The first route is cheaper to screen and should come before lower-level
candidate-score kernel work.
