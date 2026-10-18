# Packet 58c: count pinned experts separately from GPUActive shadow

CPU-only wrapper repair copied from frozen packet58b. The four native binaries
and every C++ source are unchanged. No compiler, model, GPU, service or host
setting was used or changed in this repair.

KD stopped after 78 expert tensors (layers 0–25), totaling 26,424,115,200 bytes.
The old sensor treated every byte of GPUActive growth as device shadow, whose
bound is 26,409,219,600 bytes. That is consistent with counting the pinned host
banks twice. The retained evidence does not contain the failing sample or an
aligned time series, so it cannot prove a point-by-point correlation.
The closed launch environment has no NEO debug keys; `EnableDeferBacking=0`
from the older multi-card memory note was **not** active here.

[window.py](window.py) now credits completed unique expert tensors only after
checking their names and exact sizes against the pinned census. Unfinished
allocations get no credit. It records pinned bytes, raw GPUActive growth and
remaining shadow separately. Shadow stays bounded at 26.409 GB. Pinned bytes,
shadow, full anonymous RSS and the full nonexpert file-backed allowance must
also fit the original host plan. There is no second pinned-byte subtraction
from RSS. Admission remains 118,308,908,048 bytes; reserve remains 8 GiB.
Every previous anonymous, memory-fence, fault, teardown and quality stop stays.

Each poll now writes `host-memory.jsonl`, including a rejected accounting
sample before cooperative stop. That closes the evidence gap from 58b.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md),
[memory bounds](MEMORY.md), [coordinator command](WINDOW.md),
[replay evidence](evidence/sensor-replay.json),
[task note](../../../../notes/2026-10-17-own-runtime-packet58c.md).
Copied historical design and CPU receipts remain explicitly inherited evidence.
The new wrapper has fresh CPU tests; device loading and correctness are pending.
