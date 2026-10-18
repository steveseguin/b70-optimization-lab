# Packet102: exact IQ2 lookup batching and shared gate/up input

CPU-only preparation on steve-b70s, with a two-hour time box. The initial
`git pull --rebase` refused coordinator-owned dirty files. Fetch confirmed
main equals origin/main; no shared files were stashed or replaced.

## Microbenchmark first

The standalone microbenchmark compiled before the full engine or long CPU
gates. Its lane-B proposal is
`experiments/own-xpu-runtime/ops/lane-queue/proposed-p102-micro-B.txt`.
The real lane queue planner passed on a temporary queue; no live job was added.
All 15 micro runner and threshold tests pass. The build receipt binds the
binary, source closure, runner and analyzer without mutable packet97
orchestration outputs or future engine seals.

The control is packet97's `wide64` gate/up with the existing half-cache,
canonically selected as `exp-halfcache`. Five candidates retain that layout:
lookup batches of two and four, shared gate/up activations, and each batching
choice combined with shared activations. Independent gate and up weights,
scales, FP32 chains and adjacent trees remain separate. Signs are inline code
bits; the dependent memory read is the IQ2 grid lookup.

The diagnostic uses full 640-by-2560 gate/up matrices, 512 experts and ten
selected experts. Forty alternating control/candidate pairs require at least
15% lower median kernel time overall and in each order. Output and status
bytes must match. This is not a model throughput claim.

V5 generators exist, but packet98b documents that their frozen native engine
cannot switch these expert kernels or admit this lineage. Follow-up proposals
will use v4, one candidate per B bracket and A confirmation. Records stay on A.

Byte identity under GNU and Intel, linked offline assembly, full startup-path
CPU dry runs, memory admission and screen seals are still in progress. No GPU,
service, sudo, host setting or existing packet/ops file was changed.
