# Qwen3.8 Q5_K_S F16-KV TP1 cache64 graph curve result

The full cache64 SYCL-graph arm passed all seven Qwen3.8 UD-Q5_K_S TP1,
MTP0, fit-off, F16-KV exact-depth HTTP serving cells:

| active context | decode tok/s |
|---:|---:|
| 0 | 23.98574798250926 |
| 2,048 | 23.643697282911955 |
| 4,096 | 23.42530742694006 |
| 8,192 | 23.004461687671654 |
| 16,384 | 22.216618358249068 |
| 24,576 | 21.508310356102303 |
| 32,768 | 21.023067722865875 |

Every request returned 128 token IDs with zero cached tokens. The x=0 point
means zero prior active context plus one explicit ordinary prompt token;
positive points are exact submitted token depths. This repeated-token fixture
is Grade C shape evidence, not representative natural prose.

The full natural-language battery passed independently: 7/7 exact cases, two
stable repeats with one hash, the 25,200-token pre-template needle, and 10/10
cache-zero quality requests. Graph telemetry passed the frozen mechanism gate:
947 direct replays versus the 896 minimum, cache size and limit 64, 1,182
requests, 64 created entries, zero compatibility/device rejects, and conserved
counters. Cache64 is the source-supported maximum; there is no automatic
capacity escalation beyond it.

The native terminal validator completed during the original campaign. Its
terminal receipt is `completed-valid-q5ks-f16kv-graph-cache64-depth-quality`
with all 19 checks true, and clean shutdown passed. No offline recovery, server
restart, or GPU rerun was needed.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-20260826-r1`
(25 files). All 25 paths and SHA-256s, including terminal receipt
`cb5cc3254971a321050f947baae00ce0d360c9e7ce88056adca3d35f9ed91016`,
are preserved in the compact
[`result JSON`](../data/2026-08-26-qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-result.json).

Authority is narrow: publish these seven cache64 graph-on cells beside the
separate graph-off F16/Q8_0 profiles. Do not replace graph-off data, another
selector, any headline, the protected historical values, or a LocalMaxxing
result.
