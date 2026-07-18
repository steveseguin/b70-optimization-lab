# DSpark W1-Only Replication Record

Date: **2026-07-18**

Status: **promoted TP4+EP single-session target-verified record**

## Outcome

Replicating only DSpark's small Markov W1 embedding table, while retaining the
persistent sharded W2 projection, raised the unchanged K160 target to a new
strict-suite high of **67.501117 tok/s** on four Intel Arc Pro B70s. The median
of three independent strict-suite medians is **67.182469 tok/s**. This is one
active generation, not aggregate throughput.

| Strict suite | Median tok/s | p10 tok/s | Mean tok/s | Full after-TTFT tok/s | Wall tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| screen | 65.656734 | 57.893669 | 66.384895 | 63.034655 | 54.049673 | 355.922493 |
| confirmation | **67.501117** | 60.015995 | 69.289305 | 65.094268 | 54.563136 | 331.859981 |
| third | 67.182469 | 53.426594 | 61.933023 | 64.455101 | 54.123936 | 338.547341 |

All 36 realistic requests were fresh and reported `cached_tokens=0`. Four
six-case exact-canary suites passed before, between, and after the performance
suites: 24/24 requests, including `1073 -> 437 -> 1073`. The unchanged K160
target verifies every accepted DSpark token at M=8. No prompt history, prefix
cache, response reuse, aggregate throughput, or benchmark-specific routing was
used.

Relative to the preceding 66.479103 tok/s headline, the new high is +1.022014
tok/s (+1.54%). The stability median rises from 65.674202 to 67.182469 tok/s,
+1.508267 (+2.30%).

## Why this differs from failed full replication

The full-replication experiment copied both 129280x256 Markov matrices to every
rank. Although it removed all 14 Markov collectives, each B70 then repeated all
four W2 vocabulary partitions. That exact endpoint reached only 64.358 tok/s.

W1-only replication copies only the token-to-256 embedding table. Every rank
can look up the preceding token locally, eliminating seven small embedding
all-reduces. The expensive W2 projection remains split four ways and the
existing full-vocabulary gather remains unchanged. The added memory is about
47 MiB/rank beyond the local W1 shard, not the roughly 99 MiB/rank required by
full W1+W2 replication.

The real-weight four-B70 component was bitwise exact and saved 0.451-0.452
ms/cycle over the already-persistent sharded transaction. This is slightly
below the historical 0.50 ms standalone gate. It was admitted as an explicit
small-improvement endpoint exception because the user requested that proven
micro-gains be accumulated; the complete three-suite endpoint, rather than a
relabeled component gate, is the promotion evidence.

## Rejected companion micro-fusions

Three adjacent attempts were measured and remain rejected:

- a two-stage Triton full-vocabulary fused BF16 add/argmax was exact but about
  0.08 ms/cycle slower;
- exchanging four tiny `(max, token_id)` pairs instead of full logits was exact
  but about 1.39 ms/cycle slower because tiny oneCCL all-gather fell off the
  optimized device path;
- adding each base-logit shard before the full gather was exact but about 0.06
  ms/cycle slower than the ordinary full-width post-gather add.

Only W1-only replication is present in the promoted source.

## Reproduction identity and evidence

- target: `0xSero/DeepSeek-V4-Flash-180B`, revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- draft: `deepseek-ai/DeepSeek-V4-Flash`, revision
  `aa22cb07426656189b2573b8e77a9b7333b8ae0f`;
- vLLM: `019e6f0e2e0b0b96f86a7e4d9cf2c8e47dd4183e`;
- XPU kernels: `0b99fc5360141d4dd6174fb15f30ec80c74c4d47`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- topology: four B70s, TP4+EP, concurrency 1;
- graph identity: target PIECEWISE, draft breakable PIECEWISE exact M=7,
  target verifier M=8;
- endpoint evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-replicated-w1-candidate-20260718T1800Z`;
- W1-only component evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-replicated-w1-persistent-gate-20260718T1715Z`;
- rejected fused-argmax evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-replicated-w1-fused-argmax-gate-20260718T1730Z`;
- rejected pair-exchange evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-replicated-w1-pair-gate-20260718T1740Z`;
- rejected local-add evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-replicated-w1-local-add-gate-20260718T1750Z`.

Launch with:

```bash
DSPARK_GRAPH_MODE=piecewise \
DSPARK_DRAFT_GRAPH_MODE=piecewise \
DSPARK_SPEC_TOKENS=7 \
VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1 \
VLLM_XPU_GREEDY_FUSED_REJECTION=1 \
VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=1 \
VLLM_XPU_DSPARK_PERSISTENT_MARKOV=1 \
VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1=1 \
experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-dspark-candidate.sh
```

## Decision

Promote W1-only replication. Keep full Markov replication, fused Markov
argmax, tiny-pair exchange, and pre-gather local add disabled. The remaining
large gap is architectural: W2's seven sequential projections/gathers and the
target cycle, not another generic tensor allocation.
