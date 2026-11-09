# Receiving-host build check — Own Xe engine (2026-11-08)

The 2026-11-08 developer handoff ("validation was on this computer; the
receiving machine still needs its build checked") is closed for this host.

## Gates

- CPU unittest gates (DEVELOPING.md set): `test_source_bundle`,
  `test_prepare`, `test_launch_plan`, `test_placement` — all OK.
- `build.py` → `/home/steve/ownrt-build-20261108/`: all 40 translation units
  compiled and linked, exit 0. Binary `own-engine` (30,493,296 bytes),
  SHA-256 `1a98d865c000f58bc27003b71606164268742b38836b296dd34efb2fb9a245f4`.
  Receipt: `/home/steve/ownrt-build-20261108/build-receipt.json`.

## Deviation from the guide (recorded, not silently absorbed)

- Guide's observed compiler: oneAPI DPC++ **2026.0.0**. This host has 2025.3
  and **2026.1.1** only; the build used
  `/opt/intel/oneapi/compiler/2026.1/bin/icpx` (2026.1.1.20260724). Per
  DEVELOPING.md, a different compiler version needs its own validation: this
  check is compile/link only, no GPU execution, no model qualification.
- JIT default retained (no `--aot-target`): consistent with today's separate
  finding that oneAPI 2026.1 AOT SYCL segfaults at first kernel
  (intel/llvm#23395, hit during llama.cpp reference bring-up).
- `readelf -d` NEEDED: libsycl.so.9, libze_loader, libcrypto, libstdc++ —
  all present on this host.

No model weights, GPU admission, services or host settings were touched.
Existing kernels and research files preserved; only new notes/planning
artifacts were added (see commits `1dd2dd565` and this note's commit).
