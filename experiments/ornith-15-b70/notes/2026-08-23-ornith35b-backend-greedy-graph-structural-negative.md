# Ornith 1.5 35B-A3B: backend-greedy output-head fusion audit

Date: 2026-08-23 EDT

Status: **CLOSED STRUCTURAL NEGATIVE — no throughput claim**

Ornith 1.5 is Qwen-derived, so the older Qwen Q6_K output-head/top-1 work was
reviewed as a possible transfer. That patch is not an exact drop-in: it
quantizes the activation to Q8 and relies on a large expanded weight pack. A
safer exact implementation would first need the output projection and greedy
`ARGMAX` to coexist in the same SYCL graph.

The accepted 11-feature Ornith build was run with llama.cpp's stock
`--backend-sampling --temp 0` path. Its canonical continuation was byte-exact
with the accepted oracle:

`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`

A temporary, default-off diagnostic then inspected every graph submitted to
the SYCL backend and printed the full node list whenever any
`GGML_OP_ARGMAX` node was present. No trace line fired during active prompt
and decode execution. The accepted Ornith fusion counters did fire (for
example, 30 Q/K-normalization-plus-RoPE hits in the short diagnostic run), so
this is not an idle or failed-run observation.

The sampler's output is transferred through llama.cpp's host-visible output
buffer and scheduler boundary before top-1 selection. Consequently, the
desired output-head-to-argmax edge does not exist inside the current SYCL
graph and cannot be fused by adding another local SYCL graph matcher. Doing
this exactly would require a deliberate llama.cpp runtime/output/sampler
plumbing change. The old approximate Q8-activation Qwen kernel should not be
ported blindly.

The diagnostic patch is archived at
`../patches/llamacpp-ornith15-backend-greedy-graph-trace-structural-negative-20260823.patch`.
It is evidence only, not a performance patch. The short cold CLI rate printed
in the raw transcript is not a matched benchmark and is intentionally not a
performance claim. The accepted source and all four published binaries were
restored byte-exact after the audit.

The machine-readable decision and artifact hashes are in
`../data/2026-08-23-ornith35b-backend-greedy-graph-summary.json`.
