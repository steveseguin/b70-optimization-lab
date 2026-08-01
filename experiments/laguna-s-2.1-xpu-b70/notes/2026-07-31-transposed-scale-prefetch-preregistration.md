# Laguna transposed-scale prefetch preregistration

Date: 2026-07-31 America/Toronto

Status: **static and component gate only; no endpoint authorized**.

## Premise

The confirmed record makes each width-12 target scale line contiguous in
`[expert,K/32,N]` layout, but the grouped-GEMM mainloop still issues explicit
block prefetches for those scales at the weight prefetch distance of six K
groups. The actual BF16 scale loads are small, contiguous, and unchanged.
Explicit prefetch may now be redundant or may displace useful packed-weight
lines.

The first candidate removes only the null-destination block-prefetch operations
when `TransposedScales=true`. It retains every actual scale load, BF16 value,
weight load/prefetch, dequantization operation, DPAS operation, accumulator,
store, workgroup, and persistent scheduling decision. Ordinary checkpoint
layout, prefill, draft, and selector-off paths remain byte-for-byte source
equivalent.

## Gates

1. Work from confirmed XPU-kernel source
   `8dd94f2307db3b830fe07f212c4b36f719652a5c` in a separate worktree.
2. Inspect the exact diff and production BMG AOT. Require 128 GRFs, no spills,
   unchanged live 32 BF16 multiplies, 16 shifts, 16 bitfield operations, and
   two DPAS instructions. The only intended native delta is scale-prefetch
   removal plus compiler scheduling consequences.
3. Build an ABI-matched oneAPI-2025.3 grouped-GEMM DSO. Use the existing
   changed-input component harness on a healthy idle card for real W13
   (`N=2048,K=3072,M=120`) and W2 (`N=3072,K=1024,M=120`) shapes.
4. Require raw-BF16 exactness on every comparison. Stop before integration if
   summed W13+W2 median improves by less than `1.0%`, either shape regresses by
   more than `1.0%`, or variance makes ordering unclear.
5. A component pass authorizes a separately named default-off runtime selector
   and integration smoke. It does not authorize a score claim. Endpoint work
   requires a second preregistration and the unchanged fixed cold 13-prompt
   gate.

No model, target/draft precision, BF16 KV, prompt, metric, teacher, acceptance,
graph topology, cache, warmup, retry, or quality contract may change. No reset,
reboot, or privileged recovery is authorized by this gate.
