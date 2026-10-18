# Packet58t: resident one-card lookup bytes

CPU-only work on main. Pull refused unrelated dirty orchestration files;
fetch confirmed HEAD == origin/main at `6bf515a44f200e14d24ede24a398d2c3aea024bc`.
The work uses a new `stage2/packet58t-resident-lookups/` copy. Existing packets,
screens and ops are frozen; only a new proposed queue file may be added.

The host preparation path reads one token embedding row and sixteen PLE rows
from two GGUF tensors. Together they occupy 29.32 GB but supply only 3,540
packed bytes per token. Experts already use pinned memory. The
[analysis](../experiments/own-xpu-runtime/stage2/packet58t-resident-lookups/ANALYSIS.md)
and [source-bound census](../experiments/own-xpu-runtime/stage2/packet58t-resident-lookups/evidence/lookup-inventory.json)
record exact bytes, offsets, scales and access pattern without model reads.

Implementation and CPU validation pass. The candidate uses exact, read-only
anonymous copies at load, checked by source/destination SHA-256. Missing copies
fail closed. It changes host backing only; device data and arithmetic stay the
same. Added anonymous payload is 29,321,610,240 bytes. Timing windows already
reserved these file bytes, so their total stays 118,308,908,048 bytes including
the 8 GiB reserve. Exactness windows now reserve the full copies explicitly.

Both GNU and Intel pass copy/dequant checks and fresh miniature-engine output
comparisons. All 40 retained files match the original path and frozen 58p;
32 resident decode preparations have zero major faults. The 1,024-token CPU
replay also has zero resident major faults and no file reads after warm-up.
Its original path is cached and also has zero major faults: no speed claim.
All 109 Python tests, 12 full-size mock bindings, 10 native startup/oracle
paths, 12 chain argument paths, four screen argument paths, eight budgets,
48 K1 cases, drain and local teardown integration pass.

Packet58r was available. Its bracket is copied locally and narrowed to tile16
file-backed / tile16 resident / tile16 file-backed, with preparation-specific
fault counters alongside speed. The new
[proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p58t-screen-A.txt)
passes the coordinator's planner on a temporary queue. It requests a whole-host
card-0 window, two K1 fixtures then one model load, 36 requests, 15–25 minutes
and a 7,200-second watchdog. No live queue was changed. Copies load before A0,
so the source pages have been read; this does not recreate 58n's cold cache.

The later seven-window chain requires fresh screen evidence, exact packet49
outputs, both K1 checks, complete file hashes, clean kernel logs, memory proof,
zero resident preparation major faults, and the speed/drift gate. A stored
ready flag cannot authorize it. Device parity, full-size allocation and speed
remain pending. See the [CPU closeout](../experiments/own-xpu-runtime/stage2/packet58t-resident-lookups/CPU-PREPARATION-CLOSEOUT.md)
and [reproduction commands](../experiments/own-xpu-runtime/stage2/packet58t-resident-lookups/README.md).

Build size is 89.83 MB; peak compile RSS is 695.2 MiB. Root free space stayed
above 32 GB. Compiles ran serially through packet94's compiler turn. Work used
nice19, helper cores and Python -B, with no GPU, service, sudo, settings change,
cache drop, model-wide pre-read or live queue edit. Frozen parent trees were
left alone. The first inventory milestone was pushed as `0d9e48b15`.
The implementation, CPU gates and proposed screen were pushed as `fe5a01d66`.
The final seal binds that committed source state, and both the screen's
temporary coordinator plan and the later chain's CPU-only plan pass.
