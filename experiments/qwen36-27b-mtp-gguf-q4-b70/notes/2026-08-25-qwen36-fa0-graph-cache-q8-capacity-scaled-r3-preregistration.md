# Qwen fa0 graph-cache Q8 capacity-scaled R3 repair

State: **preregistered; source applied; rebuild and GPU retry pending**.

The R3 parent candidate proved that the pointer-stable policy removed the
original queue-wait exception: two graphs recorded and replayed. It then filled
the single-graph budget of 320 stable Q8 memo slots before a third geometry
needed a 78,336-byte buffer.

This delta keeps the graph-off path exactly at its existing 320-slot bound and
retains its first-stale/ring/resize behavior. Only an active persistent graph
cache scales the bound: `320 * GGML_SYCL_GRAPH_CACHE_SIZE`. The frozen cache-eight
retry therefore has at most 2,560 slots. Reuse remains best-fit among stale
buffers already large enough; cached pointers are never resized or freed;
allocation failure and true exhaustion still abort closed.

The patch changes only `ggml-sycl.cpp`; `common.hpp` remains byte-identical. A
new backend identity and a distinct create-only parent campaign are required
before any curve. No speed, site, quality, record, or protected graph-off
replacement authority is granted by the patch or rebuild.
