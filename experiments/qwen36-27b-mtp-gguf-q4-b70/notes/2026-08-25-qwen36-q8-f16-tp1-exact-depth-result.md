# Unsloth Qwen3.6 target-only Q8_0 F16-KV TP1 exact-depth result

Date: 2026-08-25. Status: **passed; seven raw-engine cells ready**.

The frozen one-B70 campaign completed all fourteen `llama-bench` rows, and the
parser accepted every declared depth. The exact target-only Unsloth Q8_0
model, runtime, shared libraries, selectors, four locks, repaired process
census, and create-only lifecycle matched the preregistration. The direct model
read ran before the ordinary read; both produced the pinned
`f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce`
SHA-256. The benchmark and parser returned zero and cleanup passed.

| active context | decode tok/s | prefill tok/s |
| ---: | ---: | ---: |
| 0 | 19.837968 | 907.785877 |
| 2K | 19.638670 | 897.077604 |
| 4K | 19.507402 | 872.574722 |
| 8K | 19.267052 | 830.747630 |
| 16K | 18.811016 | 762.672514 |
| 24K | 18.381399 | 708.320296 |
| 32K | 17.977204 | 660.847730 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. This exact artifact contains no embedded MTP tensors;
the curve is target-only raw-engine shape evidence, not an intrinsic-MTP curve
and not an HTTP serving rate. No new model-quality battery ran.

Publication may fill only the seven matching Unsloth Qwen3.6 target-only Q8_0,
TP1/MTP0/graph-off/F16-KV cells. There is no speed floor and no new quality,
strict-suite, serving, LocalMaxxing, or record claim. Existing featured speeds
remain immutable.
