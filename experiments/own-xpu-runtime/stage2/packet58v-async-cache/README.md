# Packet58v: one-card asynchronous expert-cache maintenance

CPU-prepared experiment. Device quality and speed are pending. The unchanged
one-card record remains **26.228599 tok/s**, packet58p, tile16,
`cmvdukc200064rf01lqsql9x8`. No proposal is queued by this packet.

[Current measurement](evidence/measurement.json): the record spends **6.991363
ms/token** in serial cache work, filling **33.005051 experts / 65.456571 MB**.
It publishes 144 tables / 1,179,648 bytes per position; separate publication
latency was not recorded. Events 2–100, twelve prompts, 1,188 charged positions.
[58i's older measurement](../packet58i-onecard-attribution/ATTRIBUTION.md) was
7.834869 ms inside a 40.667671 ms token. This packet clears the 1.5 ms threshold.

## Mechanism and lifetime

The source is copied from packet58r's one-load v5 entry, with packet58j's exact
frozen tile16 kernel objects. Both original binaries are relinked and hashed
before object reuse. No parent is edited. The parent packet has no symlinks in
its own tree; copy-forward uses symlink-preserving operations. The external
packet49 oracle remains at its original authority and is verified through
`oracle-binding.json` and `shared_oracle.py`, never flattened into a source seal.

`cache_maintenance=serial|overlap` is the only runtime dimension. Both modes
retain route-exp32-rank4, rows4-shared recurrence, production HC, tile16 down,
target-only decode, full BF16 KV, 18 GB cache and 48.6 GB pinned expert banks.
There is one extra **1,179,648-byte device staging buffer**, allocated in both
arms. The existing device bound and reserve remain. No extra expert copy or
second cache is allocated.

The serial control keeps its 144 uploads and existing fill schedule. Overlap
uses one contiguous foreground H2D upload and one scatter kernel into the
unchanged 144 table allocations. The foreground queue avoids an explicit
queue dependency behind background fills. A second copy-only immediate list
on BCS has its own in-order event chain. It never chains on the compute tail
or inserts the old copy-completion barrier into compute.

The conservative pipeline deliberately delays publication:

1. Position t finishes and its routes are read back into owned storage.
2. After position t+1's kernels are enqueued, CPU LRU planning uses t's routes.
   The old table and cache bytes remain unchanged while t+1 can read them.
3. At the following drained boundary, publish every victim as a host pointer.
   Publish new fill destinations as host pointers too. Only then submit fills.
4. Position t+2 runs with this safe mixed table while BCS writes revoked slots.
   At later boundaries query the fill event once. If incomplete, keep host
   pointers and continue; if complete, publish the new device pointers.

This is one extra position of lag compared with planning before t+1. Choosing
victims while t+1 is already reading them cannot safely revoke them retroactively.
The packet keeps the next-position host-planning overlap and postpones reuse
until the next safe boundary. Only one transaction is pending; it never reuses
a slot with unfinished DMA. Every position still updates global LRU recency,
including positions while fills are pending. The latest observed routes supply
the next admission batch; hit rates and fill cadence may differ from serial.

Ordinary event retirement waits only for foreground work. Pending fill events
remain owned and count toward in-flight work, so buffer release refuses them.
Quiescent view transitions and final shutdown drain both chains. Failed or
partial fills never restore the old victim pointers. All bytes and arithmetic
are unchanged regardless of host/device source. The new CPU tests cover
pointer safety; the small device smoke is mandatory because CPU mocks cannot
prove native queue dependencies.

## Admission, proposals and evidence limits

The private `host-admission/` bundle is packet58u's sealed measured policy.
A further 32 MiB metadata allowance plus full backing for the 1,179,648-byte
staging buffer raises required MemAvailable to **95,435,761,152 bytes**.
The 8 GiB reserve, 4 GiB shadow stop, complete native allocation census,
whole-host lease and cooperative shutdown remain. Later observations cannot
silently reduce this bound. K1 keeps its original 12 GiB admission.

The two proposals use card 0, lane A, with lane B paused and drained throughout:

- `proposed-p58v-smoke-A.txt`: K1a/K1b, then one load, 12 × 64 in overlap mode.
  Expected 10–15 minutes. Every token is checked in native code and Python.
- `proposed-p58v-v5-A.txt`: K1a/K1b, then one load, serial/overlap/serial/overlap/
  serial, 12 × 128 per view. Expected 20–30 minutes. The runner refuses without
  the exact smoke's clean drain, matching build and all oracle outputs.

Both use a 7,200-second watchdog (at least 4× the upper estimate), the recorded
oneAPI LD_LIBRARY_PATH embedded in the command, fixed oracle bytes and the
getrlimit launch guard. `plan_queue.py` uses temporary queues only. No live
queue, service or GPU is started. A bracket is a diagnostic screen, not a
fresh-process repeat, strict 512-token final gate, or submission.

[Conditional projections](evidence/projections.json) recompute each prompt's
99-interval rate and then the class-balanced statistic. Assuming 25 GB/s fill
DMA, perfect hiding, no new misses/contention and 0.25 ms new overhead gives
**28.01964 tok/s (+6.83%)**. Hiding half the cache span with 0.5 ms overhead
gives **28.49486 (+8.64%)**. These are sensitivities, not predicted or measured
wins. Removing the entire cache span gives an impossible 32.07938 upper bound.
Delayed residency, zero-copy traffic competition and driver scheduling can
remove the benefit. The device bracket decides.

## CPU reproduction

Prefix each command with `nice -n 19 taskset -c 8-15,24-31 python3 -B` and use
stdin `/dev/null`. Run from this directory:

1. `measure.py`, `project.py`, `restore_fixtures.py`, `build_engine.py`.
2. `protocol_gate.py`, `k1_gate.py`, `cpu_gates.py fullshape`, `cpu_gates.py reset`.
3. `startup_gate.py`, `argument_gate.py`, `run_cpu_gates.py`.
4. `shared_oracle.py --require-complete` into `evidence/oracle-gate.json`.
5. `seal.py`, `seal.py --verify`, `plan_queue.py`.

All compilation takes the shared `ops/compile_turn.py` turn. CPU CLI processes
install limits; runtime imports do not. Full-shape sparse virtual arenas and
intercepted launch guards require unlimited virtual address space, but their
measured resident memory stays below 4 GiB. The build has a stricter 200 MB
local guard (the brief permits 300 MB); root's stop floor is 25 GB. Generated
objects and binaries are ignored and reproducible from pinned parent objects.

Hot-expert cache idea credit: **Niko1221 / Strata**. All code here is lab-authored.
[Work note](../../../../notes/2026-10-18-own-runtime-packet58v.md).
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md),
[sealed evidence](build-receipt.json), [temporary queue plans](evidence/queue-plans.json).
