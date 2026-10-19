# Packet157: where rank 1 spends its draft time

The packet was prepared on CPU only, on steve-b70s, for a two-card run.
The starting HEAD matched origin/main after fetch; pull refused unrelated edits.
All existing packets and operations files are frozen, except the four new
proposal filenames. No device, service, model payload or full-shape read is
part of this preparation.

Packet154 measured draft_issue at 1.571 ms/cycle and rank0 reply wait at 1.573.
That is the reason for decomposing the draft, not evidence for a particular
kernel optimization. Packet157 keeps bundle8 and the 80,128-row head prefix.
It vendors the packet136 source closure and packet154 harness, disables the
latter's duplicate work, and tags existing events outside capture. See the
packet README and v5/analyze.py for clocks, group boundaries and refusal rules.

Milestone 1: instrumentation and analyzer implemented. Five analyzer tests
cover conservation, top-two ranking, paired overhead, missing/empty/incomplete
streams, unmatched/duplicate/overlapping events and control contamination.
Milestone 1 was committed as `de65d4237` and pushed.

Milestone 2: CPU qualification passed. The native host and device binaries
build through the shared compiler arbiter. Four fresh miniature CPU draft runs
(timing off/on, twice) give identical proposals and mutable state bytes. The
production-geometry CPU preparation probe uses the real intercepted rank
arguments, device-conditional host code, metadata-only loading, synthetic
addresses/events, prepare and the first decode position. Both ranks pass twice;
this is control-flow evidence, not a substitute for full-model execution.

Entry checks pass for both lanes and both job kinds, with twelve bad-unit,
environment and fault-latch refusals. Per-rank admission, native launch limits,
78 simulated worker requests, first-request bad-output and empty-stream
refusals, all four report rehearsals, actual launch_env loader checks and
immutable pin checks pass. CPU preparation uses a 27 GB root-free stop;
device admission retains 25 GB plus planned writes. The inherited 145 MB/view
(725 MB total) cap stays below three times the measured 243 MB parent total.
No wall-clock limit truncates cold first requests. Expected duration is
420–600 seconds; the external watchdog is 2,400 seconds.

The four `proposed-p157-{smoke,split}-{A,B}.txt` files pass planning on temporary
queue copies. Lane A comes first. Live queues were not edited and nothing was
launched. `stage2/packet157-draft-decomp/READY-FOR-DEVICE.json` is written after
all other packet artifacts and binds the CPU evidence and proposal bytes.

The analyzer reports each group's device execution and host issue separately
against `draft_issue`: those clocks overlap and cannot be added as elapsed
time. Timed views are compared with adjacent controls for both draft-issue and
decode-interval overhead. It names the two largest measured device groups and
provides a next lever distinct from the closed packet101/106/106b/108/114/122/
126/129/146 designs. The head remains exactly 80,128 rows.

No device top-two ranking, full-model byte equality or timing overhead is
claimed yet. Those require the unqueued smoke and one-load C/T/C/T/C bracket.
Detailed evidence and reproduction commands are in the
[packet README](../experiments/own-xpu-runtime/stage2/packet157-draft-decomp/README.md)
and its `v5/evidence/` directory.

## Packet157b: printed-duration tolerance repair

The original `packet157-split-smoke-A` ran at 02:52:39–02:55:09 UTC. Device
work completed, then the first-request proof refused `host duration disagrees`.
There were no GPU faults reported; marker/latch archival belongs to the
coordinator. This repair does not launch or queue another attempt.

The retained incident64 rank-1 stream contains 6,940 host intervals. Exactly
one failed the former absolute 0.02 ms check: sequence 1, position 0,
`wait_rank0_command`, printed as 28540.4 ms while its timestamps span
28540.420976 ms. The native stream prints its first duration with six significant
digits before setting precision 17 for timestamps. Changing that writer would
require rebuilding native code, so this patch changes only the Python check.
It now accepts an absolute difference at most `max(0.02, 1e-5 * ms)` milliseconds.
The other 0.02 ms check concerns group conservation, not printed durations
against timestamps, and remains unchanged.

Seven analyzer tests pass, including the exact failing row, both +1 ms and
-1 ms disagreements, and a short-interval error exceeding the original floor.
The three timing-report tests pass. All 6,940 retained intervals pass the new
check. See [repair receipt](../experiments/own-xpu-runtime/stage2/packet157-draft-decomp/v5/evidence/packet157b-analyzer.json)
and [regression tests](../experiments/own-xpu-runtime/stage2/packet157-draft-decomp/v5/test_analyze.py).
The previous split-CPU receipt and readiness marker are retained beside the
repair receipt. `v5/reseal157b.py` refreshes the Python test evidence after
checking that the native sources and other prior inputs are unchanged; it
explicitly retains the earlier native byte runs rather than claiming new ones.

The four proposal filenames stay the same. Their fresh job names are
`packet157b-split-{smoke,bracket}-{A,B}` and their fresh output directories are
`v5/evidence/device-p157b-{smoke,bracket}-{A,B}`. The packet-local entry rehearsal
uses those new service names. Preparation uses nice 19, CPUs 8-15,24-31,
`python3 -B`, closed stdin and a 2,000,000,000-byte process data limit.
Native binaries, other packets, screen state and live queues remain untouched.

All four temporary queue plans and `v5/rehearse_entry.py PROPOSAL --report`
rehearsals pass. The four positive entry routes and twelve refusal cases,
both-lane report gate, immutable pin guard and actual loader check pass.
The reseal/rehearsal runner's peak child RSS was 54,616 KiB. The final
`READY-FOR-DEVICE.json` is written last, after these receipts and this note;
device quality, overhead and ranking still require the fresh device runs.
