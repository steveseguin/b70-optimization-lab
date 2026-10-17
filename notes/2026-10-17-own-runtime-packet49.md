# Packet 49: split32 QSA integration and production GEMV reconciliation

CPU preparation is in progress. No device program is authorized in this task.
The coordinator owns every device window. The old packet45 SPEED6 record,
39.422 tok/s (`cmv9wjmtj013gle01v8k1yg4v`), remains unchanged.

## Registered scope

Derive a separate `experiments/own-xpu-runtime/stage2/packet49-integrate/`
from the packet45 SPEED6 snapshot at `34c62b433`. The current packet45 tree
also contains later SPEED7 and diagnostic changes, so it is not the baseline.
Keep 23/25 target layers, draft rank 1, capacity 4096, write-set snapshots,
the 30 GiB arena cap, reserve policy, and device host-core placement.
Change QSA decode attention to packet47 split32 for both M=1 and M=2.
The changed reduction tree gets a separate full-model CPU oracle; old output
differences are informational and the old oracle is never overwritten.

Packet48 candidates require production reconciliation before adoption.
The initial source audit finds matching shapes and quantization classes,
but its dense control wrapper differs from the actual production P33
instantiation. Expert controls use the actual P39 kernels, while tensor
patterns and isolated versus full-layer timing still differ. Thus no packet48
kernel is yet eligible for a production swap. A separate packet48b prepares
the matched comparison; no performance conclusion is inferred from compilation.
Packet46 launch fusion and packet47 ordered attention stay closed.

## CPU and storage constraints

All CPU builds/tests run at nice 19 on cores 4–15,20–31, using `python3 -B`.
At most one compiler, two CPU model jobs, and one composite mode run at once.
Only the durable oracle job may read the admitted IQ3 payload. No GPU, sudo,
power, swap, cache, host-memory-setting or unrelated-process changes occur.
Builds and outputs use `/home/steve/own-xpu-runtime-results/` with packet
symlinks. This is the same root filesystem, not extra disk capacity; initial
free space is about 22 GiB. Existing results, sealed packets and untracked
work remain untouched.

The oracle estimate before launch is **6–12 hours** for twelve 128-token
outputs with two lean CPU workers (historical rate about 20 seconds per
consumed position, roughly 2,420 positions total). It must retain the fixture
steps needed by the chain, including 1–8 and 97–104. A static arithmetic
identity and separate completion receipt allow kernel windows to precede
oracle completion without silently changing their seal.

## Qualification boundary

Build/CPU passes will not establish full-model device parity or speed.
The coordinator chain will mirror K0/K1a/K1b/K2/W0p/KD/W2m/WS/WSs plus
WS128x/WS128. Oracle-dependent windows must fail closed while outputs are
pending. Exact runnable commands, final seal, CPU evidence, unit identity,
ETA and review will be added when prepared.

The twelve-prompt, 128-token suite preserves the old record's scope. It does
not satisfy the separate 512-token publication gate, and no comparison to
Strata's different hardware is a matched performance result.
