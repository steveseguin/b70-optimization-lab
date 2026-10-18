# Packet125: one-card expert miss transport

CPU-only preparation under the owner's 2.5-hour brief. No device, model,
service, sudo, live queue or host setting is touched. Frozen packets remain
unchanged. Initial pull refused unrelated dirty work; fetch confirmed HEAD
`b84606017f41c5447fe925efd330bbe44a52637e` equals origin/main.

The retained packet58k production screen has **33.0051 misses and 65.456571 MB
of logical missing expert bytes per charged token**, including 30.417455 MB
of down weights. Its mean step is 39.9414 ms. Cache planning, copying and
publication takes 7.1072 ms, overlapping other timers. Neither isolated PCIe
read time nor device compute time was recorded; zeros are profiling-disabled
placeholders. These are the 1,188 generated positions 2–100 from all twelve
requests, not an inferred hardware traffic measurement. Packet58g's matching
record has the same miss counts; its timing is a separate identity.
[Receipt analysis](../experiments/own-xpu-runtime/stage2/packet58n-onecard-loo/ANALYSIS.md).

Production kernels dereference pinned USM pointers on cache misses. The host
has separate per-layer gate/up/down banks. Rows are 820/1100/360 bytes;
complete projections are 524,800/704,000/921,600 bytes. After the whole position,
the missing experts are copied again into the cache on an explicitly selected
copy-only Level Zero ordinal, three copies per expert. There is no demand-copy
before computation in the zero-copy mode. The allocator calls `malloc_host`
without an explicit requested alignment; actual addresses were not retained.
Device cache slots are aligned to 256 bytes. Source: frozen 58j `main.cpp`,
`single_device.cpp`, `cache_table.hpp`, `p49d_expert.hpp`.

The retained K1 all-host useful rates are 13.964/14.026 GB/s for production,
17.561/17.468 for tile16. Tile16 groups neighboring rows' code/scale reads
and changes workgroup scheduling; it is not just a transpose of consecutive
reads. It already has a separate pending one-card screen. Sparse misses and
whole-token gains cannot be linearly inferred from these ten-expert fixtures.

Read-only sysfs shows all four CPU-facing root ports at 16 GT/s ×16, and
Intel upstream bridges at 16 GT/s ×16 (bridge capability 32 GT/s ×16).
Internal downstream bridges and endpoints expose 2.5 GT/s ×1; this does not
describe the external slot link. Unprivileged lspci denies capability access.
[Full path snapshot](../experiments/own-xpu-runtime/stage2/packet125-miss-transfer/evidence/pcie-links.json).

The current layer's routes are unavailable before its router completes.
Exact copies cannot overlap the previous layer using still-unknown routes.
Useful overlap candidates are current-layer resident work and gate/up while
DOWN copies run. Every copy must finish before its own consumer, and original
route slots, arithmetic and packet49 oracle remain fixed.

Packet100b retained actual accepted routes for two short prompts. All 64
steps are replayed through frozen packet58's position-end 18 GB cache policy;
checkpoints 1/16/32/64 include all 48 layers, yielding 384 cases, 119 with no
miss, and 945 misses (1,872,102,400 bytes). **These masks are simulated cache
state on real routes, not observed packet58 misses.** No packet58 route IDs
exist to reconstruct the latter. Cold initial-cache cases are retained.
[Replay](../experiments/own-xpu-runtime/stage2/packet125-miss-transfer/prepare_routes.py).

Next: compile the small route-driven transfer/unchanged-expert micro, CPU
check it and ship only a proposed lane-B queue. Two fresh processes must each
reach at least 1.5× useful miss bandwidth with byte equality before any engine
copy or whole-host proposal is prepared. No speed result is claimed.
