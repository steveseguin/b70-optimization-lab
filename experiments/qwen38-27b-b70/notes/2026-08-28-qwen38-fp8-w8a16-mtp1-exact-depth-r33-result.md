# Qwen3.8 official FP8 TP2 W8A16 MTP1 exact-depth R33 result

R33 closes the qualified MTP1 profile's 32K gap. The exact deterministic
compiled MTP1 image loaded with 33,024-token capacity and measured all six
preregistered points. Every request returned 128 token IDs, reported
`cached_tokens=0`, passed the exact-depth receipt gates, and matched the
corresponding qualified MTP0/W8A16 target array exactly.

| Exact active context | Decode tok/s | HTTP TTFT | Prompt/TTFT proxy |
| ---: | ---: | ---: | ---: |
| 2,048 | `44.778323` | `799.096 ms` | `2,562.897 tok/s` |
| 4,096 | `54.932011` | `1,186.647 ms` | `3,451.743 tok/s` |
| 8,192 | `51.313834` | `2,342.895 ms` | `3,496.528 tok/s` |
| 16,384 | `51.289810` | `4,868.555 ms` | `3,365.270 tok/s` |
| 24,576 | `43.715435` | `7,586.022 ms` | `3,239.642 tok/s` |
| 32,768 | **`46.636241`** | **`10,487.181 ms`** | **`3,124.576 tok/s`** |

The directly measured 32K value may populate the MTP1 package's 32K cell. It
does not replace the separately qualified `51.918757 tok/s` varied-prompt
headline. This exact-depth suite is Grade-C repeated-token context-shape
evidence, not natural prose, retrieval, task quality, or LocalMaxxing evidence.
No x=0 value is fabricated and no point is interpolated or extrapolated.

Across the six requests, the server reported 336 accepted of 429 drafted
tokens (`78.32%`). The first 2K request triggered one-time Triton JIT warnings
for two draft-preparation kernels during inference. Its observed `44.778323`
value is retained honestly; it was not rerun warm or replaced. The prompt-rate
column is exactly submitted prompt tokens divided by observed HTTP TTFT and
includes scheduling, chunked prefill, and first-token work.

The runtime was the qualified r32 image
`sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b`
with deterministic Inductor, XPU Graph off, the packed-two-row RMS replay,
TP2, FP16/auto KV, one slot, and 4,096 max batched tokens. All 66 model files
passed direct and ordinary verification before launch. The service shut down
cleanly and the port and container were absent afterward.

Evidence:

- [compact result](../data/2026-08-28-qwen38-fp8-w8a16-mtp1-exact-depth-r33-result.json)
- [tracked raw receipts and runtime log](../data/qwen38-fp8-w8a16-mtp1-exact-depth-20260828-r33/)
- [preregistration](2026-08-28-qwen38-fp8-w8a16-mtp1-exact-depth-r33-prereg.md)
- [qualified strict MTP1 result](2026-08-28-qwen38-fp8-mtp1-deterministic-r32-result.md)
