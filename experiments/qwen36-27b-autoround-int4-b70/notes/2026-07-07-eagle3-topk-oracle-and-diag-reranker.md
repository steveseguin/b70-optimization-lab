# 2026-07-07: EAGLE3 top-k oracle and diagonal reranker diagnostic

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

It trains a tiny diagonal reranker over frozen-draft top-k candidates:

```text
score(c) = alpha * draft_logit(c)
         + dot(pred_hidden * lm_head_weight[c], diag)
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

## Next implication

Do not repeat diagonal-reranker LR sweeps. If this branch continues, the next
credible options are:

- a stronger candidate reranker, e.g. low-rank bilinear or small MLP over
  `pred_hidden * candidate_weight`, still cheap enough to run before target
  verification; or
- a real tree-verifier cost model, because top-8/top-16 oracle accepted depth
  may not pay for the extra branch rows if implemented naively.

The diagnostic says top-k candidate information is useful, but the first cheap
extractor was too weak.
