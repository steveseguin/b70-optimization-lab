# Packet150 — rank-0 split first, shared correction conditional

Started CPU-only on steve-b70s at about 23:07 UTC on October 18. Pull refused
unrelated dirty orchestration files; fetch confirmed HEAD and origin/main both
at `e8544b864bcbe904afce62fdcc8db2f73935a51f`. Other agents continued committing
on shared main. Their files and all existing packets are preserved.

[The new packet](../experiments/own-xpu-runtime/stage2/packet150-rank0-split/README.md)
uses packet149's closed packet136 banked bundle8 copy and fixed report reader.
The original packet49 oracle binding, 182 symlink objects, drain fix, native
resource-limit checks and closed ops launch environment remain. No GPU, service,
sudo, host setting, live queue or model payload was touched in this preparation.
Root started at 30.974 GB free; the stop floor is 25 GB, with new build material
below 300 MB and CPU processes limited to 4 GiB where a cap belongs.

## Split diagnostic

Source inspection confirms that the old half `busy_ms` clock omits snapshot
capture, and rank0's suffix head lives outside `half_step` entirely. The new
host scopes separate those costs, token preparation, handoff/peer waits and
draft waiting. Whole-half minus layer-body and whole-head minus named head
scopes retain an explicit remainder instead of silently losing setup/report
work. No device-event profiling is attempted inside captured commands.

The five views share one load: skip/replay/skip/replay/skip. The replay repeats
identical token preparation after restoring pre-call host histories, copies
identical state to the private snapshot before rotation, and repeats the
private suffix head before publication. Original required work always runs.
Already-satisfied predicate checks provide zero-wait controls; real waits are
never removed. All twelve fixed prompts generate 64 tokens per view with a
separate incident64 reset. Every token, draft proposal and acceptance count is
checked. Extra work can alter cancellation timing, which remains diagnostic.

`v5/analyze.py` reports per-cycle host cost over the 63 generated-token intervals
and requires at least 0.4 ms in every control before flagging a segment as large.
It explicitly refuses to call duplicate service removable. Snapshot time is
host capture/submission because copying is asynchronous; it is not device copy
latency. Missing scopes fail, nested scopes are subtracted, and boundary cuts
are counted. No diagnostic becomes a performance claim.

The new proposal is `ops/lane-queue/proposed-p150-split-B.txt`, expected 8–15
minutes with a 900-second cooperative watchdog. It is only a proposal. The
coordinator owns admission and any device run; this task queues nothing.

## Checks and milestone

Both native compiler builds pass. Four fresh miniature runs verify unchanged
model bytes and history/lookup state through redundant preparation and poisoned
snapshot restore. Both compiler controller mocks pass twice. The device suffix
oracle remains pending. Drain/ownership refusal, native getrlimit, wrong-unit
and environment refusal, all 78 worker requests including corrupt-output
teardown, real report entry paths, temporary queue planning, shared report
rehearsal and the live pin guard pass. No full-shape test was run.

The shared report rehearsal initially supplied its fixed 128-token fixture to
the new 64-token-only reader. The reader now validates the declared cap and
supports both diagnostic schemas; the real packet config still requires 64.
The reused packet149 trace reader remains byte-identical. Its retained packet145
regression leaves original evidence unchanged.

The source milestone is committed and pushed before the final split marker.
`READY-FOR-DEVICE-split.json` is written last and binds those checks, binaries,
proposal and source seal. Conditional work goes into a separate subfolder that
cannot change this split seal.

## Shared-correction decision

Packet149's completed v5 became readable during preparation. Its two probe
views add **7.6850055388 and 7.6971460222 ms per miss**, far above the requested
approximately 1 ms gate. Part (a) therefore stops at an evidence-bound decision;
no shared-correction prototype or shared readiness marker is warranted. The
separate `shared-correction/` decision will retain the exact source hashes and
derivation after the split handoff is sealed. This does not close other
communication schedules or claim that routed-expert-only exchange costs the
same as packet149's 96-round-trip projection schedule.

The split marker was written at **23:40:29 UTC**, **33.5 minutes after start**,
with `ready_for_device: true`. Source commit `12038c773` and marker commit
`40778f55b` are pushed. A concurrent other-host update required a clean merge
on main; unrelated dirty work was left in place. Build material is 82.09 MB;
root had 30.25 GB free at sealing.

The [separate closeout](../experiments/own-xpu-runtime/stage2/packet150-rank0-split/shared-correction/CLOSEOUT.md)
now retains the fully validated packet149 report snapshots. Control corrected
halves average 11.804703827 ms; probe means are 19.489709366/19.501849849 ms.
Subtracting the control mean gives E = 7.685005539/7.697146022 ms per miss,
mean 7.691075780. A 2–3 ms net cut would therefore require 9.691–10.691 ms
of gross savings before any additional implementation cost. The condition for
part (a) fails, so it ends with no prototype or shared device-ready marker.
All split sources, gates and the final split marker remain unchanged.
