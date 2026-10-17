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
The exact SPEED6 non-QSA dispatch is also pinned. Fresh K2 results are retained
as measurements and a separate recommendation; a different timing winner does
not silently change this packet's unrelated production kernels. The pinned
choices still need fresh K2 exactness coverage before model windows can run.

Packet48 candidates require production reconciliation before adoption.
The source audit finds matching shapes and quantization classes. Ordinary GDN
layer4 uses IQ2_S gate/up, IQ4_NL down, and Q6_K QKV/Z. Packet48's dense control
wrapper specializes away production P33's runtime routing path, so it is not
the same compiled production control. The primary expert controls use the
actual P39 kernels. Packet46 repeats 32 synthetic blocks per tensor and measures
complete layers with 10 warmups/200 pairs; packet48 changes row bytes and measures
isolated classes with 4 warmups/24 pairs. These are known confounders, not proof
of a single cause.

| Class | Packet46 production control, µs | Packet48 isolated control, µs | Difference |
| --- | ---: | ---: | ---: |
| IQ2 gate/up | 81.875 | 106.927 | +30.6% |
| IQ4 down | 91.875 | 93.542 | +1.8% |
| Q6 QKV | 100.105 | 63.490 | −36.6% |
| Q6 Z | 39.740 | 31.875 | −19.8% |

Down remains the strongest candidate, but the registered production-layer gate
is still missing. **No packet48 kernel is production-enabled in packet49.**
[Packet48b](../experiments/own-xpu-runtime/stage2/packet48b-production/)
prepares the matched full-layer comparison and per-class decision. Its unchanged
control calls the production engine; the candidate changes only the four
primary GEMV classes. No performance conclusion is inferred from compilation.
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

The oracle estimate before launch is **6–12 hours**, about eight hours centrally,
for twelve 128-token
outputs with two lean CPU workers (historical rate about 20 seconds per
consumed position, 2,386 suite positions plus a 214-position first-prompt repeat).
It must retain the fixture
steps needed by the chain, including 1–8 and 97–104. A static arithmetic
identity and separate completion receipt allow kernel windows to precede
oracle completion without silently changing their seal.

## Qualification boundary

The oracle launched at **2026-10-17 03:44:10 UTC** in the durable CPU-only
unit **`own-iq3-p49-oracle-20261017b.service`**, with restart disabled. Initial
completion estimate: **09:44–15:44 UTC**, central estimate about11:33 UTC.
Outputs are under
`/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results/`.
The first attempt refused before reading model bytes because idle I/O priority
was absent. Its output is preserved in `oracle/attempt1-io-admission`; the
corrected one-off launch adds `ionice -c3` without changing sources or binary.
[Exact unit receipt](../experiments/own-xpu-runtime/stage2/packet49-integrate/oracle/unit-receipt.json).

The independent scalar gate passed **135,168 bitwise pre-gate values**, and
six CPU admission tests passed. Full-model completion and device parity are
still pending. The coordinator must check completion using:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet49-integrate/oracle/oracle_job.py \
  status --require-complete
```

Exit zero binds the full manifest, binary, sources, token/fixture results,
fresh-process repeat and KD captures. `old-v-new.json` is produced only once
the new suite exists; it compares against retained old outputs informationally.

Build/CPU passes will not establish full-model device parity or speed.
The coordinator chain will mirror K0/K1a/K1b/K2/W0p/KD/W2m/WS/WSs plus
WS128x/WS128. Oracle-dependent windows must fail closed while outputs are
pending. Exact runnable commands, final seal, CPU evidence, unit identity,
ETA and review will be added when prepared. [The queue runbook](../experiments/own-xpu-runtime/stage2/packet49-integrate/WINDOW.md)
and serial runner are committed. Ten CPU tests cover exact commands, topology,
oracle barrier, strict receipts, fault signatures and durable-unit admission.

The integrated bridge supports and tests M=1/M=2. The full engine retains
SPEED6's per-row attention submissions during verification; it does not acquire
new M=2 batching merely from supporting the bridge shape. The independent
[attention review](../experiments/own-xpu-runtime/stage2/packet49-integrate/REVIEW-QSA.md)
records this limit and found no blocking arithmetic or scratch defect.

The twelve-prompt, 128-token suite preserves the old record's scope. It does
not satisfy the separate 512-token publication gate, and no comparison to
Strata's different hardware is a matched performance result.
