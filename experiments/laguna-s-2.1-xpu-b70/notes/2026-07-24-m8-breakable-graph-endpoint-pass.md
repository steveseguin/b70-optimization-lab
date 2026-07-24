# Laguna M8 Breakable graph endpoint qualification PASS

Date: 2026-07-24 America/Toronto

Status: **PASS**, correctness only. This result makes no timing, throughput,
record, or LocalMaxxing claim.

## Result

The production-shaped Laguna M8 Breakable graph endpoint passed the complete
preregistered two-fresh-start qualification:

| Gate | Start A | Start B | Cross-start |
|---|---:|---:|---:|
| canonical q1 full token arrays | 13/13 | 13/13 | 13/13 |
| `cached_tokens=0` | 13/13 | 13/13 | 13/13 |
| long-then-next | PASS | PASS | PASS |
| 863-token rollover | 1/1 | 1/1 | 1/1 |
| distinct rank capture topology | 4/4 | 4/4 | n/a |
| distinct rank replay topology | 4/4 | 4/4 | n/a |
| shutdown/workers/device idle | PASS | PASS | n/a |

Both starts returned the same ordered list of 13 output hashes. Each rank
logged exactly one audited lazy capture and one replay for:

```text
BatchDescriptor(num_tokens=8, num_reqs=None, uniform=False,
has_lora=False, num_active_loras=0)
BreakableCUDAGraphCapture(graphs=146, eager_breaks=145)
```

The analyzer also directly passed the actual service environment, graph
configuration, selector stack, request identity, fixed prompt order, absence
of diagnostic evidence variables, source commits, and cleanup artifacts.
An independent read-only post-run audit recomputed both teacher comparisons,
the literal A/B token-stream equality, freshness/cache-zero fields, distinct
rank topology, environment, cleanup, idle, sealing, and residual-process
state from the raw artifacts and reported no discrepancies.

## Frozen identity

- vLLM:
  `0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- graph runtime:
  `mode=NONE`, `cudagraph_mode=PIECEWISE`, capture sizes `[8]`;
- target and DFlash models: internal NVMe paths only;
- DFlash depth 7, TP4/EP4, BF16 KV, one sequence, no async scheduling, no
  prefix caching; and
- record selectors retained: fused W1-route-W2, route interleave,
  shared-elementwise, QKNorm/RoPE, W1 N64.

No evidence recorder, deterministic graph compiler, AOT compiler, forced
collective graph, cache/history acceleration, warm-up generation, retry, or
repeated prompt was active.

## Sealed evidence

Root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-graph-endpoint-6fb4e8d10-0ce373a31-20260724T211707Z
```

The root is mode `0500` and files are mode `0400`.

Key SHA256:

```text
be5421f3083d548c0aea78dbf06345b4cc223843415098796b8a4a601399fadd  analysis.json
3eaa0e50c151aa96f39552ea978377ef4b1ab663248d5eae0cfda9d07538a2c3  cross-start.json
3dad7e920e25362c6ed43994305fd832b2822ebcf67852d2bbc1417913c2e457  start-a/bench.json
f1fcf3dbf7b056646d23b9906236fc4aa7dc2d7a29571a6028493893e46019f2  start-b/bench.json
bc3bae86e2c7d40f1209a5e49591a484f6376b9af665c9197a88073127354ae5  start-a/exactness-vs-q1.json
87058114f7d7d020e1f4b4ee316c109e3e03c479c73b554e0484dda19963da66  start-b/exactness-vs-q1.json
57145faec36d47347c34396c39d059b69ab24e46966fe4c1a45ae48d786033d4  final-idle.json
```

## Decision

The graph stack is now endpoint-exact and cross-start reproducible. This
authorizes a new, separately preregistered cold performance crossover against
the approved `33.89498511171744 tok/s` record. The qualification timings are
not eligible for comparison or submission because the run was explicitly
registered as correctness-only and did not use the formal thermal/order
protocol.
