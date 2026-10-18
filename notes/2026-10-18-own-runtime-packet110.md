# Packet110: fresh class roofline and current GDN timing

CPU-only work, October 18. `git pull --rebase` refused unrelated dirty files;
fetch confirmed HEAD == origin/main at ace4fadda79d9440859e7d1ee85687540924c843.
All existing packet trees, screen trees, orchestration and live queues stay frozen.
No GPU, service, sudo, host-setting change or process kill.

The copied packet107 harness now executes current GDN only. Its specialised
GDN and QSA code is unreachable. Production kernels and selection are unchanged.
A fresh coordinator process checks four consecutive complete layers, followed
by 10 warm-ups and 40 measured iterations at each context 128/4096. Current
versus current replay checks every mutable allocation; only the first run in
each pair is reported. The device wrapper retains its safety/admission/drain
checks, uses physical card 2, and allows 600 seconds (expected 60–120 seconds).

Device and GNU-host compilation passed through the copied packet94 compiler
turn, one compiler at a time. Frozen parent objects relink to the exact parent
binary before reuse. Two GNU CPU processes passed 572 checks each with the same
output identity. This validates the harness, not new model arithmetic or device
quality. Build footprint is 55,849,804 bytes (limit 100,000,000).

Direct plan and a temporary lane queue plan passed. The new proposal is
[proposed-p110-gdn-B.txt](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p110-gdn-B.txt).
It is not installed in a live queue. The coordinator can run it now; the table
and re-ranking follow in the next focused commit within this task.

Commands run from the repository root, each under `nice -n 19 taskset -c
8-15,24-31`, using `python3 -B` and stdin `/dev/null`: `build_engine.py --mode
device`, `build_engine.py --mode gnu-host`, `cpu_layers.py`, `seal.py`,
`run_micro.py --lane B --owner 1 --plan`. Queue planning used `lanequeue.py plan
--lane B --directory` with a temporary directory containing only the proposal.
Evidence is in [packet110](../experiments/own-xpu-runtime/stage2/packet110-class-roofline/evidence).


## Fresh roofline and decision

[ROOFLINE.md](../experiments/own-xpu-runtime/stage2/packet110-class-roofline/ROOFLINE.md)
now has all 25 QSA classes at 128 and 4096, from both packet107 fresh processes.
Each class time sums all its events before taking a 40-call process median,
then the median across processes. Both original JSONL files are retained
byte-for-byte in gzip snapshots with hashes and window/native receipts.
No historical packet77 time is used. The byte formulas build on the lab's
packet67 source accounting, re-audited for the current code; E1 gate/up reads
840 rather than 820 bytes per row. Expanded Q6 counts 3,200 useful bytes per
K2560 row, not 2,100 packed bytes or 3,380 allocation-stride bytes.

At 128 tokens, Q-gate is 97.187 µs against a 73.280 µs copy floor. Gate/up is
59.036 µs against 20.080 µs. Across six QSA layers the respective headroom
budgets are 0.1434 and 0.2337 ms. These are synthetic useful-byte floors, not
measured DRAM bandwidth or promised speedups. The router/shared tuple is at
493.60 GB/s effective throughput, about 92% of the supplied copy reference.

Provisional open ranking by available headroom × explicit feasibility:

1. E1-preserving gate/up tile16 (packet104b): 0.2337 × 0.65 = 0.1519 ms score.
   Its original 15% micro gate failed; only the explicit coordinator screening
   override opens this exact arm. It is not a qualified engine win.
2. Packet109 complete-tuple epilogues: 0.1974 × 0.50 = 0.0987 ms score.
   Do not credit unchanged route work or repeat its rejected NaN variants.
3. Pruned exact top10 network after unchanged normalized route probabilities:
   0.1124 × 0.40 = 0.0450 ms score. New design only, no implementation.

All scores currently contain only the six QSA occurrences. The eighteen GDN
occurrences remain blank until their own receipt arrives. One GDN micro gives
attribution, not a fresh-process speed comparison. No lever is implemented here.
The closure review pins `closed.json` and all 124 available DO-NOT-REPEAT files.
Closed specialisation, packed-dense, norm fusion, HC, lookup/prefetch/batching,
non-gate transpose and draft-load arms stay excluded. The refresh script refuses
to emit a stale ranking if that closure inventory changes.

Sixteen CPU analysis checks pass, including missing/duplicate iterations,
warm-up leakage, wrong context/layer, inconsistent event/class/total sums,
GDN specialised-row refusal, updated byte formats, and replay with the original
raw tree absent. The first negative test selected an alternating specialised
row by mistake; its corrected fixture and initial log are retained. The
validator was not relaxed. Neither device compilation nor CPU checks are a
model quality or speed pass.

The GDN proposal was pushed in `6fbe1b03d` as soon as it compiled and planned.
At the final analysis check no GDN device receipt had arrived. The CPU-only
`roofline.py` refresh command is in the packet README and fills both GDN tables
when the coordinator completes the job. Build remains 55,849,804 logical bytes;
no device, service, existing packet, live queue or host setting changed.
