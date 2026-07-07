# 2026-07-07: EAGLE3 top-k oracle and reranker diagnostics

## Classification

Diagnostic only. No endpoint throughput claim, no quality claim, and no
LocalMaxxing submission.

## Objective

The best v6b all-scope EAGLE3 draft reached only `1.1014610941216445` heldout
mean accepted with normal top-1 linear drafting. The evaluator showed that the
target token is often nearby in the draft distribution, so this screen tested
two questions:

1. how much accepted-depth headroom exists if a future tree/rerank verifier can
   use the draft top-k list; and
2. whether a tiny cheap reranker can convert that top-k headroom into real
   top-1 draft proposals.

## Tooling added

`scripts/evaluate-qwen27-ex0bit-eagle3-offline.py` now has:

```text
--accept-mode top1|topk-oracle
```

`topk-oracle` accepts a step if the verified target token appears anywhere in
the draft top-k and continues with the verified target token. This is an
upper-bound probe for future tree/rerank work, not a valid endpoint throughput
claim.

New diagnostic trainer:

```text
scripts/train-qwen27-eagle3-topk-reranker.py
```

It trains tiny rerankers over frozen-draft top-k candidates. The first screen
used a diagonal reranker:

```text
score(c) = alpha * draft_logit(c)
         + dot(pred_hidden * lm_head_weight[c], diag)
         + rank_bias[rank(c)]
```

The follow-up MLP screen added:

```text
score(c) = alpha * draft_logit(c)
         + MLP(pred_hidden * lm_head_weight[c])
         + rank_bias[rank(c)]
```

## Run identity

Draft checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-allscope-20260707T075425Z/all-r5-lr3e-6-decay0p25/checkpoint
```

Heldout dataset:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z/shard-3/dataset
```

Compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-v6b-topk-oracle-reranker-summary-20260707.json
```

## Top-k oracle results

Raw root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-topk-oracle-20260707T082454Z
```

| mode | heldout mean accepted | histogram |
| --- | ---: | --- |
| normal top-1 baseline | `1.1014610941216445` | `0=6175,1=4287,2=2317,3=972,4=449,5=515` |
| top-2 oracle | `1.5037037037037038` | `0=4443,1=4160,2=2928,3=1517,4=775,5=892` |
| top-4 oracle | `1.8844716275908937` | `0=3238,1=3815,2=3130,3=1929,4=1147,5=1456` |
| top-8 oracle | `2.2487937478763165` | `0=2379,1=3374,2=3088,3=2157,4=1515,5=2202` |
| top-16 oracle | `2.5896024464831804` | `0=1675,1=2998,2=2971,3=2270,4=1649,5=3152` |

Interpretation: there is real upper-bound headroom in the candidate list, but
it is not free. Any endpoint path must either rerank candidates cheaply before
proposal or verify a tree/branch structure without spending more target compute
than the accepted depth saves.

## Diagonal reranker results

Raw root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-topk-reranker-20260707T083126Z
```

| label | top-k | lr | heldout mean accepted | histogram |
| --- | ---: | ---: | ---: | --- |
| `k4-lr3e-3` | 4 | `3e-3` | `1.106897723411485` | `0=6254,1=4210,2=2236,3=1016,4=437,5=562` |
| `k4-lr1e-2` | 4 | `1e-2` | `1.090519877675841` | `0=6354,1=4164,2=2228,3=996,4=426,5=547` |
| `k8-lr3e-3` | 8 | `3e-3` | `1.0983350322799863` | `0=6281,1=4211,2=2252,3=992,4=424,5=555` |
| `k8-lr1e-2` | 8 | `1e-2` | `1.072579001019368` | `0=6437,1=4161,2=2207,3=965,4=412,5=533` |

Decision: close the diagonal reranker as no-win. It barely moves the top-1
baseline (`1.1015 -> 1.1069`) and does not extract the top-k oracle headroom.

## MLP reranker follow-up

Raw root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-topk-reranker-mlp-20260707T084344Z
```

Compact summary:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-topk-mlp-reranker-summary-20260707.json
```

| label | top-k | hidden | lr | heldout mean accepted | histogram |
| --- | ---: | ---: | ---: | ---: | --- |
| `k4-h64-lr1e-3` | 4 | 64 | `1e-3` | `1.1015970098538905` | `0=6250,1=4216,2=2271,3=1010,4=418,5=550` |
| `k4-h256-lr1e-3` | 4 | 256 | `1e-3` | `1.1046551138294258` | `0=6237,1=4231,2=2260,3=1010,4=411,5=566` |
| `k8-h64-lr1e-3` | 8 | 64 | `1e-3` | `1.1065579340808698` | `0=6195,1=4271,2=2270,3=1005,4=413,5=561` |
| `k8-h256-lr1e-3` | 8 | 256 | `1e-3` | `1.1192660550458715` | `0=6153,1=4267,2=2289,3=984,4=437,5=585` |

Decision: close this MLP shape as no-win. The best result improves the normal
top-1 baseline by only `+0.0178` accepted draft tokens and remains far below
even the top-2 oracle (`1.5037`), let alone the top-8 oracle (`2.2488`).
The result is too small to justify endpoint plumbing, tree verification, or a
runtime pre-verification MLP.

## Tree verifier cost model

New diagnostic:

```text
scripts/analyze-qwen27-eagle3-tree-cost.py
```

Output:

```text
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-tree-cost-model-20260707.json
```

Inputs:

- current valid strict Qwen27 median: `68.23626314761921 tok/s`;
- current MTP3 visible tokens per verifier step: `2.6727` (`1.6727`
  accepted draft prefix + 1 target bonus from the branch-regenerate trace);
- current verifier row shape: `4` rows (`3` draft + `1` bonus);
- tree depth: `5`.

| top-k | oracle visible tokens/step | magic same-cost tok/s | full tree rows | full-tree tok/s |
| ---: | ---: | ---: | ---: | ---: |
| 2 | `2.5037` | `63.92` | `63` | `4.06` |
| 4 | `2.8845` | `73.64` | `1365` | `0.216` |
| 8 | `3.2488` | `82.94` | `37449` | `0.0089` |
| 16 | `3.5896` | `91.65` | `1118481` | `0.00033` |

Decision: close naive tree verification for this evidence. Even the impossible
same-cost top-16 oracle is below `100 tok/s`, and the legal full tree is far
too expensive. A useful branch/tree path would need a materially cheaper
verifier shape than full breadth, or a stronger drafter that improves top-1
accepted depth directly.

## Next implication

Do not repeat diagonal or small MLP reranker sweeps. If this branch continues,
the next credible options are:

- a materially stronger candidate model, e.g. cross-token/tree-aware scoring or
  training the drafter itself to put the target into rank 1 rather than trying
  to rescue rank after the fact; or
- a verifier design with a much cheaper branch cost than full breadth; the
  naive full-tree cost model is already closed.

The diagnostic says top-k candidate information is useful, but the cheap
single-token extractors tried here are too weak.

## Wide top-k follow-up

Later on 2026-07-07, the same best v6b all-scope checkpoint and heldout shard
were rerun at `K=32,64,128`; see:

```text
experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-eagle3-wide-topk-oracle-extractor-gate.md
experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-eagle3-v6b-wide-topk-oracle-summary-20260707.json
```

Result: top-64/top-128 oracle accepted depth is high enough to cross `100 tok/s`
only under an impossible same-cost magic extractor (`103.76` / `111.23 tok/s`).
This does **not** make the oracle a benchmark or endpoint design, but it does
mean the branch is extractor-gated rather than signal-starved. Continue with
rank-promotion or selected-candidate extraction; keep naive full-tree verifier
plumbing closed.
