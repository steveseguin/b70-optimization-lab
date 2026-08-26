# Qwen3.8 Q4_K_XL/F16-KV TP1 graph cache20 R2 result

Date: 2026-08-26

## Outcome

The cache20-aware R2 sentinel passed. The matched graph-off and graph-on arms
both completed the exact 8K HTTP workload, passed every exact-depth gate,
reported `cached_tokens=0`, produced identical output token IDs, text, usage,
and returned-prompt identity, and cleaned up without a forced kill, surviving
server, open port, or busy render node.

The result binds the launch at clean pushed `main`
`d289862088af4b2141e746238a5e746f888ee3fa`, the current-weight Qwen3.8 27B
`UD-Q4_K_XL` artifact, the llama.cpp/SYCL graph runtime and patch chain, and
all 16 files in the raw root by exact path, byte size, and SHA-256. The raw
terminal receipt and validator stdout are byte-identical.

## Mechanism evidence

Graph-off reported every graph counter and its cache limit as zero. Graph-on
reported `requested=146`, `cache_hit=126`, `cache_miss=20`,
`direct_replay=126`, `recorded=20`, `created=20`, `cache_entries=20`,
`cache_limit=20`, and `replayed=146`. There were zero compatibility rejects,
unsupported requests, cache-full events, updates, or recreations. The
conservation checks all pass:

- `requested == cache_hit + cache_miss == replayed`;
- `cache_hit == direct_replay >= 120`;
- `cache_miss == recorded == created == cache_entries == 20`.

This establishes that cache20 retained and directly replayed the recurrent
Q4_K_XL decode graph with exact graph-off output parity.

## Adverse speed observation

The graph-off arm measured `22.902203617586807 tok/s`; graph-on measured
`22.270342658906237 tok/s`, or `-2.758952672114734%` relative to control.
This is an adverse observation from one mechanism sentinel, not a speed claim.
No speed floor was preregistered, and neither arm has site-cell, headline,
protected-value, or LocalMaxxing authority.

## Authority

The exact terminal authority authorizes only a separately reviewed full graph
curve preregistration. It authorizes zero site cells and does not authorize a
full curve by itself, MTP/speculation, TP2/TP4, prefill, protected/headline
replacement, or a LocalMaxxing submission. The protected historical decode
values remain unchanged.

Evidence and validation:

- compact result:
  `experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-result.json`;
- read-only validator:
  `experiments/qwen38-27b-b70/scripts/validate-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-result.py`;
- preserved raw root:
  `/mnt/fast-ai/bench-results/qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-20260826-r2`.
