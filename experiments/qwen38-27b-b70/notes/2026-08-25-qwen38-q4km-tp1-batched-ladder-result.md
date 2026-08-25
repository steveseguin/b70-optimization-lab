# Qwen3.8 27B Q4_K_M TP1 raw batched ladder result

Date: 2026-08-25

Status: **complete raw-engine mechanism evidence; not quality-qualified
concurrent serving.**

Attempt 2 completed every preregistered point on one Arc Pro B70. The source
was reconstructed from the package's pinned base and six verified lab patches,
then built with Intel oneAPI 2026.1.1. Model SHA-256 was
`31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`.
The complete capture is
[`attempt2/summary.json`](../data/qwen38-q4km-tp1-batched-ladder-20260825-r1-attempt2/summary.json).

| parallel sequences | aggregate decode tok/s | per-sequence tok/s | prefill tok/s |
| ---: | ---: | ---: | ---: |
| 1 | 24.3636 | 24.3636 | 322.1 |
| 2 | 39.6218 | 19.8109 | 664.6 |
| 4 | 54.0811 | 13.5203 | 644.1 |
| 8 | 59.0889 | 7.3861 | 555.8 |
| 16 | 58.6969 | 3.6686 | 436.9 |
| 32 | 70.9999 | 2.2187 | 437.6 |
| 64 | **95.4118** | 1.4908 | 437.8 |

These are `speed_tg` rows produced directly by `llama-batched-bench`; the
per-sequence column is only `speed_tg / pl` for the same measured row. No
point is interpolated or extrapolated. This tool feeds random token IDs and
does not emit auditable model completions, so the table must not be called an
HTTP-user curve or a quality-qualified service result.

## Finding and next lever

The 64-sequence result is only 3.92x the one-sequence raw rate and is far below
the separate 875 tok/s research objective. Runtime banners explain the first
large, testable gap: this low-latency package build has
`GGML_SYCL_DNN=OFF`, making the source's Q4_K oneDNN weight-decompression GEMM
(WDC) unavailable. The current path remains oriented around MMVQ and the
existing fused Q4_K gate/up/SwiGLU kernel. Source comments carry prior
shape-level WDC measurements but not a Qwen3.8 end-to-end result; those numbers
are hypotheses for transfer, not evidence for this model.

The next bounded A/B therefore changes only the build/runtime doors needed for
Q4_K WDC, first at parallel 1 and 64. It must retain the DNN-off result as the
control, print an engaged WDC census, and remain research-only until a separate
endpoint run compares every concurrent output with its own sequential oracle.
