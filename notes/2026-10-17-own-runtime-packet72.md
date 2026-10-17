# Packet72: bandwidth first

CPU-only preparation. The initial `git pull --rebase` refused the live packet70
log's unstaged change. A fetch confirmed HEAD equals origin/main; that log was
left untouched. Root has 30 GB free. Builds are limited to 8 GiB address space,
one compiler at a time, nice19 and cores8–15,24–31, with no device execution.

[Bandwidth audit](../experiments/own-xpu-runtime/stage2/packet72-occupancy/BANDWIDTH.md)
recomputes complete site-call times from packet64's raw lane-B events. Real
runtime Q6/Q8 representations matter: these dense weights are expanded codes
and scales. QKV, Z and Q-gate fail the requested0.3 ms/half headroom threshold.
Attention output qualifies narrowly on rank1 (0.310 ms); rank0 is0.260 ms.
It is one shared kernel class across GDN and QSA layers, including its finishing
kernel. Those are occurrence-scaled sampled-layer estimates, not new measured
whole-half times or promised speedups.

The timestamps do not contain DRAM transaction counters. The report explicitly
uses distinct runtime read bytes divided by engine time, and leaves actual
DRAM bandwidth unknown. Unsampled layer timings remain null. Packet67's
negative HC/recurrence mechanisms remain closed; route is outside the proposed
raw-code/scale sharing mechanism, and experts are already wide64 in packet70.

Next: copy packet70's sources and implement attention-output sharing of adjacent
logical chains without changing their arithmetic. GNU/Intel operator checks,
offline compiler reports and seals precede the coordinator's lane-A grid.
No model, GPU, service or host setting was touched.

CPU preparation is now complete. One attention-output candidate shares raw
loads across two adjacent chains. Both compilers pass24 operator cases twice,
including FP32 chains, BF16 outputs and exceptional values. The offline build
uses7 static load instructions versus9 in production, with128 configured GRFs
and no scratch messages. The initial13-load version is retained as a negative
compiler result. Both engine builds pass; the final build, including the selector
test and retained offline attempts, is about132 MiB.

Three views share one device binary: production, attention-out and combined.
Combined is the same sole new mechanism. The compiled selector passes all
views and rejects an unknown choice. The private screen copies v4-lanes and
passes79 CPU mock tests, including safe report failure after lease release.
LaneA has four screens; laneB has production, the canonical candidate and
production, gated on exact improving laneA results. All seven CPU plans pass.
Both proposed JSON job lines pass `lanequeue.py plan` in a private packet
directory. Live queues were not edited. [Coordinator handoff and proposals](../experiments/own-xpu-runtime/stage2/packet72-occupancy/WINDOW.md)
are ready; device execution stays with the coordinator. Generated executable
paths remain unchanged locally and recoverable by commit/hash, but are excluded
from the current Git index. Small CPU reference/candidate bytes are retained.

## Lane-A admission repair and revision 2 (CPU only)

The device wrapper refused `screen` because this private copy omitted packet65's
diagnostic lane-A window. Added that one policy entry locally. Every individual
job plan now constructs the same `Reservation(lane, window='screen')` used by
execution and reports its actual scope, without entering a lease or writing a
marker. A regression test removes the new entry and verifies planning fails.
Timing windows still require the whole host; unknown lane-A windows still refuse.

All **82 wrapper tests**, four fresh GNU/Intel operator runs, seven screen plans,
and the proposed lane-A queue plan pass. All three engine artifact hashes,
selection bytes and fixture hashes are unchanged. Prior seals and their test log
are retained under `evidence/reseal-r2/previous/`; the wrapper and three selection
views have fresh seals. Device correctness and speed remain pending.

Use `screen/jobs-A-r2.txt`, with four fresh `-r2` outputs. Lane B's winner check
now reads those four revision-2 lane-A receipts. The queue proposal is
`experiments/own-xpu-runtime/ops/lane-queue/proposed-p72-r2-A.txt`.
`validate_r2.py` plans it on a temporary copy of the queue directory; it does
not modify live queues. [Validation](../experiments/own-xpu-runtime/stage2/packet72-occupancy/evidence/reseal-r2/validation.json)
and [queue log](../experiments/own-xpu-runtime/stage2/packet72-occupancy/evidence/reseal-r2/queue-plan-A.log)
retain the commands and hashes. Recheck with `validate_r2.py` and
`final_check.py`, under `OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31
python3 -B`, stdin `/dev/null`. No GPU, model, service or host setting was touched.
