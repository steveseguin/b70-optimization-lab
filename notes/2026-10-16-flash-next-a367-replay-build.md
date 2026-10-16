# A367 replay CPU build — 2026-10-16

Prepared a separate record replay packet; no GPU work, health probe, supervisor
execution, source-tree edit or host setting change ran. Calibration and driver
remain byte-identical. The ledger was read first and all three fixes retained.
The immutable record diagnostics were confirmed, so they were not removed.

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

Open risks: generation host demand, current-boot output parity and speed remain
unmeasured. Watcher overhead, cold scratch and current host state can affect
speed. The existing one-hour owner window can preempt the 2700 s client cap
following a slow load; no automatic renewal is implemented. Stop is cooperative:
a stuck CPU client or server session can outlive a soft budget and needs owner
recovery. This build does not authorize any launch or claim measured reproduction.

The calibration derive-floor omission is addressed only in replay audit writing:
`passed=true` follows successful environment verification and final admission.
No fixture floor derivation is added.

`git pull --ff-only` fetched remote main but refused because the two histories
have diverged. No merge, rebase, stash, branch or push was performed. The focused
CPU build is committed on local main; unrelated untracked evidence is preserved.

See the [packet](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-replay/README.md),
[runbook](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-replay/LAUNCH-RUNBOOK.md),
and [CPU receipt](../data/2026-10-16-flash-next-a367-replay-build/cpu-tests.json).

Read-only identity and lifecycle reviews were performed in parallel. Replay-only
failure-path repairs ensure a failed stop-receipt write cannot suppress SIGINT,
late monitor failures cannot pass, and a client watchdog stop proceeds through
GPU exit and the full watch before waiting for a stuck CPU client. No changes
were made to the sealed calibration or driver to obtain these safeguards.

Final CPU verification: **232 passed, zero failures/errors/skips** (replay 83,
calibration 75, driver 59, payload 6, frozen-tree 9). All three active seals
have **zero mismatches**; calibration and driver tracked files are unchanged.
Runbook shell blocks pass `bash -n`; plan is CPU-only; no packet bytecode was created.

- `seal.json` SHA256: `78556b50b5ede841f399d76a1ce45eb2751b9400d25e556293fab4c3be62bb6e`
- `preregistration.json` SHA256: `a7fad58bc627d8ce16f46c1eb8bd0c20432edcbc71619eab0ff6649a9610c575`

Exact pending owner sentence (`approved=false`):

> I authorize one A367 record-replay measurement on steve-b70s with a replay-only MemAvailable start floor of 114840824 KiB, a 0.5-second watchdog and the 12000000 KiB live reserve, under preregistration SHA256 a7fad58bc627d8ce16f46c1eb8bd0c20432edcbc71619eab0ff6649a9610c575 and seal SHA256 78556b50b5ede841f399d76a1ce45eb2751b9400d25e556293fab4c3be62bb6e. This accepts the unmeasured generation-memory risk, does not lower the packet-4 fixture floor, and does not resolve the halt or authorize another launch.
