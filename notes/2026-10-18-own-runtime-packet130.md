# Packet130 — service the head suffix at a layer boundary

CPU preparation in progress. No device speed or full-model equality is claimed.
The coordinator owns all future device runs. This task uses no GPU, service,
sudo, live queue edit or host setting change.

## Frozen source trace and preregistration

Source: `stage2/packet124c-record-bundle`, bundle7, 24/24 target layers,
80,128-row draft prefix, 46,080-row target suffix, BF16 KV and
`iq3-p49-split32-v1`. The new tree is
`experiments/own-xpu-runtime/stage2/packet130-suffix-interleave`.
Its copy manifest records original hashes and symlinks; parent trees are frozen.

The native controller starts rank1's half, then synchronously executes rank0's
speculative half in `Backend::start(0, half)`. Only after that call returns does
`Backend::wait(1)` call `before_remote_wait`, which invokes suffix `service`.
Rank0 therefore does not even import the verified hidden state until its entire
half has completed. `service` waits for the release-published request, validates
sequence/position/fixture, drains rank0, imports 5,120 bytes, resets private
error/active scalars, issues the unchanged captured Q6 GEMV, argmax and pack,
drains, exports 16 bytes and release-publishes the reply.

Rank1 calls `export_hidden` immediately before submitting `logits`, binding the
current verified `final.mix` writer. It submits its 202,240-row prefix before
`publish_hidden` waits for export completion and publishes the mailbox request.
It completes prefix argmax, drains, packs/exports its best, then spins for the
suffix reply in `merge_target`. Prefix and suffix merge retain global tie order
and sticky nonfinite refusal. Rank0's speculative streams are never the head input.

Candidate: use the existing ordered queue, with at most one target layer queued
while a verified suffix request is outstanding. At each completed boundary,
check the mailbox; run the exact suffix once when ready, then resume target
layers in their original order. Suspend the target cancellation/submission
observers during private head service. The normal remote-wait path remains the
late-arrival fallback and must not service an already-completed request twice.
No new queue, priority extension, kernel arithmetic, target shape or state bank.
The scheduling choice switches only at a drained v5 request boundary.

Tradeoff: host layer fences can delay rank0; this is a testable scheduling
candidate, not a predicted win. Record suffix wait/service and rank0 half
completion in both arms. Miss verification, cancellation checks and exact
rollback remain required. Test early, boundary, late, stale and aborted arrivals,
hits/misses, repeated requests, cross-partition ties and nonfinite refusal.

Planned device screen: lane B only; a 12 × 64 candidate smoke first, then a
single-load production / interleave / production / interleave / production
12 × 128 bracket. Every output must equal the registered oracle; acceptance
must stay identical. Require both candidate rates at least 0.5% above the
strongest control, control drift at most 3%, and all teardown/quality gates.
Allow 6 minutes for smoke and 20 minutes for the bracket; watchdogs at least
1,440 and 4,800 seconds respectively. Proposals only, planned on temporary
queue copies. These are diagnostic screens, never a strict512 promotion.

## Workspace

`git pull --rebase` refused unrelated dirty orchestration/evidence files.
`git fetch origin` confirmed HEAD and origin/main both
`c7b59d9429e3c2b1c6c351f523203e36ec1327fa`. Host is `steve-b70s`.
Initial root free space exceeded 29 GB. Existing dirty work is preserved.

## Implementation milestone

The new copy now has the layer-boundary controller and runtime schedule switch.
The suffix keeps its original kernel captures and private allocations. The
candidate intentionally does not act on newly early target verification during
its current speculative half: the baseline cannot receive that verification
until the half returns. This preserves the same speculative work, bank swap
and miss rollback; owner cancellation and explicit cancel-launch tests stay live.

The GNU runtime entry and device-target entry compiled during the initial
build. Remaining serialized compilation is waiting behind another packet's
compiler turn and the coordinator's whole-host hold. Final native gates and
seals are still pending; these initial objects are not a qualification.

The copied v5 helper contained the old unclamped cooldown sleep. The retained
negative log catches it. Applying packet124c's unchanged helper inside the new
copy makes all four clock-crossing tests pass. All four teardown-refusal tests
pass, including actual CPU child stop pipes, preserving an unrelated child and
the previous drain record. Pre-exec limits and the hit/miss timing-join unit
test pass. No GPU, service, live queue or frozen tree was changed.

## Qualification boundary

The final qualification driver runs each CPU gate once and stops at the first
failure. Heavy children set an 8 GiB cap only in their own main entry; native
launch-limit probes retain and compare the inherited unlimited limits. Both
smoke and bracket wrappers refuse launch without the final extended-gate
qualification, in addition to the native CPU seal. The bracket additionally
requires the exact twelve-prompt smoke. Both planned watchdogs are 4,800 s.

The preliminary idle build and two waiting CPU gate coordinators were stopped
by their recorded PIDs after source updates. No compiler or device child was
active. Their partial build is explicitly superseded. The final build snapshots
all native source hashes before compiling and refuses source drift before
writing its receipt. The whole-host hold and serial compiler lock remain intact.
