# Qwen3.8 Flash-Next FP8 TP4 BF16 allreduce LL-threshold preregistration

Date: 2026-08-30
Status: frozen before component execution

## Question

A28 contains 97 `[1,2560]` BF16 allreduces per target token. Each message is
5,120 bytes, just above pinned oneCCL's default 4,096-byte low-latency cutoff,
and every captured kernel uses `Rt64_128_PCIE`. Does raising only
`CCL_SYCL_ALLREDUCE_LL_THRESHOLD` to 8,192 select `Rt64_PCIE` and reduce
four-rank slowest-rank latency without changing any output byte?

## Frozen procedure

- no model load and no reboot;
- exact pinned A28 Python, torchrun, `libccl`, `libsycl`, `libfabric`, and CCL
  kernel identities;
- BF16 `[1,2560]`, four ranks, one row per rank;
- 50 warmups and 500 timed allreduces per process start;
- three fresh process starts per arm, alternating AB/BA order;
- control threshold 4,096; candidate threshold 8,192;
- exact integer-derived BF16 oracle and identical all-rank/cross-arm hashes;
- one post-timing Kineto receipt per rank proving control
  `Rt64_128_PCIE` and candidate `Rt64_PCIE`;
- report combined slowest-rank median, p95, p99, and maximum.

The arm is a component positive suitable for a later endpoint screen only if
all correctness and protocol receipts pass, candidate combined median improves
by at least 5%, at least two of three candidate trial medians beat their
same-index controls, and candidate combined p95 is no more than 5% worse. A
correct candidate below the median threshold is neutral; any receipt or oracle
failure is rejected. No outcome changes protected target-only or MTP results.

Frozen tool hashes:

- benchmark: `03a0f26757ece0481850402c587e760eadc1611f67bf6749da3e8a772ba65571`;
- launcher: `d9c5f2a3940df21907ea549e741229d56aa86bb04bec77a8d68fd83e5f4a6b85`;
- tests: `c843d4ab5b6d0eb79b0157405739fc97ef6d601aeacded198fdc6b5346fdb9b1`.
