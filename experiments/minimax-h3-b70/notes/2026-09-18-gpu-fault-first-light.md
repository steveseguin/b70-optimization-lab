# MiniMax-H3 first light, session 10: a copy-engine GPU fault at the first denoise step

Date: 2026-09-18 (EDT timestamps below; the kernel log is in the same local time).
Session root `/mnt/fast-ai/bench-results/minimax-h3-s10-20260918/`, evidence copy
`/mnt/fast-ai/bench-results/gpu-fault-20260918T1506/`.

The pipeline works. Session 10 is the first run to get all the way through encode, the two-card
load and into sampling: 902 encoder tensors placed in 12.6 s, the conditioning forward in 1.5 s,
the pruned denoiser streamed onto both cards in 20.6 s at the byte-balanced block-24 split
(18.797 GiB on xpu:0, 18.747 GiB on xpu:1), host RSS bounded throughout. Then the first denoise
step ran for three seconds and the card holding blocks 0..23 faulted its copy engine.

**All GPU work on this host is halted** (AGENTS.md: a fault halts the lane until the user
decides). The FP8 service is DOWN. The card has an uncleared device coredump. Nothing was reset,
nothing was rebooted, no driver state was touched.

---

## Timeline (2026-09-18, EDT)

| Time | Event |
| --- | --- |
| 11:01:46 | FP8 service reported `ready`, then a graceful stop for the saved container only, no restart scheduled. Its last state is `/mnt/fast-ai/bench-results/minimax-h3-s9-20260918/service-restore`. |
| 11:02:08 | Host free: MemAvailable 13,958 MiB. |
| 11:02:13–11:03:11 | The host-memory probe matrix, eight runs (table below), `scripts/xpu-host-memory-probe.py`. |
| 11:03:14 | Smoke `one` started with `PYTORCH_ALLOC_CONF=expandable_segments:True`, the `pread` loader, `STEPS=8`, 256x448x124, seed 42. |
| 11:03:17.9 | `encode.tokenize` done, 46 rows. |
| 11:03:30.6 | `encode.load` done in **12.64 s**: 902 tensors (350 quantized Linears) on xpu:0, VmRSS flat at 0.778 GiB, MemAvailable never below 12.7 GiB. |
| 11:03:32.0 | `encode.forward` done in **1.46 s**; prompt embeds (1, 46, 5120); encoder freed. |
| 11:03:53.4 | `load.stream` done in **20.61 s**, 634 tensors; `rope.inv_freq` drift 0.000e+00. |
| 11:03:53.452 | `denoiser split at block 24: 18.797 GiB on xpu:0, 18.747 GiB on xpu:1`. |
| 11:03:53.675 | `sample` started. |
| 11:03:56 | `xe 0000:03:00.0` (card2 / renderD129 = **xpu:0**): 25 page faults on `EngineClass: 3 bcs`, 9 `Engine memory CAT error [18]`, one bcs engine reset, `Timedout job: seqno=305 ... in python [198500]`, `Xe device coredump has been created`. |
| 11:03:56.480 | The runner raised `RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)` inside `MiniMaxH3LoopSchedulerStep` / `scheduler.step`, i.e. **the first denoise step**. |
| after | The hung python was killed by pid. No containers were started or stopped. No driver reset, no reboot, no write to the devcoredump node. |

## The probe matrix (why the run got this far at all)

Session 9 died with the watchdog firing at 1.2 GiB MemAvailable while the runner's own RSS was
0.7 GiB: host memory was disappearing somewhere other than the process. `scripts/xpu-host-memory-probe.py`
places 8 GiB on `xpu:0` one GiB at a time, two ways (`fill` = `torch.empty` + `fill_`, `copy` =
the loader's host-buffer -> `.to('xpu:0')` path), and prints MemAvailable and the process's
dma-buf fd count after each.

| Cards visible | `PYTORCH_ALLOC_CONF` | fill: host MiB consumed by 8 GiB | copy: host MiB consumed by 8 GiB | dma-buf fds |
| --- | --- | --- | --- | --- |
| both | unset | **+8,125** | **+7,993** | 1 |
| both | `expandable_segments:True` | +54 | +149 | 1 |
| one (`ONEAPI_DEVICE_SELECTOR=level_zero:0`) | unset | +35 | +155 | 1 |
| one | `expandable_segments:True` | +12 | +102 | 1 |

Read it in one line: **with both cards visible and the default allocator, every GiB placed on a
card costs a GiB of host RAM; with expandable segments it costs nothing measurable.** The dma-buf
fd count stays at 1 in every combination, so this is not fd leakage -- it is peer residency:
making a device allocation reachable from the *other* visible card mirrors it into host pages
unless the allocator uses expandable segments. That is what killed session 9, and, with the 4 GiB
cgroup cap, the desktop session on 2026-09-17
(`../../qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md`).

`PYTORCH_ALLOC_CONF=expandable_segments:True` is therefore a **precondition** for any two-card run
on this host, not a tuning knob. `smoke_h3.sh` now sets it for every GPU run.

## The fault signature

```
xe 0000:03:00.0: [drm] Tile0: GT0:
                     ASID: 1497
                     Faulted Address: 0x00008156cc204000
                     FaultType: 0     AccessType: 1     FaultLevel: 1
                     EngineClass: 3 bcs     EngineInstance: 0
xe 0000:03:00.0: [drm] Tile0: GT0: Fault response: Unsuccessful -EINVAL      (x25)
xe 0000:03:00.0: [drm] Tile0: GT0: Engine memory CAT error [18]: class=bcs, logical_mask: 0x1, guc_id=22   (x9)
xe 0000:03:00.0: [drm] Tile0: GT0: Engine reset: engine_class=bcs, logical_mask: 0x1, guc_id=22, state=0x249
xe 0000:03:00.0: [drm] Tile0: GT0: Timedout job: seqno=305, lrc_seqno=305, guc_id=22, flags=0x20 in python [198500]
xe 0000:03:00.0: [drm] Xe device coredump has been created
```

* **Card:** PCI `0000:03:00.0` = `/sys/class/drm/card2` = `renderD129`. The other B70 is
  `0000:e3:00.0` = `card0` = `renderD128` (`card1` is the ast BMC display, not a B70). Level Zero
  enumerates by ascending PCI address, so `03:00.0` is **xpu:0** -- the card the run reported the
  902 encoder tensors and the first 24 denoiser blocks on, and the *source* of the block-24
  crossing. The devcoredump names `Process: python [198500]`, our runner, and PCI ID `0xe223`.
* **Engine:** `bcs`, the blitter / copy engine -- not a compute (ccs) engine. The faulted
  addresses are 13 distinct 4 KiB pages in one contiguous span, `0x8156cc200000`..`0x8156cc217000`.
* **Access:** `FaultType: 0` (not present), `AccessType: 1` (write), `FaultLevel: 1`. The copy
  engine was writing into a mapping the GPU page tables did not have.
* **Time:** the faults are at the instant `scheduler.step` ran for step 0, which is after the
  hidden states have been through blocks 0..23 on xpu:0 and crossed to xpu:1 for blocks 24..47.

### The same card and engine have faulted here before

| Date (UTC) | Cards | Engine | Context | Evidence |
| --- | --- | --- | --- | --- |
| 2026-09-16 06:02 | `03:00.0` | bcs | two-card FP8 service start | `/mnt/fast-ai/bench-results/gpu-fault-20260916T0602/` |
| 2026-09-17 03:10 | `03:00.0` | bcs | two-card FP8 service start | `/mnt/fast-ai/bench-results/gpu-fault-20260917T0310/` |
| 2026-09-17 07:17 | both | ccs | `CCL_SYCL_*_SIMPLE_THRESHOLD=0`, i.e. oneCCL's non-simple SYCL kernels, which use peer memory access over PCIe | `/mnt/fast-ai/bench-results/gpu-fault-20260917T0717/`, qwen38 `DO-NOT-REPEAT.md` 2026-09-17 row |
| 2026-09-18 15:06 | `03:00.0` | bcs | this run, first denoise step | `/mnt/fast-ai/bench-results/gpu-fault-20260918T1506/` |

## Hypothesis (stated, not proven)

> The runner's cross-card hand-off at the block-24 split -- `x.to(secondary)` from a tensor
> resident on xpu:0 -- is a **peer-to-peer PCIe copy issued on the blitter**, and peer access over
> PCIe is the class this host has already faulted on.

Three things make it the leading candidate and none of them makes it a proof:

1. The fault is on the copy engine of the *source* card, at the first instant a tensor crosses,
   after 34 s of single-card work on that same card had run clean.
2. The 2026-09-17 07:17Z ccs fault on both cards was attributed to oneCCL choosing SYCL kernels
   that use peer memory access; the FP8 service, which drives both cards for hours without
   faulting, **never does P2P** (its `CCL_SYCL_*_SIMPLE_THRESHOLD` are pinned at 4 GiB and its
   allreduce is host-waited).
3. The write-to-absent-mapping signature (`FaultType: 0`, `AccessType: 1`) over a contiguous
   ~96 KiB span is what a blit into a peer aperture that is not mapped would look like.

What would *falsify* it: a host-staged run (`B70_H3_XFER=host`, the new default) that reaches the
same step and beyond on the same split. What would not settle it: any single clean run, because
the two earlier bcs faults on this card happened during plain service starts with no P2P at all,
so a bad card or a driver/firmware defect is an equally live explanation until a host-staged run
either survives or faults in the same place.

## What changed in the lane because of this

* `run_h3_t2v.py` gained `B70_H3_XFER=host|direct` (**default `host`**). Every cross-card move --
  the block-23-to-24 hand-off, the cached `temb` / `adaln_indices` / rope tensors the secondary
  blocks read, the gather back to the primary card after the last block, the text-encoder
  embeddings when `--encoder-card` differs from `--cards[0]`, and the latents handed to the VAEs
  -- goes through `cross_card()`, which synchronizes the source card, copies to a CPU tensor,
  copies to the target card and synchronizes the target. `direct` restores the old behaviour for
  the A/B. **A copy is a copy: both routes are bit-exact**, so a `host` run and a `direct` run are
  comparable hash for hash.
* `smoke_h3.sh` exports `PYTORCH_ALLOC_CONF=expandable_segments:True` and `B70_H3_XFER=host` into
  every GPU run and documents both as preconditions, and its preflight now refuses to start while
  any card has an uncleared `/sys/class/drm/card*/device/devcoredump/data`, naming the card.
* `scripts/xpu-host-memory-probe.py` is committed as the standing diagnostic for driver-held host
  memory.
* **No synchronize was added to the load loops, and that is a verified answer, not an omission.**
  The pread loader drops each tensor's host buffer (`del t`) and fadvises its page-cache range
  (`release()`) the instant `.to(device)` returns, which is only safe if a pageable host-to-device
  copy is host-synchronous. It is, in this venv: no XPU C++ sources ship with the wheel, but
  `torch/lib/libtorch_xpu.so` (2.14.0+xpu, `torch.version.xpu` 20260100, git `08187d9e0`) is not
  stripped and carries SYCL `code_location` constants, and `at::native::xpu::_copy_xpu` branches
  on `non_blocking`: the `false` branch is an unconditional `queue.memcpy(dst, src, n).wait()` at
  `torch-xpu-ops/src/ATen/native/xpu/Copy.cpp:313`, with no `is_pinned` test on that path. The
  three other memcpy sites (lines 278/297/304) are the `non_blocking=True` side and are followed
  by the caching-host-allocator's `record_event` instead of a wait; the pageable one of those
  stages through a pinned block, so even it does not hold the caller's buffer across the copy.
  Re-check if the venv's torch is rebased.

## What stays halted

* **No GPU work of any kind on this host** until the user decides. No health probe, no service
  start, no retry of the smoke run.
* **No driver reset, no module reload, no reboot, and no write to the devcoredump node.** Reading
  it is fine; clearing it is the user's call and it is also the flag `smoke_h3.sh` refuses on.
* **The FP8 service is down** and stays down. Its last state directory is
  `/mnt/fast-ai/bench-results/minimax-h3-s9-20260918/service-restore`; session 10 stopped it
  gracefully at 11:01:46 before the probes, and nothing has started it since.

## What the user has to decide

1. **Health probe, then restart** -- run the bounded two-card health check on the current boot
   and, if it is clean, restore the FP8 service and re-run the smoke with `B70_H3_XFER=host`.
   Cheaper, but it runs on a card whose coredump has not been cleared and which has now faulted
   three times on this boot lineage.
2. **Reboot first** -- clears the coredump and the driver state, and gives the host-staged run a
   clean baseline; costs the uptime and whatever the running kernel/firmware combination is worth
   as evidence.

Either way the first GPU work afterwards should be the host-staged smoke run, because it is the
experiment that tests the hypothesis, and it is the only thing that can turn the
`DO-NOT-REPEAT.md` row on direct device-to-device transfers from a hypothesis into a finding.

## Evidence

`/mnt/fast-ai/bench-results/gpu-fault-20260918T1506/`:

* `devcoredump-card2.txt` -- 503,704 bytes, sha256
  `5605d576da49428d687744e09ed0f3f2e37c038bbc8600c3f198b6798a93d13c`
  (`Reason: Timedout job - seqno=305, lrc_seqno=305, guc_id=22, flags=0x20`, kernel
  7.0.0-31-generic, module `xe`, GuC `xe/bmg_guc_70.bin`, `Process: python [198500]`)
* `kernel-since-1055.txt` -- the kernel window, 25 fault responses, 9 CAT errors, one engine reset
* `h3-session10-20260918.log` -- the session log (service stop, the eight probes, the smoke launch)
* `session-out/` -- a copy of the session root

`/mnt/fast-ai/bench-results/minimax-h3-s10-20260918/`:

* `smoke-20260918T150314Z.log` -- the run log, phase timings and the DEVICE_LOST traceback
* `probe-{both,one}-{unset,expandable}-{fill,copy}.log` -- the eight probe runs
