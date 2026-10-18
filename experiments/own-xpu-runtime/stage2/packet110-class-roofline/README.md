# Packet 110: fresh class roofline

Current GDN timing only, copied from packet107. No specialised arm is reachable.
The closed GDN preparation and QSA local-sharing candidates remain closed.
Only `build_engine.py`, `cpu_layers.py`, `seal.py`, `run_micro.py` and the new
analysis scripts are entry points for this packet; other copied helpers are
provenance, not instructions to run old candidate tests.

The coordinator proposal uses one fresh lane-B process on physical card 2.
It checks four consecutive tokens, then 10 warm-up and 40 measured iterations
at each occupied context 128 and 4096. Each current run restores changing
inputs/state and is compared byte-for-byte with a second current replay.
All producer outputs, logical state and production mutable allocations are
checked. The repeat is not a candidate; its timing is discarded. Only the
first run per pair enters the table. Event sums exclude uploads, readback,
comparison, host enqueue and initialization. Synthetic weights and fixtures
make this attribution evidence, never a model speed or quality promotion.

The shared v4 wrapper retains reservations, device masking, memory/storage
admission, fault review, first-fault handling and graceful drain. Expected
runtime is 1–2 minutes; watchdog is 600 seconds, at least five times that upper
estimate. No retry, service, live queue edit or device run is part of CPU prep.

Builds reuse frozen packet97 objects read-only, after byte-identical parent
relink verification. New files stay below 100 MB. See the
[work note](../../../../notes/2026-10-18-own-runtime-packet110.md) and
[roofline](ROOFLINE.md). GDN measurements are pending the coordinator.

Refresh the table with `nice -n 19 taskset -c 8-15,24-31 python3 -B
experiments/own-xpu-runtime/stage2/packet110-class-roofline/roofline.py </dev/null`
from the repository root. Only a complete passed/drained GDN receipt is admitted.
If closure inputs changed, the table updates but the ranking requires review.
[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) and
[retention](RETENTION.md) preserve the bounded outcome and rebuild details.
