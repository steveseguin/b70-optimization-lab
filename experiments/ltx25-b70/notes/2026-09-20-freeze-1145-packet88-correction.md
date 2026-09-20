# Freeze 2026-09-20 11:45 EDT (boot dff7cf53): packet 88 — hypothesis correction

## What happened

Boot `dff7cf53` (11:29:32 EDT) ran server 88 (pid 4692) and the f88 campaign
from 11:42:54. Warm passed (3/3 exact). The journal ends 11:45:01; the last
validation write (f88-endure-00) is 11:44:57 — the freeze hit ~2 min 10 s in,
at the warm→endure transition. User rebooted; current boot `8f469374` 15:31.

## The packet-87-instrumentation hypothesis is dead

Packet 88's source is **byte-identical to packet 86** (verified by diff
against the frozen packet-86 directory), and packet 86 ran a full campaign —
including catching the wrong clip — without a freeze. Packet 88 froze at the
same campaign window as both packet-87 attempts. The differentiator was never
the instrumentation; I retract that attribution. Apologies for the two
campaigns spent on it.

## What the three freezes actually share

| Boot | Uptime at freeze | Campaign position |
| --- | --- | --- |
| 58ae370e | 2 h 17 m | ~70 s in (warm) |
| 5486d35a | 24 m | ~130 s in (warm→endure) |
| dff7cf53 | 15 m | ~130 s in (warm→endure) |

All three: the load step-change when the warm arm finishes and full-depth
pipelined traffic begins. C6 was disabled every time. Earlier same-boot
campaigns (84/85/86) passed the same window — so it is probabilistic, not
deterministic.

## Evidence pointing at the platform, not the code

1. Freeze 5486d35a: the journal died at 10:17:01 while validation writes to
   /mnt/fast-ai continued until 10:19:20 — **storage/userspace hung first,
   GPU compute continued ~2 min**.
2. Repeated `workqueue: delayed_fput hogged CPU` warnings in the minutes
   before that freeze (deferred file-close work piling up — I/O subsystem
   stress).
3. Root fs and /mnt/fast-ai are the **same single NVMe** (nvme0), which the
   kernel flags at boot with `using unchecked data buffer` (quirk list).
4. This host has **corrupted memory before** (two byte-corruption events this
   week, one in a 4.4 GB model load). Bad DRAM explains everything at once:
   freezes when kernel/driver structures land in the bad region, and the
   *deterministic* wrong clip — graph-pool placement is deterministic, so the
   same tensor can land on the same bad physical page every run.

## Leading hypothesis, revised

**A bad DRAM region** (or marginal power delivery corrupting under load) —
not any packet's code, not C6, not the GPU stack. The deterministic wrong
clip and the freezes are one disease.

## Actions

- memtest86+ is installed on this host (/boot has the EFI images) but needs a
  console reboot — still the user's call, still the definitive test.
- I am running a userspace memory test now (memtester from the Ubuntu
  archive, no sudo needed) over as much free RAM as practical. It covers
  almost everything memtest86+ would except the kernel's own pages.
- Campaign continuation after the memory test, with a settle gap between
  arms to soften the load step-change.
- User-held items unchanged: BIOS Power Supply Idle Control = Typical
  Current Idle; PSU rating vs ~190 W × 4 + 280 W CPU on the 12 V rails;
  `drm_kms_helper.fbdev_emulation=0` so pstore can finally record a panic.
