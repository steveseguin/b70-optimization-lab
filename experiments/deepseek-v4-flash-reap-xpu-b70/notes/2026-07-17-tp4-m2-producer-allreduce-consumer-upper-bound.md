# TP4 M=2 producer/all-reduce/consumer upper bound

Date: 2026-07-17

## Outcome

The fixed-M=2 TP4 producer/all-reduce/MHC-consumer boundary clears its
component gate twice. Two independent 40-epoch confirmations save **0.953386
ms/cycle** and **0.928339 ms/cycle** at the slowest rank, above the required
`0.50 ms/cycle`. Every one of 87 reduced BF16 `[2,4096]` tensors and all four
outputs from 85 boundary-distinct native M=2 MHC consumers are bitwise exact
on all four B70s in every measured epoch.

This is a dependency-relaxed hardware ceiling, not an integrated decode win.
It authorizes the guarded finite event-chain implementation; it does not
authorize a performance or LocalMaxxing claim.

## Why the first measurements failed

The current oneCCL Arc LL-ring path accepted dependencies at
`allreduce_sycl`, then discarded them before `allreduce_ll_ring` submitted the
device kernel. Early reductions could therefore read the previous producer
value. A clean oneCCL worktree based on production `48fda4f0e` now threads the
incoming SYCL events through the ring and calls `cgh.depends_on(dep_events)`.
The default-off experimental commit is `6fd2356`; its isolated runtime is
`/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-deps-llring-20260717`, with libccl
SHA-256 `7b239bd6b70fcb8ed6dc708e4e068cca603ddc5d4fb878ade566943bd56d1f47`.

That repair made every reduced tensor exact, but repeated MHC executions with
the same exact input still disagreed during early epochs. The custom MHC
operation did not expose completion strongly enough to the following graph or
stream work. Copying one BF16 from the final `layer_input` after each
85-consumer chain supplies the graph-visible device witness. With that witness,
all MHC outputs become exact from the first measured epoch. The witness cost is
included in the passing timings.

One further measurement bug was caught before promotion. The specialized Arc
ring implements sum, so asking it for `ReduceOp.MAX` summed four rank times.
The harness now gathers scalar times and computes the maximum on the host.
The earlier correctness-valid run remains classified as timing-invalid.

## Confirmed measurements

- confirmation A: serial `8.623024 ms`, overlap `7.669638 ms`, saving
  `0.953386 ms`;
- confirmation B: serial `8.601899 ms`, overlap `7.673560 ms`, saving
  `0.928339 ms`;
- both use 40 changing epochs, 87 reductions, 85 consumers, the exact record
  XPU extension hash, wide-epoch geometry, and the isolated dependency-aware
  oneCCL runtime.

Raw evidence:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-m2-producer-allreduce-consumer-deps-witness-confirm-a-20260717T0530Z`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-m2-producer-allreduce-consumer-deps-witness-confirm-b-20260717T0531Z`.

Invalid diagnostics are preserved under the three preceding run directories
listed in the structured result packet.

## Next implementation gate

Build a finite same-queue chain:

```text
producer event -> unchanged dependency-aware Arc ring -> native M=2 MHC
consumer event -> one-BF16 completion witness -> next model consumer
```

The implementation must remain fixed-shape, TP4-only, persistent-buffered,
default-off, and fail closed. It must not use resident polling, an auxiliary
polling queue, readiness markers, or MHC arithmetic inside the ring. Before a
service load it must pass dependent producers, rank skew, 40 changed eager
epochs, and at least 70 changing fixed-address graph replays across positions
28 and 58, while retaining at least `0.50 ms/cycle` at the slowest rank.
