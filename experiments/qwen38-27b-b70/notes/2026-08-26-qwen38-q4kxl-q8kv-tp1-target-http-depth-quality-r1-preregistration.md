# Qwen3.8 Q4_K_XL Q8_0-KV target HTTP depth + quality preregistration

This packet changes one serving selector from the passed Q4_K_XL/F16-KV
sibling: target KV K/V become `q8_0`. It retains the exact Qwen3.8 current
weights, Q4_K_XL model hash, llama.cpp build and local DSO closure, TP1,
MTP0/target-only routing, graph off, fit off, 33,024-token capacity, cache and
checkpoint isolation, seven exact active-context depths, 128 generated tokens,
and the full quality battery.

The run is create-only and inert by default. Execution requires the exact
acknowledgement and a clean pushed `main`. It binds the passed F16 result and
terminal receipt by SHA-256, but borrows no speed, token hash, quality, or site
authority from F16. The historical Q8_0 raw-engine curve is fit/shape evidence
only and likewise transfers no serving authority.

A complete pass authorizes exactly seven Grade C target-only Q4_K_XL/Q8_0-KV
HTTP serving cells at 0/2/4/8/16/24/32K plus their own quality disclosure. It
authorizes no F16, other quantization, speculative, graph, TP2/TP4, prefill,
concurrency, headline, protected-speed replacement, or LocalMaxxing claim.

Campaign: `qwen38-q4kxl-q8kv-tp1-target-http-depth-quality-20260826-r1`.
Output root:
`/mnt/fast-ai/bench-results/qwen38-q4kxl-q8kv-tp1-target-http-depth-quality-20260826-r1`.
