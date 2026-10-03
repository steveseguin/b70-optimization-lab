# Four-B70 host: forensic review and catch-up after a 12-day gap (2026-10-03)

No lane work ran between 2026-09-21 03:29 EDT and 2026-10-03. This note
records what a full read of the journal, the hardware and upstream showed.
Sources: journal boots -37..0 (dumps were made in a session scratchpad, not
kept), `dmidecode`, `ipmitool`, `lspci -vvv`, `nvme`, apt history, and web
research by subagents. Items marked (agent) were not re-verified first-hand.

## Hardware facts not in earlier notes

- **Memory is not ECC.** `dmidecode -t 16`: `Error Correction Type: None`.
  Four Kingston unbuffered 32 GB dual-rank DIMMs at 3200 MT/s, 1.2 V, slots
  A1/B1/E1/F1; one module has a different part number (`99U5734-056.A00G`
  against `9905734-403.A00G`). This is why no EDAC memory controller exists.
  ECC cannot be enabled; it needs registered ECC modules.
- BIOS 2.4a (2025-07-17) is still the newest for the M12SWA-TF (agent).
- AER is firmware-first (`_OSC: platform does not support AER`), so the OS
  never sees PCIe errors. BMC SEL has no entry after 2026-09-01.
- BMC sensors with GPUs idle and the CPU under memtester: 12V 11.913 V,
  5VCC 5.015, 3.3VCC 3.253, SOC_VRM 74 C, CPU 50 C. 12 V under four loaded
  cards has never been logged.
- NVMe (Samsung 980 PRO, fw 5B2QGXA7): 0 media errors, 4 % used, 38 unsafe
  shutdowns of 76 power cycles, APST enabled. Its sticky AER status shows
  `RxErr` and `BadTLP` correctable link errors after one hour of uptime.
  Every other device shows only the benign enumeration pattern
  (`UnsupReq`/`AdvNonFatalErr`).
- GPU links: 16 GT/s x16 on all four (the cards are 32 GT/s capable; the
  board is Gen4), no physical-layer errors latched.
- pstore is empty; no kdump; `kernel.panic=0`.

## Boot timeline (agent, spot-checked)

37 finished boots since 09-13: 4 clean, 33 unclean (25 reset pin, 3 internal
CPU shutdown, 4 CF9 without a logged shutdown, 1 ACPI power transition). Most
unclean boots end on a routine cron line with no kernel message.

Software: every package change since 09-13 came from unattended-upgrades. On
09-28 it installed 7.0.0-34 and **removed 7.0.0-30**. -34 and -31 are both
upstream 7.0.14; the -34 changelog has no xe, drm, GuC, AMD, cpuidle or
clocksource entry. GuC 70.44.1 is simply the linux-firmware package's file
(restored 09-17 23:18); nothing else pins it. The 09-17 review's kernel -30
and GuC restore were applied together on one boot and neither was tested
alone.

## Signatures

1. **Hard lockup inside the xe GuC interrupt handler, three times, always
   CPU 21** (verified first-hand): 09-14 22:09:20 and 23:35:49 (boot
   64bbd5d2, survived both, followed by 16.3 s and 71.8 s clocksource long
   readouts) and 09-20 00:39:41 (boot 58ae370e, final line).
   `RIP: memcpy_fromio`, `g2h_read+0x42a [xe] <- xe_guc_ct_fast_path <-
   xe_guc_irq_handler <- dg1_irq_handler`. On the current boot the MSI of
   **0000:43:00.0** has effective affinity CPU 21 (the other cards: 25, 27,
   23). 43:00.0 is also the card that logged the CAT error and engine reset
   on 09-17. A CPU stuck for seconds in an MMIO copy from a card's BAR means
   the card was not answering reads.
2. `clocksource: Long readout interval`: seven lines in five boots, all
   unclean; in three it is the last kernel line. Two follow signature 1
   directly. It is a symptom of the stall (agent, lore link in the session).
3. Soft lockups in `smp_call_function_many_cond` in two boots, both before
   the cpuidle state2 disable. After the disable (boots from 09-19 22:22)
   this signature is gone, and an idle boot ran 09-27..10-02 cleanly; five
   boots under load still ended unclean.
4. xe engine faults (`Fault response: Unsuccessful -ENOENT`, CAT error) in
   five boots; not followed closely by a freeze (gaps 22-100 min; two of
   those boots ended cleanly).
5. The same python GP fault (ip 184cfbb) on two boots.

Zero MCE, zero AER (cannot be seen), zero nvme errors, zero GuC CT messages.

## Corrections to earlier notes

- 09-19 freeze note: "hard-lockup detection did not fire" and "the xe driver
  is excluded" are wrong. Signature 1 is in the xe interrupt path.
- `kernel.hardlockup_panic=1` with `kernel.panic=0` and an empty pstore turns
  a lockup the machine survived twice on 09-14 into a permanent halt with no
  record. The 09-20 00:39 freeze is exactly that.
- "Storage-first hang" (journal stops minutes before the freeze while clips
  keep completing): journald syncs every five minutes by default
  (`SyncIntervalSec=5m`, unchanged) and ext4 writes back dirty data after
  about 30 s. Every observed gap fits that. It is not evidence of an NVMe
  stall. The NVMe link errors above are a separate, weaker observation.
- The cpuidle state2 disable is installed and persistent
  (`disable-cpuidle-state2.service`); PLAN.md and CURRENT.md said otherwise.

## Upstream (agents, URLs in the session log)

- Ubuntu 7.0.0-38 (noble-updates, 2026-10-01; apt candidate verified here):
  "drm/xe/guc: Hold device ref until queue teardown completes"
  (CVE-2026-68382, teardown deadlock), two xe page-table bind fixes, an
  `iommu/amd` locking fix.
- 7.0.0-39 (-proposed): "drm/xe: Don't hand out the flat CCS storage as
  usable VRAM" (CVE-2026-90047); reproduced on B580/B570, B70 unconfirmed;
  the fixed kernel logs a FLAT_CCS misalignment line if affected.
- xe recommends GuC 70.54.0 for BMG; 70.44.1 misses two Intel BMG bug-fix
  bumps. No public evidence supports pinning 70.44.1.
- No public report of a kernel fixing B70 freezes. compute-runtime #948 and
  #999 describe our fault signature on dual B70/B65, open.
- PyTorch: the lane venv is already 2.14.0+xpu with the 2026.1 runtime, the
  release that adds native XPUGraph recording and the mempool capture fix.
- LTX-2 1.4.0 (09-29) changed the reference sampler defaults and added
  chunked long-video generation; our reference is the pinned ComfyUI graph.
- Nobody has published lossless real-time LTX 2.5; every faster-than-playback
  claim uses lower precision, fewer steps or residual caching.

## Working hypotheses, ranked

1. Card 0000:43:00.0 (or its slot, riser or power feed) intermittently stops
   answering on PCIe; the CPU servicing its interrupt hangs in the MMIO read.
   Fits the load-transition clustering. Tests: 12 V logged under load, swap
   the card to another slot, kernel -38/-39, GuC 70.54.0.
2. Non-ECC memory errors for the two single-byte corruptions and the two
   identical heap-corruption crashes. Test: memtest86+ (userspace memtester
   over 104 GB is running at the time of writing).
3. C-state IPI lockups: fixed by the state2 disable.

## Instruments still missing

Off-box kernel log (netconsole to the two-B70 host; the receiver has to be
started by the user), a 12 V/temperature logger during GPU load, and a
runtime `kernel.hardlockup_panic=0` so a lockup can be survived and logged.
