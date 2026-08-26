# Qwen3.8 Q4_K_XL F16-KV target HTTP depth + quality result

The current-weight Qwen3.8 27B UD-Q4_K_XL target-only F16-KV lane passed all
seven TP1, graph-off, fit-off HTTP serving cells in one fresh server lifetime.
Conventional 99-interval decode measured:

| active context | decode tok/s |
|---:|---:|
| 0 | 21.826326109162604 |
| 2,048 | 21.311674949425424 |
| 4,096 | 20.87064005039118 |
| 8,192 | 20.01988162715276 |
| 16,384 | 18.641111109262432 |
| 24,576 | 17.370272845612092 |
| 32,768 | 16.387443320790123 |

Every depth request returned 128 token IDs with zero cached tokens. The x=0
point means zero prior active context plus one explicit ordinary prompt token;
positive points are exact submitted token depths. The repeated-token fixture is
Grade C context-shape evidence, not representative natural prose.

The independent full Qwen3.8 quality battery also passed: 7/7 exact semantic
canaries, 2/2 stable repeats with one output hash, the long-context needle at
25,200 pre-template prompt tokens (25,212 API-reported prompt tokens), and
10/10 cache-zero quality requests. Cleanup passed without a forced kill, open
port, busy render node, or surviving server.

The exact identity was `unsloth/Qwen3.8-27B-GGUF` revision
`4ca720788d1e01f1bff70c033e0d0028fd02e502`, UD-Q4_K_XL model SHA-256
`3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`,
running llama.cpp commit `9fee29e9435f865ec0b811a783a6471a136d9317` with
`llama-server` SHA-256
`ff2441d012488e3cf7fc537a3e7c1a05fea9159043f3f3a0b257f6647e7c6964`.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-20260826-r1`
(24 files). The terminal receipt SHA-256 is
`7686c8e460e3a45a81b625833b561de091e4db3fd0c2b3fac2f2cbbaca26731c`.
The compact result is
[`../data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-r1-result.json`](../data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-r1-result.json).

Authority is narrow: these seven F16-KV target-only serving cells may be
published with their Grade C fixture and full-quality disclosure. No Q8-KV,
speculative, TP2/TP4, graph, prefill, concurrency, headline, protected-speed
replacement, or LocalMaxxing claim is authorized. The next packet should
qualify the same Q4_K_XL artifact with Q8_0 KV before publishing a matched KV
comparison.
