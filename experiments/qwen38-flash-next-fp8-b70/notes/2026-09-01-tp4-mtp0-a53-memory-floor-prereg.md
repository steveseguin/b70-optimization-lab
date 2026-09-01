# Qwen3.8 Flash-Next FP8 A53 memory-floor preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A53 is the attempt `53`/port `19725` successor to A52. Model, external
checkpoint, tokenizer, vLLM/kernel/runtime, TP4/EP4, MTP0, synchronous PLE-only
placement, full decode graph, graph-safe oneCCL `twoshots`, prompts,
authorities, and the complete losslessness battery are identical.

The sole runtime change is the loaded-state `MemAvailable` floor:
`28,000,000 KiB` becomes `16,000,000 KiB`. This is a meaningful margin below
the two observed healthy zero-PSI capture/init minima (`31,789,856` and
`27,980,704 KiB`) while remaining far above the prior host-freeze state of
roughly 1 GiB available plus exhausted disk swap. A53 still requires:

- at least `120,000,000 KiB` before launch;
- disk-backed swap disabled for the entire arm;
- bounded memory and I/O pressure;
- no fatal/recoverable link, OOM, or B70 fault report;
- the existing local-NVMe read/AER and root-port limits;
- exact isolated-path, endpoint, quality, authority, teardown, and postflight
  gates.

Loader behavior remains lazy/default. No reboot or per-boot load rule applies.

## Frozen packet

- derived launcher SHA-256:
  `76d687f8febdfa7393192471b9c324a0a2858c250af9f777d11fb9beceb5766d`;
- launcher SHA-256:
  `21d8847459900f60f496ae596effecdcd90cb0bff263b1cdb3fbee263010ab88`;
- client SHA-256:
  `5e1229459998d3aeea9d93268b5abc8bc783021446ecc0bad4a0daa07eab2005`;
- supervisor SHA-256:
  `59e00337ed0a9260261ca706e6f82147d8a659ca2f0072c8570932b7df080ad2`;
- privileged host wrapper SHA-256:
  `82c3a4efa88b0c87f90d02dd323c851c7eb4618a10f35cd0cc1d380e4395091a`;
- rewrite helper SHA-256:
  `6586651120d640c59132149500ad68c8a9218e91ff9d1f6e8f59be168a1b113d`;
- unchanged A48 runtime verifier SHA-256:
  `a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8`.

A valid result requires every inherited losslessness and performance gate.
