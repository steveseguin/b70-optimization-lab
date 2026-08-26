# Qwen3.8 Q5_K_S target-only HTTP depth + quality result

Completed at `2026-08-26T04:05:13.661492+00:00`, the current-weight Qwen3.8
27B UD-Q5_K_S target-only lane passed all seven
TP1, graph-off, fit-off, Q8_0-KV HTTP serving cells in one fresh server
lifetime. Conventional 99-interval decode measured:

| active context | decode tok/s |
|---:|---:|
| 0 | 22.485360956826327 |
| 2,048 | 20.880043911731846 |
| 4,096 | 19.585282238140003 |
| 8,192 | 17.50471579785839 |
| 16,384 | 14.048644681829956 |
| 24,576 | 11.822951271745719 |
| 32,768 | 10.214448950905807 |

Every depth request returned 128 token IDs with zero cached tokens. The 8K
output hash exactly matched the sealed target-only sentinel parent. The x=0
point means zero prior active context plus one explicit ordinary prompt token;
the positive points are exact submitted token depths. The repeated-token depth
fixture remains Grade C context-shape evidence rather than representative
natural prose.

The separate full Qwen3.8 quality battery passed: 7/7 exact semantic canaries,
2/2 stable repeats with one output hash, the long-context needle at 25,200
pre-template prompt tokens (25,212 API-reported prompt tokens), and 10/10
cache-zero quality requests. The server then shut down cleanly without a forced
kill, open port, busy render node, or surviving process.

The exact identity was `unsloth/Qwen3.8-27B-GGUF` revision
`4ca720788d1e01f1bff70c033e0d0028fd02e502`, UD-Q5_K_S model SHA-256
`d8d62ffcf84d42658dd6ccf9782b4d0404700af78b26d750507510c7597b5bfe`,
running llama.cpp commit `9fee29e9435f865ec0b811a783a6471a136d9317` with
`llama-server` SHA-256
`ff2441d012488e3cf7fc537a3e7c1a05fea9159043f3f3a0b257f6647e7c6964`.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q5ks-q8kv-tp1-target-http-depth-quality-20260825-r1`
(24 files). The terminal receipt SHA-256 is
`2290101bbcf4a98af5758b7ab3b8eeb102ac4732b1f868ec8a08509cdcf456b6`.
The compact result with per-cell output hashes and raw-artifact hashes is
[`../data/2026-08-25-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1-result.json`](../data/2026-08-25-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1-result.json).

Authority is deliberately narrow: these seven target-only serving cells may be
published with their Grade C fixture and full-quality disclosure. The result
authorizes no speculative, TP2/TP4, prefill, concurrency, headline,
protected-speed replacement, or LocalMaxxing claim. Next, publish only these
seven cells, keep the failed external-MTP routes non-promotable, and continue
filling current-weight Qwen3.8 quantization, MTP, and topology gaps through
separate preregistered runs.
