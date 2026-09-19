# Validation start 2 of 3: the two-card FP8 service start of 2026-09-19 18:59 EDT, with no container swap

The second of the three service starts that validate `--memory-swap` equal to `--memory` before
either launcher's `serve.py` is edited. Same boot as the 17:20 start and as start 1, so all three are
the same machine in the same state with one setting changed. The start was one batch window 3
(`/mnt/fast-ai/bench-results/batch3-session-20260919.sh`, `RESUME_ROOT
/mnt/fast-ai/bench-results/resume-20260919f`) was going to make anyway, after its
[MiniMax-H3 canvas ladder](../../../minimax-h3-b70/data/2026-09-19-canvas-ladder/): **nothing was
restarted for this measurement.** The narrative and the analysis are in the
[finding note](../../notes/2026-09-19-container-memory-cap-swap.md#validation-start-2-of-3-2026-09-19-1859-edt--2259-utc).

**Outcome: start 1 reproduced.** Container `pswpout` **0**, host-wide swap-out **288 MiB** (start 1:
293 MiB; swapping baseline: 4,514 MiB), `memory.events max` **12,964** with `oom_kill` **0**, ready
at 23:02:00Z, strict **12/12** against the comm-2 no-MTP reference at **89.79 tok/s**, zero `xe`
fault lines. The figure that mattered most from start 1 -- the corrected working-set size -- came
back at `anon` **9,600,892,928 bytes (8.94 GiB)**, **0.08 % away** from start 1's 9,608,658,944, so
the ~3 GiB of headroom under the 12 GiB cap is a stable number rather than one reading. Two small
moves, neither a regression: ready took 160 s against 150 s, all of it inside `init engine` (the
weight load was identical at 8.44 s, so it is torch.compile variance), and the strict suite read
89.79 tok/s against 89.9, a tenth of a percent, with the comparison still 12/12 exact.

| File | What it is |
| --- | --- |
| `noswap-helper.log` | **The key receipt.** `scripts/apply-container-noswap.sh --name-prefix neural-fp8` waiting for a new container, finding `neural-fp8-42a89cfc17924bbd8d59d68dfb3f0cd4` (`43c88dbb33e9...`) **18 s** into the start at `memory.current` 119,361,536 bytes -- under the 6 GiB refusal threshold, but 19x the 6 MB of start 1, which is the reminder that this window is a race and the margin is what makes it safe. Records the full cgroup state before and after: `memory.swap.max` 4,294,967,296 -> **0** in the same second. |
| `cgroup-after-start.txt` | The live container's cgroup files read after the service was up and the strict suite had run. `memory.max` 12 GiB, `memory.swap.max` **0**, `memory.peak` 12.0 GiB, `memory.swap.peak` **0**, `memory.current` 12,485,853,184, `anon` **9,600,892,928 (8.94 GiB)**, `file` 2,743,660,544, `pswpout` **0**, `pgscan_direct` 5,792,235, `memory.events max` 12,964 with `oom` 0 and `oom_kill` **0**. Read-only: nothing was started, stopped, updated or written. |
| `swap-during-start.csv` | `scripts/measure-swap-during-start.sh` at 0.5 s: 509 rows over 263 s, `t=0` at 18:59:02 EDT / 22:59:02Z. Host-wide `/proc/vmstat`, `/proc/meminfo` and `/proc/pressure/memory` fields (the sampler's header names each one). Totals over the window: 73,644 pages out = **288 MiB**, 71,962 pages in = 281 MiB, largest single 0.5 s sample 69 MiB, minimum MemAvailable **3.0 GiB**, peak PSI `some avg10` **3.52**, peak `Cached` 9.73 GiB. |
| `session.log` | The resume script's phase-by-phase record: preconditions (MemAvailable 13,890 MiB, no containers), two XPU/XCCL health probes (both clean on both cards), the port-free wait on 18124, the `systemd-run` line for unit `fp8-service-20260918-resume`, ready at 23:02:00Z, strict 12/12 at 89.79 tok/s. |

Raw root, with the service state directory, the server log and the strict-suite outputs that are too
large to copy here: `/mnt/fast-ai/bench-results/resume-20260919f/` (`service/`, `service-strict/`,
`service-strict-vs-reference.json`, `health.log`, `swap-sampler.log`). The batch window's own log is
copied beside the MiniMax receipts at
[`../../../minimax-h3-b70/data/2026-09-19-canvas-ladder/batch3-session-20260919.log`](../../../minimax-h3-b70/data/2026-09-19-canvas-ladder/batch3-session-20260919.log).

The container is `neural-fp8-42a89cfc17924bbd8d59d68dfb3f0cd4`, unit `fp8-service-20260918-resume`,
port 18124, state `/mnt/fast-ai/bench-results/resume-20260919f/service`. It was still serving when
these receipts were taken and was not disturbed.

**The setting is per-container.** `docker update` changed this container only; the next container
`serve.py` creates comes back at `--memory-swap 16g`. Until the launchers are edited,
`scripts/apply-container-noswap.sh` has to be armed beside every start. **One more validation start,
then the `serve.py` edit, the pinned packets and acceptance.**
