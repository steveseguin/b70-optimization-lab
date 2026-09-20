# Two-card acceptance on the no-swap launcher, 2026-09-19 20:08-20:14 EDT -- receipts, not a packet

This directory holds the receipts of the two-card FP8 acceptance session run on the no-swap launcher
(commit `fc48856e6`). **It is not an evidence packet and it did not retire anything.** The session
itself was clean -- every stage returned 0, strict was 12/12 exact, the six practical requests passed
with exact repeats, the stop was clean and both health probes were clean -- but
`collect-fp8-tp2-acceptance-evidence.py` **refuses to freeze it**, because the session was launched
without `QUALIFIED_CONTAINER` set and therefore recorded its runtime comparison against the wrong
reference server. See
[the no-swap launcher change](../../notes/2026-09-19-noswap-launcher-change.md#gpu-run-1-attempt-1-2026-09-19-2008-2014-edt----the-session-was-clean-and-the-packet-still-cannot-be-frozen).

Raw session root: `/mnt/fast-ai/bench-results/fp8-tp2-acceptance-noswap-20260919`
(kept; the packet must be collected from a *new* session, not from this one).
Session log: `/mnt/fast-ai/bench-results/batch5-session-20260919.log`.

| File | What it is |
| --- | --- |
| `cgroup-memory.json` | the container's own cgroup counters, read by the session runner just before the graceful stop. **The first such reading taken from a container the shipped launcher started with `--memory-swap 12g`, with no helper armed beside it.** |
| `runtime-comparison.json` | the session's own image/argument/environment comparison against the qualified container. **This is the file that blocks the packet**: `environment_differences` is non-empty. |
| `strict-comparison.json` | 12/12 complete token arrays exact against the September 16 same-image no-MTP reference, 89.867 tok/s against 33.035. |
| `session-rcs.json`, `session-runner.log`, `health-result.json` | every stage rc 0; preflight and postflight rc 0 with `gpu_faults: []`. |
| `host-before.json`, `host-after.json` | host memory and swap either side of the session; same boot id throughout. |
| `swap-tp2-acceptance.csv`, `swap-sampler-tp2.log` | `scripts/measure-swap-during-start.sh` across the whole session: 737 samples at 0.5 s over 377 s. |

## The container never swapped

`cgroup-memory.json`, from `docker-f14d0a17...scope`:

| Counter | Value | Reading |
| --- | --- | --- |
| `memory.events` `oom_kill` | **0** | the number that had to stay 0, and did |
| `memory.events` `oom` / `low` / `high` | 0 / 0 / 0 | nothing else tripped either |
| `memory.events` `max` | **11,198** | the ceiling is still hit constantly; this is the mechanism working |
| `memory.max` / `memory.peak` | 12,884,901,888 / 12,884,901,888 | ran flat against the 12 GiB ceiling, as every start does |
| `memory.swap.max` / `memory.swap.peak` | **0 / 0** | no allowance, none used -- straight from `serve.py`, no helper |
| `memory.stat` `pswpout` / `pswpin` | **0 / 0** | the container swapped nothing at all |
| `memory.stat` `anon` | **9,654,628,352 B = 8.99 GiB** | the working set |
| `memory.stat` `file` / `file_dirty` | 2,603,409,408 B (2.42 GiB) / **0** | all clean, all reclaimable |
| `memory.stat` `pgscan_direct` | 4,835,312 pages | direct reclaim inside the cgroup |
| `anon_headroom_bytes` | **3,230,273,536 B = 3.01 GiB** | the margin the whole change rests on |

That `anon` is the fourth independent reading of the two-card working set and the first from the
launcher's own bytes: 8.95 / 8.94 / 8.94 / **8.99 GiB**. The ~3 GiB of headroom under the 12 GiB cap
is a property of the workload, not of a run or of the helper.

## The host swapped 1,106 MiB, all of it before the server was ready

From `swap-tp2-acceptance.csv` (`t=0` is 20:08:10 EDT / 00:08:10Z; ready at `t=269`):

* **Total host swap-out over the session: 283,127 pages = 1,106 MiB**; swap-in 89,575 pages = 350 MiB.
* All of it in 66 samples between **20:09:41 and 20:12:39** (`t=91`-`269`) -- the source download, the
  model verify and the weight load. **Nothing swapped once the server was serving.**
* Peak **630 MiB in one 0.5 s sample at 20:11:10**, then 196 MiB at 20:11:11; essentially over by
  20:11:16.
* Host `SwapFree` 36,822,552 -> 36,026,184 kB, a net **778 MiB** consumed.
* Minimum `MemAvailable` **3.01 GiB** (at `t=362`, during the practical requests); peak `Cached`
  **10.48 GiB** at `t=91`. Peak PSI memory `some`/`full avg10` **4.04**.

**None of that 1,106 MiB came from the container** -- its own `pswpout` is 0. It is host-side
reclaim of other resident pages as the container's page cache grew through the 29 GB read, and it is
four times the 275-293 MiB the three helper-applied validation starts saw. The difference is what
else was on the host: those three starts followed a quiet resume, this one followed an anonymous
codeload download and a full model verify in the same window. Worth watching on the next session, not
a regression in the change: the pages the copy engine reads are the container's, and the container
swapped nothing.
