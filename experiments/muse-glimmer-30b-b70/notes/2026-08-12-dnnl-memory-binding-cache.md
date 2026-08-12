# oneDNN GEMM memory-binding cache: exact win

Date: 2026-08-12

## Decision

Keep and stack the default-off oneDNN memory-binding cache. On top of the
primitive cache, it improves the exact three-class BF16 TP4 comparator by
1.62%, with identical generated-text hashes and accepted-token counts.

Drafter training remains closed by operator direction. No drafter weights or
training artifacts changed.

## Implementation

Source commit `c57964390` extends each cached oneDNN GEMM entry with reusable
source, weight, destination, and scratchpad memory objects plus its argument
map. On each call it only rebinds the current USM pointers with
`set_data_handle` before executing the same cached matmul primitive.

The feature is default-off behind
`GGML_SYCL_DNNL_GEMM_BIND_CACHE=1` and requires the existing
`GGML_SYCL_DNNL_GEMM_CACHE=1`. It does not change descriptors, data types,
primitive selection, or the device kernel.

## Exact adjacent A/B

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| primitive-cache control | 44.381 | 64.936 | 78.544 | 62.620 |
| memory-binding cache | 45.470 | 66.150 | 79.300 | 63.640 |
| improvement | +2.45% | +1.87% | +0.96% | **+1.62%** |

Output hashes were identical:

- prose: `914f754747d0edaa`;
- code: `cf2b2c4fd9e36fe5`;
- JSON: `4f813a9706abc163`.

Accepted-token counts were identical at 172 / 197 / 207. Prose draft
attempts differed (1168 control versus 1172 candidate); code and JSON attempts
were identical.

Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dnnl-memory-bind-cache-ab-20260812.jsonl`;
- SHA-256 `ea435178eafadf1a13065e2a55fa88e44795bed4b58452c415e79d4ebfc55651`.

Production was restarted on the incumbent binary after the test. The next
measurement must test the exact stack—primitive cache, memory-binding cache,
and shared FFN conversion together—rather than add separate A/B percentages.
