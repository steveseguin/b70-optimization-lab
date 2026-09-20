# Packet 83: the sharded encoder is exact, and the host is not (2026-09-19/20)

Packet 83 keys the text encoder's graph memory pool **and** its capture stream
by `(device, worker thread)` instead of by device alone. Packet 82's receipts
had shown one finite, fully wrong clip per run on servers 79b, 80, 81 and 82b,
always during the fill phase where the two encode workers dispatch back to
back; a pool shared between threads lets the allocator hand one thread's
replay the blocks the other thread's capture freed.

## Result: correctness fixed

Server 83c, boot 534bf39d, 22:46-22:50 UTC on 2026-09-19.

| Arm | Prompts | Distinct clips | Exact |
| --- | --- | --- | --- |
| f83c-warm | 3 | 0 (fills) | 3/3 |
| f83c-tsh | 30 | 27 | **30/30, `all_exact` true** |

Every fixture matched its reference byte for byte, including `bird`, the clip
that failed on 79b (muxer EINVAL from NaN audio), 81 (all four tensors NaN)
and 82b (finite but 100% different). Four graph pools were live throughout
(`graph_pools: 4` = two devices x two threads), 96 captured graphs and 1584
replays by the last prompt. The shard sat where it was asked: 48 layers split
at index 24, `xpu:2` primary 15.33 GB, `xpu:3` secondary 10.90 GB.

The endurance arm (120 prompts) has not run: the host froze at 22:50 UTC,
and two later launch attempts died of host memory corruption (below).

## Result: no speed gain, and the sampler is the wall

Twenty-four of the twenty-six steady intervals are clean; two were platform
stalls (below) and are excluded here.

| | Packet 74 (control) | Packet 82 | Packet 83 |
| --- | --- | --- | --- |
| Steady mean | 1.607 s | 1.622 s | 1.685 s |
| p95 | - | 1.955 s | 1.988 s |
| min / max | - | 1.085 / 2.129 s | 1.130 / 3.344 s |
| Histogram <1.3 / 1.3-1.7 / >1.7 | - | 1 / 16 / 9 | 2 / 17 / 5 |
| fps equivalent | 15.6 | 15.4 | 14.8 |

Stage times per clip, stall-affected clips excluded: encode 3.257 s mean
(1.762 min, 4.820 max), decode 1.063 s (0.912, 1.419). With two clips in
flight the sharded encoder delivers about 1.63 s per clip and the two-clip
sampler about the same, so the shard has moved the bottleneck without moving
the number. Memory at prompt 20: xpu:0 28.4 GB reserved, xpu:1 28.1, xpu:2
23.2, xpu:3 17.9.

**The encoder is closed as a lever.** Everything below 1.6 s/clip now has to
come from the sampler: more clips in flight, or a transformer split that uses
the headroom on xpu:2 and xpu:3.

## The host stalls mid-run, and corrupts memory

Two intervals in the sharded arm were 18.237 s and 10.678 s, between clips
that were themselves bit-exact. The kernel's only line in that window:

```
2026-09-19T18:49:16-04:00 kernel: clocksource: Long readout interval,
  skipping watchdog check: cs_nsec: 4276605235 wd_nsec: 4276604987
```

22:49:16 UTC falls inside the 18.2 s gap (22:48:59.869 to 22:49:18.106). A
clocksource readout gap of that size means no core executed for that long and
the platform timer agreed, so this is a whole-platform stall, not a stuck
core and not a GPU fault. The run recovered, produced twelve more exact
clips, and the host froze about two minutes later (twelfth freeze; the
eleventh, at 22:20 UTC, had the same signature with a 6.035 s gap). **The
stalls are the freeze in survivable form.**

Then, on two different boots, a single byte of the 32,169,626-byte
`tokenizer_json` tensor inside the 26 GB text-encoder safetensors came back
wrong while the file was being loaded:

| Server | Boot | Position | Byte on disk | Byte the process saw |
| --- | --- | --- | --- | --- |
| 83b | 534bf39d | 25,610,902 | `0x2c` | `0xda` |
| 83d | da8627aa | 7,941,018 | `0x5d` | `0xb5` |

Checked immediately after each failure: both positions read the correct byte
through the page cache **and** through O_DIRECT, the whole tensor decodes as
UTF-8, and the file hashes to
`ef7243612fdae7a75cb4d5cee9433e81380675fb6c213bd98ae74a9cd16561d1`, the value
in `model-verification.json`. So the disk is right, the page cache is right,
and the corruption happened in the copy into the process's buffer. Four bits
differ in one case and six in the other, which is not a classic single-bit
DRAM soft error; it looks like a bad burst on a cache line or an interconnect
path. This board exposes no EDAC memory-controller instance, so if the DIMMs
are ECC at all, nothing is reporting.

**This host is corrupting data.** The campaign harness happens to catch it,
because every clip is compared sha256-by-sha256 against a stored reference
and the tokenizer happens to be UTF-8 text, but nothing guarantees the next
corruption lands somewhere noisy. Until a memory test passes, no measurement
from this machine should be promoted, and the one-wrong-clip history of
packets 79b-82 now has a second possible cause besides the pool race that
packet 83 fixed.

## What the user needs to decide

1. Run memtest86+ for at least one full pass. This is now ahead of every
   software lever in the lane.
2. BIOS: Power Supply Idle Control = Typical Current Idle; then re-check the
   PSU rating against four B70s (about 190 W each) plus a 280 W CPU, and the
   12 V rails under load.
3. The runtime `cpuidle` state2 disable, still not applied, is the cheap half
   of item 2.
4. `drm_kms_helper.fbdev_emulation=0` so a panic stops printing through the
   GPU framebuffer and pstore can finally record one.
