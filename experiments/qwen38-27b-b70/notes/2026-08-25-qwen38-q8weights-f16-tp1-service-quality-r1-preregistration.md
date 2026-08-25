# Qwen3.8 Q8_0/F16 TP1 service-quality r1 preregistration

This campaign closes the quality boundary left intentionally open by the exact
raw-engine depth curve. It uses the identical Q8_0 model, reconstructed
llama.cpp build, backend, one-B70 topology, F16 KV policy, and accepted runtime
doors. It changes the executable from `llama-bench` to the same build's pinned
`llama-server` solely to exercise the public OpenAI-compatible service path.

The gate is deliberately independent of the earlier Q4_K_M result. Q4_K_M and
Q8_0 are different weight quantizations, so exact cross-quant output parity is
not a promotion requirement. The frozen checks are instead seven deterministic
semantic canaries, eight same-seed repeat hashes, an approximately 8K-token
needle-recall request, and explicit zero cached prompt tokens on every response.
There is no speed floor and no performance claim in this campaign.

The local tokenizer copy is pinned by all three relevant file hashes and loaded
offline. This avoids making the run depend on the currently unreliable NFS
model share. The server uses one slot, 8192 context tokens, F16 K/V cache,
`--cache-ram 0`, `--ctx-checkpoints 0`, and reasoning disabled. A fit failure is
retained as an exact unsupported boundary; the runner must not silently lower
context, precision, or topology.

Frozen identity and classification rules are machine-readable in
[`../data/2026-08-25-qwen38-q8weights-f16-tp1-service-quality-r1-prereg.json`](../data/2026-08-25-qwen38-q8weights-f16-tp1-service-quality-r1-prereg.json).

