# Qwen3.8 Q8 collective RMS unroll5: neutral

Date: 2026-08-16  
Disposition: closed; not promoted

The accepted 5,120-element register-direct collective tail launches 1,024
work-items, so each work-item visits exactly five RMS elements. A template
specialization unrolled those five visits on both ranks while retaining each
thread's original element sequence and left-associated FP32 accumulation
order. The unchanged template remained the same-binary control, selected by
`GGML_SYCL_COMM_RMS_UNROLL5=0`.

The candidate mechanism smoke selected the new path, completed at
`37.086655 tok/s`, retained every promoted fusion, and reported
`VERIFY_MISMATCH=0`. The `p64/n256/r3` A-B-B-A bracket measured:

| Lane | Mean | Samples |
| --- | ---: | --- |
| control A1 | `36.672236` | `36.7248`, `36.5615`, `36.7305` |
| unroll5 B1 | `36.591258` | `36.5411`, `36.5124`, `36.7203` |
| unroll5 B2 | `36.652078` | `36.5717`, `36.6956`, `36.6889` |
| control A2 | `36.542427` | `36.5236`, `36.4805`, `36.6232` |

Pooled candidate throughput was `36.621668 tok/s` versus `36.607332` control,
only **`+0.039%`**. The candidate sits between the two controls, so the fixed
loop's address/branch savings are below end-to-end resolution. No endpoint run
was warranted. Accepted source and binaries were restored exactly after the
screen; no Xe compute fault, reset, hang, device-lost, or CAT error appeared.

The rejected patch is retained for recognition at
[`q8-collective-rms-unroll5-neutral-20260816.diff`](../patches/q8-collective-rms-unroll5-neutral-20260816.diff).
Structured evidence and raw hashes are in
[`2026-08-16-q8-collective-rms-unroll5-neutral.json`](../data/2026-08-16-q8-collective-rms-unroll5-neutral.json).
