# Qwen3.8-27B Q4_K_M c16 TP1 reference/no-dedup replay: failed

The fresh no-dedup replay matched **13/16** frozen token-ID sequences. All completion, cache, isolation, collision, WDC-negative, kernel, and cleanup gates passed; its 15.78713643257908 tok/s rate is diagnostic only.

Q8 dedup changes trajectories but disabling it is not sufficient for exact reproducibility. The next control disables the remaining integration defaults together: general optimization, DNN routing, fusion infrastructure, MMQ, MMVQ pad/split, MKL direct, Q8 dedup, and Level Zero immediate command lists. This deep base profile is expected to be slow and exists only to establish a deterministic floor.
