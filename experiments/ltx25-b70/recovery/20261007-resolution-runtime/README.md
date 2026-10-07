# 640×384 reference/runtime components — CPU integration reviewed

Packet101 exposed a native FP32 inventory omission;101b corrected it and
produced six finite, exactly repeating native clips, then exposed a verifier
job-tag convention error. Both attempts stopped cleanly with healthy postflight.
The [101b closeout](../../notes/2026-10-07-resolution101b-verifier-refusal.md)
and [nonqualifying diagnostic](101b-offline-verifier-diagnostic.json) are retained.
These authored components now target101c with corrected producer-rooted tag
checks and fresh names/indices throughout. No optimized640×384 result is qualified.
The original model, qualified99b and both failed packets remain unchanged.

The reviewed [request plan](../20261007-resolution-reference-101c/README.md) fixes
three original fixtures, native BF16, original8+3 steps, accepted text window,
23/25 placement,25frames and640×384. Its plan hash is
`3281a1eb45d210ac75f2a07c415cf2f99b2b9308651456587aa483e2596d65e2`.
W1 is the first optimized scheduling configuration. Native sampling/decoding
must run before optimized sampler capture, with independent repeats; the
accepted text encoder remains graph-sharded. This is not an all-eager oracle.

Implemented components:

- `geometry_overlay.py` transforms exactly seven hash-pinned source paths,
  retaining historical guards and adding an explicit phase-bound comparison
  mode. [Source contract](source-contract.md).
- `session.py` admits only exact registered graphs with new execution IDs,
  enforces ordered native/optimized phases, records barriers, and permanently
  halts after a failure. Completed pipeline tails may be released only after
  their identities are durably recorded; unfinished work cannot be cleared.
- `executor_guard.py` delays Comfy's success event until post-request checks
  and the authority's durable completion succeed. A refusal becomes a failed
  history entry. Halt-receipt write failure cannot kill the prompt worker.
- `runtime_observer.py` reads the actual registered node modules and pipeline
  jobs, including completed but uncollected tails. Importing a separate source
  mirror cannot stand in for the active node's ownership state.
- `reference_gate.py` rereads six native executions and all four tensor files,
  verifies distinct executions and exact repeat pairs, and exclusively writes
  a reference receipt. Reading the receipt reconstructs its proof from retained
  artifacts. [Reference contract](reference-gate-contract.md).
- `setup_gates.py` checks actual text-window, coverage, chain/freeze and decoder
  verdicts. A successfully completed setup prompt can still contain a negative
  result. Seeded native/replica decoder consistency remains distinct from real
  reference-clip equality; the old internal speed-only labels are preserved.

`native_safety.py` and its concrete `native_adapter.py` now check actual
registered node owners, unchanged resident tensor identities and fresh device
memory. The narrow loader wrapper protects loaded owners from eviction; ordinary
Comfy allocator bookkeeping is retained. `candidate_gate.py` verifies real
emissions against the three native references and excludes fills. The complete
`request_client.py` accepts only the32 exact scheduled requests and reads fresh
server phase observations; `schedule.py` binds the seven setup graphs.

`integration.py` connects setup-result checks, native safety, source identity and
phase proofs. It also observes the separate preview writer queue, so unfinished
tail previews cannot cross phase boundaries. `runtime_packet.py` prepares a new
source packet only with an explicit reviewed input-inventory hash; its default
is read-only. `campaign.py` operates one already-owned application, submits each
request once, and attempts a single graceful stop only after actual quiescence.
It does not start or restart a server. The initial timing screen uses a serial
client feeding asynchronous pipeline stages, not a fully queued throughput run.

All14 CPU suites pass, including independent [source/lifecycle review](runtime-build-review.md).
Required before device execution: immutable materialization and launch checks,
fresh actual host/storage admission, then
real resident-object/memory observations. All32 names and26 clip indices were
reserved separately; no prior canonical request used the selected interval.
The one finite application must end with graceful shutdown and health postflight.
A component test or reservation is not a launch admission.

The failure guard must prevent estimated/actual native VAE OOM from reaching
automatic tiled decoding or its cache-flush fallback. Pre-native physical free
thresholds6/6/2/7GiB include provisional allowances, not proven full-model peak
bounds. Actual resident weights and encoder graphs must already be present.
Keep the50GiB disk reserve, fresh4GiB write allowance and32-capture bound.

Tests are adjacent `test_*.py` scripts, run with `python3 -B` individually.
Synthetic schema controls are labeled as such and are not model measurements.
No throughput or visual-quality result is claimed by this folder.
