# Packet153 — static speculative snapshot descriptors

Started about 00:18 UTC on steve-b70s. The requested work is CPU preparation of
a two-card lane-B experiment, not a launch. Pull refused unrelated dirty work;
fetch confirmed HEAD and origin/main at 3db45a0bd41f623bd70b09a0c3e70bfefea50fa2.
Root began at 31.44 GB free. Existing packets, queue files and orchestration
edits remain untouched. frozen_paths.py was run; its entire union is protected.

The first repository-wide search covered every DO-NOT-REPEAT.md and notes
folder for snapshot, descriptor and rotation work. Relevant exclusions:
[packet131](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/DO-NOT-REPEAT.md),
[packet62](../experiments/own-xpu-runtime/stage2/packet62-miss-path/DO-NOT-REPEAT.md),
[packet121](../experiments/own-xpu-runtime/stage2/packet121-miss-table/DO-NOT-REPEAT.md),
[packet144](../experiments/own-xpu-runtime/stage2/packet144-miss-path/DO-NOT-REPEAT.md),
and [packet150](../experiments/own-xpu-runtime/stage2/packet150-rank0-split/DO-NOT-REPEAT.md).
No extra bank rotation, lost old-spare state, skipped QSA copies, diagnostic
speed promotion or miss-only overlap estimate is being reused.

[Packet153](../experiments/own-xpu-runtime/stage2/packet153-snapshot-host/README.md)
starts with a symlink-preserving packet136 copy. Packet150 supplies a vendored
one-load harness and the same timing scopes, with all replay modes disabled.
The new static path builds one table at load. Its nonbank sources are invariant
across all six bank pairs; QSA offsets use the captured position in the kernel.
Capture and restore both avoid the descriptor build and upload. Required copy
traffic, kernel search, host metadata and synchronization remain.

The CPU audit identified and fixed immutable-table reset handling and the
protected-active negative test. The smoke analyzer now validates the real
embedded native-trace schema and rejects missing streams/scopes. Compiler turns
wait behind the active record chain's whole-host hold. No device or service
was started; no model payload/full-shape read or privileged operation occurred.

Initial source milestone: implementation and CPU test sources prepared;
qualification and final readiness are still pending. No proposal is queued.

At 00:42 UTC the record chain's freeze ended. A CPU fixture that had been frozen
hit its wall-clock timeout on resumption; its failed-attempt log is retained and
is not evidence. I stopped only the replacement CPU fixture and its own Python
parent to preregister a two-worker run that fits the time box: each worker has a
1.25 GiB address-space cap. The state fixture retains twelve boundary positions,
forced hits/misses/cancellations, all four abandoned-redo cases, a 98-step mixed
sequence, six bank-role pairs, all three corruption negatives and immutable-table
checks across resets. Every compiler/choice runs twice from a fresh process.
The real-size transport fixture separately tests 984 extents at nine positions,
including 4095, using synthetic bytes and the actual static kernel tile body.

By 00:49 UTC both native builds, GNU/Intel real-size copy checks, controller
checks, admission, drain/limits, strict timing-data analysis and loader checks
passed. The packet's own `prepare_submission` replayed a copied packet136 bundle
at its original 58.798108759182306 rate and refused to label it packet153.
Historical pins in that rehearsal live only in temporary scratch. No submission
payload is retained, sent or used as a new measurement. The longer byte-state
matrix is still running before final sealing.

Final CPU qualification update: the second coordinator freeze also interrupted
the long state matrix. The completed gate is explicitly narrower than the
original twelve-position plan: the existing 98-step sequence-only mode plus
three corruption negatives, GNU and Intel, production and static, twice each
from fresh processes. All eight canonical digests agree. Six bank-role pairs,
forced rollback and request reset are covered; nine real-copy positions through
4095 pass separately. Failed/partial attempts remain local evidence and are not
counted. The exact final execution driver is retained, while the normal driver
still recompiles its fixtures. The live binaries and all runtime sources match
the tested seal. Peak recorded state RSS was 849.5 MiB; two workers were each
capped at 1.25 GiB. Generated builds remain local and below 300 MB.

The new table is 47,232 bytes (984 extents), uploaded once. Capture and restore
copy the same 19,025,640 bytes with no per-cycle descriptor build or upload.
No lane-to-extent map was added. All device output and timing claims are pending.
The smoke and five-view proposals are prepared only; neither is queued. The
25 GB launch floor, 240 MB/view allowance and 3,600-second watchdog are retained.
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet153-snapshot-host/CPU-PREPARATION-CLOSEOUT.md)
and the last-written readiness marker bind the final gate outcome. No GPU,
service, privileged operation or live queue edit was performed by this task.

## Packet153b — first-request data proof, without a wall deadline

The lane-B smoke at 01:27:29–01:30:12 UTC completed incident64 exactly:
64 tokens, 59.74034915570937 decode tok/s, and no cached tokens. Its first
prefill took 59.58 seconds and the request took 60.64 seconds. The analyzer
then rejected valid timing streams because the elapsed view time exceeded
60 seconds. This is a smoke diagnostic, not a new performance result. The
coordinator reported no new GPU faults (count remained 2).

Removed the elapsed-time rejection in both `first_minute_proof()` and
`analyze()`. The worker still runs the real proof immediately after incident64,
before the remaining prompts. Missing or empty streams and missing comparison
scopes still fail closed. `seconds_after_view_start` remains informational;
the existing `first-minute-data-proof.json` filename remains compatible. Cold
prefill and time spent frozen cannot invalidate this data proof.

The CPU regression uses byte-exact copies of this failed smoke's receipt and
both rank timing streams. It invokes the real proof with the view start more
than 120 seconds earlier, checks the written proof and final analyzer, and
rejects empty rank streams and a missing rank stream. All eight analyzer tests
pass. Compressed fixtures and their original SHA256/size manifest are retained
under `lineage-inputs/timing-fixture-p153b/`; when the original output is present,
the tests also compare every fixture byte with it. The full failed output under
`v5/evidence/device-static-smoke-B/` remains untouched local history.

Minimal CPU reseal only: no compile, GGUF read, GPU work, service, sudo or host
setting change. Native binary hashes and `iq3-p49-split32-v1` arithmetic are
unchanged. Timing-report tests, pre-exec guards, both-lane entry checks, report
checks, source seal and live pin guard pass. Entry/report/planner peak RSS was
37,844 / 197,544 / 33,488 KiB. Commands ran with `nice -n 19`,
`taskset -c 8-15,24-31`, `python3 -B` and stdin from `/dev/null`.

The two proposal files now use fresh `-p153b` job and output names. The bracket
requires `device-static-smoke-B-p153b`, so it cannot reuse the failed smoke.
Both were planned on temporary queue copies and passed
`ops/rehearse_entry.py --report --json`; live queues remain untouched. The first
plan attempt correctly refused the stale readiness marker's old proposal hash.
That marker is archived as `v5/evidence/p153b-prior-ready.json` and was withdrawn
while completing the reseal. The replacement readiness marker is written last,
after all gates and notes. Device quality and performance remain pending.

Reproduction from the packet's `v5/` directory: run `analysis_gate.py`,
`p153_v5_queue_plan.py --stage`, `exec_gate.py`, `cpu_seal.py --seal`,
`entry_gate.py`, `report_gate.py`, `p153_v5_queue_plan.py`, `pin_gate.py`, then
verify the source seal and write the final readiness marker. Withdraw/archive
any old readiness marker before changing proposals; never rewrite live queues.
The existing native state/transport evidence is retained under its unchanged
source and binary hashes; this repair makes no new device qualification claim.
