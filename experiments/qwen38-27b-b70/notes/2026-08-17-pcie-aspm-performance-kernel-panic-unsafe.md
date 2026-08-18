# PCIe ASPM `performance`: unsafe kernel panic on dual B70/ReBAR host

Date: 2026-08-17 EDT

Status: **unsafe; never retry on this host or stack**

## Intent and immediate outcome

A reversible runtime-only PCIe latency experiment changed the global Linux
ASPM policy from the boot default to `performance`. Both B70s were idle and
runtime-suspended at the time. The policy change triggered a broken PCI resume
path before any candidate model workload ran.

Both Xe devices became inaccessible and SYCL reported no requested device.
Restoring the ASPM text policy to `default` did not recover the devices; the
host subsequently panicked and required a reboot. No benchmark result exists
and no performance inference is valid.

## Exact failure signature

Previous-boot kernel logs recorded both BDFs, `0000:03:00.0` and
`0000:e3:00.0`, failing D3 resume:

```text
Unable to change power state from D3hot to D0, device inaccessible
Unable to change power state from D3cold to D0, device inaccessible
UBSAN: array-index-out-of-bounds ... drivers/pci/iov.c:948:51
pci_restore_iov_state
UBSAN: shift-out-of-bounds ... include/linux/log2.h:57:13
pci_rebar_bytes_to_size
Runtime PM usage count underflow!
```

Affected stack:

- kernel `7.0.0-28-generic`;
- Xe driver;
- two ASRock Intel Arc Pro B70s;
- full 32 GiB Resizable BAR on each card;
- ASRock Rack TURIND8-2L2T BIOS 10.06.

After reboot, `/sys/module/pcie_aspm/parameters/policy` again selected
`default`, `xpu-smi discovery` reported both devices `normal`, and the new boot
contained no Xe fault/reset/hang.

## Permanent boundary

Do not change global ASPM policy, per-device PCI power controls, bind/unbind
state, PCI reset state, or related runtime power-management controls as part of
this optimization effort. Future work is restricted to userspace runtime and
isolated source/build experiments. A newer kernel does not automatically
authorize a retry; it would require a separate explicit safety decision.
