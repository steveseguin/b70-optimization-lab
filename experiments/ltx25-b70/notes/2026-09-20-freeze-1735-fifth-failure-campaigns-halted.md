# Freeze 2026-09-20 ~17:35 EDT (boot 8f469374, second attempt): fifth failure

## What happened

The retried f88 campaign (60 s post-construction rest, 60 s settle between
arms) **passed warm** (receipt adc781b6 committed 17:35) and began the endure
arm. The journal died 17:35:01 while validation writes continued to at least
17:36:30 — the second time the storage-first hang signature appears: logging
blocks on the stuck device while the GPU pipeline keeps completing clips.
The user found the machine wedged and rebooted 23:11.

## Salvage from the zombie window (4 endure prompts validated before the wedge)

| Prompt | Contents | Verdict |
| --- | --- | --- |
| f88-endure-00 | all-zero tensors | pipeline fill, by design |
| f88-endure-01 | all-zero tensors | pipeline fill, by design |
| f88-endure-02 | latents **bitwise EXACT** vs `baseline-01`; images/waveform zero | correct clip, save truncated by the freeze — NOT the wrong-clip bug |
| f88-endure-03 | all four tensors bitwise EXACT vs `stability-01-r01-boat` | correct |

No wrong-clip reproduction. The sampler was producing bitwise-correct output
right up to the wedge (endure-03 verified at 17:36:30, ~90 s after the
journal died).

## Scoreboard, 2026-09-20

Five campaign attempts, five failures, all in the launch→warm→early-endure
window, on two code versions (one byte-identical to a version that passed
three campaigns yesterday): 3 freezes, 1 segfault in interpreter text during
encoder load, 1 freeze. Userspace memtester passed 64 GB. C6 disabled
throughout. Every freeze that left a signature died storage-first.

## Campaigns are halted

Per the pre-committed retry budget, no more campaign attempts until at least
one user-held item lands:

1. **memtest86+ at the console** (installed in /boot, pick it in GRUB) —
   the definitive RAM verdict; the userspace pass cannot see the kernel's
   pages or the DMA path.
2. **BIOS: Power Supply Idle Control = Typical Current Idle** — the queued
   fix for the AMD idle-power delivery mode that matches whole-machine
   wedges under load transients.
3. **Kernel cmdline `drm_kms_helper.fbdev_emulation=0`** (needs sudo) — lets
   pstore/ERST actually record the panic; turns the next freeze from a
   silent wedge into a stack trace. Optionally `kernel.hardlockup_panic=1`
   so the machine reboots itself instead of needing a hand.
4. PSU rating sanity check (~190 W × 4 cards + 280 W CPU on the 12 V rails).

Meanwhile the lane continues offline: packet 89 (audio adaLN fusion, proven
bitwise-equal swap, ~0.05 s/clip) is build-ready in the repo, and the next
attempt also drops the campaign script's explicit `sync` calls to reduce
forced-flush pressure on the NVMe during the window.
