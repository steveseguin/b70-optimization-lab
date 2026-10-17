# Packet 58: one-card IQ3 engine

CPU preparation in progress. No device result or speed claim exists yet.
Packet 56 is the immutable source baseline; packet 49 is the unchanged
`iq3-p49-split32-v1` oracle. All 48 target layers, head, full BF16 KV and
state use one selected card (0, or 2 under coordinator ownership).

The first milestone is plain greedy decoding. Target experts retain their
original packed bytes in pinned host memory and an 18 decimal GB device LRU
cache. Device kernels resolve each expert through a pointer table. The small
K1 window must establish host-USM access correctness and actual speed before
selecting zero-copy or copy-before-use misses. CPU fixtures do not establish
PCIe performance. Cache contents are immutable weights only; request state
and KV reset, and initial placement is content-independent.

Full host pinning and every device window belong to the coordinator. CPU
work uses nice 19, cores 4–15/20–31, Python -B, no model payload reads and
no large pinned allocations. Keep build output below 1.5 GB. Packet 57 and
all sealed parents are protected. No host setting, service or power change.

Credit Niko1221 / Strata for the hot-expert cache idea. This implementation
is independently written lab code; no external runtime code is imported.

The 1-GPU record is separate from the 2-GPU record. The local submission
ledger contains no submitted matching 1-GPU IQ3 record as inspected on
2026-10-17. The llama.cpp 15.9–21.6 tok/s reference is contextual evidence,
not a same-runtime exactness oracle or submitted record threshold.
