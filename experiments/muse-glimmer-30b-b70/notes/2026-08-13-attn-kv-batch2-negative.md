# Muse attention K/V oneDNN batch=2: rejected

Date: 2026-08-13

## Experiment

Source commit `c3bd0eac2` added a default-off Muse graph-lifetime dependency
that prevented raw K and V projection outputs from aliasing. Composed with
`GGML_SYCL_DNNL_ATTN_BATCH2=1`, the existing strict planner then issued one
strided oneDNN batch=2 GEMM for K/V. The first-hit marker confirmed execution
at `m=128 n=2 k=6656`; the ordinary gate/up batch=2 path also remained active.

## Result

The canonical 64-token smoke measured:

| class | candidate tok/s | adjacent control tok/s | candidate/control |
|---|---:|---:|---:|
| prose | 68.336 | 68.865 | 0.9923x |
| code | 114.103 | 114.636 | 0.9954x |
| JSON | 188.476 | 222.053 | 0.8488x |
| arithmetic mean | **123.638** | **135.185** | **0.9146x** |

All final 64-token hashes remained canonical. Prose/code proposal counts also
matched the control, but JSON changed from `58 accepted / 65 drafted` to
`57 / 77`. The batched oneDNN K/V projection therefore perturbed target
features enough to change later DFlash proposal history and produced a large
JSON throughput regression. It is not a byte-stable or performant target
kernel replacement.

Evidence:

- config:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-attn-kv-batch2-smoke64.json`;
- JSONL:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-attn-kv-batch2-smoke64-20260813.jsonl`,
  SHA-256 `49cba275c5bd52b5ff2167c19da5cf14e0afd2855a115ae4951adcd127cccc12`;
- server log:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-dflash-attn-kv-batch2-smoke64-20260813-attn-kv-batch2.log`,
  SHA-256 `57e233ebb1427a6454ea9a54a6ab742b15ced7990bc68845d0d527958dc87b78`.

## Decision

Preserve and revert. The graph-lifetime change costs memory, changes the
proposal path, and loses throughput. Keep only the separately confirmed
gate/up batch=2 kernel.
