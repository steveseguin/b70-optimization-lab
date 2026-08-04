# The recurring CCL wedge is a GuC job-timeout loop on stale firmware

Date: 2026-08-04 America/Toronto

Status: **root cause identified and recovery verified. The firmware upgrade
itself is proposed, not applied.**

## What happens

A serving run stops at the CCL topology-recognition warning and never reaches
model load. It then sits until the launcher's health timeout kills it, which
orphans in-flight GPU jobs and starts a GuC reset loop that outlives the run.

The signature is exact and easy to check. In a healthy run, `server.log` reaches
the CCL warning and emits `Starting to load model` **in the same second**, with
full startup to `Graph capturing finished` taking about **2 minutes 28 seconds**.
A wedged run stops at that identical line and emits nothing further.

```
healthy   line 79  23:20:46 CCL topology warning
          line 80  23:20:46 Starting to load model ...
          ready    23:22:20 Graph capturing finished

wedged    line 79  00:22:27 CCL topology warning
          (nothing, 18 minutes, killed at 00:41)
```

## Why it persists after the run dies

The kernel reports the timed-out jobs as `in no process [-1]` -- they are
orphaned. `fuser` on all four render nodes returns nothing, so no process holds
the devices, yet the reset loop continues indefinitely. It was measured at
**360 resets per minute across three of the four cards** while the machine was
otherwise idle, long after the owning run had exited.

Every subsequent run on that stack inherits the degraded state, which is why
these failures cluster: one wedge poisons the following attempts.

## Root cause candidate

```
xe 0000:27:00.0: [drm] GuC firmware (70.54.0) is recommended,
                       but only (70.44.1) was found in xe/bmg_guc_70.bin
```

- installed: GuC **70.44.1**, from `linux-firmware 20240318.git3b128b60-0ubuntu2.27`
- driver in kernel **7.0.0-28-generic** asks for **70.54.0**
- the failure mode is `guc_exec_queue_timedout_job` -- GuC submission itself

The firmware package predates the driver by roughly two years, and only one BMG
GuC blob is present (`/lib/firmware/xe/bmg_guc_70.bin.zst`), so there is no
newer version to fall back to locally.

This is a strong candidate rather than a proven cause: the wedge is
intermittent, and no run has yet been done on 70.54.0 to compare against.

## Recovery that works

Unbinding all four devices and reloading the module clears it. Verified: zero
resets in a clean window afterwards, all four cards re-enumerated, `xpu-smi`
reporting 4 devices, and a relaunched run passing the exact line that had hung.

```bash
for b in 0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0; do
  echo $b | sudo tee /sys/bus/pci/drivers/xe/unbind >/dev/null
done
sudo modprobe -r xe && sudo modprobe xe
```

Safe on this host because the console is on the `ast` BMC adapter, not `xe`, and
no display manager is running. Confirm both before reloading on any other host.

## Why this matters to the campaign

Several earlier measurement attempts were recorded as failing for unrelated
reasons -- "CCL wedge on stale driver" among them. That description was
accurate but incomplete, and the shared cause was not chased. The cost is
real: each wedge burns a full run slot, and the machine keeps resetting between
attempts unless the driver is explicitly reloaded.

**Recommendation:** upgrade `linux-firmware` to a build carrying GuC 70.54.0
before further kernel-profiling work. Not applied here -- it is a system-level
change to the GPU stack on a host holding a protected record, so it is the
user's call.

## Boundaries

No measurement in this campaign is affected. The recovery changes no serving
configuration, no quantisation, and no kernel. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
