# Qwen3.6 UD-Q4_K_XL F16-KV TP1 exact-depth result

Date: 2026-08-25. Status: **passed; seven raw-engine cells ready**.

The frozen one-B70 campaign completed all fourteen `llama-bench` rows and the
parser accepted every declared depth. The model, runtime, shared libraries,
selectors, four locks, repaired process census, and create-only lifecycle
matched the preregistration. Cleanup passed and the kernel window contained no
XPU reset, device-lost, OOM, or fault evidence.

| active context | decode tok/s | prefill tok/s |
| ---: | ---: | ---: |
| 0 | 28.204518 | 840.763300 |
| 2K | 27.725352 | 890.406168 |
| 4K | 27.404946 | 864.381702 |
| 8K | 26.897264 | 826.178656 |
| 16K | 25.966478 | 758.859063 |
| 24K | 25.112731 | 701.503117 |
| 32K | 24.305050 | 654.617886 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. These are target-only raw-engine shape measurements,
not HTTP serving rates, and this campaign ran no new model-quality battery.

The transient command stdout retained the imported Qwen3.8 terminal schema;
the immutable on-disk terminal receipt correctly uses the Qwen3.6 schema. No
run artifact was edited after creation.

Publication may fill only the seven matching Qwen3.6 UD-Q4_K_XL,
TP1/MTP0/graph-off/F16-KV cells. There is no speed floor and no new quality,
strict-suite, serving, LocalMaxxing, or record claim. Existing featured speeds
remain immutable.
