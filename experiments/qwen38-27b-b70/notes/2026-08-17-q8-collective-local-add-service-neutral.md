# Qwen3.8 Q8 collective local-add staging

Date: 2026-08-17

Status: closed endpoint-neutral; do not repeat unchanged

The accepted register-direct TP2 tail rereads each 5,120-element post-residual
vector from global memory when it produces the next reordered Q8_1 activation.
This candidate copied those exact FP32 values into a 20 KiB workgroup-local
array during the already-required RMS pass, then quantized from the local copy.
It removed the second global read on both ranks and the intra-kernel global
fence on rank 1. Collective addition, RMS reduction, multiply, Q8 reduction,
FP32 stores, and weight kernels retained their accepted operation order.

The default-off `GGML_SYCL_COMM_DIRECT_Q8_LOCAL_ADD=1` door was live. A memo
verification smoke compared 4,950 Q8 buffers with zero mismatches. The fully
position-balanced `p64/n512/r3` gate was positive in both halves:

| Arm | Mean decode |
| --- | ---: |
| accepted behavior | `36.741151 tok/s` |
| local-add staging | `37.049130 tok/s` |
| pooled delta | **`+0.838240%`** |

The realistic service gate did not confirm that direct gain. Two 12-prompt
cache-zero suites were run on each same-binary arm. Cold process-state results
matched closely (`36.603594` treatment, `36.607733` control conventional).
The fair warmed comparison was:

| Metric | Control | Treatment | Delta |
| --- | ---: | ---: | ---: |
| conventional 99-interval median | `37.396195` | `37.405487` | `+0.02485%` |
| full decode median | `37.480080` | `37.489669` | `+0.02558%` |
| full wall median | `37.022969` | `37.024387` | `+0.00383%` |

All 48 endpoint outputs were hash-exact and cache-zero. The service deltas are
below resolution, so the added local-memory footprint and compiler-reported
three-register spill are not justified. Accepted source and library were
restored byte-for-byte; both B70s remained normal.

- candidate source SHA-256:
  `a76c2a14bc8d99446e342bc18d42503b0015fcf6576a28151bc9eb5f05937053`;
- candidate library SHA-256:
  `99a3bcb7607b4f4cae302dd63f3ae98731896c0c1ae6f8535feef62fff04ff4d`;
- exact compressed increment:
  [`../patches/q8-collective-local-add-service-neutral-20260817.diff.gz.b64`](../patches/q8-collective-local-add-service-neutral-20260817.diff.gz.b64);
- structured measurements:
  [`../data/2026-08-17-q8-collective-local-add-service-neutral.json`](../data/2026-08-17-q8-collective-local-add-service-neutral.json).
