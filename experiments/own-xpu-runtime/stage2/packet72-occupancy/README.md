# Packet72: attention-output raw-load occupancy

CPU preparation is complete. No GPU or CPU model ran. Device quality and speed
remain unmeasured; the coordinator owns the prepared screens.

- [In-engine bandwidth and selection](BANDWIDTH.md), [full JSON](BANDWIDTH.json).
- [Kernel arithmetic and offline compiler evidence](OCCUPANCY.md).
- [Four fresh GNU/Intel operator checks](evidence/cpu-byte-identity.json).
- [Built selector checks](evidence/selection-gate.json).
- [79 private v4 wrapper tests](screen/placement-validation/tests.log).
- [LaneA four-screen job](screen/jobs-A.txt), [conditional laneB three-screen job](screen/jobs-B.txt).
- [Coordinator commands and queue proposals](WINDOW.md), [passing queue plans](evidence/queue-plans.json).

The three sealed views are `production`, `attention-out` and `combined`, all
sharing one device binary. Production is packet70's selected configuration:
wide64 experts, draft-HC, batch rollback,24/24 layers and rank1 draft. The
combined view equals the sole new candidate. Each device screen still checks
incident64 and every token of all twelve cold128-token responses against the
packet49 oracle. The strict512-token final gate remains false.

The private screen snapshots `screen/v4-lanes` and preserves its shared
teardown gate and lane leases. It releases both leases after drain/postflight
and before CPU reporting. A report failure cannot leave a device-fault latch.
The watchdog is3600 seconds, more than4× the210-second planning estimate.
Each internal gap is90 seconds; there are no retries.

CPU planning from the repository root:

```sh
P=experiments/own-xpu-runtime/stage2/packet72-occupancy
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/screen/run.py" --lane A --jobs "$P/screen/jobs-A.txt" --plan </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/screen/run.py" --lane B --jobs "$P/screen/jobs-B.txt" --plan </dev/null
```

LaneB planning verifies seals and fresh outputs, but does not pretend laneA
has run. Actual laneB execution validates all four laneA receipts and refuses
before device work if they are incomplete, inexact or fail to improve.

Build order: `cpu_gate.py`, `build_engine.py`, `inspect_registers.py`,
`screen/cpu_seal.py`, `seal_selections.py`. All are CPU-only and use nice19,
cores8–15,24–31, stdin from `/dev/null`, `python3 -B` and `OMP_NUM_THREADS=2`.
One compiler runs at a time under an8 GiB address-space cap. Creation helpers
and sealers refuse to overwrite finished packets. The C++ tree was copied
from packet70; unchanged objects are hardlinked from its actual packet65 build
provenance. Packet70's stale copied command list is deliberately not used.

The all-layer byte inventory keeps unmeasured timings null. Historical
`outside_layer_work.roofline_us` fields in BANDWIDTH.json retain packet67's
540 GB/s read-plus-write planning denominator; they are excluded from all
packet72 ranking and qualification. The repeated-site ranking uses only
distinct reads at555 GB/s. Actual DRAM bytes remain unknown without counters.
