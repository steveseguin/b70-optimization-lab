# Two-card FP8 service start of 2026-09-19 17:20 EDT: swap and cgroup receipts

The first start after the user's 17:17 EDT reboot, with `vm.swappiness` lowered from 60 to 1
(`/etc/sysctl.d/90-b70-swappiness.conf`) and nothing else having touched the cards on that boot. A
one-shot user unit ran `experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh
--only-service` with [`scripts/measure-swap-during-start.sh`](../../../../scripts/measure-swap-during-start.sh)
sampling beside it at 0.5 s.

**Outcome: ready at 17:22:45 EDT (21:22:45Z), strict 12/12 against the comm-2 no-MTP reference at
90.24 tok/s, zero `xe` fault lines on the boot -- and 4.41 GiB still swapped out during the weight
load, 89 % of it from inside the service container.** The narrative and the analysis are in the
[finding note](../../notes/2026-09-19-container-memory-cap-swap.md).

| File | What it is |
| --- | --- |
| `swap-during-start.csv` | The sampler's output: 508 rows at 0.5 s over 262 s. `t=0` is 17:19:48 EDT / 21:19:48Z; the container appears at `t=17`; the 4.2 GiB burst is `t=79`-`t=88`; ready at `t=177`. Columns are host-wide `/proc/vmstat`, `/proc/meminfo` and `/proc/pressure/memory` fields (see the sampler's header for each one). |
| `swap-sampler.log` | The sampler's own stderr summary: 4,513 MiB out, peak 1,178 MiB in one 0.5 s sample. |
| `cgroup-counters.txt` | **The key receipt.** `docker inspect` plus a `cat` of the live container's cgroup files, read at 17:28 EDT while the service was up. Read-only: nothing was started, stopped, updated or written. Shows `memory.max` 12 GiB, `memory.swap.max` 4 GiB, `memory.peak` = `memory.max` exactly, `memory.swap.peak` = `memory.swap.max` exactly, `memory.events max` 2,005 with `oom_kill` 0, and container `pswpout` 1,033,915 pages = 3.94 GiB of the host's 4.41 GiB. |
| `session.log` | The resume script's phase-by-phase record: health probes, port wait, `systemd-run` line, ready at 21:22:45Z, strict 12/12 at 90.24 tok/s. |
| `postboot.log` | The one-shot unit's wrapper: swappiness at boot, host `pswpin`/`pswpout` before (0/0) and after (613,604 / 1,155,516 pages), the same session transcript, and `fault lines this boot: 0`. |

Raw root, with the service state directory and the strict-suite outputs that are too large to copy
here: `/mnt/fast-ai/bench-results/resume-20260919c/` (`service/`, `service-strict/`,
`service-strict-vs-reference.json`, `health.log`).

The container is `neural-fp8-c866dbbf52f04eae85d6b76c367ac3a0`
(`77d403499ee704a17ad343b1479f0905da27f8b8e89f3133ef88a6bd6d4f3388`), unit
`fp8-service-20260918-resume`, port 18124, started 21:20:05Z. It was still serving when these receipts
were taken and was not disturbed.
