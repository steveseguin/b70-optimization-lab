# Qwen3.6 Q4_K_M q8_0-KV TP1 exact-depth result

Date: 2026-08-25. Status: **r2 passed; seven raw-engine cells ready**.

The fresh r2 campaign completed all fourteen `llama-bench` rows, and the
exact-depth parser accepted every declared depth. The checksum-pinned model,
runtime, shared libraries, selectors, four locks, new create-only root, and
repaired process classifier matched the preregistration. Cleanup passed and
the kernel window contained no XPU reset, device-lost, OOM, or fault evidence.

| active context | decode tok/s | prefill tok/s |
| ---: | ---: | ---: |
| 0 | 28.427444 | 824.618443 |
| 2K | 25.907235 | 884.563514 |
| 4K | 23.996142 | 865.761332 |
| 8K | 20.918488 | 823.096859 |
| 16K | 16.167457 | 756.105791 |
| 24K | 13.301100 | 698.561985 |
| 32K | 11.375246 | 648.263152 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. These are target-only raw-engine shape measurements,
not HTTP serving rates, and this campaign ran no new model-quality battery.

R1 remains a failed-closed diagnostic because its frozen post-run process
census matched evidence filenames. R2 used a new root and reran every row; the
on-disk terminal receipt explicitly records `r1_rows_reused=false`. The
transient command stdout retained the imported Qwen3.8 terminal schema, while
the immutable on-disk receipt correctly uses the Qwen3.6 schema.

Publication may fill only the seven matching Qwen3.6 Q4_K_M,
TP1/MTP0/graph-off/q8_0-KV cells from r2. There is no speed floor and no new
quality, strict-suite, serving, LocalMaxxing, or record claim. Existing
featured speeds remain immutable.
