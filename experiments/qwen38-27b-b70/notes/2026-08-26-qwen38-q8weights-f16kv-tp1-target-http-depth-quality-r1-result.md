# Qwen3.8 Q8_0 weights / F16-KV target HTTP depth + quality result

The current-weight Qwen3.8 27B Q8_0-weight target-only F16-KV lane passed all
seven TP1, graph-off, fit-off HTTP serving cells in one fresh server lifetime.
Conventional 99-interval decode measured:

| active context | decode tok/s |
|---:|---:|
| 0 | 15.717197487271713 |
| 2,048 | 15.458843096537539 |
| 4,096 | 15.230509805983916 |
| 8,192 | 14.775880887179762 |
| 16,384 | 14.007513353127061 |
| 24,576 | 13.321273594224953 |
| 32,768 | 12.6788728221903 |

Every depth request returned exactly 128 token IDs with zero cached tokens.
The compact result preserves each output-token hash, text hash, and raw receipt
hash. The x=0 point means zero prior active context plus one explicit ordinary
prompt token; positive points are exact submitted token depths. The
repeated-token fixture is Grade C context-shape evidence, not representative
natural prose.

The independent full Qwen3.8 quality battery passed: 7/7 exact semantic
canaries, 2/2 stable repeats with one output hash, the long-context needle at
25,200 pre-template prompt tokens (25,212 API-reported prompt tokens), and
10/10 cache-zero quality requests. All 16 terminal checks passed. Cleanup
closed the port and left the render node idle with no forced kill or surviving
server.

The exact artifact is `ggml-org/Qwen3.8-27B-GGUF` revision
`0669b98607d47046c7c2b3f801011d54a08cfccf`, Q8_0 model SHA-256
`f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`.
It ran llama.cpp commit `9fee29e9435f865ec0b811a783a6471a136d9317`
with `llama-server` SHA-256
`ff2441d012488e3cf7fc537a3e7c1a05fea9159043f3f3a0b257f6647e7c6964`.
The quantized artifact remains a subset of the current Qwen3.8 27B model
revision, not a separate model family.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q8weights-f16kv-tp1-target-http-depth-quality-20260826-r1`
(24 files). The terminal receipt SHA-256 is
`42d12af5440c63f7b0ae1c765e491df5a7bff7138c367916d6202b2ff45b1aad`.
The compact result is
[`../data/2026-08-26-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1-result.json`](../data/2026-08-26-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1-result.json).

Authority is narrow: these seven Q8_0-weight/F16-KV target-only cells may be
published with their Grade C fixture and full-quality disclosure. No Q8-KV,
other weight quantization, speculative, TP2/TP4, graph, prefill, concurrency,
headline, protected-speed replacement, or LocalMaxxing claim is authorized.
The next matched packet should qualify this exact Q8_0 artifact with Q8_0 KV.
