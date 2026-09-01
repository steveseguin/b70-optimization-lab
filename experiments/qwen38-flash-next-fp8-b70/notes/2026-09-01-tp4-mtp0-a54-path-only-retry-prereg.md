# Qwen3.8 Flash-Next FP8 A54 path-only retry preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A54 is the single allowed exact retry after A53's rank-1 post-load profile
failure. It changes only attempt `53` to `54`, port `19725` to `19726`, and the
corresponding run, cache, compile, RPC, temporary, supervisor, and lifecycle
paths. Model, external checkpoint, tokenizer, source/runtime/kernel identities,
TP4/EP4, MTP0, synchronous PLE-only placement, full decode graph, graph-safe
oneCCL `twoshots`, the `16,000,000 KiB` loaded-state memory floor, prompts,
authorities, diagnostics, and the complete losslessness battery are unchanged.

No reboot or per-boot load rule applies. A54 must pass the ordinary host,
storage, source, four-card, pressure, link, endpoint, quality, repeat,
performance, teardown, and postflight gates. If the same post-load
profile/dispatch failure repeats, no A55 endpoint retry is allowed without
report-only startup instrumentation or a bounded component reproduction.

## Frozen packet

- derived launcher SHA-256:
  `7b4d1c9b2b07aad4c43fea7b03a9cb881559775bb4aeb1010b1a9f5b5ac2729e`;
- launcher SHA-256:
  `9c89ff47eb8a46efa0b3fcec50114f8f46743e489536ec344731bce5b83e22a1`;
- client SHA-256:
  `959a5c7b1ac9c8b28e59a90dada2bd11a81e1f9b87dc42bd55ba463bb054a82c`;
- supervisor SHA-256:
  `54db6272267468f51cb7d6eb41a2915b674ed9e0d2ff347c091d0e0b99d77a86`;
- privileged host wrapper SHA-256:
  `82d676349b0b4fdf90ad7874afe8ae1e01ec3f6b8b9f4c46d39bf35a5d5d2be3`;
- rewrite helper SHA-256:
  `3079a75ad7ef05e6533e19127db6e5def87540355687b9707c09f80cb6f60f3d`.
