# Qwen3.8-27B Q4_K_M TP2 WDC feasibility r1 — preregistration

At c64, Q4_K weights are above the MMVQ/MMQ windows and use dequantize-to-F16
plus GEMM. The source has a Q4_K oneDNN weight-decompression-on-compute path,
but the earlier Qwen tests were TP1 and exhausted per-card memory before an
engaged B64 result. TP2 halves weight residency per card, so this exact
question remains open.

This is a two-process raw mechanism screen, not performance evidence for the
website. Both arms use the same WDC-capable binary, force the same Q4_K nibble
plane, and disable q6_K reorder. Only `GGML_SYCL_WDC_Q4K` changes from 0 to 1.
The candidate must complete, prove WDC engagement in the census, and beat the
matched control by at least 5%. Otherwise the route closes without an HTTP
build. If it passes, it earns only a server build and a separately
preregistered output/quality campaign.

The full frozen contract is
[`2026-08-30-qwen38-q4km-tp2-wdc-feasibility-r1-prereg.json`](../data/2026-08-30-qwen38-q4km-tp2-wdc-feasibility-r1-prereg.json).
