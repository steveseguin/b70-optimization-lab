# The swapping during a service start comes from the container's own memory cap, not from the host (2026-09-19)

Date: 2026-09-19. Host `steve-TURIND8-2L2T` (two B70s, 15.2 GiB RAM, 36 GiB swap). Times are EDT with
UTC in brackets. This note explains a measurement taken beside the 17:20 EDT two-card service start
that followed the user's reboot, and it revises the swap paragraph of the
[fifth GPU fault note](2026-09-19-gpu-fault-service-start.md).

## In plain words

We turned the machine's swapping setting almost all the way off (`vm.swappiness` 60 to 1), rebooted,
and started the two-card service first thing on the fresh boot with a recorder running beside it. The
start was perfect: ready in 2 minutes 40 seconds, all twelve test prompts exactly right, 90.24 tokens
a second, and not one fault line from either card.

**But the machine still swapped 4.4 GB out during the weight load, and 4.2 GB of that went out in a
single 20-second burst.** That should not happen with swapping turned down and 7 GB of memory still
free. The reason, read straight off the running container's own counters: **the swapping is not the
host's decision at all. It is the container's.** Our launcher starts the server with `--memory 12g
--memory-swap 16g`, which tells the kernel "this container may use 12 GB of memory and 4 GB of swap".
Reading a 29 GB file of model weights fills the container's page cache, the container hits its own
12 GB ceiling about two thousand times, and every time it does the kernel pushes some of the
container's real working memory out to swap to make room for more file cache. The host's
`vm.swappiness` setting has no say in it; a cgroup at its limit swaps regardless.

**This is the same mistake as the MiniMax runner's 4 GB `MemoryMax` cap that helped kill the user's
desktop session on September 17** -- a memory cap set below what the job actually touches, which turns
into reclaim thrash instead of a tripwire.

It is also the best explanation we have for the copy-engine faults that keep striking during weight
loads: the pages the card's copy engine is reading from host memory can be swapped out from under it
mid-copy. **That is not proven.** This start swapped 4.4 GB and did not fault.

The fix is one word in each launcher -- make the container's swap allowance equal to its memory
allowance, so that at the ceiling the kernel throws away clean file cache (which it can re-read from
disk) instead of swapping out live working memory. Before changing the launchers, which are pinned by
published evidence packets, we validate it on the next three service starts that were going to happen
anyway, with a helper that applies the setting to the running container.

**Update, 18:23 EDT the same evening: validation start 1 of 3 is done and it worked.** The container
swapped **nothing at all** (0 pages, against 3.94 GiB), the host swapped 293 MiB instead of 4,514 MiB,
the service came up ready with 12/12 exact at 89.9 tokens a second, no out-of-memory kills, no fault
lines -- and the weight load was very slightly *faster*, not slower. One thing did change for the
worse: with nothing able to leave for swap, the container's true working memory turns out to be
**8.95 GB, not the 6.91 GB we read last time**, because 2-3 GB of it had been sitting in swap when we
measured. The room to spare under the 12 GB ceiling is therefore about 3 GB, not about 5. See
[Validation start 1](#validation-start-1-of-3-2026-09-19-1823-edt--2223-utc).

**Update, 19:03 EDT: validation start 2 of 3 is done and it matched start 1.** Again no swapping at
all inside the container, 288 MB swapped host-wide against 293 MB last time, no out-of-memory kills,
service ready, 12 of 12 exact at 89.79 tokens a second, no fault lines. The number that matters --
how much memory the container actually needs -- came back **within 0.08 % of start 1** (8.94 GB
against 8.95 GB), so the roughly 3 GB of room to spare is a stable figure and not a single reading.
Two things moved slightly and neither is a regression: the service took 10 seconds longer to be
ready, all of it inside a code-compilation stage while the weight load was identical to the
hundredth of a second, and the speed test read 89.79 against 89.9 tokens a second, which is a tenth
of a percent. **One more start, then `serve.py` is edited.** See
[Validation start 2](#validation-start-2-of-3-2026-09-19-1859-edt--2259-utc).

**Update, 19:45 EDT: validation start 3 of 3 is done, three of three passed, and both launchers have
been edited.** The container again swapped nothing at all, the host swapped 275 MB against 293 and
288, there were no out-of-memory kills, the service came up ready, 12 of 12 exact at 89.84 tokens a
second, and no fault lines. The working-set figure came back a third time within a hundredth of a
percent of the other two -- 8.94 GB -- so the roughly 3 GB of room to spare under the 12 GB ceiling
is settled, not a reading. The weight load was the fastest of all four starts at 8.21 seconds, which
puts to rest the worry that dropping file cache instead of swapping would cost I/O. `serve.py` in
both the two-card and the one-card package now ships `--memory-swap 12g`, so a normal start no longer
needs the helper armed beside it. See
[Validation start 3](#validation-start-3-of-3-2026-09-19-1945-edt--2345-utc) and, for what the edit
costs in pinned evidence and what GPU work is still owed,
[the no-swap launcher change](2026-09-19-noswap-launcher-change.md).

**Update, 20:14 EDT: the first start made by the edited launcher itself confirms all of it.** The
two-card acceptance session ran on `serve.py`'s own `--memory-swap 12g` with no helper armed beside
it, and the container again swapped **nothing at all**, with **no out-of-memory kills** and a working
set of **8.99 GB** -- a fourth reading inside 0.6 % of the three taken through the helper, leaving
**3.01 GB to spare** under the 12 GB ceiling. Twelve of twelve prompts exact, no fault lines. One
number did move: the *host* swapped 1,106 MB during the session against 275-293 MB on the three
validation starts. None of it came from the container, and all of it happened before the server was
ready, while a 29 GB model verify and a source download were competing for page cache in the same
window. See [Confirmation from the launcher's own
bytes](#confirmation-from-the-launchers-own-bytes-2026-09-19-2008-2014-edt).

---

## What was run

| Time (EDT) | [UTC] | Event |
| --- | --- | --- |
| 17:17 | 21:17 | Reboot, with `vm.swappiness` 60 -> 1 persisted in `/etc/sysctl.d/90-b70-swappiness.conf`. |
| 17:18:47 | 21:18:47 | One-shot user unit starts on the fresh boot. Host `pswpin`/`pswpout` both 0. Nothing else has touched the cards. |
| 17:19:48 | 21:19:48 | `scripts/measure-swap-during-start.sh` starts (sampler `t=0`, 0.5 s interval), then `experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh --only-service`. Health probe clean on both cards. |
| 17:20:05 | 21:20:05 | Container `neural-fp8-c866dbbf52f04eae85d6b76c367ac3a0` created (`t=17`). |
| 17:21:07-17:21:16 | 21:21:07-21:21:16 | **The swap burst**: 4.2 GiB out in nine seconds, at container age 62-71 s. Host `Cached` rises 2.9 -> 11.4 GiB in the same window. |
| 17:22:45 | 21:22:45 | Service ready (`t=177`, 160 s after container creation). |
| 17:22:45-17:24:10 | 21:22:45-21:24:10 | Strict suite: **12/12 against the comm-2 no-MTP reference at 90.24 tok/s**. |
| 17:24:10 | 21:24:10 | Session ends. **Zero `xe` fault lines this boot.** |

Raw receipts: `/mnt/fast-ai/bench-results/resume-20260919c/`, copied into
[`../data/2026-09-19-service-start-swap/`](../data/2026-09-19-service-start-swap/).

## The numbers, in 20-second buckets

From [`swap-during-start.csv`](../data/2026-09-19-service-start-swap/swap-during-start.csv) (508
samples at 0.5 s over 262 s). `t=0` is 17:19:48 EDT / 21:19:48Z; the container appears at `t=17`;
ready at `t=177`. "Out" and "in" are `pswpout_d`/`pswpin_d` summed over the bucket (host-wide
`/proc/vmstat`); MemAvailable and Cached are the last sample in the bucket; PSI is the maximum
`some avg10` in the bucket.

| Window (s) | Swapped out | Swapped in | Major faults | MemAvailable (end) | Cached (end) | PSI some avg10 (max) | Phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0-20 | 0 MiB | 0 MiB | 9,999 | 12.96 GiB | 2.80 GiB | 0.00 | health probes; container created at t=17 |
| 20-40 | 0 MiB | 0 MiB | 2,697 | 12.08 GiB | 3.37 GiB | 0.00 | container start, image and Python import |
| 40-60 | 0 MiB | 0 MiB | 1,334 | 11.64 GiB | 3.52 GiB | 0.00 | engine init |
| 60-80 | 10 MiB | 0 MiB | 8,454 | 7.25 GiB | 7.13 GiB | 0.72 | **weight load begins** (safetensors reads start ~t=76) |
| **80-100** | **4,484 MiB** | 1,011 MiB | 137,102 | 9.14 GiB | 8.97 GiB | **3.85** | **the burst**: cgroup at its ceiling |
| 100-120 | 0 MiB | 21 MiB | 4,348 | 8.80 GiB | 8.70 GiB | 1.36 | target weights resident |
| 120-140 | 3 MiB | 52 MiB | 10,275 | 8.63 GiB | 8.59 GiB | 0.18 | drafter load |
| 140-160 | 17 MiB | 164 MiB | 26,543 | 6.67 GiB | 6.56 GiB | 0.02 | compile / warmup |
| 160-180 | 0 MiB | **1,120 MiB** | 134,288 | 4.89 GiB | 4.79 GiB | 0.00 | swap-in as the server touches its own pages again; **ready at t=177** |
| 180-200 | 0 MiB | 9 MiB | 2,077 | 4.89 GiB | 4.71 GiB | 0.00 | strict suite |
| 200-220 | 0 MiB | 5 MiB | 1,140 | 4.89 GiB | 4.71 GiB | 0.00 | strict suite |
| 220-240 | 0 MiB | 3 MiB | 660 | 4.89 GiB | 4.71 GiB | 0.00 | strict suite |
| 240-260 | 0 MiB | 11 MiB | 2,922 | 4.90 GiB | 4.77 GiB | 0.00 | strict suite |
| 260-280 | 0 MiB | 1 MiB | 261 | 4.89 GiB | 4.78 GiB | 0.00 | end of window |
| **Total** | **4,514 MiB (4.41 GiB)** | **2,397 MiB (2.34 GiB)** | 341,972 | -- | -- | -- | |

Inside the burst, at 0.5 s resolution: first swap-out at `t=79.0`, peak **1,178 MiB in one 0.5 s
sample** at `t=82.0`, essentially over by `t=88.0`. Host `Cached` peaks at **11.39 GiB at t=82** having
been 3.5 GiB at `t=76`. Minimum MemAvailable over the whole window is **4.87 GiB at t=180** -- after
the burst, not during it. Swap used peaked at 4.63 GiB host-wide (`SwapFree` 36.00 -> 31.37 GiB).

Three things in that table matter:

1. **The swap-out is not driven by memory scarcity.** MemAvailable was 7.0-7.3 GiB when the burst
   started and *rose* to 11.5 GiB while it ran. A host under 15 GiB with 7 GiB available and
   `vm.swappiness=1` has no reason to evict 4.2 GiB of anonymous memory.
2. **It tracks the page cache, not free memory.** `Cached` climbs from 3.5 to 11.4 GiB in exactly the
   seconds the swap-out happens. Something is making room for file pages by evicting anonymous ones.
3. **2.3 GiB comes straight back in** over the next 100 seconds, including 1.1 GiB in the 20 seconds
   before ready. The pages were still live; they were evicted early and faulted back.

## The container's own counters say who did it

Read live and read-only from the running service (nothing was started, stopped or updated):
`docker inspect` plus `cat` of `/sys/fs/cgroup/system.slice/docker-<id>.scope/*`. Full capture:
[`cgroup-counters.txt`](../data/2026-09-19-service-start-swap/cgroup-counters.txt).

| Counter | Value | Reading |
| --- | --- | --- |
| `HostConfig.Memory` | 12,884,901,888 (12 GiB) | the launcher's `--memory 12g` |
| `HostConfig.MemorySwap` | 17,179,869,184 (16 GiB) | the launcher's `--memory-swap 16g` |
| `memory.max` | 12,884,901,888 | 12 GiB, as configured |
| `memory.swap.max` | 4,294,967,296 | **4 GiB** = `memory-swap` minus `memory`; this is the swap allowance |
| `memory.peak` | 12,884,901,888 | **exactly `memory.max`** -- the cgroup ran flat against its ceiling |
| `memory.swap.peak` | 4,294,967,296 | **exactly `memory.swap.max`** -- it used its entire swap allowance |
| `memory.events` `max` | **2,005** | the cgroup hit `memory.max` and reclaimed two thousand times |
| `memory.events` `oom` / `oom_kill` | **0 / 0** | it never actually ran out; reclaim always found something |
| `memory.stat` `pswpout` | **1,033,915 pages = 3.94 GiB** | **89 % of the host's entire 4.41 GiB** came from this container |
| `memory.stat` `pswpin` | 547,978 pages = 2.09 GiB | 89 % of the host's 2.34 GiB swap-in, likewise |
| `memory.stat` `pgscan_direct` | 2,173,237 pages | direct reclaim *inside the cgroup* -- allocation stalls, which is what PSI 3.9 was |
| `memory.stat` `anon` | 7,422,877,696 (6.91 GiB) | the server's real working set |
| `memory.stat` `file` | ~4 GiB (3.6-4.3 GiB, drifts) | leftover weight-file page cache, all clean |

The arithmetic closes: anon 6.9 GiB + file ~4 GiB + slab 0.1 GiB ~= 11-12 GiB, pinned against a 12 GiB
ceiling, with a 4 GiB swap allowance that was used to the last byte.

## The mechanism

1. The two-card launcher runs the server with `--memory 12g --memory-swap 16g`
   ([`serve.py:222`](../../../packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py)). Docker's
   `--memory-swap` is *memory plus swap*, so this is "12 GiB of RAM and 4 GiB of swap". In cgroup v2
   that becomes `memory.max=12G`, `memory.swap.max=4G`.
2. The model is ~29 GB of safetensors on `/mnt/fast-ai`, bind-mounted into the container and read with
   `mmap`. Every page read is charged to **the container's** memory cgroup as file cache.
3. Within seconds the container's anon (6.9 GiB of loaded tensors, workers, runtime) plus the growing
   file cache exceeds 12 GiB. The cgroup enters reclaim -- 2,005 `max` events, 2.17 M pages of *direct*
   reclaim.
4. Cgroup reclaim will evict clean file pages **or** swap anonymous pages, and it balances the two
   using `memory.swap.max` and the swappiness that applies to the cgroup. With a 4 GiB swap allowance
   available it swaps, and it keeps swapping until the allowance is exhausted -- which the counters
   show it did, to the byte.
5. `vm.swappiness=1` does not stop this. It biases global reclaim; a cgroup at `memory.max` with
   swap headroom reclaims within itself regardless. **This is why the reboot at `swappiness=1` still
   produced a 4.2 GiB burst.**
6. The swapped-out pages are the server's own anonymous memory -- including, during a load, the host
   staging buffers that the card's copy engine reads through userptr mappings. That is the link to the
   faults.

### Why this is the same mistake as the MiniMax cap

The [September 17 oomd incident](2026-09-18-host-oomd-incident.md) set
`--property=MemoryMax=4G` on a runner whose real working set was ~25 GiB, as a "tripwire". A cgroup
far below its working set does not trip; it thrashes in reclaim, and sustained reclaim pressure is
exactly what `systemd-oomd` kills on. Here the cap is 12 GiB against a working set of 6.9 GiB anon
plus an unbounded streaming read, and the result is the same class of behaviour: continuous reclaim
at the ceiling, with swap as the release valve. In both cases the number was chosen without measuring
what the job touches.

## What is proven and what is not

**Proven by this measurement:**

* The two-card service start swaps 4.4 GiB out, 89 % of it from inside the container, and it does so
  at `vm.swappiness=1` with 7+ GiB MemAvailable.
* The cause is the container's own `--memory 12g --memory-swap 16g`: `memory.peak` equals
  `memory.max`, `memory.swap.peak` equals `memory.swap.max`, and `memory.events max` is 2,005 with
  zero OOM kills.
* Host `vm.swappiness` does not control it. Turning it from 60 to 1 did not stop the burst.
* Both launchers hardcode the same pair of flags
  ([tp2 `serve.py:222`](../../../packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py),
  [tp1 `serve.py:221`](../../../packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py)), so every profile on
  this host has it.

**Not proven:**

* **That this causes the copy-engine faults.** This start swapped 4.4 GiB during the weight load and
  did not fault. The swap burst is necessary for the hypothesis, not sufficient for it; nothing here
  shows a swapped page and a faulting copy engine touching the same address. A defect on
  `0000:03:00.0` still fits every row of the fault history.
* **That removing the swap allowance removes the faults.** It removes the swapping of *anonymous*
  pages at the ceiling. Clean file pages will still be dropped and re-read, and page migration
  (compaction, THP) is a separate mechanism this change does not touch.
* **That 12 GiB is the right ceiling.** We have not measured what the load would use uncapped; the
  container may simply be being asked to do a 29 GB streaming read in a 12 GiB box.

**What this does establish for certain:** the swap activity during starts was being read as a host
property for four fault notes running. It is a container configuration we wrote ourselves.

## The fix

Set the container's swap allowance to zero by making `--memory-swap` equal `--memory`:

```
'--memory', '12g', '--memory-swap', '12g',
```

Docker semantics: `--memory-swap` equal to `--memory` means **no swap is available to the container**;
in cgroup v2 it sets `memory.swap.max=0`. At the ceiling, cgroup reclaim then has only one option --
drop clean file pages, which are the weight file's page cache and are re-readable from disk at NVMe
speed. Nothing the server is actively using goes to disk.

Headroom: anon is 6.91 GiB against a 12 GiB cap, so **about 5 GiB of slack** before the cgroup would
have to choose between OOM and nothing. The file cache is fully reclaimable (`file_dirty 0` --
everything is read-only mmap of the model and of read-only bind mounts), so there is always something
to reclaim.

> **Corrected 2026-09-19 18:27 by validation start 1: the real figure is anon 8.95 GiB and ~3 GiB of
> slack.** The 6.91 GiB reading was taken while 2-3 GiB of the container's anonymous memory was
> sitting in swap and therefore not counted. See
> [Validation start 1](#validation-start-1-of-3-2026-09-19-1823-edt--2223-utc).

Expected cost: the weight load may be slower, because pages dropped early are re-read instead of the
load proceeding at the cost of swapping something else out. This start took 160 s from container
creation to ready with the swapping; that is the number to beat or accept.

## Validation plan (before any `serve.py` edit)

`serve.py` is byte-pinned by the published evidence packets -- editing it broke site CI the last time
(see the "evidence pins" memory and the guides workflow). So the change is validated on the running
container first, and only then written into the launchers.

1. **At the next service start that was going to happen anyway** -- not a start made for this test; the
   service is up and must not be restarted for a measurement -- run
   [`scripts/apply-container-noswap.sh --name-prefix neural-fp8`](../../../scripts/apply-container-noswap.sh)
   in the background just before the start, with
   [`scripts/measure-swap-during-start.sh`](../../../scripts/measure-swap-during-start.sh) beside it.
   The helper waits for a *new* container with that name prefix and immediately runs
   `docker update --memory 12g --memory-swap 12g <name>`. There is a wide window: the container appears
   ~0 s into the start and the weight-file reads do not begin until ~55-60 s later (`t=17` and `t=76`
   in this run). The helper refuses, non-zero, if the container it finds is already above 6 GiB of
   `memory.current`, which means the load has begun and the measurement would be worthless.
2. **Success criteria per start:** container `memory.stat pswpout` ~0 (a few hundred pages of
   pre-update activity is fine); `memory.events max` still non-zero (the ceiling is still being hit --
   that is expected and is the point: it now reclaims file cache); `memory.events oom_kill` **0**;
   service reaches ready; strict suite **12/12**; no `xe` fault lines.
3. **Repeat over at least three starts.** One clean start proves nothing -- 2026-09-19 14:20 was a
   clean start in the exact order that faulted an hour later.
4. **Then edit both launchers** (`--memory-swap 12g` in the tp2 and tp1 `docker_argv`), regenerate the
   pinned packets by the repo's process, run `guides.yml` locally in full, and re-run acceptance for
   the affected packages.
5. **Keep the sampler in the loop afterwards.** The fault question is not closed by this change; every
   start should still be recorded so the next fault, if it comes, has a swap trace beside it.

## Validation start 1 of 3 (2026-09-19 18:23 EDT / 22:23 UTC)

The first of the three. A batched window (`/mnt/fast-ai/bench-results/batch2-session-20260919.sh`,
`RESUME_ROOT /mnt/fast-ai/bench-results/resume-20260919e`) ran a MiniMax-H3 block first and then put
the two-card service back, which is exactly the "start that was going to happen anyway" the plan
asked for: **no restart was made for this measurement.** Same boot as the 17:20 start, so the two
rows below are the same machine in the same state with one setting changed.

The helper caught the container in the window it was designed for:
`neural-fp8-1390b553d19e450d8110ac7f631f57d6` found **17 s** into the start at `memory.current`
**6,209,536 bytes (6 MB)** -- far under the 6 GiB refusal threshold -- and
`docker update --memory 12g --memory-swap 12g` took `memory.swap.max` from 4 GiB to **0** in the same
second (`noswap-helper.log`).

### Side by side: the 17:20 start (swap allowed) against the 18:23 start (no swap)

| | 17:20 EDT, `memory.swap.max` 4 GiB | 18:23 EDT, `memory.swap.max` **0** |
| --- | ---: | ---: |
| Container `pswpout` | 1,033,915 pages = **3.94 GiB** | **0** |
| `memory.swap.peak` | 4 GiB (= `memory.swap.max`, exactly) | **0** |
| Host-wide swap-out during the start | **4,514 MiB** | **293 MiB** |
| Host-wide swap-in during the start | (not summed) | 299 MiB |
| `memory.events max` | 2,005 | **12,646** |
| `memory.events oom` / `oom_kill` | 0 / 0 | **0 / 0** |
| `memory.peak` | 12 GiB (= `memory.max`) | 12.0 GiB (= `memory.max`) |
| `anon` | 7,422,877,696 B = 6.91 GiB | **9,608,658,944 B = 8.95 GiB** |
| `file` | 3.88 GB | 2.70 GB |
| `pgscan_direct` | 2.17 M pages | **5.70 M pages** |
| Minimum host MemAvailable | 4.87 GiB | **3.0 GiB** |
| Peak PSI memory `some avg10` | 3.9 | 4.0 |
| `Loading weights took` (TP0, first shard set) | 8.53 s | **8.44 s** |
| `Model loading took` | 11.99 s | 11.34 s |
| `init engine` (profile + KV + warmup) | 73.69 s | 72.94 s |
| Service ready | 21:22:45Z | 22:26:22Z (150 s after the start command) |
| Strict suite vs the comm-2 no-MTP reference | 12/12, 90.24 tok/s | **12/12, 89.9 tok/s** |
| `xe` fault lines | 0 | **0** |

Every success criterion in the plan is met: container `pswpout` **0** (not "a few hundred pages" --
actually zero), `memory.events max` still non-zero and in fact **6.3x higher** at 12,646, `oom_kill`
**0**, ready, strict **12/12**, no fault lines. The sampler took 489 samples over 252 s
(`swap-during-start.csv`).

**The mechanism behaved exactly as predicted.** `memory.events max` going *up* 6.3x and
`pgscan_direct` going up 2.6x is the point, not a problem: the cgroup still hits its ceiling
constantly while reading a 29 GB file, and with no swap to fall back on it must reclaim clean file
pages every time. The cost of that -- re-reading dropped pages from NVMe -- did not show up:
**the weight load was 0.09 s faster, not slower**, and ready came 10 s sooner than the 160 s of the
swapping start. `/mnt/fast-ai` is fast enough that this trade is free.

**And it is not just the container that stopped swapping.** Host-wide swap-out during the start fell
from 4,514 MiB to 293 MiB -- a 15x drop -- which is more than the container's own 3.94 GiB share.
Removing the container's reclaim pressure also stopped the host reclaiming elsewhere on its behalf.
The 293 MiB that remains is roughly matched by 299 MiB swapped back **in**, i.e. ordinary
pre-existing idle pages moving around, not a burst.

### The headroom figure was wrong, and the corrected number is ~3 GiB

The plan's "about 5 GiB of slack" came from reading `anon` **6.91 GiB** off the swapping start. That
reading was low, and for a reason that is obvious once the swap is gone: **2-3 GiB of the container's
anonymous memory was sitting in swap at the moment it was read**, so it was not counted in `anon`.
With `memory.swap.max=0` nothing can leave, and the honest figure is:

> **`anon` 9,608,658,944 bytes = 8.95 GiB against a 12 GiB cap. Headroom is ~3 GiB, not ~5 GiB.**

This does not change the verdict on the fix -- 3 GiB of slack on a workload whose anonymous
footprint is stable after load is still comfortable, `file_dirty` is still 0, and `oom_kill` stayed
0 through a start that scanned 5.7 M pages directly. It does change the **margin of safety**, and
every downstream estimate built on 6.91 GiB has to be redone. The remaining `file` of 2.70 GB is the
buffer that absorbs the next spike, and it is fully reclaimable.

### Consequence for the one-card profiles: the estimate is now tighter, and it must be measured

The tp1 launcher carries the same `--memory 12g --memory-swap 16g`
([`packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py:221`](../../../packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py))
and its `BASE_ENV` sets `B70_CPU_EMBED=1`, which moves **2.368 GiB** of input-embedding table
permanently into host memory. That is anon, it is read on every decode step, and it can never be
reclaimed to a file.

Redoing the arithmetic on the corrected base:

| | Old estimate (from anon 6.91 GiB) | Corrected (from anon **8.95 GiB**) |
| --- | ---: | ---: |
| Two-card anon, measured | 6.91 GiB | **8.95 GiB** |
| Drop one worker | -2.5 to -3 GiB | -2.5 to -3 GiB |
| Add the host embedding table | +2.368 GiB | +2.368 GiB |
| **One-card anon, estimated** | 6.5-7.5 GiB | **8.3-8.8 GiB** |
| **Headroom under the 12 GiB cap** | 4.5-5.5 GiB | **3.2-3.7 GiB** |

**This remains an estimate from arithmetic, and it is now close enough to the cap that arithmetic is
not good enough.** The one-card profiles must have `memory.stat anon` read off a live container --
after the weight load and after at least one decode, so the embedding table is resident and touched
-- **before** they inherit `--memory-swap 12g`. The `no-quantization` profile additionally builds an
FP16 draft-head copy (`B70_DRAFT_FP16_SHORTLIST`) whose residency has never been checked, so it needs
its own reading on top. A one-card container that OOM-kills at load is a dead server, and the whole
safety story for this change is the margin.

The supporting evidence that the one-card profiles hit the same ceiling (2.2-2.7 GiB swapped per
start on 2026-09-17) is unchanged and is in the Risks section below.

### What is left

1. **Two more validation starts**, same conditions, same helper, same criteria -- and they must be
   starts that were going to happen anyway, not restarts made to test this. Start 1 is on the books;
   one clean start still proves nothing on its own (2026-09-19 14:20 was a clean start in exactly the
   order that faulted an hour later).
2. **The setting is per-container and does not survive a restart.** `docker update` changed this
   container only; every new container comes back at `--memory-swap 16g` from `serve.py`. Until the
   launchers are edited, `scripts/apply-container-noswap.sh` must be armed beside **every** start, and
   a start that forgets it is a start that swaps.
3. **Then edit both launchers** (`--memory-swap 12g` in the tp2 and tp1 `docker_argv`), regenerate the
   pinned evidence packets by the repo's process, run `guides.yml` locally in full, and re-run
   acceptance for the affected packages -- with the one-card `anon` measurement from the section
   above done first, because the tp1 edit depends on it.
4. **Keep the sampler running** after the launcher edit, so the next fault, if it comes, has a swap
   trace beside it.

Receipts: [`../data/2026-09-19-service-start-noswap-1/`](../data/2026-09-19-service-start-noswap-1/)
-- `noswap-helper.log`, `cgroup-after-start.txt`, `swap-during-start.csv`, `session.log`. Raw root
`/mnt/fast-ai/bench-results/resume-20260919e/`.

## Validation start 2 of 3 (2026-09-19 18:59 EDT / 22:59 UTC)

The second of the three, and again a start that was going to happen anyway: batch window 3
(`/mnt/fast-ai/bench-results/batch3-session-20260919.sh`, `RESUME_ROOT
/mnt/fast-ai/bench-results/resume-20260919f`) ran the [MiniMax-H3 canvas
ladder](../../minimax-h3-b70/notes/2026-09-19-first-light.md#canvas-ladder-2246-2259-utc) first and
then put the two-card service back. **Nothing was restarted for this measurement.** Same boot as the
17:20 start and as start 1, so all three rows below are the same machine in the same state.

The helper caught the new container `neural-fp8-42a89cfc17924bbd8d59d68dfb3f0cd4`
(`43c88dbb33e9d382a3923a292fbc5801bde2c271f211c24e18d4a1b81d5ed20f`) **18 s** into the start at
`memory.current` **119,361,536 bytes (119 MB)** -- well under the 6 GiB refusal threshold, though
19x the 6 MB of start 1, which is the honest reminder that the window is a race and the margin is
what makes it safe. `docker update --memory 12g --memory-swap 12g` took `memory.swap.max` from 4 GiB
to **0** in the same second.

### Start 2 beside start 1 and the swapping baseline

| | 17:20, swap allowed | 18:23, start 1 | **18:59, start 2** |
| --- | ---: | ---: | ---: |
| Container `pswpout` | 1,033,915 pages = 3.94 GiB | 0 | **0** |
| `memory.swap.peak` | 4 GiB (= the cap) | 0 | **0** |
| Host-wide swap-out during the start | 4,514 MiB | 293 MiB | **288 MiB** |
| Host-wide swap-in during the start | (not summed) | 299 MiB | 281 MiB |
| `memory.events max` | 2,005 | 12,646 | **12,964** |
| `memory.events oom` / `oom_kill` | 0 / 0 | 0 / 0 | **0 / 0** |
| `memory.peak` | 12 GiB (= `memory.max`) | 12.0 GiB | 12.0 GiB |
| `anon` | 7,422,877,696 B = 6.91 GiB | 9,608,658,944 B = 8.95 GiB | **9,600,892,928 B = 8.94 GiB** |
| `file` | 3.88 GB | 2.70 GB | 2.74 GB |
| `pgscan_direct` | 2.17 M pages | 5.70 M pages | **5.79 M pages** |
| Minimum host MemAvailable | 4.87 GiB | 3.0 GiB | **3.0 GiB** |
| Peak PSI memory `some avg10` | 3.9 | 4.0 | 3.5 |
| `Loading weights took` (TP0, first shard set) | 8.53 s | 8.44 s | **8.44 s** |
| `Model loading took` | 11.99 s | 11.34 s | 11.22 s |
| `init engine` (profile + KV + warmup) | 73.69 s | 72.94 s | 75.16 s (compile 66.41 s) |
| Service ready | 21:22:45Z | 22:26:22Z, 150 s after the command | 23:02:00Z, **160 s** after the command |
| Strict suite vs the comm-2 no-MTP reference | 12/12, 90.24 tok/s | 12/12, 89.9 tok/s | **12/12, 89.79 tok/s** |
| `xe` fault lines | 0 | 0 | **0** |

Every success criterion is met again: container `pswpout` **0**, `memory.events max` non-zero at
**12,964**, `oom_kill` **0**, ready, strict **12/12**, no fault lines. The sampler took 509 samples
over 263 s.

**The point of a second start is reproducibility, and it reproduced.** The figure that mattered most
from start 1 -- the corrected working-set size -- came back at `anon` **9,600,892,928 bytes**, which
is **7.8 MB (0.08 %)** away from start 1's 9,608,658,944. A workload whose anonymous footprint lands
within a tenth of a percent across two independent starts is a workload whose **~3 GiB of headroom
under the 12 GiB cap is a real, stable number**, not one reading. `pgscan_direct` (5.79 M against
5.70 M) and `memory.events max` (12,964 against 12,646) repeated within 2 %, so the reclaim behaviour
is stable too.

**Host-wide swap-out was 288 MiB**, essentially identical to start 1's 293 MiB and still a 15x drop
from the swapping baseline's 4,514 MiB. As before it is roughly matched by 281 MiB swapped back
**in**, i.e. idle pages moving around rather than a burst; the largest single 0.5 s sample was 69
MiB. Minimum MemAvailable was again **3.0 GiB**.

**The two figures that moved are both noise, and both are worth naming rather than hiding.** Ready
came **10 s later** (160 s against 150), entirely inside `init engine`, which was 2.2 s longer with
66.41 s of it in torch.compile -- the weight load itself was **identical to the hundredth of a
second** at 8.44 s, so this is compile-time variance, not the no-swap change costing I/O. And the
strict suite came in at **89.79 tok/s against 89.9** -- 0.1 %, well inside run-to-run spread, with
the comparison itself still **12/12 exact**. Neither is a regression; both are recorded so the third
start has something to be compared against.

### What is left after start 2

1. **One more validation start**, same conditions, same helper, same criteria, and again one that was
   going to happen anyway. Two clean starts are better than one, and they are still not three.
2. **The setting is still per-container.** This start needed the helper exactly as much as start 1
   did, and the next container will come back at `--memory-swap 16g`.
   `scripts/apply-container-noswap.sh` stays armed beside every start until the launchers are edited.
3. **Then edit both launchers** (`--memory-swap 12g` in the tp2 and tp1 `docker_argv`), regenerate the
   pinned evidence packets by the repo's process, run `guides.yml` locally in full, and re-run
   acceptance -- with the **one-card `anon` measurement done first**, because the tp1 edit depends on
   it and the corrected two-card base leaves that profile an estimated 3.2-3.7 GiB of headroom.
4. **Keep the sampler running** afterwards, so the next fault, if it comes, has a swap trace beside it.

Receipts: [`../data/2026-09-19-service-start-noswap-2/`](../data/2026-09-19-service-start-noswap-2/)
-- `noswap-helper.log`, `cgroup-after-start.txt`, `swap-during-start.csv`, `session.log`. Raw root
`/mnt/fast-ai/bench-results/resume-20260919f/`.

## Validation start 3 of 3 (2026-09-19 19:45 EDT / 23:45 UTC)

The last of the three, and again a start that was going to happen anyway: the `--only-service` resume
(`RESUME_ROOT /mnt/fast-ai/bench-results/resume-20260919g`, git `b68ecf0c1`) putting the two-card
service back on 18124. **Nothing was restarted for this measurement.** Same boot as the 17:20
baseline and as starts 1 and 2, so all four columns below are the same machine in the same state.

The helper caught `neural-fp8-277ee9175b5c4b32a97a9a35a1d4241f`
(`11d63815396009fa3ecfc62857705323509f263595188abda1e684b8d9bf8c5b`) **17 s** into the start at
`memory.current` **20,516,864 bytes (20 MB)** -- between start 1's 6 MB and start 2's 119 MB, all
three far under the 6 GiB refusal threshold -- and `docker update --memory 12g --memory-swap 12g`
took `memory.swap.max` from 4 GiB to **0** in the same second (`noswap-helper.log`).

### All four starts side by side

| | 17:20, swap allowed | 18:23, start 1 | 18:59, start 2 | **19:45, start 3** |
| --- | ---: | ---: | ---: | ---: |
| Container `pswpout` | 1,033,915 pages = 3.94 GiB | 0 | 0 | **0** |
| `memory.swap.peak` | 4 GiB (= the cap) | 0 | 0 | **0** |
| Host-wide swap-out during the start | 4,514 MiB | 293 MiB | 288 MiB | **275 MiB** |
| Host-wide swap-in during the start | (not summed) | 299 MiB | 281 MiB | 257 MiB |
| `memory.events max` | 2,005 | 12,646 | 12,964 | **16,117** |
| `memory.events oom` / `oom_kill` | 0 / 0 | 0 / 0 | 0 / 0 | **0 / 0** |
| `memory.peak` | 12 GiB (= `memory.max`) | 12.0 GiB | 12.0 GiB | 12.0 GiB |
| `anon` | 7,422,877,696 B = 6.91 GiB | 9,608,658,944 B = 8.95 GiB | 9,600,892,928 B = 8.94 GiB | **9,602,744,320 B = 8.94 GiB** |
| `file` | 3.88 GB | 2.70 GB | 2.74 GB | 2.88 GB |
| `pgscan_direct` | 2.17 M pages | 5.70 M pages | 5.79 M pages | **6.82 M pages** |
| Minimum host MemAvailable | 4.87 GiB | 3.0 GiB | 3.0 GiB | **3.07 GiB** |
| Peak PSI memory `some avg10` | 3.9 | 4.0 | 3.5 | **2.73** |
| `Loading weights took` (TP0, first shard set) | 8.53 s | 8.44 s | 8.44 s | **8.21 s** |
| `Model loading took` | 11.99 s | 11.34 s | 11.22 s | 10.94 s |
| `init engine` (profile + KV + warmup) | 73.69 s | 72.94 s | 75.16 s | 73.18 s (compile 64.41 s) |
| Service ready | 21:22:45Z | 22:26:22Z, 150 s after the command | 23:02:00Z, 160 s | 23:47:58Z, **150 s** |
| Strict suite vs the comm-2 no-MTP reference | 12/12, 90.24 tok/s | 12/12, 89.9 tok/s | 12/12, 89.79 tok/s | **12/12, 89.84 tok/s** |
| `xe` fault lines | 0 | 0 | 0 | **0** |

Every success criterion is met for the third time: container `pswpout` **0**, `memory.events max`
non-zero at **16,117**, `oom_kill` **0**, ready, strict **12/12**, no fault lines. The sampler took
489 samples over 251 s.

**Three independent readings of the working set land inside a tenth of a percent of each other**:
9,608,658,944 / 9,600,892,928 / 9,602,744,320 bytes, a spread of 7.8 MB on 8.94 GiB. The headroom
figure this change rests on -- **about 3 GiB under the 12 GiB cap** -- is therefore a property of the
workload, not of a run. `memory.events max` rose again (16,117 against 12,964 and 12,646) and
`pgscan_direct` with it (6.82 M pages), which remains the mechanism working rather than a fault: with
no swap to fall back on, every touch of the ceiling has to reclaim clean file cache.

**And the feared cost never appeared.** The worry was that re-reading dropped pages from NVMe would
slow the weight load. Across the four starts the load went 8.53 -> 8.44 -> 8.44 -> **8.21 s**: the
three no-swap starts are all *faster* than the swapping baseline, and start 3 is the fastest of the
four. Ready came 150 s after the command, matching start 1 and 10 s quicker than start 2 (that
difference was compile-time variance both times). Peak memory pressure was also the mildest of the
four at PSI 2.73, against 3.9 on the swapping start.

**With three of three passed, both launchers were edited**: `--memory-swap 12g` in the two-card and
the one-card `docker_argv`, with the reasoning and the note reference in a comment at the call site.
What that costs in pinned evidence, what was regenerated without a GPU, and what GPU runs are still
owed is in [the no-swap launcher change](2026-09-19-noswap-launcher-change.md).

Receipts: [`../data/2026-09-19-service-start-noswap-3/`](../data/2026-09-19-service-start-noswap-3/)
-- `noswap-helper.log`, `cgroup-after-start.txt`, `swap-during-start.csv`, `session.log`, with a
`README.md` reading each one. Raw root `/mnt/fast-ai/bench-results/resume-20260919g/`.

## Confirmation from the launcher's own bytes (2026-09-19 20:08-20:14 EDT)

The three validation starts all reached `memory.swap.max=0` through
`scripts/apply-container-noswap.sh`, racing a `docker update` into a window 17-18 s wide. The
two-card acceptance session at 20:08 EDT is the first start where the setting came from `serve.py`
itself, on commit `fc48856e6`, with **no helper armed beside it at all**. That is the start that
proves the edit, rather than the mechanism the edit was modelled on.

`cgroup_memory()` read the container's counters just before the graceful stop, the way
`run-fp8-tp2-acceptance-session.py` was taught to:

| | 17:20, swap allowed | start 1 | start 2 | start 3 | **20:08, launcher** |
| --- | ---: | ---: | ---: | ---: | ---: |
| How `memory.swap.max` got to 0 | -- (4 GiB) | helper | helper | helper | **`serve.py`** |
| `memory.swap.max` / `memory.swap.peak` | 4 GiB / 4 GiB | 0 / 0 | 0 / 0 | 0 / 0 | **0 / 0** |
| Container `pswpout` / `pswpin` | 3.94 GiB / 2.09 GiB | 0 / 0 | 0 / 0 | 0 / 0 | **0 / 0** |
| `memory.events` `oom` / `oom_kill` | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | **0 / 0** |
| `memory.events` `max` | 2,005 | 12,646 | 12,964 | 16,117 | **11,198** |
| `memory.peak` | 12 GiB (= `max`) | 12.0 GiB | 12.0 GiB | 12.0 GiB | **12 GiB (= `max`)** |
| `anon` | 6.91 GiB | 8.95 GiB | 8.94 GiB | 8.94 GiB | **8.99 GiB** (9,654,628,352 B) |
| Headroom under the cap | -- | ~3.0 GiB | ~3.0 GiB | ~3.0 GiB | **3.01 GiB** (3,230,273,536 B) |
| `file` / `file_dirty` | 3.88 GB / 0 | 2.70 GB / 0 | 2.74 GB / 0 | 2.88 GB / 0 | **2.42 GiB / 0** |
| `pgscan_direct` | 2.17 M pages | 5.70 M | 5.79 M | 6.82 M | **4.84 M pages** |
| Host-wide swap-out over the window | 4,514 MiB | 293 MiB | 288 MiB | 275 MiB | **1,106 MiB** |
| Strict suite | 12/12, 90.24 tok/s | 12/12, 89.9 | 12/12, 89.79 | 12/12, 89.84 | **12/12, 89.87 tok/s** |
| `xe` fault lines | 0 | 0 | 0 | 0 | **0** |

**Every success criterion is met a fourth time, and this time by the shipped code.** Container
`pswpout` 0, `memory.events max` non-zero, `oom_kill` 0, ready, strict 12/12, no fault lines. Four
independent readings of the working set -- 8.95 / 8.94 / 8.94 / **8.99 GiB** -- span 0.6 %, and the
~3 GiB of headroom the whole change rests on is confirmed on a container nobody reconfigured after
the fact. `memory.events max` of 11,198 is the lowest of the four no-swap starts and `pgscan_direct`
the lowest too, which fits: this container ran 6 minutes rather than a resume's couple of minutes,
but the host had already read most of the model through the verify step, so there was less to fault
in.

**The host swapped 1,106 MiB, and that is the one number to keep an eye on.** It is four times the
275-293 MiB of the three validation starts, and the obvious question is whether removing the
container's swap allowance has merely pushed the reclaim onto the host. The sampler says not:

* **The container's own `pswpout` is 0.** Not one of those pages was the server's.
* **All 66 samples with swap-out fall between 20:09:41 and 20:12:39** -- the codeload download, the
  29 GB model verify and the weight load. The server was ready at 20:12:39 and the host swapped
  **nothing at all** through the strict suite, the six practical requests and the stop.
* Peak **630 MiB in a single 0.5 s sample at 20:11:10**, 196 MiB in the next; over by 20:11:16.
* Peak `Cached` **10.48 GiB**, minimum `MemAvailable` **3.01 GiB**, peak PSI memory `some avg10`
  **4.04** -- the same shape as the validation starts, at a larger scale.

The difference against starts 1-3 is what else was in the window. Those were quiet resumes that put
an already-verified service back. This session downloaded the repository anonymously from codeload
and ran a full hash verify over 29 GB of safetensors *before* the container started, so the host page
cache was already large when the weight load added to it, and the kernel evicted other resident
anonymous pages to make room. That is ordinary host reclaim under a large sequential read, not the
mechanism this note is about -- the mechanism is a cgroup at `memory.max` with a swap allowance, and
this container had none and used none. **It is recorded rather than dismissed** because the fault
hypothesis is about pages the card's copy engine reads through userptr mappings, and those pages are
the container's: they did not move. The next session should be sampled the same way, and a host
swap-out burst that lands *during* serving rather than during the load would be a new finding.

Receipts:
[`../data/2026-09-19-fp8-tp2-acceptance-noswap-attempt/`](../data/2026-09-19-fp8-tp2-acceptance-noswap-attempt/)
-- `cgroup-memory.json`, `swap-tp2-acceptance.csv`, `health-result.json`, `strict-comparison.json`
and the session receipts, with a `README.md` reading each one. Raw root
`/mnt/fast-ai/bench-results/fp8-tp2-acceptance-noswap-20260919/`. **That session was an acceptance
attempt and it did not produce a packet** -- for why, and for what is still owed, see
[the no-swap launcher change](2026-09-19-noswap-launcher-change.md).

## Risks

**1. Cgroup OOM kill.** With `memory.swap.max=0`, a cgroup whose *anonymous* memory alone exceeds
`memory.max` has nothing left to reclaim and the kernel OOM-kills inside the container. Today's margin
is comfortable -- anon 6.91 GiB against 12 GiB (**corrected by validation start 1 to 8.95 GiB against
12 GiB, i.e. ~3 GiB rather than ~5**) -- but the margin is the whole safety story, so:

* Check `memory.events` `oom_kill` after every validation start; it must stay **0**. `max` going up is
  fine and expected.
* A profile that raises resident host memory (longer context does not, but a host-resident tensor
  does) must be re-measured before it inherits the change.
* If a start ever OOM-kills, the reversal is `docker update --memory-swap 16g <name>` on a running
  container, or reverting the one word in `serve.py`. The failure mode is a dead server at load time,
  not a corrupted one -- unlike the MiniMax cap, it cannot reach outside the container, because the
  kill happens inside the cgroup rather than through host pressure and `systemd-oomd`.

**2. The one-card profiles carry more anonymous memory.** The tp1 launcher uses the *same*
`--memory 12g --memory-swap 16g`
([`serve.py:221`](../../../packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py)) and its
`BASE_ENV` sets `B70_CPU_EMBED=1`, which moves the input embedding table permanently into **host**
memory: the overlay logs `b70_cpu_embed: 2.368 GiB of input embeddings now on host memory`
(`/mnt/fast-ai/bench-results/fp8-ckpt2-20260917/*/state.json`). That 2.368 GiB is anon, it is read on
every decode step, and it can never be reclaimed to a file.

Estimate for a one-card container, from the two-card figure of 6.91 GiB anon across two workers plus
the API server and EngineCore: dropping one worker saves roughly 2.5-3 GiB, adding the host embedding
table costs 2.368 GiB, so **one-card anon should land around 6.5-7.5 GiB** -- about the same as
two-card, with **4.5-5.5 GiB of headroom** under a 12 GiB cap. That is an estimate from arithmetic,
not a measurement, and the one-card profiles must have `memory.stat anon` read on a live container
before they inherit `--memory-swap 12g`.

> **Superseded by validation start 1.** On the corrected two-card base of 8.95 GiB anon, the one-card
> estimate becomes **8.3-8.8 GiB with 3.2-3.7 GiB of headroom** -- tight enough that the live
> measurement is now a requirement rather than a formality. See
> [Validation start 1](#validation-start-1-of-3-2026-09-19-1823-edt--2223-utc).

Supporting evidence that the one-card profiles hit the same ceiling today, from the September 17
campaigns' own `memory-guard.jsonl` (host `SwapFree` delta across a start):

| Run | Swap used during the start |
| --- | --- |
| `fp8-ckpt1-20260917/tp1-ckpt-mtp5` | 2.61 GiB |
| `fp8-ckpt1b-20260917/tp1-ckpt-mtp5` | 2.68 GiB |
| `fp8-ckpt2-20260917/tp1-ckpt-mtp5` | 2.68 GiB |
| `fp8-ckpt2-20260917/tp1-stock-b896` | 2.69 GiB |
| `fp8-ckpt2-20260917/tp1-mtp0-b896` | 2.16 GiB |
| `fp8-ckpt3-20260917/tp1-ckpt-32k` | 2.70 GiB |

Every one-card start on that boot swapped 2.2-2.7 GiB -- less than the two-card 4.4 GiB, same
mechanism, same 12 GiB cap. The `no-quantization` profile additionally builds an FP16 draft head copy
(`B70_DRAFT_FP16_SHORTLIST`); whether that copy is host-resident has not been checked and must be
before that profile inherits the change.

**3. A slower load.** Re-reading dropped file pages costs NVMe bandwidth. `/mnt/fast-ai` is fast and
the read is sequential, so this is expected to be small, but ready-time is part of the validation
criteria and a large regression is a reason to stop and reconsider the 12 GiB ceiling instead.

## Receipts

[`../data/2026-09-19-service-start-swap/`](../data/2026-09-19-service-start-swap/) --
`swap-during-start.csv` (the sampler), `cgroup-counters.txt` (the live read-only cgroup capture),
`session.log` and `postboot.log` (the start and its strict suite), `swap-sampler.log`. Raw root
`/mnt/fast-ai/bench-results/resume-20260919c/`.

[`../data/2026-09-19-service-start-noswap-1/`](../data/2026-09-19-service-start-noswap-1/) --
validation start 1: `noswap-helper.log` (the `docker update`, with the cgroup before and after),
`cgroup-after-start.txt`, `swap-during-start.csv`, `session.log`. Raw root
`/mnt/fast-ai/bench-results/resume-20260919e/`.

[`../data/2026-09-19-service-start-noswap-2/`](../data/2026-09-19-service-start-noswap-2/) --
validation start 2, the same four files. Raw root
`/mnt/fast-ai/bench-results/resume-20260919f/`.

[`../data/2026-09-19-service-start-noswap-3/`](../data/2026-09-19-service-start-noswap-3/) --
validation start 3, the same four files plus a `README.md`. Raw root
`/mnt/fast-ai/bench-results/resume-20260919g/`.

Related: [the no-swap launcher change](2026-09-19-noswap-launcher-change.md) (what the edit costs in
pinned evidence and the GPU acceptance runs it leaves owed), [fifth GPU fault](2026-09-19-gpu-fault-service-start.md) (the fault history and the swap
hypothesis this revises), [host oomd incident](2026-09-18-host-oomd-incident.md) (the same mistake
with a 4 GiB cap), [2026-09-15 restore fault](2026-09-15-fp8-restore-gpu-fault.md) (the first recorded
swap burst before a fault), and the `2026-09-19` rows in [DO-NOT-REPEAT.md](../DO-NOT-REPEAT.md).
