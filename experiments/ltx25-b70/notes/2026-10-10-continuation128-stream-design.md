# Packet 128: let the receipt handoff pass before periodic cleanup

The [timestamp analysis](2026-10-10-continuation-evenchunk-stall.md) identifies
full Python collection and allocator cleanup as the repeated handoff blocker.
All 119 long packet 126 handoffs overlap that pair. Preview and decode-tail work
finish beforehand. The receipt handler already serves stored JSON bytes.
Moving preview encoding into a process would not address the recorded stall.

Packet 128 inherits sealed 127, manifest
`c2564507a9bb88a948bc726d079d8b5a981b3834ad54801be47d0d0c81dc359e`.
Its new `LTX_MAINTENANCE_MODE=idle` option changes when the existing cleanup pair
runs. Default `parent` retains 127's decisions and queue waits. The exact source
transform is in [maintenance128.py](../recovery/20261010-continuation128-stream/maintenance128.py);
[contract](../recovery/20261010-continuation128-stream/CONTRACT.md) and
[launch reference](../recovery/20261010-continuation128-stream/LAUNCH.md) give the
scope and coordinator commands.

## Scheduling and exactness

With GC 10, periodic cleanup becomes due as before. Instead of collecting
immediately after a prompt, the candidate waits for a 250 ms quiet gap. A queued
successor runs first, without clearing the pending cleanup debt. At 60 seconds
since the prior collection, cleanup is mandatory at the next prompt boundary.
An in-flight prompt can exceed that age. Startup and explicit free/unload keep
forced cleanup; native exception handling and failure order remain unchanged.
GC 60 already becomes due at this hard bound, so idle adds no deferral there.

The initial 100 ms design was widened using saved packet 126 timestamps
([replay](../data/resume-20261008/continuation128-handoff-grace.py),
[evidence](../data/resume-20261008/continuation128-handoff-grace.json)).
This selection includes boundary receipt pairs in the captured source inventory.
Among 126 handoffs without a long maintenance pause, next-queue minus executor
exit has median 65.4 ms and p90 119.7 ms: 103 fit below 100 ms, 124 below 250 ms.
The maximum was a real 7.19-second client gap, retained in the evidence. A
bounded gap cannot cover arbitrary client delay. This is an admission grace,
not a sleep added to an already queued prompt: queue.get wakes on a successor.

Both original cleanup calls remain on the prompt thread. Automatic GC remains
active. No collection generation, heap-freeze rule, tensor, model arithmetic,
precision, snapshot, file hash, preview encoder or write durability changes.
The original maintenance timestamps remain and a bounded decision history adds
quiet/deferred/forced reasons and collection age. No cleanup runs on another
process's unrelated heap. The default path has the same condition and timeout
arithmetic as 127; the additional timestamp bookkeeping does not choose a
changed parent schedule.

The new mode is in the plan, run name, launch identity, status, all receipt
options, verdict and client expectation. The client pins the inner plan hash.
The runtime validators retain ancestor fixture defaults but every 128 runtime
emits the explicit mode, and the 128 client refuses missing or changed modes.
The new option is scoped to 145/169 cone/frame paths, full fingerprint snapshots,
legacy auxiliaries and serial display3 or inherited parallel display2. Existing
169 residency, GC60 and snapshot-cache admission limits remain in force.

## Forecast and remaining gates

Forecast at 145 frames is 5.50–5.75 seconds for six seconds of new video,
center 5.60 seconds / 0.933 s/s. Removing only the observed excess handoff from
the saved trace gives an illustrative median 5.567 seconds / 0.928 s/s. Neither
is a benchmark. Reused-text rows may approach 5.57 seconds, while fresh text
every fourth chunk still costs more. Equal pooled parities are not supported.
The GC60 whole-window result was neutral, so a period win must be demonstrated,
not inferred from eliminating one wait alone.

At 169, keep the prior parallel-display forecast of 6.20–6.65 seconds for seven
seconds of new video (0.886–0.950 s/s). The opportunity from a two-chunk cleanup
beat is about 0.14–0.16 seconds per chunk on the mean if that beat is present;
it cannot simply be subtracted from another session's median. The combination
is not measured here.

Coordinator update during CPU preparation (CURRENT, 09:15 UTC): packet 127 at
169 with parallel display2 refused during qualification at 8,465,399,808 bytes
free, below its 6.5 GiB transient reserve plus 2 GiB floor. There was no GPU
fault. This blocks a 169 live recommendation until memory headroom is recovered;
128 changes no memory admission and cannot fix that refusal. The 169 forecast is a
conditional performance budget, not an admissible first launch. Do not lower
the reserve to make it fit.

Forced minute-age and automatic collection can still stall the GIL. A long
client gap can allow cleanup before admission. A 250 ms quiet gap can overlap
background decoding, as parent cleanup could. Thus this candidate removes the
usual short-handoff opportunity for the recurring two-chunk stall, not every
possible event-loop pause. Native memory plateau, retained reference/byte
checks and matched speed on two fresh qualified servers remain open. No native
speed or quality claim is made from CPU tests.

## CPU preparation and verification

All work used nice 19, OMP/MKL 2 and the pinned Python with -B. There was no GPU
work, model server, launch/check-only, live endpoint/port8188/unit access, signal,
render-device open, host-setting change, existing-run or live client-tree write.
The coordinator's live server remains theirs to operate.

The timing test invokes the actual aiohttp receipt handler without a socket,
while a synthetic decode thread runs. A simulated 300 ms C operation holding
the GIL reproduces the parent maintenance stall; idle deferral serves the exact
same receipt body within 50 ms. This models the selected boundary, not arbitrary
GIL-holding work or network delivery. Executed transformed-worker tests also
check debt across successors, idle wakeups, hard age, explicit free/unload,
failure flow, and unchanged model-call arguments.

The [build receipt](../data/resume-20261008/continuation128-build.json) records
the final seal, recursive file and cache counts, complete CPU suite counts,
all-pins results, log hashes, source identity and development failures. The
first development suite ran before option inventories were complete: receipt
and verdict validators rejected maintenance_mode. They were fixed before seal,
with dedicated invalid/mixed-mode tests. A float-fixture comparison, inherited
main-source and explicit-parent-mode assertions, and stale in-process plan imports during development were
also corrected; logs remain preserved. Final validation covers **763 unique
recovery cases**: 761 passed the full run; the corrected 17-case GC module and
7-case snapshot/runtime class pass, covering
both inherited fixture failures without double counting. All **3,322 client
checks across 31 suites**, **10 mocked preflight checks**, and **two complete CPU
candidate runtime cases** pass. The two candidate cases cover 22 mocked chunks,
12 cross-chain tensor hash comparisons and every preview file hash. The actual
receipt-handler synthetic timing gate passes below 50 ms (about 21 ms, versus 306 ms
for the parent simulated GIL stall).

The sealed packet has **2,171 recursively verified files**, zero Python caches,
and author component bytes identical to the seal after all tests. Manifest:
`bd6471f7e10d2ec3219879a281820056178556a3388f50fb7c2c7896199f5ead`.
Inner plan:
`d0f849d2f9b59bf8a28ae5c9f5186ee68914d372796c4d63e2ca5bd5c492f3d5`.
The broad literal-pin audit still finds231 pre-existing Flash-Next pin drifts
across two untouched files; its output is identical to127's audit. Packet128
closure and all client inner-plan pins pass.
