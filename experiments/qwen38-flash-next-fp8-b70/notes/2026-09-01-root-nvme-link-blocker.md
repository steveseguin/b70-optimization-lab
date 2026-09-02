# Qwen3.8 Flash-Next root-NVMe link blocker

Date: 2026-09-01
Status: GPU execution blocked pending physical/firmware maintenance and a clean
link-clearance receipt

## Finding

The repeated host freezes are not a Qwen model failure or a B70 failure. The
local root device is a `Samsung SSD 980 PRO with Heatsink 1TB` at PCIe Gen4 x4.
It repeatedly reports corrected physical-layer receive errors at endpoint
`0000:01:00.0`.

The W13 confirmation A1 made the boundary decisive. During an otherwise idle
admission window, the endpoint corrected counter changed from `345` to `346`
after about 21.6 seconds while the local-NVMe sectors-read counter remained
exactly unchanged. Swap use and memory-full PSI were zero, the root-port
corrected counter remained zero, and no GPU or component process had started.
The runner stopped and tore down cleanly.

Local controller evidence:

- installed firmware: `4B2QGXA7`;
- negotiated link: PCIe `16 GT/s x4`;
- ASPM: disabled/performance;
- temperature: 43 C at the audit;
- SMART critical warning: 0;
- media/data-integrity errors: 0;
- NVMe error-log entries: 0;
- percentage used: 4%.

This points to the PCIe endpoint/link path rather than NAND corruption. It also
means moving the checkpoint, caches, or temporary files cannot by itself make
the host safe: a corrected receive event occurred with zero storage reads.

## Required maintenance boundary

Do not mask AER reporting, raise event limits, or launch another full-model or
component GPU run from the current state. Before GPU work resumes:

1. back up the root SSD;
2. fully power off and reseat/inspect the 980 PRO, heatsink/thermal pad, M.2
   connector, and standoff; use another CPU-connected M.2 slot if practical;
3. update the drive offline from `4B2QGXA7` to Samsung's official current
   `5B2QGXA7` firmware with stable power;
4. cold boot and verify firmware, SMART, and Gen4 x4 negotiation;
5. require at least 30 minutes idle and a bounded read test with zero new
   endpoint or root-port corrected events before W13 A2 may execute.

The clearance receipt must be created and consumed in that same verified boot.
The fixed validator compares its boot ID to live `/proc` state and its root
controller identity to live sysfs: `nvme0`, serial `S6WSNS0T109768K`, model
`Samsung SSD 980 PRO with Heatsink 1TB`, BDF `0000:01:00.0`, and firmware
`5B2QGXA7`. A copied receipt from an earlier boot, or a receipt describing the
right firmware while the live drive still reports another revision, fails.
Validator SHA-256:
`2293b3588a275e15a630b813d7a273e650eb64c49eaacedcf212f99fe485d5a5`.
The live BDF is derived from the nearest PCI-function ancestor of the resolved
`/sys/class/nvme/nvme0` target and must also equal the controller's live
`address` attribute; the controller basename is not treated as a PCI address.

If errors persist, Gen3 x4 is a diagnostic/temporary discriminator, not a
performance fix. Persistence after reseat and firmware indicates the SSD,
slot, or motherboard path needs replacement/service.

## Prepared media; firmware not executed

The official updater ISO was downloaded to the external drive:

`/mnt/usb-models/tools/samsung-980-pro-firmware/Samsung_SSD_980_PRO_5B2QGXA7.iso`

- bytes: `28,311,552`;
- SHA-256:
  `4c02f7b5641c2b6ab6f0b43686f80b303a50a33e0da1abc6465c1ba6d2dc6e1c`;
- source:
  `https://semiconductor.samsung.com/resources/software-resources/Samsung_SSD_980_PRO_5B2QGXA7.iso`.

It was written to the 8-GB USB and read back exactly. The user then selected
that USB in UEFI, but the vendor image hung before its updater UI appeared; no
drive selection, updater execution, or firmware write occurred. Temporary UEFI
entries were subsequently removed and the original boot order was restored.
The verified modern-live fallback and its exact current state are recorded in
the [firmware-update preparation](2026-09-01-root-nvme-firmware-update-preparation.md),
which supersedes the earlier untouched-media statement without changing the
GPU block above.

Structured result:

`experiments/qwen38-flash-next-fp8-b70/data/20260901-root-nvme-link-blocker.json`
