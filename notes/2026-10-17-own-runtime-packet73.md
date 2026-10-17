# Packet 73 — HC gates and second expert round

CPU preparation started at 20:29 UTC, with a 22:59 UTC sealed-candidate deadline.
No GPU, model, service or host-setting change is authorized in this task.
The coordinator owns packet70 and every future device screen.

`git pull --rebase` initially refused the live packet70 orchestration log's
uncommitted change. Fetch found no incoming main commits; that file stays
untouched. Root had 28 GB free. The owner's explicit sub-1-GB build budget
is used for this preparation. Every compiler is serial within this task,
nice 19, affinity 8–15,24–31, with an 8 GiB address-space ceiling and no stdin.

[Packet](../experiments/own-xpu-runtime/stage2/packet73-hc-experts2/README.md).
Its C++ sources are copied from packet70, with parent hashes retained.
Production means packet70's wide64 experts, draft-HC, batch rollback and 24/24
placement. It does not mean packet65's old production expert path.

The HC candidate shares packed Q8 code and scale loads across four adjacent
logical chains. Each subgroup owns four adjacent rows of ONE stream; the
four streams stay in separate subgroups and retain the packet60 mix epilogue.
This is not packet67's four-stream subgroup geometry. Exceptional activation
values use the original SG32 arithmetic. No decoded buffer is added.

Expert candidate A loads two IQ2 packed blocks before consuming them.
Candidate B shares a 64-byte IQ4 code span and four half scales across sixteen
chains. Both start from wide64, preserve its geometry, original logical sums,
reduction tree, types and rounding. Offline load/GRF/spill evidence determines
which variants can proceed. Any spilling variant is rejected before sealing.

Route fusion is deferred: preserving its globally normalized selection and
ties would require a separate synchronization design, beyond this short task.
The next performance measurement is in-engine v4-lanes, never a microbenchmark
speed claim. CPU byte identity and seals do not establish device quality or speed.

## Offline decisions and CPU byte gates

The first HC layout spilled flags even after correcting the offline device
library link. It was rejected. The accepted HC path keeps the original
32-lane arithmetic and computes two adjacent rows per subgroup, sharing their
raw inputs and widening code reads. It has no spill metadata or spill/fill
messages. A stride error in its first implementation was caught by the GNU
fixture and fixed before acceptance; the expanded row includes twenty bytes
of preserved metadata.

Expert A's deeper IQ2 load pipeline passes without spills (54 static loads
versus 51 in wide64). Expert B's smaller IQ4 shared span passes without spills
and cuts static loads from 79 to 43; its larger span spilled and is retained
as a rejection. Combined means HC plus B, chosen from offline evidence.
These numbers describe code, not speed or measured occupancy.

Both compilers pass 44 small operator cases in two fresh processes each,
including 118,784 raw FP32 chain checks and 3,456 raw tree checks per repeat.
All compared bytes match production. No CPU model ran. The engine build and
v4 screen preparation follow these gates. [Offline decision and limitations](../experiments/own-xpu-runtime/stage2/packet73-hc-experts2/OCCUPANCY.md).

## Sealed handoff

All five views are sealed with one device binary. The private v4 wrapper passes
82 mock checks. Six lane-A plans and all twelve possible lane-B plans pass;
both proposed queue files pass `lanequeue.py plan` in a private copy. No live
queue, frozen screen or parent packet was edited by this task, and no GPU,
CPU model, service, sudo or host-setting operation ran.

Lane A brackets the four candidates with production. Lane B resolves its
middle job only after all six A screens are exact and an improving winner
exists. It then brackets that candidate with fresh controls. Combined is HC
plus expert B. The 3,600-second per-screen watchdog exceeds four times the
210-second estimate; inter-screen gaps stay 90 seconds. Speed is still pending.

The final build is 302,710,656 bytes (about 303 MB). Engine compile peak RSS
is 726,108 KiB. [Final verification](../experiments/own-xpu-runtime/stage2/packet73-hc-experts2/evidence/final-validation.json),
[commands](../experiments/own-xpu-runtime/stage2/packet73-hc-experts2/WINDOW.md),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet73-hc-experts2/CPU-PREPARATION-CLOSEOUT.md).
Both queue proposals are under `experiments/own-xpu-runtime/ops/lane-queue/`,
with `proposed-p73-A.txt` and `proposed-p73-B.txt`; neither was enqueued here.
