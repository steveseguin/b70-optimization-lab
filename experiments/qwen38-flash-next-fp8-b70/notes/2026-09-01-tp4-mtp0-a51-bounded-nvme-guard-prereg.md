# Qwen3.8 Flash-Next FP8 A51 bounded-NVMe-guard preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A51 is the fresh attempt `51`/port `19723` successor to A50. Model,
checkpoint, vLLM/kernel/runtime, TP4/EP4, MTP0, synchronous PLE-only placement,
graph, `twoshots`, prompts, authorities, and the complete losslessness battery
are identical. It retains the external 131-shard checkpoint.

The sole behavioral change is the host-storage interpretation. The root wrapper
now records local-NVMe read sectors alongside endpoint/root AER. The launcher,
one-second supervisor, and postflight require:

- root-port corrected count unchanged;
- local endpoint corrected count monotonic and delta no greater than `64`;
- local NVMe read-sector delta no greater than `8,388,608` (4 GiB);
- no journal report with fatal/recoverable severity, uncorrected error, DPC,
  link-down, or controller-down wording;
- the inherited swap-off, ASPM-performance, memory/PSI, process, listener, and
  four-B70 gates.

The prior exact-zero rule is not retained because A50 observed a corrected
event with exactly zero local-NVMe read-sector movement. All events and counters
remain evidence; the new bounds are safety limits, not a waiver.

## Frozen packet

- derived launcher SHA-256:
  `c2469e79014a3827391605f168a562495ad39976188954340803ef2cf31a3442`;
- launcher SHA-256:
  `1513d8e952b85d4ce6a4ef19f9c5cbefeab56d620ebe34f8ae4a4cffdd520a2f`;
- client SHA-256:
  `673f396e14176f229efd856b1a0c7c8b527912bd7bb0345bd57036a4db5d66ff`;
- supervisor SHA-256:
  `0928175d9716caf1537fe8dbf11b1e323abd6cd0496d329b732722ef47caeea1`;
- privileged host wrapper SHA-256:
  `32233dec06891fb3ff7b4db42769ed240886959cb875f5ff5453e4960bca428b`;
- rewrite helper SHA-256:
  `6b0d874cb3eb4f6a801dab6c06d0e01cc1770b92651a3dae52d2bed60386287b`;
- unchanged A48 runtime verifier SHA-256:
  `a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8`.

A valid result still requires every inherited quality and exact-output gate.
No reboot or one-load-per-boot rule applies.
