# A367 sealed record-replay supervisor

CPU-built only on 2026-10-16. No device, health probe, model load or replay ran.
One future owner-admitted replay checks the certified FP8 TP4/EP4 MTP1 A367
record `cmtzask41000nlq011f16bpbc` (46.854250 tok/s). A slower exact replay passes;
a faster mismatching replay fails. This is not a new benchmark promotion.

Lifecycle copied with attribution from the immutable calibration at `5efca23e3`,
seal `b75d9f86`; driver imports remain pinned. Preserve short IPC, ESRCH handling,
local ext4 scratch, 0.5 s sampler/live reserve, admission, shutdown guards, one
SIGINT, complete session exit and 305 s watch. Add one record client after the
20 s plateau and the record's full 30 s delay; budget 2700 s, latch only, no retry.

The exact record includes `TORCH_TRACE` and `--cudagraph-metrics`; both remain.
OMP returns to 1 and the server inherits nice0/unrestricted affinity. Future
execution requires that profile before any model launch. The normal-priority
client is pinned to coordinator cores. See [launch runbook](LAUNCH-RUNBOOK.md).

Default admission refuses. The pending four-field `replay_memory_exception`
proposes 114840824 KiB, measured load need plus reserve; generation demand is
unmeasured. Approval binds preregistration and seal bytes. No owner approval
is recorded by this build. A one-hour owner window may preempt the client cap.

`environment.json` explicitly writes `passed=true` only after successful audit
and final admission, addressing the calibration schema omission in this packet.
No copy of `derive_floor.py` is needed: this packet does not derive fixture floors.

The seal pins code/tests/docs, the calibration seal and dependencies, driver,
record launcher/base/supervisor, client/checker/suite, record/attestation/identity.
The pending approval and test receipts are outside the seal to avoid self-reference.

| Change | Reason | Speed risk |
|---|---|---|
| OMP_NUM_THREADS=1; normal server priority; no server CPU affinity restriction; frozen clean base environment and PATH | Restore record identity from calibration OMP2/nice19/taskset; execute refuses wrong inherited profile | Removes calibration scheduling deltas; actual speed remains unmeasured |
| TORCH_TRACE and --cudagraph-metrics retained; trace path relocated to run directory | Both are present in frozen A367; not calibration-only diagnostics | Same diagnostics; storage timing may differ |
| Fixed record client once; 20s plateau then full record 30s health delay; client nice0 on cores 4-15,20-31 | Bound generation after proven lifecycle readiness; prevent client starvation | Client affinity and added plateau can affect timing; no prompt warmup |
| 0.5s memory sampler, journal watcher, 12000000 KiB live reserve and admission gates retained | Preserve current-boot safety; client watchdog latches at 2700s without killing | Monitor CPU/I/O overhead remains; measured speed only |
| One API PID SIGINT, guarded entry/spawn shutdown guards, all-session exit, 305s watch | Reuse calibration lifecycle; no retry, hard kill or resident server | No intended arithmetic change; startup/shutdown overhead |
| Fresh local ext4 scratch/cache/tmp/RPC; short a367r run name; ESRCH skip retained | Preserve all three calibration fixes; reject non-ext4 scratch | Cold compilation and cache placement may affect startup/first-use timing |
| Clean byte-identical source export; guarded entry and driver/prep PYTHONPATH prefixes; PACKET4_* bindings | Protect shared trees and install cooperative guards; preserve source/stage/model byte checks | Import overhead possible; no intended compute difference |
| Pinned reconciliation and calibration dependency scope; omit historical launcher bookkeeping env | Keep fresh payload verification; do not admit changed fixture arithmetic or fake attempt367 metadata | No compute selectors omitted; no expected compute effect |
| 114840824 KiB exception only, default refuse, four-field hash-bound owner sentence | Measured 102840824 KiB load need plus 12000000 reserve; generation demand unmeasured | Memory pressure could change speed or stop the run; owner risk acceptance required |
| Historical host-controlled wrapper omitted; no power/swap/page-cache changes | Current host rules and safe calibration lifecycle | Host/cache/driver state differs from historical record; one replay does not establish a new record |

Replay-only failure-path hardening: stop-receipt I/O failure cannot suppress the
one SIGINT; late monitor failures fail the result. Failed runs still observe the
full 305 s post-exit watch. A client deadline latches the stop and lets server
teardown/watch proceed before waiting for the CPU client to drain. A stuck client
can still require owner recovery; nothing sends it a kill signal.

## October 16 sampler fix after replay attempt b

Attempt b (`a367r-20261016T194524Z`) passed admission, and its server ran with the record profile (nice 0, CPUs 0-31, OMP=1). During weight load, one sample took 1.738 s, which tripped the `sampler delayed >1.5s` watchdog.

The cause: every sample read `/proc/<pid>/cmdline` for every session process. That read takes the target's mmap lock, which a loading worker can hold through a slow FUSE page fault. The sampler now reads `comm`/`status`/`cgroup` each sample and reads `cmdline` only until a worker's rank is known, caching it per pid.

The SIGINT sent during loading was deferred by the API server until engine initialization finished. The engine then shut down in order: all four workers reported shutdown done, zero GPU fault lines. A test pins the no-re-read behaviour. Nothing else changed.

