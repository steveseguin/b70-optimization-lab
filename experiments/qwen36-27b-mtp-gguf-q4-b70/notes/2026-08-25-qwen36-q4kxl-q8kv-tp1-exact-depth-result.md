# Qwen3.6 UD-Q4_K_XL q8_0-KV TP1 exact-depth result

Date: 2026-08-25. Status: **passed; seven raw-engine cells ready**.

The frozen one-B70 campaign completed all fourteen `llama-bench` rows and the
parser accepted every declared depth. The model, runtime, shared libraries,
selectors, four locks, repaired process census, and create-only lifecycle
matched the preregistration. Cleanup passed and the kernel window contained no
XPU reset, device-lost, OOM, or fault evidence.

| active context | decode tok/s | prefill tok/s |
| ---: | ---: | ---: |
| 0 | 27.395786 | 837.719471 |
| 2K | 25.050958 | 883.049663 |
| 4K | 23.208806 | 859.579899 |
| 8K | 20.326377 | 822.394416 |
| 16K | 15.864377 | 751.828274 |
| 24K | 13.112415 | 696.253636 |
| 32K | 11.214628 | 645.980903 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. These are target-only raw-engine shape measurements,
not HTTP serving rates, and this campaign ran no new model-quality battery.

The transient command stdout retained the imported Qwen3.8 terminal schema;
the immutable on-disk terminal receipt correctly uses the Qwen3.6 schema. No
run artifact was edited after creation.

Publication may fill only the seven matching Qwen3.6 UD-Q4_K_XL,
TP1/MTP0/graph-off/q8_0-KV cells. There is no speed floor and no new quality,
strict-suite, serving, LocalMaxxing, or record claim. Existing featured speeds
remain immutable.
