# Qwen3.8 Flash-Next FP8 A61 bundled-oneCCL control: kernel soft lockup at worker init

Date: 2026-09-02 15:32--16:45 EDT, boot `95bac684-...`, GuC 70.72.1
Status: operational interruption; the oneCCL hypothesis was not tested; host
requires a reboot

## Timeline

- 15:31:06--15:31:10: A60 teardown after its engine hang; the kernel logged
  GPU page faults on all four B70s (`Fault response: Unsuccessful -ENOENT`
  and `-EINVAL`, repeated), the host wrapper failed its postflight (exit 70)
  and restored swap/ASPM; `xpu-smi` still enumerated four devices and the
  render nodes were idle.
- 15:32: A61 launched detached (bundled oneCCL, no public preload, eager,
  tuned map). Host wrapper preflights passed; all four workers initialized
  (`world_size=4` at 15:35:46); the last server-log lines at 15:35:43 are the
  workers selecting the Triton FP8 MoE backend, i.e. the start of weight
  loading and PLE offload.
- 15:40 onward: kernel `hung task` warnings every two minutes, then
  `watchdog: BUG: soft lockup` on CPUs 10, 13, 14 for `VLLM::Worker_TP`
  PIDs 161453, 161699, 162005 (stuck 3755 s by 16:42:57) and on CPU 7 for
  `kworker/7:1` (3386 s); over 1,000 call traces since 15:30, taint flags
  `W L`. The launcher's PLE-offload receipt check timed out
  (`FAIL: workers did not each report exact 11.92-GiB selective offload`);
  its teardown sent SIGKILL, which is still pending on the four workers
  (`ShdPnd` includes SIGKILL) while they remain `R` in the kernel; the
  EngineCore is a zombie. Load average 32, CPU pressure 88%, 90 GB of host
  memory held, swap not restored (wrapper never reached its EXIT path).
- 16:45: `ps`, `sudo`, and `dmesg` stall; `/proc/<pid>/status` and sysfs
  reads still work; the root SSD counters are 0; the external drive mount
  responds.

## Interpretation

A61 never served a request, so it says nothing about the public-oneCCL
hypothesis. What it shows is that the GPU state left behind by A60's page
faults was not usable: the next four-GPU initialization on the same driver
instance locked up in the kernel. This matches the lab's July observation
that a wedge poisons subsequent runs until the driver is reloaded. Rule
going forward: after any run that ends with `Fault response` lines in the
kernel log, reload the xe driver (unbind all four B70s, `modprobe -r xe`,
`modprobe xe`) or reboot before the next launch; do not chain arms.

## Recovery

Reboot. After boot: verify BIOS 2.4a, GuC 70.72.1, Gen4 root SSD with zero
corrected events, four B70s with 32 GB BARs, remount the Corsair drive with
`ntfs-3g -o allow_other,default_permissions,uid=1000,gid=1000`, reapply the
B70 runtime power policy, then relaunch A61 (fresh attempt number) as the
first and only GPU job.
