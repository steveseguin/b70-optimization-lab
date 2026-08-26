# Qwen3.8 Q4_K_XL Q8_0-KV target HTTP depth + quality result

The current-weight Qwen3.8 27B UD-Q4_K_XL target-only Q8_0-KV lane passed
all seven TP1, graph-off, fit-off HTTP serving cells in one lifetime:

| active context | decode tok/s |
|---:|---:|
| 0 | 21.769202757569552 |
| 2,048 | 20.267185566421563 |
| 4,096 | 19.088507810265277 |
| 8,192 | 17.118296247131028 |
| 16,384 | 13.830939568896348 |
| 24,576 | 11.64708116811193 |
| 32,768 | 10.07665400680413 |

All depth requests returned 128 token IDs and zero cached tokens. The
independent full battery passed 7/7 exact canaries, 2/2 stable repeats, the
25,200-token long-context needle, and 10/10 cache-zero quality requests.
Cleanup passed without a forced kill, open port, busy render node, or survivor.

Against the separately qualified same-artifact F16 sibling, F16 was faster at
all seven depths: +0.262% at x=0, rising to +62.628% at 32K. Exact 128-token
hashes matched at x=0, 4K, 16K, and 32K and differed at 2K, 8K, and 24K. Both
KV modes passed their own full batteries, so this is recorded as
precision-dependent behavior, not corruption.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q4kxl-q8kv-tp1-target-http-depth-quality-20260826-r1`
(24 files); terminal receipt SHA-256 is
`de0d7ac0485fc03b492dc21e0557e66b22d14189953644346ada3c63f7ede64c`.
The compact result is
[`../data/2026-08-26-qwen38-q4kxl-q8kv-tp1-target-http-depth-quality-r1-result.json`](../data/2026-08-26-qwen38-q4kxl-q8kv-tp1-target-http-depth-quality-r1-result.json).

Authority is exactly seven Grade C Q4_K_XL/Q8_0-KV HTTP cells and their own
quality disclosure. It grants no F16, other-quantization, MTP, graph, TP2/TP4,
prefill, concurrency, headline, protected-speed, LocalMaxxing, or submission
claim.
