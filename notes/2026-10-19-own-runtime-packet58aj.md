# Packet58aj: resident lookup copies on the full one-card composition

CPU preparation started 2026-10-19 01:17 UTC; 60-minute time box. Nothing is
queued, launched or submitted. The original packet58ah, packet58t, packet58u,
all other packet trees and live queues remain unchanged.

The question is whether complete anonymous copies of the two packed lookup
tensors keep fresh record windows at the warm decode rate. Packet58ah chain a
was exact but WS128 was 30.050 tok/s, with 3,736 major faults versus 124 in
WS128x. The cause of eviction is unproven. Packet58t was exact and warm-neutral
(-0.162%) on the older tile16 line; this is a new composition and stability
test, not a claim that packet58t improved warm throughput.

The private packet58ah copy retains the full packet58ag composition and adds
`lookups=mapped|resident`. Packet58t's resident storage implementation copies
all rows of both original packed tensors, checks source/copy SHA256, and makes
the copies read-only. It introduces no cache advice, pre-read, pinning, sparse
fallback, settings change or arithmetic change. A five-view process retains
the copies for its entire lifetime, including mapped controls. That load warms
source pages and cannot recreate the original cold-file condition.

Production accounting, every model window: 48,627,712,000 pinned expert bytes,
29,321,610,240 anonymous lookup bytes, 4,001,477,120 remaining file allowance,
565,325,824 measured process overhead, 4,294,967,296 shadow margin,
3,587,987,968 cache/metadata/staging allowance and 1,236,992 observed increment.
Total host bound is 90,400,317,440 bytes; adding the unchanged 8 GiB reserve
requires 98,990,252,032 bytes available. This extends packet58u's 95.401 GB
18 GB-cache admission with packet58ah's existing larger-cache allowance.
The 21,552,729,600-byte device cache is unchanged. Actual RssAnon is charged
in full; resident bytes replace the matching file allowance, never double-counted.
K1 keeps its separate 4 GiB bounded fixture and 12 GiB admission.

The smoke and bracket will be proposed on lane A, card 0, whole host, after
p153 and p151 complete their lane-B work. The one-load order is mapped,
resident, mapped, resident, mapped. A0 remains exact and reported as warm-up;
only A1/A2 count as warm controls. Both resident rates must be within inclusive
±0.5% of both warm controls. Exactness is required against iq3-p49-split32-v1.
The later seven-window chain freezes Codex only from WS, uses unit
`packet58-onecard-58aj-a`, and writes fresh `evidence/card0-58aj-a`.

Compilation waits behind the two-card preparation markers and then uses
`ops/compile_turn.py`. All preparation uses nice19, helper cores, Python -B,
closed stdin and a 4 GiB cap where runtime-limit interception is not required.
No model/GGUF payload is read. Source/build copies preserve links; the new
engine copy retains only its transitive headers and pinned object dependencies.
Parent provenance snapshots remain under lineage. Binary outputs are ignored
and restorable from pinned inputs plus the retained build commands.

Milestone 1: source integration and production memory arithmetic prepared.
Builds, new exactness gates, seals and final readiness remain pending.

## Resume p58ajr — October 19, 01:41 UTC

The owner lowered the preparation stop from 30 to 27 GB. The device floor is
25 GB after declared writes. The first free-space check was 30.140 GB; no
cleanup was performed here. Pull refused the unrelated dirty tree; fetch
confirmed HEAD equalled origin/main. The previous source commit f850e4c4e and
its unfinished edits were retained. No existing packet or live queue changed.

The earlier GNU, Intel and device builds remain hash-exact (94,364,720 bytes
of build files). New lookup copy/dequantization and complete miniature-engine
checks already passed under GNU and Intel twice, including equality to the
frozen 58ah engine, actual bracket resets, and wrong-oracle refusal. The
production-size metadata and inherited unchanged full-shape probes were
retained; no model payload or full-shape allocation was needed on resume.

The resumed seven-window intercepted entries and all 28 unit/environment
refusals pass, as do 134 passive chain tests, six screen entries, shared
loader/parser/report checks on both proposals, and the offline submission
rehearsal. A fresh frozen-path audit passed with 60,254 paths and no owned
path in the frozen union. A parallel read-only audit found no blocker in the
resident integration, byte evidence, accounting or warm-neutral comparison.
The remaining screen test's small parser compile waits for the two-card
preparation markers and the shared compiler turn. Seals and final markers
are still pending at this milestone.

The predecessor is now 58ah chain b: 31.66271941826957 tok/s, submitted as
cmvekebvh00a0rf01q3v2c3cz. Both 58ah attempts and their paging counts are
disclosed by the submission tool. Its successful replay uses explicitly
labeled synthetic substitutions over old 58ad evidence, never a new result.

## CPU preparation complete — p58ajr

The retained work and resumed fixes pass. There are 134 fresh chain tests and
102 fresh screen tests, plus the unchanged native size-parser test retained
from its previous successful compile/run. Its test source, parser header and
original successful log are hash-checked. The redundant new parser attempt
was interrupted by PID while waiting for the two-card preparation marker;
it had started no compiler or native child. The interrupted log is retained.
No compiler priority was bypassed and no native binary changed on resume.

The pin guard exposed 68 inherited object links pointing outside the private
packet. They now point to 43,865,080 bytes of exact owned copies, preserving
the symlink layout. Restoration checks pass. Total build files are
138,229,800 bytes, below 300 MB. The old refusal is preserved. The miniature
GNU/Intel equality and reset proof was rerun after fixing a receipt schema
that had described temporary output digests as repository pins. The original
receipt and executed copy-gate producer remain under lineage; the copy-gate
function is unchanged. Relative proposal pins were also corrected.

Both shared `ops/rehearse_entry.py --report` checks pass on the actual final
proposals, and `ops/launch_env.py` passes on both device entry binaries. The
13 intercepted entry paths, 28 chain unit/environment refusals, complete
report replay, honest offline submission rehearsal, seven-window plan, both
temporary lanequeue plans and both pin admissions pass. The seal binds 694
source entries; the pin guard checked 731 obligations. No Python subprocess
wall timeout remains in the active packet/screen helpers.

The proposals declare their complete measured write budgets explicitly:
48,683,776 bytes for smoke and 78,362,228 bytes for v5, including K1a/K1b.
The chain reserves 397,492,208 bytes. Each is at most three times the measured
predecessor bytes; no generic 1.1 GB/view reservation is used. Root free space
was 29.542 GB at the final checks, above the new 27 GB preparation stop;
lanequeue and each device window require 25 GB after reserved writes.

`ready.json` is deliberately false because this composition's own smoke and
five-view device bracket do not exist yet. The final packet marker qualifies
those proposals for coordinator admission; the orchestration marker prepares
the seven-window chain but keeps `ready_for_device_chain=false`. The
coordinator waits for p153/p151 lane-B runs, runs smoke then v5 on lane A with
the whole host held, and recomputes `verify_ready.py` before the chain. Codex
freezing begins only at WS. Both 58ah attempts remain disclosed; only fresh
58aj WS128 can supply a new timing. Strict512 and a second fresh timing are
still pending. Nothing was queued, launched, submitted or left running here.

The sealed preparation is committed and pushed first. Then the packet and
orchestration `READY-FOR-DEVICE.json` files are the final content writes,
followed only by read-only pin/seal checks and their separate commit/push.
[Final CPU checks](../experiments/own-xpu-runtime/ops/packet58aj-orchestration/final-checks.json)
and [coordinator contract](../experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/WINDOW.md).

## First-request timeout repair — p58ajb, resumed as p58ajb2

The interrupted preparation was recovered without rebuilding its valid native
outputs or repeating its completed engine proof. Pull refused the shared dirty
tree; fetch confirmed HEAD matched origin/main. All work here was CPU-only,
nice19 on helper cores, with closed child stdin. Nothing was queued or launched.

The failed WSCREEN omitted `--wait-seconds`, selecting the native default of
60 seconds. K1a/K1b used a 300-second per-wait ceiling within a 900-second
fixture deadline. The passing 58ag WSCREEN (58ah's qualification) and 58ah WS
also used 60 seconds. Their cold first-token times were about 23–24 seconds,
with recorded host waits around 70 milliseconds. A 59.6-second whole-request
TTFT is not evidence that one device event needs 60 seconds.

The failed resident run completed load, lookup-copy SHA256 verification and
request reset, then timed out before its first prefill token completed. It
never reached decode. The exact waited event was not recorded, so the root
cause remains unproven: a long cold operation, memory pressure and a device
stall cannot be distinguished from the old receipts. Review found no new lock
or ordering edge in resident lookup preparation; it changes the source of
packed row reads, retaining the existing staging, copy queue and dependencies.
This is a bounded timeout mitigation with better evidence, not a claim that
a GPU stall has been fixed.

All model windows now explicitly use 300 seconds per wait, retaining the
watchdogs. This is at least four times the measured cold-token envelope and
the owner's reported 59.6-second TTFT, and meets the requested 300-second
minimum. First prefill now records phase checkpoints; a failed wait records
the event, phase, token, upload/readback allocation and size, last submitted
site and elapsed wait. The arithmetic and `iq3-p49-split32-v1` oracle stay
unchanged. Fresh jobs are `packet58ajb-smoke-A` and `packet58ajb-v5-A`, under
`screen/evidence/card0-58ajb-screen-a/{smoke,resident}`.

The retained real-entry CPU probe uses device defines, real argv with the new
wait, `lookups=resident` and the real first prompt token. Production allocation,
prepare and first-prefill issue paths pass: 1,119 prepared operations, 1,110
issued operations and 1,480 sites. It substitutes a CPU transport and synthetic
packed weights, including bounded PLE rows; peak child RSS was 1,106,771,968
bytes. It does not test GPU scheduling or full resident-memory pressure.
On resume, the probe binary hash and generated entry were verified against
the retained receipt and current source. All 116 historical diagnosis input
hashes still match, including the failed smoke and predecessor timing files.

The GNU/Intel exact-output, repeat, request-reset, frozen-58ah equality and
wrong-oracle refusal proofs passed before interruption and remain valid.
Resume reran the 134 passive chain tests and six intercepted screen entries
because their source receipts were stale. The 103 screen checks remain bound
to their tested source. Both actual proposals again passed the shared native
loader/parser and one-card report rehearsal. Its preparation adapter still
reports WARN: it cannot admit this unranked one-card argv/private RoPE path.
The independent device-define probe supplies the scoped preparation evidence;
no synthetic rank or sandbox bypass was added.

Stale proposal and rebuilt-binary receipts left by the interruption were
refreshed from the passing checks. The original copy/parent manifests are
preserved under `lineage/packet58ajb-before`. Both temporary queue plans,
the seven-window plan, final seal and pin admission pass. Build files total
160,608,865 bytes. Root had over 30 GB free during final checks, above the
27 GB preparation floor. The original failed smoke stays unchanged. Its three
1,688,594-byte kernel-boot logs are retained to establish the incident's fault
baseline; restore their exact bytes from this commit's Git blobs. Generated
driver caches stay on disk and are ignored by Git, not deleted.

The preparation is committed and pushed before the two READY files are written
last and committed separately. Both markers set `ready_for_device=true` for
the fresh smoke/v5 proposals, with coordinator admission still required.
Both retain `ready_for_device_chain=false`; `ready.json` still refuses the
seven-window chain until its own exact smoke and five-view device gate pass.
Device quality and performance remain pending. No service, GPU job, live
queue, host setting or external submission was changed.

Evidence: [diagnosis](../experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/evidence/packet58ajb-diagnosis.json),
[CPU preparation](../experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/evidence/packet58ajb-preparation.json),
[final checks](../experiments/own-xpu-runtime/ops/packet58aj-orchestration/final-checks.json).

The post-marker pin check caught one additional metadata issue: recursively
pinning the historical diagnosis caused the shared guard to interpret old
window-relative build paths as current inputs. The finalizer now binds that
diagnosis with a content digest, keeping the incident out of the live build
closure. The failed first marker attempt was removed before this correction;
the corrected two markers are regenerated last and checked before their push.
