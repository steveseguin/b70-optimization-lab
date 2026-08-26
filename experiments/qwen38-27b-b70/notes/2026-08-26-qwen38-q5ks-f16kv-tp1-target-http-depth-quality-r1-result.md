# Qwen3.8 Q5_K_S F16-KV target HTTP depth + quality result

The current-weight Qwen3.8 27B UD-Q5_K_S target-only F16-KV lane passed all
seven TP1, graph-off, fit-off HTTP serving cells in one fresh server lifetime.
Conventional 99-interval decode measured:

| active context | decode tok/s |
|---:|---:|
| 0 | 22.617348746656774 |
| 2,048 | 22.072826293347987 |
| 4,096 | 21.51247483924336 |
| 8,192 | 20.699622782660835 |
| 16,384 | 19.116902989029395 |
| 24,576 | 17.847541304863622 |
| 32,768 | 16.72668172192112 |

Every depth request returned 128 token IDs with zero cached tokens. The x=0
point means zero prior active context plus one explicit ordinary prompt token;
the positive points are exact submitted token depths. The repeated-token depth
fixture remains Grade C context-shape evidence rather than representative
natural prose.

The separate full Qwen3.8 quality battery independently passed: 7/7 exact
semantic canaries, 2/2 stable repeats with one output hash, the long-context
needle at 25,200 pre-template prompt tokens (25,212 API-reported prompt
tokens), and 10/10 cache-zero quality requests. The server then shut down
cleanly without a forced kill, open port, busy render node, or surviving
process.

The matched Q8_0-KV sibling is useful context, not borrowed authority. F16 KV
was faster at all seven depths: from +0.587% at x=0 through +63.755% at 32K.
The exact 128-token output hashes matched at 2K, 4K, and 16K, and differed at
x=0, 8K, 24K, and 32K. Both KV modes passed their own full batteries, so these
differences are recorded as KV-precision-dependent output behavior, not as a
corruption finding. No Q8 speed, hash, quality, or site authority transfers to
this result, and no F16 authority transfers back to Q8.

The exact identity was `unsloth/Qwen3.8-27B-GGUF` revision
`4ca720788d1e01f1bff70c033e0d0028fd02e502`, UD-Q5_K_S model SHA-256
`d8d62ffcf84d42658dd6ccf9782b4d0404700af78b26d750507510c7597b5bfe`,
running llama.cpp commit `9fee29e9435f865ec0b811a783a6471a136d9317` with
`llama-server` SHA-256
`ff2441d012488e3cf7fc537a3e7c1a05fea9159043f3f3a0b257f6647e7c6964`.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q5ks-f16kv-tp1-target-http-depth-quality-20260826-r1`
(24 files). The terminal receipt SHA-256 is
`4ec596d510ec9854e77ecb56aacd18763c68386512c0e9df3a77c3f902a81bd9`.
The compact result with per-cell output hashes and raw-artifact hashes is
[`../data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1-result.json`](../data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1-result.json).

Authority is deliberately narrow: these seven F16-KV target-only serving cells
may be published with their Grade C fixture and full-quality disclosure. The
result authorizes no Q8-KV, speculative, TP2/TP4, graph, prefill, concurrency,
headline, protected-speed replacement, or LocalMaxxing claim. Next, publish
the two KV curves distinctly and continue filling current-weight Qwen3.8
quantization, MTP, graph, and topology gaps through separate preregistered
runs.
