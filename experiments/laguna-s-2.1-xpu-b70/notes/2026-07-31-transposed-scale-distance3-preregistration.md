# Laguna transposed-scale-only distance-3 preregistration

Date: 2026-07-31 America/Toronto

Status: **stopped at component gate; exact but slightly slower; no endpoint
authorized**.

## Premise

The confirmed exact record prefetches packed weights and the new contiguous
BF16 scale line at the same distance of six K groups. Removing scale prefetch
was a decisive `0.687432x` loss, so scale latency must be hidden. A coupled
3/6/12 sweep was exact but timing-inconclusive: W13 was unchanged while W2
transitioned between two timing modes inside every worker.

The narrower candidate keeps packed-weight prefetch at the record distance six
and moves only `TransposedScales=true` scale prefetch to distance three. The
hypothesis is that a 128-byte contiguous scale line needs less lead time and
benefits from arriving closer to use, while the much larger packed-weight tile
retains the latency cover already proven at distance six.

## Source and static gates

1. Branch from record source
   `8dd94f2307db3b830fe07f212c4b36f719652a5c` in a separate worktree.
2. Change only the initial and steady-state transposed-scale prefetch indices.
   Actual BF16 loads, scale values, packed-weight prefetch, operands,
   dequantization, DPAS, accumulation, stores, scheduling, ordinary scale
   layout, prefill, and draft paths must remain unchanged.
3. Inspect matched BMG ISA. Require 128 GRFs, no spill load/store, unchanged
   arithmetic body (32 BF16 multiplies, shifts/bitfields, and two DPAS in the
   matched probe), and evidence that packed-weight distance remains six while
   transposed-scale distance becomes three.

## Component gate

Build an ABI-matched oneAPI-2025.3 grouped-GEMM DSO. Compare it against record
DSO SHA-256
`c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`
on rank 1 with the deterministic changed-input transposed-scale corpus:

- W13 `N=2048,K=3072,M=120`;
- W2 `N=3072,K=1024,M=120`;
- GRF128, `SCALE_VEC=1`, `DEQUANT_MAD=0`, `SCALE_FOLD=0`, weight distance 6.

Use 200 unrecorded launches per shape, followed by 15 samples of 40 launches
each, in one fresh process per arm. This replaces the prior protocol's eight
warmups and nine samples of 20, which exposed a mid-series W2 transition.
Inspect all timing samples rather than relying on one median. Require raw-BF16
exactness on all six changed-input outputs. Stop if summed stable median
improves by less than 1.0%, either shape regresses by more than 1.0%, or timing
ordering remains unclear.

A component pass authorizes only a separately named default-off integration
selector and integration smoke. It does not authorize an endpoint or score
claim. No model, target/draft precision, BF16 KV, prompt, metric, teacher,
acceptance, graph topology, cache, warmup, retry, or quality contract may
change. No reset, reboot, or privileged recovery is authorized.

## Result

Candidate source commit:
`588ce4e636e7ad7561aec533bda85e2eaf35cdac`. Matched BMG inspection retained
128 GRFs, the same 32 BF16 multiplies and two DPAS instructions, and no spill
load/store. In the small transposed probe it emitted six packed-weight A/B
prefetch pairs, three scale prefetches, and steady-state scale immediate 3;
the record emitted six of each and scale immediate 6. The ordinary-layout
probe remained at 370 instructions.

The oneAPI-2025.3 full build completed in 16:36.43, peaked at 106,673,668 KiB
RSS, exported the same ABI as the record, and produced:

- DSO:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scale-dist3-build-588ce4e-20260801T0230Z/libgrouped_gemm_xe_2.so`;
- SHA-256:
  `91e90c002f2f0d7d2bb5a8ce92d2067b32c854b712b7a70c8b6298dfb203ca0f`.

Component artifact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scale-dist3-component-588ce4e-20260801T0250Z`

Both fresh workers used the preregistered 200 warmups per shape and 15 samples
of 40 launches. The prior W2 mid-series transition did not recur, and the
sample ranges overlap tightly.

| shape | record distance 6 | scale-only distance 3 | speedup | raw BF16 exact |
|---|---:|---:|---:|---:|
| W13, N=2048 K=3072 M=120 | 0.320845075 ms | 0.3211281 ms | 0.999119x | 3/3 |
| W2, N=3072 K=1024 M=120 | 0.183574375 ms | 0.18437965 ms | 0.995633x | 3/3 |
| summed | 0.50441945 ms | 0.50550775 ms | 0.997847x | 6/6 |

The candidate is **0.2153% slower** by the preregistered summed measure and
misses the 1.0% promotion threshold. No integration selector, model load,
endpoint, score claim, reset, or reboot followed.

## Learning

The record distance six is not merely compensating for packed-weight latency:
bringing only the contiguous 128-byte scale line closer does not help. Together
with the `0.687432x` no-scale-prefetch loss and the stabilized null coupled
sweep, this closes the transposed-scale prefetch seam. Further attempts should
not tune this same mechanism by one more nearby distance without new evidence.
