# Freeze 2026-09-20 00:39:41 EDT (boot 58ae370e): hard lockup during packet-87 warm

## What happened

Boot `58ae370e` (2026-09-19 22:22 EDT) ended with the kernel's last message:

```
Sep 20 00:39:41 kernel: watchdog: CPU21: Watchdog detected hard LOCKUP on cpu 21
```

The packet-87 campaign had started at 00:38:31 EDT — server 87 (pid 145307) up,
warm arm executing. Three request dirs exist (`f87-warm-00/01/02`). The freeze
hit roughly 70 seconds into the warm arm, during shard install, graph capture
and the first sampling. pstore captured nothing (empty), so no stack trace.
The host stayed down ~9.3 h; boot `5486d35a` came up 09:53 EDT.

## What I was running that is a candidate cause, honestly ranked

1. **Packet 87's new instrumentation** (first run ever): the sampler workers
   now take strided D2H fingerprints of ~10 device tensors per clip
   (stage_a/upscaled/stage_b av latents, sigmas, generated noise) plus 14
   timing events per clip — several blocking `tensor.cpu()` copies per clip
   on the worker streams, mid-pipeline, on a driver stack (xe + Level-Zero)
   that has frozen this host under GPU stress before. This is the largest new
   GPU-driver interaction introduced by my changes, and the freeze happened
   on its first exercise.
2. **Fourth encoder-server launch on one boot** (84, 85, 86, 87). Launches
   move ~60 GB through the copy engines; earlier freezes in this lane also
   clustered near launches.
3. **The standing host instability.** cpuidle state2 (C6) was disabled at
   runtime for this entire boot — and it froze anyway. That weakens the C6
   hypothesis as a sufficient explanation; PSU idle-control and
   load-dependent memory corruption remain open. (BIOS "Power Supply Idle
   Control" and the fbdev_emulation=0 line were never applied.)

## What is NOT a candidate

- The wrong-clip investigation itself: receipts and fingerprints are
  reads/hashes; the only device-touching additions are item 1.
- Packet 86's event-only instrumentation ran a full warm + 30-prompt arm on
  this same boot without issue (so events alone are weakly exonerated; the
  blocking D2H copies are 87's main addition).

## Current boot state (5486d35a)

- `/sys/.../cpuidle/state2/disable = 1` already set at boot (user-side
  persistence — thank you). Runtime PM pinned on all four cards; no FAULT.
- Packet 87's campaign was interrupted before any receipts; nothing from it
  is promoted.

## Continuation decision

Relaunch the packet-87 campaign once on this boot (single launch, PM pinned,
C6 off). The instrumentation is the current critical path for the wrong-clip
root cause, which gates trusting any future speed measurement. If this boot
freezes the same way during warm, that reproduces the correlation and the
instrumentation comes out — the D2H fingerprints move to an offline
post-hoc comparison instead of in-pipeline reads.
