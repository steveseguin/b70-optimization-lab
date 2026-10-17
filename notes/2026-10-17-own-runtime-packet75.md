# Packet75 record bundle — October17

CPU-only preparation began21:09UTC on steve-b70s, with a75-minute time box.
The initial pull --rebase refused the coordinator's dirty packet70 log; fetch
confirmed main matched origin. That file and every frozen packet/ops tree stay
untouched. Root had27GB free. Only the new packet75 and orchestration folders,
plus this explicitly requested note, are edited. No GPU, service, sudo, settings
change, kill or chain launch is used.

## Merge and byte-check milestone

Packet70 is the source of the chain,90-second gaps, resumed-submission gates,
and fixed draft-HC/batch/24+24 preset. Packet74's packed head/dense choices and
packet73's HC/expert choices compose independently:24 registered combinations.
The dense storage selector excludes the fused HC groups. The shared v4-lanes
wrapper is referenced under source hashes from d5b060769, never hand-modified.
Every chain/window plan now calls the actual shared lane admission predicate.

GNU and Intel each pass two fresh executions of both operator fixtures:44 HC/
expert cases and60 packed-dense cases per execution, including FP32 chains and
exact dequantization. The merged GNU and device binaries compile/link. Receipt
creation initially missed the inherited RoPE symlink; exact original bytes were
restored, then completed compiler commands/output hashes were checked before
finalizing the receipt. No compiler or device result was fabricated.

The mandatory full-shape mock keeps actual production plans,3380-byte expanded
head rows, allocation gates, command capture, speculative snapshots and draft
initialization. It replaces only payload access and backend execution in generated
test copies. It uses numeric device-address tokens with real logical extents,
so it cannot touch GPU or allocate tens of GB of host memory. Full sweep remains
in progress at this milestone; device quality/speed remain pending.

The helper reads each packet's own comparison and best-selection logic in
isolated Python processes, then requires its exact best-of-A B confirmation.
It writes ready.json and the coordinator command; it never starts a chain.

## Complete CPU and chain preparation

All 24 composed views now pass their own selected implementation against
reference bytes under GNU and Intel, twice each: 96 fresh executions, 90 cases
per execution. All 48 full-shape mock runs pass across both ranks. They use
the real 3,380-byte expanded-head stride and retain post-load captures,
speculative snapshots and the rank-one draft prefix. A deliberately undersized
packed-head allocation is rejected by the real extent check. No GPU or model
payload is touched by these tests.

The chain/submission test set passes 117 tests plus 32 subtests, including
registered and pinned-resume submissions, selection replay, lane admission and
queue boundaries. The submission records every selected dense, HC and expert
change; all normal and resumed notes are 1,649–1,787 characters. The live
wrapper stays the unmodified shared code. Portable historical receipt replay
uses a separately hash-pinned packet70 verifier because the shared verifier
does not accept in-memory receipt bytes; it is not the live lane wrapper.

The input census finds 12,709 static paths and 352 prospective write paths.
Build artifacts occupy about 650 MB, below 1.2 GB. All chain prechecks are CPU
only. Evidence and reproduction steps are in the packet
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet75-record-bundle/CPU-PREPARATION-CLOSEOUT.md).

Release-order review confirms the shared screen wrapper releases both locks
before CPU report aggregation, as packet70 did. Chain windows retain the
packet70 order: initial reports first, then drain/lease completion, then the
final admission-bound receipt. No lane-wrapper code was copied and modified.

## Final CPU milestone and screen snapshot

All 264 real window plans pass: 24 composed views times 11 chain windows.
The baseline selection was restored afterwards. Final seal, input, storage,
selected-chain plan and queue-plan checks all pass. The orchestration tests
also pass all 11 checks, including single-packet wins, incomplete screens,
precheck failure, and the required precheck order. The build uses 649,893,864
bytes. No registered chain output directory exists.

At the final preparation snapshot, packet74 has a complete exact lane-A grid
but no winner under its own best rule: none of its three candidates beats
both production controls. Packet73 is still incomplete. Therefore production
dense remains the only eligible dense setting for this attempt, and
`ops/packet75-orchestration/ready.json` stays false pending packet73. The helper
can select a packet73-only winner after its exact lane-B confirmation, reseal
without compiling, and write the exact chain command. It never launches that
command. No background waiter or service was started.

Milestones are pushed to main: `40f98297b` (merged engine/initial gates) and
`8e2611f7a` (all compositions and complete chain preparation). CPU work finished
well inside the 75-minute limit. Device qualification remains the next gate.
