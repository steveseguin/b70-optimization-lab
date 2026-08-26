# Official Qwen3.8 FP8 TP1 bounded fit/depth R2

Status: **preregistered, not launched**. R2 supersedes the never-run R1 packet
without modifying it.

R19 showed why R1's `gpu-memory-utilization=0.98` cannot start on the observed
card state: 29.38 GiB was free while the requested budget was 29.69 GiB. R20
then showed that `0.96` passes the startup guard and loads the full official
FP8 checkpoint, although the compiled profile left negative KV capacity. R21
showed that enforce-eager removes that compile/graph residency and reaches a
healthy TP1 service. R21 itself used `0.968`; R2 deliberately keeps the
independently proven `0.96` budget and imports no R21 concurrency, context,
throughput, or opportunistic tuning.

Accordingly, the only configuration delta from R1 is `0.98 -> 0.96`. The
official revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, pinned image
`f01e24f6...eab1ba4f`, TP1/MTP0, FP16/auto KV, enforce-eager execution,
fixture, client, block/batch settings, descending 8K/4K/2K ladder, and frozen
interpretations remain identical. Campaign, output, cache, port, and container
identities are fresh R2 values.

All 66 USB weight files are complete-sized at preparation. Execution still
fails closed until the reused strict verifier reads every entire file through
O_DIRECT and then again through ordinary I/O with publisher hashes matching.
The packet never downloads or repairs weights.

Each fit arm gets a fresh server and fresh cache. The first successful arm
measures that exact depth and every smaller depth in the same lifetime. Larger
explicit fit failures may coexist with valid smaller Grade-C cells; explicit
failure at 2K closes this exact tuple as unsupported at 2K and above. An
unclassified startup failure remains inconclusive, while any post-boot receipt
or correctness failure publishes no cells from that lifetime. No result may
replace a headline, protected speed, TP2/TP4 cell, speculative cell, or
LocalMaxxing row.
