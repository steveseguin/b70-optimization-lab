# Qwen3.8 Q5_K_S F16-KV graph sentinel result

The bounded 8K TP1 graph sentinel failed closed on graph-mechanism evidence.
Correctness itself passed: both fresh server lifetimes accepted exactly 8,192
prompt tokens, generated exactly 128 tokens with zero cached tokens, and
returned identical token-ID and text hashes. Both servers also shut down
cleanly without a forced kill, open port, busy render node, or surviving
process.

The graph-off control measured `23.712998310490885` conventional 99-interval
decode tok/s. The graph-on/cache-8 candidate measured
`23.07605058705001` tok/s, a difference of `-0.636947723440876` tok/s or
`-2.686069956658%`. Speed was not the terminal gate, but the candidate did not
improve it.

The mechanism evidence was decisive. The candidate summary reported 146
requests, zero hits, 146 misses, 138 cache-full events, zero direct replays,
eight recorded/created graphs, and eight replays. Reject, unsupported, update,
and recreate counts were all zero. In other words, the eight initial graph
entries recorded and replayed once, no later request reused them, and every
request after the cache filled fell through. This failed the preregistered
positive-hit, positive-direct-replay, all-request-replayed, and zero-cache-full
gates. The underlying reason that every identity missed is not established by
this sentinel.

The exact model was `unsloth/Qwen3.8-27B-GGUF` revision
`4ca720788d1e01f1bff70c033e0d0028fd02e502`, UD-Q5_K_S SHA-256
`d8d62ffcf84d42658dd6ccf9782b4d0404700af78b26d750507510c7597b5bfe`.
Both arms used the same patched llama.cpp graph-port server based on
`fa0f3b25a47f346858a4d0d169f5181aa424b110`, server SHA-256
`b82fcfc3bda77b0446c11daa5da62b39ddf941202150d9b44a9092968658e19b`,
and graph backend SHA-256
`7d03bc06f46f188fd6ecd47034a878a2bd96d20a752a6a0731121176e101c8e2`.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-20260826-r1`.
The compact result records hashes for the identity, both exact-depth receipts,
server logs, arm statuses, cleanup receipts, and model probes:
[`../data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1-result.json`](../data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1-result.json).

This negative sentinel grants no graph cell, full-curve, full-quality, site,
estimate, protected-speed replacement, or submission authority. Stop graph
expansion on this patch/cache design. The independently qualified graph-off
F16 curve remains unchanged. Resume graph work only after a separately
preregistered mechanism fix can explain and eliminate the all-miss/cache-full
behavior; otherwise return to higher-priority coverage lanes.
