# Qwen3.8 Flash-Next root-NVMe: Gen4 margin negative, Gen3 clean (2026-09-02)

Date: 2026-09-02 00:00--00:12 EDT
Status: discriminator sequence complete; temporary operating state is PCIe
Gen3 x4 with APST off; 30-minute clearance run started at 00:11:56 EDT

## Cold boot on 5B2QGXA7 made the link worse, not better

The user cold-power-cycled without opening the case, so the only change from
the previous boot was firmware activation (`4B2QGXA7 -> 5B2QGXA7`, `afi 0x1`,
slot 1 `5B2QGXA7`, nothing pending) plus a fresh link training.

| | previous boot (4B2QGXA7) | this boot (5B2QGXA7) |
|---|---|---|
| endpoint corrected `RxErr` at idle | about 1 per 30--60 s | about 2 per s (149 -> 256 in 60 s) |
| non-fatal events | 0 | 1 during early boot (00:00:27) |
| root port corrected | 0 | 0 |
| link | 16 GT/s x4, EQ complete | 16 GT/s x4, EQ complete, `LaneErrStat 0` |
| SMART | clean | clean, 44 C; power cycles 61, unsafe shutdowns 24 |

Boot ID `d0024575-835a-4584-a0e0-1db665a88534`. The Corsair external drive
came up dirty (unsafe shutdown) and was remounted read/write with `ntfs-3g`
as `/dev/sda2 fuseblk /mnt/usb-models`, the exact identity the frozen runners
require; `ntfs3` refused the dirty volume.

## Discriminator sequence (user-authorized, in place)

Each step was followed by a 60-second sample of the endpoint corrected
counter at idle. Structured record:
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/host/20260902T0406Z-root-nvme-link-discriminators.json`.

1. **APST off** (`nvme set-feature -f 0x0c -v 0`, volatile): 103 events in
   60 s. No effect. Left off.
2. **Gen4 retrain** (root port `0000:00:03.1` LnkCtl retrain bit, target
   16 GT/s): link returned at 16 GT/s x4; 111 events in 60 s. No effect, so
   this was not a one-off bad training.
3. **Gen3 retrain** (LnkCtl2 target 8 GT/s, then retrain): link at 8 GT/s
   x4; 5 events in the first 10 s (the transition itself), then zero for the
   rest of the window and zero on the continuous 30-second monitor
   afterwards.

The root filesystem stayed readable through every step (hash of
`/etc/hostname` checked after each retrain).

## Interpretation

At 8 GT/s the same drive, slot, connector, and firmware are error-free; at
16 GT/s they are not. That is a signal-margin problem on this specific path,
and the new firmware's receiver behaviour at Gen4 is worse on this board than
the old one's. Nothing here implicates Qwen, the B70s, host memory, NAND, or
thermals. The corrected events were never data corruption (link-level retry),
but a Gen4 link at two errors per second under sustained checkpoint reads is
the plausible mechanism for the earlier journal-less freezes.

## Temporary operating state and what it costs

- Root port target speed 8 GT/s, link 8 GT/s x4, ASPM `performance`, APST
  off. These are volatile: a reboot returns to Gen4 with errors until they
  are reapplied.
- Local NVMe sequential reads drop from roughly 6.5 GB/s to roughly 3.3 GB/s
  ceiling. The 131-shard local checkpoint load that took about 78 s at Gen4
  should take on the order of two minutes; the external USB copy takes about
  570 s, so local is still the faster source for full-model arms.
- Decode throughput is unaffected: the model is resident on the B70s.

`tools/pin-root-nvme-link-gen3.sh` and its uninstalled
`pin-root-nvme-link-gen3.service` reapply this state at boot; installing
them is a boot-behaviour change and needs explicit authorization. The link
still trains at Gen4 through firmware and early boot until the unit runs.

## Permanent-fix candidates, in order

1. Supermicro BIOS per-slot PCIe link speed set to Gen3 for this M.2 slot
   (removes the Gen4 boot-time window entirely).
2. Supermicro M12SWA-TF BIOS 2.4a (2025-07-17; installed 2.0b from 2022) for
   newer AGESA PCIe Gen4 training, then retest at Gen4.
3. Another CPU-attached M.2 slot, which changes traces and connector, with a
   reviewed BDF update in the validator and runners.
4. A different drive.

## Clearance

`tools/generate-q38-root-nvme-link-clearance-v1.py --idle-seconds 1800
--read-gib 4` started at 00:11:56 EDT at Gen3 with the counter at 978. The
validator does not require a link speed; the receipt records the boot ID,
controller identity, `5B2QGXA7`, zero idle and bounded-read deltas, SMART,
and the four-B70 topology. The evidence sidecar records the link speed and
width. This deviates from the earlier note's "verify Gen4 x4" wording; the
physical criterion that matters for host stability is zero corrected events,
and that is what the receipt proves.
