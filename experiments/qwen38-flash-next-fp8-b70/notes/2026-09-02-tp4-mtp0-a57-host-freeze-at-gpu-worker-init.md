# Qwen3.8 Flash-Next A57: host freeze at four-GPU worker initialization (2026-09-02)

Date: 2026-09-02 11:38--11:43 EDT
Status: operational interruption; no probe data; the freeze class is now
separated from the root-SSD link

## Timeline

- 11:36--11:38: after the agent session's background task was killed (which
  took the first A57 launch down with it), the killed attempt's run, cache,
  compile, RPC, and state paths were preserved or cleared and A57 was
  relaunched detached (`setsid nohup`).
- 11:38:32: host wrapper started (swap off, ASPM performance, AER baselines).
- 11:38:35--11:39:16: launcher preflights passed: filesystem, four-XPU
  discovery and stats, staged runtime, and the `xccl` TP4 preflight
  (barrier and allreduce OK on all four ranks).
- 11:39:19: server started; identity written.
- 11:39:27: last server-log line, `Enabled custom fusions: norm_quant,
  act_quant`. In A56 the EngineCore's DP-leader line followed this point by
  8 s and the four workers' `world_size=4` lines by 16--30 s.
- 11:39:33: last one-second host-pressure sample on the external drive:
  `MemAvailable 124,692,152 KiB`, swap 0, all PSI `avg10=0.00`--`0.22`, no
  paging.
- The root-SSD journal's last entry is 11:38:46 (journald syncs lazily, so
  that is not the freeze time). No kernel warning, oops, lockup, MCE, or AER
  message exists for the window. The BMC event log has no entry. This boot's
  kernel reports `Previous system reset reason: system reset pin
  BP_SYS_RST_L was tripped`, i.e. the user pressed reset at 11:43.

The host therefore froze between 11:39:33 and roughly 11:39:45, during
EngineCore/worker start-up: device initialization, `torch.distributed` XCCL
initialization with `CCL_TOPO_P2P_ACCESS=1`, and PLE UVA allocation across
the four B70s.

## Why this is a different failure class from the SSD

- BIOS 2.4a, Gen4 x4, endpoint and root-port corrected counters `0` for the
  whole boot and for this boot so far; the validated Gen4 clearance and
  three GPU component runs preceded the freeze in the same boot.
- Memory, swap, and pressure were clean at the last sample.
- No storage activity is involved at the freeze point (weights had not
  started loading).

The earlier journal-less freezes (A46 after graph capture, the dense
component screen, A48-era) all coincided with GPU activity as well; the SSD
link errors were real and are fixed, but they were not the whole story.

## Standing GPU-firmware discrepancy

Every boot of this kernel (`7.0.0-30-generic`) logs, per B70:

```
GuC firmware (70.54.0) is recommended, but only (70.44.1) was found in xe/bmg_guc_70.bin
```

- installed: Ubuntu `linux-firmware 20240318.git3b128b60-0ubuntu2.27`,
  `xe/bmg_guc_70.bin` 70.44.1 (`b95b0d18...`), HuC 8.2.10;
- pending Ubuntu candidate `...0ubuntu2.29`: byte-identical Battlemage GuC
  file (same SHA-256), so the package upgrade does not help;
- upstream linux-firmware (kernel.org, fetched 13:52 EDT to
  `/mnt/usb-models/tools/intel-xe-firmware/`): `xe/bmg_guc_70.bin`
  **70.72.1** and `xe/bmg_huc.bin`, both same major ABI (70.x / 8.x).

A 2026-08-04 note in this lab already tied the four-B70 collective wedge
class to this GuC gap. Installing the upstream GuC/HuC is the first
corrective action to try; it is a system change and is staged behind
`tools/install-upstream-xe-firmware.sh` (dry-run by default) for explicit
authorization. The xe module can be reloaded in place by unbinding the four
B70s, or the host can be rebooted; either way the clearance receipt must be
regenerated if the boot changes.

## What was lost

A57's depth-determinism probe never ran. Its packet and probe remain frozen
and can be relaunched at attempt 58 after the firmware decision; the
run/cache/compile/RPC paths of both the killed and the frozen A57 attempts
are preserved with `.killed-session-...` / `.frozen-host-...` suffixes.
