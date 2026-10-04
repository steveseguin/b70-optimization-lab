# Comm-5, attempt 1: the profiler tripped the memory guard, and the kill logged GPU fault lines (2026-10-03 22:37-22:40 EDT)

## In plain words

The experiment never reached its real test. Its first stage was a measurement run with a profiler switched on. The
profiler used host memory faster than expected, the launcher's own safety guard stopped the server before the machine
could run short, and stopping a busy GPU server that abruptly made the graphics driver log fault lines. The campaign
runner saw those lines, halted as it is built to, and did **not** put the chat service back. The machine stayed up and
responsive throughout. **The chat service is down until the machine is rebooted**, because our rule is no GPU work on
a boot that has logged a fault.

Nothing about the candidate change (reusing the exchange buffers) was tested. It is neither confirmed nor refuted.

## What happened, in order

| Time (EDT) | Event |
| --- | --- |
| 22:36:55 | campaign start (`run-20261003-fp8-comm5-campaign.py`, git `09ba409ee`), service stopped cleanly, health probe clean |
| 22:39:42 | profiled server ready (shipped two-card recipe + `b70-step-profiler`, rank 0, 30 steps). Host memory available at ready: **3.2 GiB** |
| 22:39:43 | `profiler_start`; rank 1 correctly did not profile (the September 18 rank-gate fix works) |
| 22:39:46 | `profiler_stop` after the 30-step window; trace export begins in the worker |
| 22:39:47.1-47.6 | available host memory falls 3.17 -> 2.79 -> **2.42 GiB** in one second |
| 22:39:47 | the research launcher's memory guard (`min_available` 2.5 GiB) kills the container's cgroup: `MEMORY-GUARD.json`, reason "available host memory fell to 2.42 GiB" |
| 22:39:47 | kernel: `xe 0000:e3:00.0 ... Engine reset: engine_class=ccs`, `Fault response: Unsuccessful -EINVAL`, `Engine reset: engine_class=bcs` |
| 22:39:49 | fault latch: `GPU FAULT detected (3 journal lines); campaign halted, no restore` |

No trace file was written (the kill landed during the export). No device coredump was created. `earlyoom` did not
fire (its floor is 1.2 GiB). Receipts: [`../data/2026-10-03-fp8-comm5-attempt1/`](../data/2026-10-03-fp8-comm5-attempt1/);
raw run `/mnt/fast-ai/bench-results/fp8-comm5-20261003/`.

## What it shows

1. **The fault lines were caused by the kill, not by the workload.** They appear in the same second as the cgroup
   kill, on the card whose worker was mid-kernel. This is the third time this host has shown it (the September 21
   watchdog kill, tonight) and other dual-B70 owners report the same from `docker rm -f` on a busy server
   (`intel/compute-runtime` issue 948). **A hard kill of a busy GPU process is itself a fault source on this driver.**
2. **A steady two-card server leaves only about 3.2 GiB of host memory available** on this 15 GiB machine, and the
   research launcher's guard fires at 2.5 GiB. That is a 0.7 GiB margin. A 30-step profile needs more than that for
   its event buffers and export. The September 17 profile ran with the same settings and survived; tonight the host
   also carried an interactive agent session and its tools (roughly 1 GiB).
3. **The safety chain did its job.** Guard before memory exhaustion, fault latch before a second GPU run, service left
   down rather than restarted on a boot with fault lines. The cost is a reboot.

## What changes

- The rerun is [`../scripts/run-20261003-fp8-comm5b-campaign.py`](../scripts/run-20261003-fp8-comm5b-campaign.py): the
  control and candidate stages run **first**, the profile runs **last**, with an **8-step** window, and is skipped
  outright unless the idle host has at least 13 GiB available. The decision rule of the
  [preregistration](2026-10-03-fp8-comm5-prereg.md) is unchanged.
- Not changed, but worth a decision: the memory guard stops a server with a cgroup kill. A graceful stop would avoid
  the fault lines but takes seconds the host may not have. With 2.4 GiB still available tonight there was time; a
  two-level guard (graceful stop at the first floor, kill at a lower one) would have saved this boot.
- Rule restated for profiling on this host: never first in a campaign, never more than about 10 steps with a
  resident two-card server, and close other memory users first.
