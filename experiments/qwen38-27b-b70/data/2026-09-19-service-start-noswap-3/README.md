# Validation start 3 of 3: the two-card FP8 service start of 2026-09-19 19:45 EDT, with no container swap

The third and last of the service starts that validate `--memory-swap` equal to `--memory` before
either launcher's `serve.py` is edited. Same boot as the 17:20 swapping baseline and as starts 1 and
2, so all four rows compare the same machine in the same state with one setting changed. The
narrative and the analysis are in the
[finding note](../../notes/2026-09-19-container-memory-cap-swap.md#validation-start-3-of-3-2026-09-19-1945-edt--2345-utc),
and the launcher edit that followed is in
[the no-swap launcher change](../../notes/2026-09-19-noswap-launcher-change.md).

**Outcome: three of three passed.** Container `pswpout` **0** and `memory.swap.peak` **0**,
host-wide swap-out **275 MiB** (starts 1 and 2: 293 and 288 MiB; the swapping baseline: 4,514 MiB),
`memory.events max` **16,117** with `oom` and `oom_kill` **0**, ready 150 s after the start command,
strict **12/12** against the comm-2 no-MTP reference at **89.84 tok/s**, zero `xe` fault lines.
`anon` came back at **9,602,744,320 bytes (8.94 GiB)**, within **0.02 %** of start 2 and **0.06 %**
of start 1 -- three independent starts inside a tenth of a percent, so the roughly 3 GiB of headroom
under the 12 GiB cap is a settled figure. The weight load was the fastest of the four at **8.21 s**.

| File | What it is |
| --- | --- |
| `noswap-helper.log` | **The key receipt.** `scripts/apply-container-noswap.sh --name-prefix neural-fp8` waiting for a new container, finding `neural-fp8-277ee9175b5c4b32a97a9a35a1d4241f` (`11d638153960...`) **17 s** into the start at `memory.current` 20,516,864 bytes (20 MB) -- far under the 6 GiB refusal threshold. Records the full cgroup state before and after: `memory.swap.max` 4,294,967,296 -> **0** in the same second. |
| `cgroup-after-start.txt` | The live container's cgroup files read after the service was up and the strict suite had run. `memory.max` 12 GiB, `memory.swap.max` **0**, `memory.peak` 12,884,901,888 (= `memory.max`), `memory.swap.peak` **0**, `memory.current` 12,621,553,664, `anon` **9,602,744,320 (8.94 GiB)**, `file` 2,884,149,248, `pswpout` **0**, `pgscan_direct` 6,821,897, `memory.events max` **16,117** with `oom` 0 and `oom_kill` **0**. Read-only: nothing was started, stopped, updated or written. |
| `swap-during-start.csv` | `scripts/measure-swap-during-start.sh` at 0.5 s: 489 rows over 251 s, `t=0` at 19:45:11 EDT / 23:45:11Z. Host-wide `/proc/vmstat`, `/proc/meminfo` and `/proc/pressure/memory` fields (the sampler's header names each one). Totals over the window: 70,280 pages out = **275 MiB**, 65,759 pages in = 257 MiB, largest single 0.5 s sample 45 MiB, minimum MemAvailable **3.07 GiB**, peak PSI `some avg10` **2.73**, peak `Cached` 9.20 GiB. |
| `session.log` | The resume script's phase-by-phase record: preconditions (MemAvailable 14,036 MiB, no containers), two XPU/XCCL health probes (both clean on both cards), the port-free wait on 18124, the `systemd-run` line for unit `fp8-service-20260918-resume`, ready at 23:47:58Z, strict 12/12 at 89.84 tok/s, health clean on both cards afterwards. |

Raw root, with the service state directory, the server log and the strict-suite outputs that are too
large to copy here: `/mnt/fast-ai/bench-results/resume-20260919g/` (`service/`, `service-strict/`,
`service-strict-vs-reference.json`, `health.log`, `service-health.log`, `swap-sampler.log`,
`service.command.json`). The server log's own timings: `Loading weights took` **8.21 s**,
`Model loading took` 10.94 s, `init engine` 73.18 s of which 64.41 s is compilation.

The container is `neural-fp8-277ee9175b5c4b32a97a9a35a1d4241f`, unit
`fp8-service-20260918-resume`, port 18124, state
`/mnt/fast-ai/bench-results/resume-20260919g/service`. It was still serving when these receipts were
taken and was not disturbed.

**This is the start that ends the validation.** Both launchers now carry `--memory-swap 12g`
themselves, so `scripts/apply-container-noswap.sh` no longer has to be armed beside a start; the
script is kept for containers launched from older bytes. What is still owed is the GPU acceptance
work listed in [the no-swap launcher change](../../notes/2026-09-19-noswap-launcher-change.md).
