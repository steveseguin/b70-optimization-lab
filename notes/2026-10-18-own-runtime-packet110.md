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
