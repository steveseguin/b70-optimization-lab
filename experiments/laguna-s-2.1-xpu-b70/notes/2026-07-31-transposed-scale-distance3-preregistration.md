# Laguna transposed-scale-only distance-3 preregistration

Date: 2026-07-31 America/Toronto

Status: **static and component gate only; no endpoint authorized**.

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
