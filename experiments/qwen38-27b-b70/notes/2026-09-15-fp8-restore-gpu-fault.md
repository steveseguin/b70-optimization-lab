# FP8 service restore: GPU fault during load

After the [research-stage out-of-memory incident](2026-09-15-research-load-host-oom.md),
the admitted restore of the qualified FP8/MTP1 service stopped on a GPU fault.
The API on port 18124 remains offline. All GPU work on this boot is halted and
the campaign fault latch is set. This closes the
[recovery and metadata plan](2026-09-14-fp8-recovery-metadata-plan.md) with the
metadata change unvalidated.

## Sequence (UTC, September 15)

| Time | Event |
| --- | --- |
| 01:58:17–01:58:27 | Bounded standard health check on the qualified image passed on both cards: exact copy/compute and XCCL sums, normal cleanup, confirmed exit, clean kernel window, at least 11.15 GiB available. |
| 01:58:47 | Qualified R304 FP8/MTP1 service started in `final-service`: same image, arguments and settings as the 19:19 restore that passed 12/12. |
| 02:00:25–02:00:35 | While the last weight shards loaded, available memory fell to 7.7 GiB and about 4.6 GiB was swapped out within five seconds. |
| 02:00:38 | Card `0000:e3:00.0`: 33 unsuccessful page-fault responses on the copy engine (bcs), 8 engine memory CAT errors, one bcs engine reset and a timed-out job in a worker; device coredump created. Target weights had just loaded (8.67 s) and the drafter was loading. |
| 02:00:38–02:01:10 | The helper detected the fault, made its single graceful stop and exited; the container was removed. |

## Established

- The signature matches the 18:30 UTC incident on September 14 (memory-fault
  responses, CAT error, bcs engine resets). This time it happened with the
  unchanged qualified image and no custom communicator.
- A standard health check passed 20 s before the service started; the full
  model load still faulted. On September 6 this host also retired a boot after
  xe faults on both cards during model loads (R277/R278; see
  [archived ledger](../../../CURRENT-history-20260909.md)).
- The only page allocation failure in the window was the coredump's GuC log
  snapshot, a high-order allocation after the fault.
- Postflight: container gone, no model process on either render node, port
  closed, no kernel lines after the halt.

## Not established

The cause. One lead is host memory: the fault followed a sudden swap-out burst
while the 12 GiB-limited container read the last weight shards. However, this
boot had already seen GPU faults on both cards at 18:30 and a five-hour
out-of-memory stall, so device or driver state is an equally open explanation.

## Disposition

- No retry, reboot, driver reset or settings change by the agent. Restoring the
  service needs the user's decision on a host reboot.
- After a reboot: a newly admitted recovery root, the bounded standard health
  check, the qualified service and the full strict output check. Recording host
  memory during that load would test the memory lead without changing settings.
- Do not relaunch the research recipe until its environment contract is fixed
  and the bounded diagnostic has run; see the
  [incident note](2026-09-15-research-load-host-oom.md). This restore already
  carried all five qualified variables, so their omission does not explain
  this fault.

## Evidence

Raw root `/mnt/fast-ai/bench-results/fp8-mtp-recovery-metadata-20260914`:

- `FAULT.json` (SHA256 `9b22ae9d70f2304a579a6cd83c2b0c19d777f91335602efd4bbe8db1f3d4d516`)
- `final-service/postflight.json` (SHA256
  `c62eceab770545003212bc4a0587a70b0fa443f1b9c9279762fd63c573b0c9ac`) with the
  fault counts, memory samples, stop receipts and owner/listener checks
- `final-service/kernel.log`, `final-service/server.log`, `health-after-research-oom/`
- `campaign-completion.json` (`closed-after-gpu-fault`)
- local only: `final-service-incident/devcd1-data.txt`, the device coredump
  (103,185 bytes, SHA256
  `28c4ce428860758bcc62490f0e6b042bb83ee2c5250a0302a0254655492e34a7`), and the
  full kernel journal window
