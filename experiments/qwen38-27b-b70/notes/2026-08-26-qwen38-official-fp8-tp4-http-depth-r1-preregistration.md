# Qwen3.8 official FP8 TP4 exact-depth R1 preregistration

This packet fills the official-weight TP4 target-only context curve on the
resident `f01e24f6c7ff` vLLM/XPU image. It promotes the already-passed official
FP8 TP2 depth protocol to all four B70 cards without changing the model
revision, FP16 KV, MTP0 generation mode, size-one PIECEWISE graph, one-slot
service shape, exact-depth fixture, or measurement definitions.

The single create-only server lifetime measures exact active contexts
2K/4K/8K/16K/24K/32K. Every response must report the exact prompt count, 128
streamed output token IDs, cache zero, no truncation, and a positive 99-interval
decode rate. TTFT and the disclosed `active context / HTTP TTFT` prompt proxy
are retained for every cell. The repeated-token fixture is Grade C shape
evidence, not natural prose.

Before GPU launch the runner requires clean pushed `main`, exclusive host and
all-four-GPU locks, the immutable image ID, ext4 output, and the strict complete
ordinary plus O_DIRECT verification of all 66 weight files. Startup, capacity,
identity, or receipt failure publishes no cells and authorizes no same-campaign
retry. A changed topology, memory budget, graph, cache, or workload requires a
new preregistration.

These cells are additive. They cannot replace, lower, or reinterpret the
protected AutoRound TP4 short-decode results, and they authorize no MTP,
alternate-KV, concurrency, or LocalMaxxing claim.
