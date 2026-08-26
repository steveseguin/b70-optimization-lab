# Qwen3.8 Q4_K_XL F16-KV TP1 cache64 graph curve result

The full cache64 SYCL-graph arm passed all seven Qwen3.8 UD-Q4_K_XL TP1,
MTP0, fit-off, F16-KV exact-depth HTTP serving cells:

| active context | decode tok/s |
|---:|---:|
| 0 | 23.20717810276497 |
| 2,048 | 22.822029963348005 |
| 4,096 | 22.66142475534695 |
| 8,192 | 22.267522660577832 |
| 16,384 | 21.45337721637781 |
| 24,576 | 20.760840745828116 |
| 32,768 | 20.3516257692428 |

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

The GPU workload and clean shutdown completed before the original composed R3
validator exposed an R2-only entry-path bug. Commit `2206b49cc` changed only
manifest/validator composition. The fixed validator then regenerated the
terminal receipt offline from the immutable raw root; no server or GPU workload
was relaunched. The original empty `validator.stdout.json` remains preserved
and hash-bound rather than being overwritten.

Raw evidence is retained at
`/mnt/fast-ai/bench-results/qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-20260826-r3`
(25 files). All 25 paths and SHA-256s, including terminal receipt
`008943ce0c41d63f2b2620a2785e0dc7f3cbd170c7b45d334eae9420aa771e9b`,
are preserved in the compact
[`result JSON`](../data/2026-08-26-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-r3-result.json).

Authority is narrow: publish these seven cache64 graph-on cells beside the
separate graph-off profile. Do not replace graph-off data, another selector,
any headline, the protected historical values, or a LocalMaxxing result.
