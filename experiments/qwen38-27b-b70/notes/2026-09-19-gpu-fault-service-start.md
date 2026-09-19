# Fifth GPU fault: card `03:00.0` copy engine, 70 s into a two-card service start (2026-09-19)

Date: 2026-09-19. Times below are EDT with UTC in brackets; the host is `steve-TURIND8-2L2T`
(two B70s), boot started 14:14 EDT after the user's reboot.

The batched GPU window of September 19 ran three things in one 49-minute boot: a MiniMax-H3
retry, a stock-vs-lab FP8 comparison on one card, and finally the restore of the two-card FP8
service. The restore faulted the same card and the same engine as September 16, 17 and 18. The
launcher detected it, halted, and restored nothing.

**All GPU work on this host is halted** (AGENTS.md: a fault halts the lane until the user
decides). The FP8 service is DOWN -- stopped deliberately at 14:42 for the batch, failed to come
back at 15:04. `card2` holds an uncleared device coredump. Nothing was reset, cleared, killed or
rebooted.

---

## Timeline (2026-09-19)

| Time (EDT) | Event |
| --- | --- |
| 14:14 | Host boot after the user's reboot. |
| 14:18-14:19 | `experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh`: health probe clean on both cards; the host-staged MiniMax control denoised all eight steps in **17.70 s with no fault** -- the step that faulted on 09-18 -- then ran the card out of memory in `decode.video`. |
| 14:20-14:24 | The same script's `--only-service` arm: two-card FP8 service up, strict **12/12 at 90.36 tok/s** (unit `fp8-service-20260918-resume`). Both cards healthy under a full two-card load. |
| 14:40 | Batched window opens (`/mnt/fast-ai/bench-results/batch-session-20260919.sh`, log `batch-session-20260919.log`). The service is stopped for it. |
| 14:40:55-14:42:11 | MiniMax retry (`RESUME_ROOT /mnt/fast-ai/bench-results/resume-20260919b`): denoise clean again, denoiser release now verified by `[vram]` lines (0.000 GiB allocated on **both** cards after release), video VAE loads at 9.700 GiB on `xpu:1`, decode then grows to 31.42 GiB and OOMs on a 396 MiB attention allocation. Allocator refusal, no `xe` lines. |
| 14:42:11-15:02:27 | Stock-vs-lab FP8 GDN check on **one** card (two research servers in turn, `--gpu 0`), section below. Both arms came ready, ran the strict suite and stopped cleanly. No fault. |
| 15:02:36 | The check's own restore step: health probe `rc=0`, then `systemd-run --user --unit fp8-service-20260919-batch` starts the two-card service on 18124. |
| 15:03:45 | Target weights loaded (9.39 s), `Loading drafter model...`, MTP drafter shards begin. |
| 15:03:46 [19:03:46Z] | **FAULT.** `xe 0000:03:00.0`: 45 page faults on `EngineClass: 3 bcs`, 10 `Engine memory CAT error [18]`, one bcs engine reset, `Timedout job: seqno=4294967283, guc_id=19 in python3 [13359]`, device coredump created (503,277 bytes). |
| 15:04:18 | `serve.py` writes `status: failed`, `error: New GPU fault detected. Halting this server`. |
| 15:04:26 | The campaign runner logs `GPU FAULT detected (58 journal lines); campaign halted, no restore`, copies the evidence and exits `rc=3`. No container left, no service, nothing killed. |

The fault is **70 s after the service start and ~1 s after the target weights finished loading**,
while the drafter was loading. That is the same phase as the September 15 fault ("target weights
had just loaded (8.67 s) and the drafter was loading").

## The signature

```
xe 0000:03:00.0: [drm] Tile0: GT0:
                     ASID: 126
                     Faulted Address: 0x0000800400213000
                     FaultType: 0     AccessType: 0     FaultLevel: 1
                     EngineClass: 3 bcs     EngineInstance: 0
xe 0000:03:00.0: [drm] Tile0: GT0: Fault response: Unsuccessful -EINVAL           (x45)
xe 0000:03:00.0: [drm] Tile0: GT0: Engine memory CAT error [18]: class=bcs, ...   (x10)
xe 0000:03:00.0: [drm] Tile0: GT0: Engine reset: engine_class=bcs, logical_mask: 0x1, guc_id=19, state=0x249
xe 0000:03:00.0: [drm] Tile0: GT0: Timedout job: seqno=4294967283, lrc_seqno=4294967283, guc_id=19, flags=0x20 in python3 [13359]
xe 0000:03:00.0: [drm] Xe device coredump has been created
```

* **Card:** `0000:03:00.0` = `/sys/class/drm/card2` = `renderD129` = `xpu:0`. The other B70,
  `0000:e3:00.0`, logged **nothing** in this window.
* **Engine:** `bcs`, the blitter / copy engine. Not a compute engine.
* **Access:** `FaultType: 0` (not present), `AccessType: 0` (**read** -- 09-18 was a write),
  `FaultLevel: 1`. The faulted addresses are a contiguous span,
  `0x800400204000`..`0x800400228000` (about 36 pages / 144 KiB of one mapping).
* **Process:** `python3 [13359]`, a vLLM worker.
* **No P2P.** The two-card FP8 service pins `CCL_SYCL_*_SIMPLE_THRESHOLD` at 4 GiB (oneCCL's
  simple paths) and host-waits its allreduce; it never issues a peer copy. The fault also
  happened during weight loading, before any collective ran.

## Fault history on this host

Every `xe` fault this host has logged, in order. "P2P" = a direct device-to-device copy was in
flight or in the configuration.

| Time (UTC) | Card(s) | Engine | What was running | P2P? | Host memory / swap evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-09-06 04:47 and 05:34 (as logged; timezone not recorded) | `03:00.0`, then `e3:00.0` | not recorded | INT4 lane model loads (R277, then R278); boot retired and re-run from a `@reboot` autolaunch | no | not recorded |
| 2026-09-15 02:00:38 | `e3:00.0` | bcs | Two-card FP8/MTP1 service restore, last weight shards / drafter load, 111 s in | no | MemAvailable fell to 7.7 GiB and **~4.6 GiB swapped out in five seconds** immediately before the fault |
| 2026-09-16 06:02 | `03:00.0` | bcs | Two-card FP8 service start, 111 s in, after a day of one-card work | no | not recorded |
| 2026-09-17 03:10 | `03:00.0` | bcs | Two-card depth-5 service start, 67 s in, after the one-card 24K campaign | no | not recorded |
| 2026-09-17 07:17 | **both** | ccs | First server with `CCL_SYCL_*_SIMPLE_THRESHOLD=0` (oneCCL's non-simple SYCL kernels), 2 min in | **yes** (peer memory access over PCIe) | not recorded |
| 2026-09-18 15:06 | `03:00.0` (`e3:00.0` logged a bcs CAT error 4 min later) | bcs | MiniMax-H3 first denoise step, 2.8 s in = the first `xpu:0 -> xpu:1` hand-off at the block-24 split | **yes** (direct `x.to(other_card)` blit) | MemAvailable 13.96 GiB at 11:02; no swap sample |
| 2026-09-19 19:03:46 | `03:00.0` | bcs | Two-card FP8 service start, 70 s in, drafter load, after MiniMax + two one-card research servers on the same boot | no | MemAvailable 13.9 GiB at the fault, but `/proc/vmstat` shows **3,955,161 pages (15.1 GiB) swapped OUT** and 1.69 M swapped in during this 49-minute boot, `vm.swappiness=60` |

Read the table two ways and both readings matter:

* **By cause.** Two faults (09-17 07:17, 09-18 15:06) have a direct peer-to-peer copy in them and
  are explained by it -- the 09-19 host-staged control run passed the same split that faulted on
  09-18, which is the evidence behind the "never copy card to card on this host" rule. The other
  five have **no P2P at all**, so P2P is not the general explanation.
* **By pattern.** Of the five bcs faults with no P2P, **three** (09-16, 09-17 03:10, 09-19) are a
  two-card service start that followed one-card GPU work earlier on the same boot, and a fourth
  (09-15) is a two-card restore after a one-card research load and a host OOM on the same boot.
  Every one of them faulted during the weight-load phase, on the copy engine, within 70-111 s of
  the start. The two-card service itself runs for hours without faulting once it is up.

## The swap hypothesis

**Not proven. Stated so it can be killed.**

> The model load streams weights into host staging buffers that the GPU reads through userptr
> mappings. When the kernel swaps or migrates those anonymous pages -- which it does eagerly at
> `vm.swappiness=60` while a 27 GB safetensors read is churning the page cache -- the mapping the
> copy engine holds is invalidated, and the `xe` driver answers the resulting GPU page fault with
> `-EINVAL` instead of rebinding. The copy engine then takes a CAT error and resets.

What makes it worth testing:

* The fault is always on the **copy engine**, always during the **weight load**, never during
  steady-state serving.
* `FaultType: 0` is "page not present" and the response is `-EINVAL`, i.e. the driver looked the
  address up and declined -- the shape of a revoked host mapping, not a wild pointer.
* The September 15 fault note independently recorded a **4.6 GiB swap-out burst in the five
  seconds before that fault**, and this boot swapped out 15.1 GiB in 49 minutes.
* One-card work earlier on the same boot is what fills the page cache and drives the swap-outs,
  which would explain why "one-card work first, two-card start second" is the pattern rather than
  the two-card start alone.

What makes it uncertain:

* MemAvailable was 13.9 GiB at the fault -- there was no memory emergency at that instant. The
  hypothesis needs swap *activity*, not swap *exhaustion*, to be the trigger, and nobody has
  sampled `pswpout` at second resolution across a service start.
* A card or driver/firmware defect on `03:00.0` specifically is still live: six of the seven
  faults name that card, and the card is not chosen by the workload.
* There is no upstream bug report tying `xe` userptr rebinding to swap on this driver revision;
  this is our inference from the signature, not a known defect.

**What would confirm it:** `scripts/measure-swap-during-start.sh` running beside the next
two-card service start, showing a `pswpout` burst in the same second as the fault (or, on a clean
start, a start that completed with `pswpout` flat). **What would kill it:** a fault on a start
with `pswpout` flat throughout, or a clean start at `swappiness=60` after the same one-card
workload.

The alternative that would also fit every row -- a defect on `03:00.0` -- is distinguished by the
same measurement: it predicts faults independent of swap activity.

## Proposed mitigations (for the user's decision; nothing has been changed)

1. **`vm.swappiness` 60 -> 1**, by `sysctl -w` and a line in `/etc/sysctl.d/`. Fully reversible,
   costs nothing on a host that is not memory-starved, and directly targets the hypothesis. This
   host has 15 GiB and no budget for more, so reducing the *rate* of swapping is the only lever
   available.
2. **Drop the page cache before a two-card start** (`echo 3 > /proc/sys/vm/drop_caches`), so the
   load does not begin against a full cache the kernel is about to reclaim against.
3. **One two-card service start per boot, first.** Order the day: reboot, start the service,
   then one-card and MiniMax work afterwards -- never a two-card start after one-card work on the
   same boot. Three of the five no-P2P faults are exactly that order.
4. **Measure it.** Run `scripts/measure-swap-during-start.sh` beside the next start regardless of
   which mitigations are adopted; without the measurement the next clean start proves nothing and
   the next fault teaches nothing.

Mitigations 1-3 are guesses ranked by cost, not a fix. Only 4 turns the next start into evidence.

## Evidence

`/mnt/fast-ai/bench-results/gpu-fault-20260919T1904/`:

* `kernel-boot.txt` -- the full kernel log for the boot, fault block at 15:03:46
* `devcoredump-card2.txt` -- 503,277 bytes, copied while the sysfs node was still live (it expires
  after about an hour)
* `campaign.log` -- the runner's own line-by-line record
* `service-state/` -- `state.json` (`failed`), `server.log` (the load up to the drafter),
  `kernel.log`, `launch.json`, `container-final.json`

Related: `/mnt/fast-ai/bench-results/fp8-stock-gdn-20260919/` (the one-card check that preceded
it, and its `FAULT-HALT.json`), `/mnt/fast-ai/bench-results/resume-20260919b/` (the MiniMax
retry), `/mnt/fast-ai/bench-results/batch-session-20260919.log` (the whole window). Earlier
faults: `gpu-fault-20260916T0602/`, `gpu-fault-20260917T0310/`, `gpu-fault-20260917T0717/`,
`gpu-fault-20260918T1506/` under the same root.

Prior notes: [2026-09-15 restore fault](2026-09-15-fp8-restore-gpu-fault.md),
[MiniMax first-light fault](../../minimax-h3-b70/notes/2026-09-18-gpu-fault-first-light.md),
[host oomd incident](2026-09-18-host-oomd-incident.md), and the `2026-09-19` row in
[DO-NOT-REPEAT.md](../DO-NOT-REPEAT.md).
