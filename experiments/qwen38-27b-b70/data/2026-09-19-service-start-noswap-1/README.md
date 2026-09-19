# Validation start 1 of 3: the two-card FP8 service start of 2026-09-19 18:23 EDT, with no container swap

The first of the three service starts that validate `--memory-swap` equal to `--memory` before
either launcher's `serve.py` is edited. Same boot as the 17:20 EDT start, so this is the same
machine in the same state with one setting changed. The start was one the batched window
(`/mnt/fast-ai/bench-results/batch2-session-20260919.sh`, `RESUME_ROOT
/mnt/fast-ai/bench-results/resume-20260919e`) was going to make anyway, after its MiniMax-H3 block:
**nothing was restarted for this measurement.** The narrative and the analysis are in the
[finding note](../../notes/2026-09-19-container-memory-cap-swap.md#validation-start-1-of-3-2026-09-19-1823-edt--2223-utc).

**Outcome: container `pswpout` 0 (against 3.94 GiB on the 17:20 start), host-wide swap-out 293 MiB
(against 4,514 MiB), `memory.events oom_kill` 0, ready at 22:26:22Z, strict 12/12 against the comm-2
no-MTP reference at 89.9 tok/s, zero `xe` fault lines -- and the weight load was 0.09 s *faster*, not
slower.** The one figure that moved the wrong way is the headroom: with nothing able to leave for
swap, container `anon` reads **8.95 GiB** against the 12 GiB cap, not the 6.91 GiB measured while
2-3 GiB of it was sitting in swap. Slack is therefore ~3 GiB, not ~5.

| File | What it is |
| --- | --- |
| `noswap-helper.log` | **The key receipt.** `scripts/apply-container-noswap.sh --name-prefix neural-fp8` waiting for a new container, finding `neural-fp8-1390b553d19e450d8110ac7f631f57d6` 17 s into the start at `memory.current` 6,209,536 bytes (far under its 6 GiB refusal threshold), and running `docker update --memory 12g --memory-swap 12g`. Records the full cgroup state before and after: `memory.swap.max` 4,294,967,296 -> **0** in the same second. |
| `cgroup-after-start.txt` | The live container's cgroup files read after the service was up and the strict suite had run. `memory.max` 12 GiB, `memory.swap.max` **0**, `memory.peak` 12.0 GiB, `memory.swap.peak` **0**, `anon` 9,608,658,944 (8.95 GiB), `file` 2,702,733,312, `pswpout` **0**, `pgscan_direct` 5,700,193, `memory.events max` 12,646 with `oom` 0 and `oom_kill` **0**. Read-only: nothing was started, stopped, updated or written. |
| `swap-during-start.csv` | `scripts/measure-swap-during-start.sh` at 0.5 s: 489 rows over 252 s, `t=0` at 18:23:35 EDT / 22:23:35Z. Host-wide `/proc/vmstat`, `/proc/meminfo` and `/proc/pressure/memory` fields (the sampler's header names each one). Totals over the window: 74,891 pages out = **293 MiB**, 76,562 pages in = 299 MiB, minimum MemAvailable **3.0 GiB**, peak PSI `some avg10` **3.95**, peak `Cached` 11.83 GiB. The sampler's own stderr summary rounds the out total to 292 MiB. |
| `session.log` | The resume script's phase-by-phase record: preconditions, two XPU/XCCL health probes (both clean on both cards), the port-free wait, the `systemd-run` line, ready at 22:26:22Z, strict 12/12 at 89.9 tok/s. |

Raw root, with the service state directory, the server log and the strict-suite outputs that are too
large to copy here: `/mnt/fast-ai/bench-results/resume-20260919e/` (`service/`, `service-strict/`,
`service-strict-vs-reference.json`, `health.log`, `swap-sampler.log`).

The container is `neural-fp8-1390b553d19e450d8110ac7f631f57d6`
(`c46dd8a5dba879fd468f9837a030012a09b4300c0b3cd8c84b99f714c186325c`), unit
`fp8-service-20260918-resume`, port 18124. It was still serving when these receipts were taken and
was not disturbed.

**The setting is per-container.** `docker update` changed this container only; the next container
`serve.py` creates comes back at `--memory-swap 16g`. Until the launchers are edited,
`scripts/apply-container-noswap.sh` has to be armed beside every start.
