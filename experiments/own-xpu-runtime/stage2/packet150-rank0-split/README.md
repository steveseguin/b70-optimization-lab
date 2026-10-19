# Packet150: rank-0 work outside the layers

CPU-prepared diagnostic on the current **packet136 banked bundle8** composition.
No device result or speed gain is claimed. Arithmetic remains
`iq3-p49-split32-v1`, with the original packet49 oracle binding and BF16 state.
The 58.798108759182306 two-card record is unchanged.

The lane-B proposal is `ops/lane-queue/proposed-p150-split-B.txt` relative to the
runtime root. It loads once and runs **skip / replay / skip / replay / skip**,
with all twelve fixed prompts at 64 generated tokens per view, plus each view's
separately reset incident64. The first control is the in-load exactness smoke.
Expected duration is 8–15 minutes; the cooperative watchdog is 900 seconds.
A timeout stops new work and drains the owned ranks without a hard kill or retry.
The proposal is not a live queue entry. The handoff is
`READY-FOR-DEVICE-split.json`, written after every preparation edit and check.

## What is measured

Every real operation still runs. Replay views add redundant work, and skip
views skip only that redundant work. These are output-neutral diagnostic
perturbations, never speed candidates:

| Segment | Original boundary | Replay or zero-work arm |
| --- | --- | --- |
| Token preparation | Lookup/dequantization/upload and token-history readback | Restore pre-call host history and prepare the identical token again |
| Capture/snapshot | Complete speculative capture, plus accept/rollback commands | Copy the same sources to the private backup again, before bank rotation |
| Suffix head | Rank-0 suffix commands through completion | Replay the identical private suffix commands before publishing the winner |
| Merge/handoff waits | Hidden publication wait, imports/exports, host handoff and remote reply wait | Check the already-satisfied hidden predicate; no real wait is skipped |
| Draft wait | Wait for the expected draft publication | Check its already-satisfied sequence; no required dependency is bypassed |

The suffix callback is excluded from remote reply waiting, preventing head
compute from being counted as a wait. Half-total and layer-body scopes supply
an explicit remaining outside cost; head-total similarly retains setup and
publication. Original and duplicate scopes are separately named. All records
are buffered until the request finishes, after its last token timestamp.
There are no profiling events inside captured commands.

Snapshot copying is asynchronous: its scope measures **host capture and
submission**, not isolated device completion. The duplicate cannot establish
that the original copy is removable. Token and suffix replay similarly
measure incremental redundant service, not a safe optimization. Required
waits cannot be removed merely because their durations are large. Extra work
can change speculative cancellation timing; cancellation counts are retained,
and every view must still match the target oracle, draft proposals and
per-prompt acceptance counts.

## Preregistered analysis

`v5/analyze.py` selects complete host scopes inside generated-token timestamps
1 through 64, excluding prefill and incident64, and sums them over **63 cycles**
per prompt. It reports each prompt and the median across prompts, all three
controls, both replay-minus-skip differences, control spread, boundary-excluded
scope counts and the remaining outside cost. It subtracts nested duplicate
snapshot time instead of counting it twice. This is a host split, not a sum of
GPU kernel times. Rank1 merge is included in rank0's reply wait.

A segment reaches the size gate only if it is **at least 0.4 ms/cycle in every
control**. A large scope is not automatically removable. These diagnostic
arms do not remove required work, so the analyzer explicitly reports
`removable: false` and names larger boundaries for a subsequent lossless
scheduling/removal test. Missing clocks fail instead of becoming zero. No
point is extrapolated and no 64-token rate is labeled as a 1–100 benchmark.

The corrected-half reader is packet149's fixed `v5/timing_report.py`, unchanged
byte for byte. Its real retained packet145 trace regression passes without
requiring absent per-request head-transfer logs. Its historical fixture times
are not packet150 measurements. The report adapter supports its retained
128-token fixtures and the registered 64-token diagnostic via declared caps.

## Source and checks

This is a private copy of packet149's closed packet136 source/harness, with its
exchange callback unreachable (`xchg` is refused by the new selector). The
inherited private exchange allocation remains; no exchange runs in this packet.
All original packet136 symlink objects remain preserved as literal links in
`lineage-inputs/packet136-symlinks`; the active oracle link is unchanged.
The native source closure is local. Original parent ELF inputs remain immutable
and hash-bound. Every existing packet and shared ops implementation is frozen.

GNU host and Intel SYCL builds pass. Four fresh miniature GNU runs check every
model-buffer byte, token history/lookup state and poisoned snapshot restore
with replay off/on. GNU and Intel controller mocks each pass twice. Real suffix
output equality remains a device oracle gate, not a CPU miniature claim.
Drain refusal/ownership, native getrlimit, real entry/environment, all worker
requests and failure teardown, report regression, temporary queue planning,
`ops/rehearse_entry.py --report` and the live pin guard all pass.

CPU commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`, and at most 4 GiB. Caps exist only in explicit CPU test/build mains;
the actual device-launch boundary must inherit unlimited address space and
unchanged resource limits. Compilers use `ops/compile_turn.py`. No full-shape
startup, model payload read, GPU, service or privileged operation ran here.
See the [work note](../../../../notes/2026-10-18-own-runtime-packet150.md).

The conditional shared-correction decision will live under `shared-correction/`.
That folder is outside this split's source seal and readiness scope.
