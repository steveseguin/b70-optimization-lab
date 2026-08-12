# BF16 FFN shared activation conversion: exact win

Date: 2026-08-12

## Decision

Keep the default-off paired FFN projection path. It improves the exact
three-class BF16 TP4 comparator by 2.10% on top of the oneDNN primitive cache,
with identical generated-text hashes and accepted-token counts.

Drafter training remains closed by operator direction. No drafter weights or
training artifacts changed.

## Implementation

Source commit `5d28f39c7` detects adjacent BF16 `MUL_MAT` operations that read
the same contiguous F32 activation in a batch of 2 through 16 tokens. The
feature is default-off behind `GGML_SYCL_BF16_PAIR=1`.

The path converts the shared activation to BF16 once, then invokes the same
cached oneDNN BF16/BF16/F32 primitive separately for each projection. It does
not fuse, reorder, or replace either GEMM. On Muse this matches consecutive
FFN gate/up projections and removes one allocation plus one conversion kernel
per local FFN subgraph.

## Exact adjacent A/B

- source: `/home/steve/src/llama.cpp-muse-100` at `5d28f39c7`;
- isolated build: `build-sycl-b70-aot-bmg-g31-bf16mkl-icpx`;
- four Arc Pro B70 GPUs, tensor parallel, KV mirroring off;
- BF16 two-part target and stock BF16 DFlash drafter;
- greedy prose/code/JSON, 256 generated tokens, `cache_prompt=false`;
- both arms use `GGML_SYCL_DNNL_GEMM_CACHE=1`;
- only changed variable: `GGML_SYCL_BF16_PAIR=0/1`.

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| primitive-cache control | 44.073 | 63.730 | 77.519 | 61.774 |
| shared FFN conversion | 45.243 | 65.129 | 78.849 | 63.074 |
| improvement | +2.65% | +2.20% | +1.72% | **+2.10%** |

Output hashes were identical:

- prose: `914f754747d0edaa`;
- code: `cf2b2c4fd9e36fe5`;
- JSON: `4f813a9706abc163`.

Accepted-token counts were identical at 172 / 197 / 207. Prose draft
attempts differed by one (1172 control versus 1171 paired); code and JSON
attempts were identical.

Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/bf16-ffn-pair-ab-20260812.jsonl`;
- SHA-256 `88cace4b3e2d032d9c516c124e9d57f5ed17956add68f7a5f6b0df09c655dec2`.

Production was restored on the incumbent binary. The model list, cache-zero
512-token code canary, and red-image routing canary passed.

## Next action

The exact candidate mean is now about 63.1 tok/s, still far short of the
honest 100 tok/s goal. A source audit found that a DFlash top-k tree could be
target-exact but projects only about 1--5% and requires invasive server/KV
integration. Do not implement it as the primary lane.

Collect device event timing rather than host submission wall time, then target
the largest device-side verify operation or synchronization interval. The
existing host profiler shifts queue backpressure into later ADD/GLU calls and
cannot reliably rank device kernels.
