# Qwen3.8 Flash-Next FP8 A52 memory-floor preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A52 is the attempt `52`/port `19724` successor to A51. Model, external
checkpoint, tokenizer, vLLM/kernel/runtime, TP4/EP4, MTP0, synchronous PLE-only
placement, full decode graph, graph-safe oneCCL `twoshots`, prompts,
authorities, and the complete losslessness battery are identical.

The sole runtime change is the one-second supervisor's loaded-state
`MemAvailable` floor: `32,000,000 KiB` becomes `28,000,000 KiB`. A51 reached
`31,789,856 KiB` during graph capture with zero swap and zero memory PSI, so the
old floor was a narrow false stop. A52 retains the `120,000,000 KiB` initial
launch floor, disabled disk-backed swap, memory/IO pressure checks, bounded
local-NVMe read/AER policy, root-port and journal checks, isolated paths,
teardown, and four-card postflight.

The safetensors loading strategy remains lazy/default. Explicit prefetch or
eager loading is not introduced because the `172.78 GiB` checkpoint cannot fit
in the available host RAM during the four-rank load.

## Frozen packet

- derived launcher SHA-256:
  `1dc280fb680dec39a4c11ec7fa77193e197249b3804ea1b9493116bfe1d281a2`;
- launcher SHA-256:
  `05c8e37372870d66322c9d071eb9fd4c31a73e4b33035568baa8bda3f8807707`;
- client SHA-256:
  `23341580a10daedc64ff9993f3be103103d5e90cb7353e877334ca38985529a4`;
- supervisor SHA-256:
  `f3bc6139446c04797f9235bf9e7d5b269aff25606f18ba1d3f7ba802a8c42d59`;
- privileged host wrapper SHA-256:
  `33472abe3b64161f62c5aaffb6f419132e21ae051b8a1554224bc4c8405cfaf3`;
- rewrite helper SHA-256:
  `21fdc5cc0b94a08b0992fbe93679bbcb8b991f2bf1da1584059bf2fac9ccfa3a`;
- unchanged A48 runtime verifier SHA-256:
  `a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8`.

A valid result requires every inherited quality, exact-output, graph-runtime,
storage, host, and postflight gate. No reboot or per-boot load rule applies.
