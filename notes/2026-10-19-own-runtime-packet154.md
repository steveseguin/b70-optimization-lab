# Packet154 rank-1 reply-wait attribution

CPU-only preparation, October 19. Packet150 measured 1.54 ms/cycle of rank0
remote reply waiting but did not attribute the rank1 work inside it. Packet154
vendors that harness and the packet136 base and adds command-correlated host
scopes. No GPU, service, sudo or host setting change; no live queue edit.

Entry: main equaled origin/main at d61bfcdf after pull refused unrelated dirty
and staged files. Root began at 30.756 GB. All existing packets and the frozen
path union are treated as read-only. Compile turns go through the shared
arbiter, after packet153 and packet151 builds.

Milestone 1: source closure and rank1 scopes prepared. Analyzer tests cover
complete smoke/bracket, exact command joins, missing/empty/incomplete streams,
invalid clocks and nested overlap conservation. Device equality and attribution
remain pending. Inherited binary objects are copied into this packet, with
source paths and hashes retained in evidence/vendor-objects.json; no mutable
parent object alias is needed for its incremental build.

Milestone 2: both GNU host and Intel SYCL binaries compiled. Peak compiler child
RSS was 748,376 KiB. The byte/restore miniature passed four runs; GNU and Intel
controller mocks passed twice each, including repeated merge/export byte checks
across ties, signed zero, infinities and NaNs. Five analyzer tests pass, including
missing/empty/incomplete streams and nested overlap conservation. Per-rank
admission rechecks the unchanged memory plan with retained 64 KiB scratch;
it is not new device-residency or full-shape measurement.

Budget correction: 250 MB/view × five would exceed three times the measured
243 MB total. The stricter bound is 145 MB/view = 725 MB, below 729 MB. Actual
writes remain to be measured. Expected duration 7–10 minutes; watchdog 40 minutes.
No local CPU subprocess uses an elapsed-wall timeout. Shared frozen tools retain
their own implementation; their checks will be reported separately.

The first complete validation passed both lane entry paths (including wrong-unit
and poisoned-environment refusals), native limit interception, all 78 simulated
requests, corruption abort and a first-request empty-stream abort. Both temporary
lane-B plans and shared `ops/rehearse_entry.py --report` checks passed. The shared
`ops/launch_env.py` loader check passed for both binaries. The vendored environment
helper is byte-identical to that shared authority. No device was opened.

Final review added per-scope control ranges and both replay-minus-skip deltas,
and removed the remaining elapsed-time assertion from the cooperative-stop CPU
test. The final qualification reruns the dependent checks before sealing.
The focused normalized-parent delta is `evidence/rank1-scopes.patch`; exact input
and current source hashes are `evidence/scope-origins.json` in the new packet.

During the final repetition a shared fault/ownership latch appeared and the
original entry rehearsal correctly refused. That CPU failure is retained in
`v5/evidence/entry-operational-latch-refusal.log`. The entry test now explicitly
simulates absent operational latches for its positive path and adds a present-
latch negative for every lane/window. The real launcher is unchanged and still
refuses live latches. No latch was removed, no device health probe was run, and
no other process was stopped. `evidence/operational-observation.json` records the
passive observation; it is not a pin on live coordinator state.

Final CPU qualification passed. Four entry routes and twelve unit/environment/
latch negatives pass; native limits, all request paths, reports, both temporary
queue plans, shared report rehearsal and pin admission pass. The passive latch
recheck found zero latches. GNU/Intel outputs and all source/gate hashes were
verified again before handoff. No full-shape startup, model payload read, GPU,
service, privilege or live queue operation occurred.

The smoke and split proposals are `ops/lane-queue/proposed-p154-smoke-B.txt`
and `proposed-p154-split-B.txt`. Device equality and measured attribution remain
pending. CPU readiness never waives fresh storage, memory, ownership or fault
admission. The 58.798 tok/s record is unchanged. The final marker is written
last, after the qualification milestone is committed and pushed.

## Packet154b — final-marker pin admission repair

The coordinator's refusal was reproduced against the complete final marker.
The guard follows hash-linked JSON and treats `source` / `source_sha256` as
a live pin, even in origin evidence. All six packet150 origin entries were
therefore mutable cross-packet dependencies. The final marker also pinned this
work note outside the packet. The earlier pin pass preceded that final closure
and did not establish admission of the handed-off marker.

`evidence/scope-origins.json` now records repository-relative origin names under
`origin_provenance_only`. Its six `path` / `sha256` records bind only the existing
vendored packet154 copies. Original source hashes remain in Git history. The
marker links this work note as provenance only. No runtime source, binary,
proposal, arithmetic, smoke scope proof or deadline changed; no native rebuild
was needed. The unchanged CPU seal still verifies `iq3-p49-split32-v1`.

Validation: both lane-B proposals pass the live `lanequeue.py plan --lane B
--directory <temporary-copy>` and the shared `ops/rehearse_entry.py <proposal>
--report --json`. All 23 live `test_pin_guard` unit tests pass. The same live
`lanequeue.check_pins` used immediately before launch passes for both jobs.
`evidence/p154b-admission.json` records commands and hashed logs; the original
seven-pin refusal is retained in `evidence/p154b-before-refusal.json`.

The initial rehearsal used a 2,000,000,000-byte address-space hard cap, below
the frozen sandbox's fixed 2 GiB limit, so child setup refused before execution.
That failure is retained as `evidence/p154b-smoke-rehearsal-cap-refusal.log`.
Repeating with the sandbox's matching 2 GiB cap passes. Checks used nice 19,
CPUs 8–15 and 24–31, Python `-B`, and closed stdin. No new elapsed-wall timeout
was added. No GGUF payload, GPU, service, sudo, settings, live queue or other
packet was touched. Device equality and attribution still await the coordinator.

Entry HEAD matched origin/main at `651fb9c65a63a573d4e9f3c15cf3d254eaf4ea5a`
after pull refused unrelated dirty files. The minimal readiness reseal is the
last packet write, with `ready_for_device: true`; fresh storage and operational
admission remain mandatory. Only packet154 and this note belong to this commit.

## Packet154c — restore the unchanged 25 GB device storage floor

The 01:55:16 UTC smoke refusal happened before device work. Both screen checks
incorrectly used the CPU preparation stop line of 30 GB while their messages
said 25 GB. Both now enforce 25 GB after planned writes. The packet-local
storage helper uses the same floor; the private vendored helper called by the
screen and worker also now enforces 25 GB instead of its inherited 8 GB.
The two CPU preparation checks use the coordinator's new 27 GB stop line.

Planned writes are unchanged: 145 MB for smoke and 725 MB for five views,
within three times the measured 243 MB. The new CPU regression executes both
actual screen admission expressions and both storage helpers. Smoke and bracket
pass at 29.7 GB and at exactly 25 GB plus planned writes; one byte below the
required amount refuses. The full bracket needs 25.725 GB free.

This is a minimal source reseal with no native rebuild. Both native binary
hashes and every native build input were verified unchanged. The build receipt
explicitly records that only its driver's CPU admission check changed. The
affected entry, limit and report checks were rerun; all pass. Both proposal
outputs have fresh `device-p154c-split-` names. Each proposal passed the live
planner on a temporary queue copy and the same shared entry/report rehearsal
used for packet154b. All 23 pin-guard unit tests pass. Evidence and command logs
are under `evidence/p154c-*`; `p154c-validation.json` links the checks.

Work used nice 19, CPUs 8–15 and 24–31, Python `-B`, closed stdin, and less
than 2 GB actual RAM. No GGUF reads, compiler, GPU, service, sudo, settings or
live queue changes occurred. Other packets and shared tools stayed frozen.
Pull refused unrelated dirty work; fetch confirmed entry HEAD and origin/main
both at `3e275ea2c33cec553df353cc26bbcdb78a5ef5cf`.
The readiness marker is written last with `ready_for_device: true`; the final
marker and both proposals receive a read-only prelaunch pin replay. Device
equality and attribution remain pending, with fresh coordinator admission
still mandatory. The 58.798 tok/s record is unchanged.
