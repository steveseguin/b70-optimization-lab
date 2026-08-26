# Qwen3.8 Q5_K_S F16-KV TP1 target HTTP depth/quality preregistration

This packet fills a serving-evidence gap, not a raw measurement gap. The exact
UD-Q5_K_S/F16-KV target-only depths `0/2K/4K/8K/16K/24K/32K` already have a
five-repeat `llama-bench` curve in
`../data/2026-08-22-qwen38-tp1-weight-ladder-sweep.json`. They do not yet have
the conventional HTTP 99-interval metric, cache-zero receipts, or a full
same-server-lifetime Qwen3.8 quality battery.

The packet changes only target KV K/V from `q8_0` to `f16` relative to the
passed Q5_K_S Q8-KV serving packet. The target artifact, llama.cpp binary and
effective DSOs, TP1/MTP0/graph-off/fit-off identity, exact depth fixture,
transport, response length, quality helper, tokenizer, and lifecycle policy
remain sealed. No draft model is loaded.

One fresh lifetime runs seven 128-token exact-depth requests followed by the
seven semantic canaries, two stable repeats, and long-context needle. Every
request must report zero cached tokens and cleanup must pass. There is no speed
floor and no Q8 output hash is transferred to F16.

A full pass authorizes only seven Grade-C target-only F16-KV HTTP serving cells
for this exact Qwen3.8 Q5_K_S TP1/MTP0/graph-off tuple. It authorizes no
speculative, Q8-KV, graph, TP2/TP4, prefill, headline, protected-value, or
LocalMaxxing claim. This preparation is inert and does not launch the GPU.
