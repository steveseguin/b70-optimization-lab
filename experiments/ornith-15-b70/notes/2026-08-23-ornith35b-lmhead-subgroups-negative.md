# Ornith 1.5 35B-A3B: smaller output-head workgroups regress

Date: 2026-08-23 EDT

Status: **CLOSED ENGINE NEGATIVE — do not ship**

Ornith's Qwen-derived Q6_K output head has the exact reordered decode shape
`[248320,2048]`. Its stock SYCL kernel packs 32 independent row subgroups into
each workgroup. A narrow default-off candidate tested 16 and 8 subgroups per
workgroup without changing any row's Q6_K reads, accumulation, 32-lane
reduction, or FP32 output store. Prefill and every other projection were
excluded by the exact single-column shape guard.

The aggressive eight-subgroup form produced the canonical forced 128-token
transcript SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
All accepted feature hit counts remained intact.

The engine ladder was monotonically negative:

| subgroups/workgroup | llama-bench tg128 tok/s | σ |
| ---: | ---: | ---: |
| 32 (control) | **121.575727** | 0.921494 |
| 16 | **121.233438** | 1.096587 |
| 8 | **121.087152** | 1.016793 |

The best candidate is already 0.28% below control. No mirrored or server test
was justified. This differs from the earlier four-row-reuse experiment: the
candidate changed only workgroup occupancy, not activation reuse or row
arithmetic.

The incremental source is preserved at
`../patches/llamacpp-ornith15-lmhead-subgroups-negative-20260823.patch.gz.b64`;
decode with `base64 -d | gzip -dc`. Raw rows and structured exactness/result
records are under `../data/2026-08-23-ornith35b-lmhead-subgroups-*`. The
accepted package remains unchanged.
