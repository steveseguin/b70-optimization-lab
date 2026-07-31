# Laguna transposed decode-scale layout preregistration

Date: 2026-07-31 America/Toronto

Status: **source/static and component work authorized; no endpoint authorized**.

## Premise

The exact width-12 INT4 grouped GEMM reads packed weights in contiguous K32
tiles, but the checkpoint scale layout is `[expert,N,K/32]`. At each K group,
the 64 output columns owned by a workgroup therefore read BF16 scales with a
stride of `K/32`: 96 elements (192 bytes) for W13 and 32 elements (64 bytes)
for W2. The kernel already issues a separate scale prefetch, so this scattered
layout can waste transactions and cache lines in the bandwidth-dominant MoE
path.

Transpose only the immutable per-expert scale table to `[expert,K/32,N]` once
before decode. Add a separately named default-off exact-decode kernel that
uses the transposed addresses while retaining the confirmed GRF128 geometry,
group-32 vectorized dequantization, K/N/M tiles, packed weight bytes, BF16
scale values, BF16 multiplies, DPAS operations, accumulator order, stores, and
persistent expert scheduler unchanged.

## Gates

1. The new selector must require the exact width-12 target identity and must
   not reach draft, prefill, another group size, another dtype, or selector-off
   calls.
2. A production BMG static build must show the intended contiguous scale
   addressing, 128 GRFs, no scratch/spill metadata, and the same live 32 BF16
   multiplies, 16 shifts, 16 bitfield operations, and two DPAS instructions as
   the confirmed exact mainloop.
3. Only after static pass, build the ABI-matched oneAPI-2025.3 DSO. A
   changed-input component compares ordinary `[N,G]` control scales with the
   logically identical `[G,N]` candidate scales for real W13 and W2 shapes.
   Require every raw BF16 output to match.
4. Stop before vLLM integration unless the candidate improves the summed W13
   plus W2 component median by at least `2.0%`. This higher threshold reflects
   the added model-load storage/layout plumbing and the endpoint's noise.
5. A component pass authorizes a separate integration design and smoke, not a
   score-bearing endpoint.

No target/draft/KV precision, model, prompt, acceptance policy, benchmark
metric, teacher, or quality contract may change. No reboot, reset, driver
action, endpoint, or submission is authorized here.

