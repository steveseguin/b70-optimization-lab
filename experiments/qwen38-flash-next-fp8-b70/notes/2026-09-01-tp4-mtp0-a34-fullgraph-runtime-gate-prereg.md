# Qwen3.8 Flash-Next FP8 A34 full-graph runtime-gate preregistration

Date: 2026-09-01
Status: frozen before model load

A34 is the exact A33 successor after A33 reached a healthy full-graph endpoint
but sent zero requests due to a redundant runtime-verifier check. It changes
only:

- attempt 33 to 34, port 19705 to 19706, and all dependent no-clobber paths;
- runtime verification from exact `LD_PRELOAD` string equality to the live
  process-map authority: every collective process must map only the pinned
  public libccl with the exact digest, and any declared different libccl
  preload path is rejected.

Official model/revision, current source receipts, accepted staged runtime,
TP4/EP4, MTP0, synchronous PLE-only UVA placement, 4,352-token capacity,
128 MiB KV cache, untuned MoE, public oneCCL protocol, compilation mode NONE,
size-1 `FULL_DECODE_ONLY`, request order, full quality battery, protected
hashes, teardown, and interpretation are A33-exact. This boot is healthy and
reusable; no per-boot load rule and no reboot requirement exists.

A pass remains a candidate until a separately started exact repeat. Any graph
use, output, quality, health, or runtime-map failure is preserved as a negative
without changing protected results.

## Frozen files

- successor rewriter: `3dfd9bf23e83cd63fdb8eb1d367d9c601bc55d333ba4952869ffa5c778b60a7e`;
- runtime verifier: `679512374ece0b5ee48d9f48185e2abd24e251fe6dfcceb6eb891e545ef28747`;
- verifier tests: `065a53081dcb635e8047925087579e18f3908e04c79525e712d00e7c3a5fd760`;
- launcher: `6a2629debf63dc63c759d6c6eea34897ff7a0cc17b709febb1a7078499151531`;
- client: `cf9b044839c5027f57bc74982328adf969c131921aba3b222704b269285da247`;
- supervisor: `2b5e8dcf7e1ea2030b4f4a4083318f30ff35d2db7caaed83981e2123f7daf607`;
- generated inner launcher: `ca84bb3d2a5d7792313c9ee1584b9da2dbe06bc32b148a4fa31c43fd224e2033`.
