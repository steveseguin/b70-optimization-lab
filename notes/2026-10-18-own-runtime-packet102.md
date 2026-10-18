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

## CPU and assembly milestone

All six views (control and five built candidates) pass GNU and Intel twice.
Each run compares ten cases, 73,728 raw FP32 chain values and 2,304 tree values,
plus all 1,024 IQ2 grid indices × 256 sign bytes across six exceptional/finite
scale patterns. The output gate includes full gate/up row counts, partial and
invalid routes, inactive/error state, NaNs, infinities, subnormals and signed zero.
No tolerance is used. See `evidence/cpu-byte-identity.json` in the packet.

The final eligible set is **batch2, batch4 and shared-input-only**. All use 128
registers with zero scratch messages and zero flag spills in linked offline
BMG assembly. `lookup_proof.py` checks vISA aliases, maps grid-load instruction
IDs to final assembly, and rejects a batch consumed or waited on before all
its sends issue. All eight grid reads per step are checked. Shared-input code
has sixteen activation d32 reads per step versus thirty-two in production.
These are code-generation findings, not measured speedups.

The initial shared V8 mapping spilled. V4 preserves the same 32 logical chains
and adjacent reduction tree with less live state. Consolidating its duplicate
output/status paths removed the remaining spills for shared-input-only.
The V4 batch2/shared and batch4/shared combinations still spill; they are
built and byte-exact but **closed at the no-spill gate**, excluded from micro
and screen candidates. A per-kernel 256-register property compiled to an
extension the installed offline stack rejects; it is not used. All these
attempts retain their source and assembly under `evidence/attempt*`.

The early micro proposal is unchanged. Its rebuilt binary now includes only
the three eligible candidates. Device execution additionally requires the
completed CPU identity, linked assembly and issue-order proof. Planning can
still run before those gates; no plan is a speed or quality verdict.

The generated build mirror was mistakenly included in the first commit and
removed from tracking immediately in the next pushed commit. It remains on
disk and is reproducible with `kernel_gate.py`; no unique evidence was deleted.
The copied 4 MiB `rope.bf16` is required by real startup, carries its parent hash
in `copy-lineage.json`, and restores byte-for-byte from packet97 or Git.
The build is approximately 153 MB logically, below the 300 MB cap.

The final screen control snapshots packet97's selected half-cache composition:
`route-fast`, `rec-both-plus`, HC wide and ordered retirement, with all other
choices and draft settings preserved. The local immutable snapshot is
`lineage-inputs/control-selection.json` (SHA-256
`6c58206cad748a8385b41389d5b9c05ff1891340b4bd0b12ce3611b5cddca739`).
Its original mutable selection/orchestration files are not seal dependencies.
The final byte metadata and full startup gates were rerun for this exact
composition; the earlier rec-parallel setup is not the screen baseline.


## Final CPU handoff

All twelve full-shape startup runs pass (six views, both ranks), including
24 short/misaligned allocation refusals and five selection refusals. These
exercise real Engine initialization/capture and actual allocation accounting,
without reading model payloads or calling a device. All twelve memory
admissions pass. The shared worker imports in the actual restricted queue
environment. Eighty shared-wrapper tests and 23 packet tests pass.

Four views are sealed: half-cache production, batch2, batch4 and shared input.
Seven proposed jobs pass the real queue planner on a temporary copy. The first
is [`proposed-p102-micro-B.txt`](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p102-micro-B.txt).
The other six are single-candidate B control/candidate/control brackets and
conditional A confirmations. They refuse device admission until the measured
micro gate passes; A additionally requires an exact B win with unchanged
acceptance counts. The micro gate requires at least 15% lower kernel time
overall and separately in both alternating orders. Records remain on lane A.

Packet97's separate KD host-reference refusal was reported during preparation.
Packet102 does not claim record-chain readiness: copied K2/submission and
chain entry points explicitly refuse, and the original copied implementations
are retained where replaced. All six selections exercise these refusal
boundaries in CPU tests. Qualifying every record window and its host reference
is separate follow-up work. No inherited chain is submitted or proposed here.

The final verification receipt binds the CPU evidence, four seals and seven
proposals. This task ran CPU preparation only and edited no live queue.

## Coordinator result observed during final checks

The coordinator independently executed the early micro proposal while these
CPU gates finished. [Its result note](2026-10-18-own-runtime-packet102-result.md)
reports no qualifying arm. The local hash-bound receipt verifies all three
byte/status checks passed and the micro drained cleanly. Batch2 reduced kernel
time by 1.89%; batch4 increased it by 0.16%; shared input increased it by 3.31%.
None approached the required 15% reduction in either alternating order.

All six conditional screens remain closed. The seven original successful
pre-execution plans are retained; the final planner checks six screen plans
and correctly refuses to overwrite the completed micro output. No device
retry, model screen or record submission was launched by this task.
[Closeout](../experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/MICRO-CLOSEOUT.md).

The coordinator's retained boot-journal capture exceeds 1 MiB. It is required
to audit fault review and clean drain under that exact boot; keep its original
bytes with the window receipt. Restore it from this evidence commit.
