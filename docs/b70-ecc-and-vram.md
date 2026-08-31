# Intel Arc Pro B70 ECC And Usable VRAM

The Intel Arc Pro B70 has 32 GB of physical GDDR6 and supports memory ECC.
When ECC is enabled, some of that memory is reserved for error correction.
Intel documents the visible result as roughly **28 GB with ECC enabled** versus
the expected **32 GB with ECC disabled**.

For local LLM inference, turning ECC off can be a reasonable capacity trade:
the additional VRAM may let a model, a larger KV cache, or more concurrent
requests remain fully on the GPU. It is not a documented memory-bandwidth
overclock, and it removes memory error correction.

This is a hardware setting, not a model optimization. Stop GPU workloads before
changing it, and verify the state after reboot.

## Quick Decision

| Choose | When it makes sense | Trade-off |
| --- | --- | --- |
| ECC disabled | Local inference, model development, or benchmarking where the extra VRAM prevents OOM or offload | About 4 GB more usable VRAM, but no VRAM error correction |
| ECC enabled | Long unattended jobs, reliability-sensitive work, or diagnosing possible memory errors | Error correction and reporting, but roughly 28 GB rather than 32 GB visible |

ECC off does **not** make an already-fitting workload automatically faster.
Intel specifies the B70 at **608 GB/s** memory bandwidth regardless of the ECC
setting and does not publish a matched B70 ECC-on/off bandwidth benchmark. The
large performance difference comes indirectly when the additional capacity
avoids CPU/RAM offload, paging, an out-of-memory failure, a smaller KV cache, or
reduced concurrency.

## Check ECC On Linux

Intel's supported public Linux interface is XPU-SMI. Discover the device IDs
first; do not assume that the first B70 is always device 0:

```bash
xpu-smi discovery
```

Then inspect each B70:

```bash
xpu-smi config --device 0
xpu-smi config --device 1
```

Look for both fields under `Memory ECC`:

```text
Current: disabled
Pending: disabled
```

`Current` is the state in effect now. `Pending` is the state that should take
effect after the required reset or reboot. If they differ, do not describe a
benchmark as having the pending state yet.

## Disable ECC On Linux

Stop containers, inference servers, desktop applications, and other processes
using the selected GPU. Then change one explicitly identified device at a time:

```bash
sudo xpu-smi config --device 0 --memoryecc 0
sudo xpu-smi config --device 1 --memoryecc 0
sudo reboot
```

Only run the second command if device 1 is another B70 that you intend to
change. XPU-SMI also accepts a comma-separated device list, but explicit
per-device commands are easier to audit.

After reboot, run `xpu-smi discovery` and `xpu-smi config --device DEVICE_ID`
again. Do not rely only on the larger reported memory total; require `Current`
and `Pending` to both say `disabled`.

## Re-enable ECC On Linux

Use the same process with `1` instead of `0`, then reboot and verify:

```bash
sudo xpu-smi config --device 0 --memoryecc 1
sudo xpu-smi config --device 1 --memoryecc 1
sudo reboot
```

After reboot, both fields should say `enabled`. Re-enabling ECC reduces usable
capacity again, so re-check every model's VRAM budget before restarting it.

## Windows

Intel documents the Windows control in **Intel Graphics Software** under
**Graphics**. Stop GPU workloads, open the ECC setting, choose the desired
state, reboot if requested, and verify both the setting and reported VRAM after
the restart. Names and placement may move between driver releases; use Intel's
current support page rather than an old screenshot as the authority.

## What Changes, And What Does Not

- **Usable VRAM changes.** Intel documents approximately 28 GB visible with ECC
  on and the full advertised 32 GB with ECC off. Exact MiB/GiB values vary with
  reporting units and driver reservations.
- **Reliability changes.** ECC enabled can correct supported memory errors and
  is the conservative choice for reliability-sensitive or unattended work.
  Disabling it removes that protection.
- **The published bus and bandwidth specification does not change.** The card
  remains a 256-bit GDDR6 design rated at 608 GB/s. We have no controlled B70
  evidence that supports advertising an ECC-off bandwidth increase.
- **Model quality does not intentionally change.** The weights and arithmetic
  are unchanged, but an uncorrected memory fault can corrupt any computation.
- **Capacity-limited performance can change dramatically.** Keeping weights,
  KV cache, and active requests on GPU can be much faster than offloading or
  paging. That is a capacity effect, not proof of higher raw bandwidth.

## This Lab's Benchmark State

On **2026-08-30**, both B70s on the current two-card lab host reported:

```text
Memory ECC Current: disabled
Memory ECC Pending: disabled
Reported total memory: 32656 MiB per card
```

Recent benchmarks made on this host therefore used ECC disabled unless a run's
own artifact says otherwise. Older benchmark manifests did not always record
ECC state, so we will not retroactively claim that every historical result used
the same setting. Going forward, an ECC-sensitive result should record the
device IDs plus the `Current` and `Pending` fields in its hardware receipt.
The exact read-only observation is retained in
[`data/2026-08-30-b70-ecc-state.json`](../data/2026-08-30-b70-ecc-state.json).

## Troubleshooting

- If `xpu-smi` is missing, install a current Intel XPU Manager/XPU-SMI package
  supported by your driver stack before changing anything.
- If `--memoryecc` is not listed by `xpu-smi config --help`, do not invent an
  `xe` module option or copy an undocumented sysfs command. Update the supported
  management stack or ask Intel/system-vendor support for that platform.
- If `Pending` changes but `Current` does not, reboot. Intel notes that a device
  reboot may be required.
- If the setting is unavailable on a nominally supported card, check the board
  firmware, driver, XPU-SMI version, and system-vendor support. Intel notes that
  supported features can still depend on the complete system configuration.
- If a previously fitting model fails after ECC is enabled, reduce context,
  cache allocation, concurrency, or model size before assuming a runtime bug.

## Official References

- [Intel support: Arc Pro B-Series showing less VRAM](https://www.intel.com/content/www/us/en/support/articles/000102907/graphics.html)
- [Intel Arc Pro B70 specifications](https://www.intel.com/content/www/us/en/products/sku/245797/intel-arc-pro-b70-graphics/specifications.html)
- [Intel XPU-SMI `config` documentation](https://intel.github.io/xpumanager/2.0/xpu-smi/config.html)
