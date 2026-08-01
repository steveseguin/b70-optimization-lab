# Laguna transposed-scale prefetch preregistration

Date: 2026-07-31 America/Toronto

Status: **stopped at component gate; exact but decisively slower; no endpoint
authorized**.

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

## Result

The source-only candidate is commit
`32aa4a4057414163411d0388af10d896da1df442`. It removes only the two
`TransposedScales=true` block-prefetch sites described above. The build used
oneAPI 2025.3, completed in 16:38.63, peaked at 106,664,928 KiB RSS, and
produced this DSO:

- artifact:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scale-noprefetch-build-32aa4a4-20260801T0131Z/libgrouped_gemm_xe_2.so`;
- SHA-256:
  `2381bb5ce32f67bfdd9123f06d823f7dd81774ba1bc4d467393130e26d711d14`.

Matched static probes used 128 GRFs and showed no spill load/store. The
candidate retained the same 32 BF16 multiplies, two DPAS instructions, shifts,
and bitfield operations as the control while reducing the probe instruction
count from 370 to 291. This established that the intended prefetch operations
were removed without changing the arithmetic body; it did not predict the
runtime result.

The component comparison is preserved at:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scale-noprefetch-component-32aa4a4-20260801T0150Z`

Both fresh workers used the same deterministic changed-input corpus, physical
transposed-scale layout, rank 1, GRF128, `SCALE_VEC=1`, and prefetch distance
six. The control was the confirmed record DSO
`c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`.

| shape | control median | candidate median | speedup | raw BF16 exact |
|---|---:|---:|---:|---:|
| W13, N=2048 K=3072 M=120 | 0.3209409 ms | 0.47565495 ms | 0.674735x | 3/3 |
| W2, N=3072 K=1024 M=120 | 0.1823991 ms | 0.2565484 ms | 0.710973x | 3/3 |
| summed | 0.50334 ms | 0.73220335 ms | 0.687432x | 6/6 |

The candidate is bitwise exact but **31.2568% slower** by the preregistered
summed measure. The ordering is large and stable across all nine timing samples
per shape. This is a hard stop: no integration selector, model load, endpoint
run, score claim, reset, or reboot was attempted.

## Learning and next implication

Contiguous scale storage does not make explicit scale prefetch redundant on
BMG. Removing it exposes roughly 0.15 ms of additional W13 latency and 0.07 ms
of W2 latency per grouped-GEMM call. Static instruction-count reduction was
therefore misleading in isolation: these block-prefetch sends hide much more
memory latency than their scheduling/address overhead costs.

The result closes prefetch removal, not prefetch timing. A future experiment
may keep every scale prefetch while giving transposed scales their own distance
instead of inheriting the packed-weight distance. That is a separate candidate
and requires its own preregistration and component screen.
