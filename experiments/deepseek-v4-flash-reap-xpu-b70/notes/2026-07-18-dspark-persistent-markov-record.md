# DSpark Persistent Markov Transaction Record

Date: **2026-07-18**

Status: **promoted TP4+EP single-session target-verified record**

## Outcome

The unchanged uniform-K160 target reached a new strict-suite high of
**66.479103 tok/s** for generated tokens 1-100 after TTFT on four Intel Arc
Pro B70s. The median of three independent strict-suite medians is
**65.674202 tok/s**, above the preceding 64.661411 tok/s record. This is one
active generation, not aggregate throughput.

The candidate keeps the successful exact-M7 DSpark draft and M=8 target
verifier. It replaces the seven-step eager Markov sampler's allocation-heavy
PyTorch transaction with fixed, persistent device buffers while retaining the
sharded W1 and W2 computation and the same TP4 collectives.

| Strict suite | Median tok/s | p10 tok/s | Mean tok/s | Full after-TTFT tok/s | Wall tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| screen | 65.674202 | 57.218180 | 65.281420 | 62.703107 | 53.141162 | 350.450966 |
| confirmation | **66.479103** | 59.380378 | 66.441173 | 65.641264 | 54.805657 | 340.315117 |
| third | 63.558530 | 55.751431 | 64.606215 | 63.263739 | 53.469004 | 344.586112 |

All 36 realistic requests were fresh and reported `cached_tokens=0`. Four
independent six-case exact-canary suites passed before, between, and after the
performance suites: 24/24 requests, including the changed-input sequence
`1073 -> 437 -> 1073`. The unchanged target verifies every accepted draft
token. No prompt history, prefix cache, response reuse, model substitution, or
benchmark-specific routing was used.

Relative to 64.661411 tok/s, the headline is +1.817692 tok/s (+2.81%) and the
median-of-three stability figure is +1.012791 tok/s (+1.57%). This is a real
record, but it remains far short of the 100/200 tok/s objectives.

## Why the remaining sampler overhead was real

The earlier cycle profile measured about 10.50 ms/cycle inside the eager
Markov sampler. Its arithmetic is small, but its ordinary implementation
created intermediate tensors, concatenated rank shards, copied results, and
launched generic embedding/add/argmax operations on every one of seven
sequential steps. Graph replay could not safely absorb the transaction because
the 14/15 collective boundaries break the graph and a combined sampler/model
graph corrupted output.

Two tempting replication approaches were measured and rejected:

- replicating the full target LM head made its real-weight component about
  1.257 ms slower than the sharded path;
- fully replicating DSpark W2 removed the Markov collectives in isolation, but
  paid four times the matrix-vector work. Its exact endpoint measured only
  64.358 tok/s and did not beat the record.

The important distinction is that the successful path does **not** replicate
the expensive projection. It preserves parallel weight work and removes
transaction overhead around it.

## What fixed it

vLLM commit `0873ffa6730a46c31c89764159363b07f469df6f` adds a guarded,
fixed-geometry persistent Markov transaction for the exact TP4, concurrency-1,
DSpark7 shape:

- a custom Triton local-W1 lookup writes directly into a persistent buffer;
- the W1 all-reduce operates in place;
- `torch.mm(..., out=...)` writes the local W2 projection into persistent
  storage;
- `dist.all_gather_into_tensor` writes directly into a persistent
  `[4, 32320]` buffer;
- bias addition and argmax reuse persistent output buffers;
- unsupported shapes fail closed to the ordinary implementation.

The real-weight four-B70 component gate was exact on every rank. Against the
faster bracketing ordinary control, the slowest-rank seven-step median improved
from 2.966522 to 2.179909 ms, a **0.786613 ms/cycle** saving. The component
did not meet the lane's newer 4 ms architectural bundle threshold by itself,
but it exceeded the historical 0.50 ms admission floor and the complete
endpoint then established a valid record.

The same bundle also retains two smaller exact, default-off optimizations from
vLLM commit `1aaf54e7992dfd898d23aa5ab5f87853c5cffc78`:

- fixed-M7 target-input metadata buffers; and
- a fused greedy verifier/bonus/rejection-count kernel with the original tie
  geometry.

Their preceding endpoint was only 64.457440 tok/s, so they are preserved as
part of the tested bundle but are not credited with the Markov component gain.

## Reproduction identity and evidence

- target: `0xSero/DeepSeek-V4-Flash-180B`, revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- draft source: `deepseek-ai/DeepSeek-V4-Flash`, revision
  `aa22cb07426656189b2573b8e77a9b7333b8ae0f`;
- vLLM: `0873ffa6730a46c31c89764159363b07f469df6f`;
- XPU kernels: `0b99fc5360141d4dd6174fb15f30ec80c74c4d47`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`, with the
  131,072-byte all-reduce routing threshold;
- topology: four B70s, TP4+EP, concurrency 1, one active generation;
- graphs: target PIECEWISE, draft breakable PIECEWISE exact M=7, target
  verifier M=8;
- KV cache: FP8; temperature: 0; prefix caching: disabled;
- endpoint evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-persistent-markov-bundle-20260718T1640Z`;
- persistent component gate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-persistent-markov-gate-20260718T1630Z`;
- rejected replicated-head gate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-replicated-lmhead-gate-20260718T1550Z`;
- rejected full-replication endpoint:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-exactm7-replicated-markov-r2-20260718T1500Z`.

Launch with:

```bash
DSPARK_GRAPH_MODE=piecewise \
DSPARK_DRAFT_GRAPH_MODE=piecewise \
DSPARK_SPEC_TOKENS=7 \
VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1 \
VLLM_XPU_GREEDY_FUSED_REJECTION=1 \
VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=1 \
VLLM_XPU_DSPARK_PERSISTENT_MARKOV=1 \
experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-dspark-candidate.sh
```

## Next action

The next Markov experiment should replicate **only** the small W1 embedding
table while keeping W2 sharded and persistent. That removes seven W1
all-reduces without repeating the expensive W2 projection or changing target
verification. It must first beat the persistent-sharded real-weight component
on all four B70s and remain bitwise exact before any endpoint integration.
