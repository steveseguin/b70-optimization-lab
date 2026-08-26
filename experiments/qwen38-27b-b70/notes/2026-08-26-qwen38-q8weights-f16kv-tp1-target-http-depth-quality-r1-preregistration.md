# Qwen3.8 Q8_0-weight/F16-KV TP1 HTTP depth/quality preregistration

This packet closes a serving-metric gap for the current-weight ggml-org Q8_0
artifact. The exact F16-KV target-only depths `0/2K/4K/8K/16K/24K/32K`
already passed a five-repeat raw `llama-bench` curve, and the same artifact
selectors separately passed the Qwen3.8 service-quality battery at 8K. Neither
record is an exact HTTP depth curve on the sealed current serving runtime.

The packet changes only the target weight artifact relative to the passed
Q5_K_S/F16-KV HTTP sibling. Runtime binary and complete local DSO closure,
fixture, clients, tokenizer, TP1/MTP0/graph-off/fit-off selectors, F16 K/V,
transport, response length, and lifecycle remain sealed. No draft is loaded.

One fresh lifetime runs seven 128-token exact-depth requests and then the full
quality battery: seven semantic canaries, two stable repeats, and the 27.2K
needle. Every response must report zero cached prompt tokens. There is no speed
floor, and no speed or output hash transfers from another quantization.

The 28.6 GB GGUF was rotated out after the earlier measurements and is absent
at preparation time. Execution therefore has an additional fail-closed
preflight: the exact size and full SHA-256 must match before locks, output-root
creation, or GPU checks. Restoring or downloading the artifact is outside this
packet's authority.

A full pass authorizes only seven Grade-C Q8_0-weight/F16-KV target-only HTTP
cells for this exact tuple. It authorizes no other weights, Q8 KV, speculative,
graph, TP2/TP4, prefill, headline, protected-value, or LocalMaxxing claim. The
default action is inert and does not launch the GPU.
