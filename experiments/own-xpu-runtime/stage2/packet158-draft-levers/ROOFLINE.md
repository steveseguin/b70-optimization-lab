# Per-draft byte reference and measured gaps

Scope: packet122 cyclic replay;128 occupied tokens;two processes. This is diagnostic evidence, not a speed result.

| Rank | Group | Useful bytes | /537 GB/s ms | Measured ms | Signed gap ms |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | routed_experts | 77,726,542.0 | 0.144742 | 0.307689 | +0.162947 |
| 2 | input_norm_embedding_mix | 39,774,088.0 | 0.074067 | 0.184503 | +0.110435 |
| 3 | attention | 425,248.0 | 0.000792 | 0.088526 | +0.087734 |
| 4 | attention_projections | 102,962,432.0 | 0.191736 | 0.232592 | +0.040856 |
| 5 | final_norm | 13,257,600.0 | 0.024688 | 0.054807 | +0.030119 |
| 6 | argmax_publication | 160,300.0 | 0.000299 | 0.026355 | +0.026057 |
| 7 | shared_expert | 9,863,690.0 | 0.018368 | 0.041962 | +0.023594 |
| 8 | head_gemv | 256,574,976.0 | 0.477793 | 0.445348 | -0.032446 |

Host issue: packet154 control median **1.571 ms/cycle**, not a ninth additive GPU kernel; no GPU roofline/gap applies. See [source map and arithmetic](SOURCE-MAP.md).

The head reads 3,200 useful bytes per row but retains a 3,380-byte storage stride. Its negative signed gap is evidence that a copy-bandwidth reference is not a hard latency floor. Do not promote a negative gap to a speedup.

The useful-byte model omits repeated cache-served reads, scratch traffic, metadata/control traffic and instruction costs. In particular hidden projection has four independent input vectors; 13,107,200 unique weight bytes correspond to 52,428,800 logical weight-byte loads before cache/compiler reuse. The attention byte model is a K/V union, not the repeated loads by 24 query heads. No compute ceiling is borrowed from a different precision.

All group times are means of complete per-step event sums; class medians are never added. The two historical processes each contribute 40 non-warmup replays. They are cyclic-input operator diagnostics, not cold prompt results. Source hashes and individual process rows are in [roofline.json](roofline.json).

## Historical context sensitivity

| Group | 128-token time ms (P1 / P2) | 128-token gap ms (P1 / P2) | 4096-token time ms (P1 / P2) | 4096-token gap ms (P1 / P2) |
| --- | ---: | ---: | ---: | ---: |
| input_norm_embedding_mix | 0.184380 / 0.184625 | 0.110313 / 0.110558 | 0.201875 / 0.201625 | 0.127807 / 0.127558 |
| attention_projections | 0.232560 / 0.232625 | 0.040823 / 0.040889 | 0.242622 / 0.242068 | 0.050886 / 0.050331 |
| attention | 0.088526 / 0.088526 | 0.087734 / 0.087734 | 0.609992 / 0.609922 | 0.601391 / 0.601320 |
| routed_experts | 0.307451 / 0.307927 | 0.162709 / 0.163185 | 0.310127 / 0.310758 | 0.165385 / 0.166015 |
| shared_expert | 0.041982 / 0.041943 | 0.023614 / 0.023574 | 0.042057 / 0.042039 | 0.023689 / 0.023671 |
| final_norm | 0.054823 / 0.054791 | 0.030135 / 0.030103 | 0.054859 / 0.054825 | 0.030171 / 0.030137 |
| head_gemv | 0.445336 / 0.445359 | -0.032457 / -0.032434 | 0.445435 / 0.445456 | -0.032358 / -0.032337 |
| argmax_publication | 0.026378 / 0.026333 | 0.026079 / 0.026035 | 0.026422 / 0.026328 | 0.026123 / 0.026030 |

These are the two measured context points. No interpolation or extrapolation is a measurement. Live packet157 positions, when available, price analytical bytes only; their time must come from their own events.
