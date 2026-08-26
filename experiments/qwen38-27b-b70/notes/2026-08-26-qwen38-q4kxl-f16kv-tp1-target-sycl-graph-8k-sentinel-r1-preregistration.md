# Qwen3.8 Q4_K_XL/F16 TP1 HTTP SYCL-graph 8K sentinel

This create-only packet asks one narrow question before any graph depth-curve
expansion: on the retained, checksum-pinned SYCL graph runtime, does the
current-weight UD-Q4_K_XL model produce a real reusable HTTP graph at exact 8K
while remaining byte- and token-identical to a same-binary graph-off control?

The caution is concrete. The Q5_K_S sibling on this runtime produced 146 graph
misses, no hits or direct replays, and 138 cache-full events. Its output was
correct but its mechanism failed. Qwen3.6 `llama-bench` cache8 evidence cannot
answer the HTTP question because the request shapes differ. This packet does
not assume Q4_K_XL behaves differently; it is designed to fail closed if it
does not. The failed Q5 trace contains 18 non-decode requests before 128
generated-token requests. Qualified same-architecture nonzero-depth evidence
has two recurrent decode shapes, making cache20 the smallest evidence-derived
bounded candidate. The runtime supports up to 64, but this packet forbids
automatic escalation beyond 20.

Two fresh server lifetimes use identical model, binary, DSOs, source patches,
argv, fixture, F16 KV, fit-off, TP1, MTP0, and exact 128-token request. The only
deliberate delta is:

- control: `GGML_SYCL_ENABLE_GRAPH=0`, `GGML_SYCL_GRAPH_CACHE_SIZE=0`;
- candidate: `GGML_SYCL_ENABLE_GRAPH=1`, `GGML_SYCL_GRAPH_CACHE_SIZE=20`.

A pass requires exact output text, token IDs, usage, returned-prompt hash, and
cache-zero parity. It also requires positive graph requests, cache hits, and
direct replays, including at least 120 of each; consistent
request/hit/miss/replay accounting; and zero
compatibility rejection, device-unsupported, cache-full, update, or recreate
events. Speed has no floor and cannot rescue a failed mechanism.

Even a pass authorizes only preregistration of a seven-depth graph curve. It
publishes no cell and does not authorize MTP, TP2/4, prefill, headline or
protected-speed replacement, estimates, or LocalMaxxing submission. A failure
stops full-curve expansion on this exact graph design.

Default invocation is inert. Execution requires a clean pushed `main`, idle
GPU0, the shared lock set, an absent create-only output root, and the exact
acknowledgement embedded in the manifest.
