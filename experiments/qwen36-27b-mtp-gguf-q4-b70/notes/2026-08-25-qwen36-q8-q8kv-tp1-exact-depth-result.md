# Unsloth Qwen3.6 target-only Q8_0 q8_0-KV TP1 exact-depth result

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
| 0 | 19.405005 | 901.906305 |
| 2K | 18.267808 | 891.929001 |
| 4K | 17.345650 | 862.373352 |
| 8K | 15.709473 | 823.052319 |
| 16K | 12.876788 | 757.048246 |
| 24K | 10.961461 | 702.840157 |
| 32K | 9.568652 | 653.732827 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. This exact artifact contains no embedded MTP tensors;
the curve is target-only raw-engine shape evidence, not an intrinsic-MTP curve
and not an HTTP serving rate. No new model-quality battery ran.

Publication may fill only the seven matching Unsloth Qwen3.6 target-only Q8_0,
TP1/MTP0/graph-off/q8_0-KV cells. There is no speed floor and no new quality,
strict-suite, serving, LocalMaxxing, or record claim. Existing featured speeds
remain immutable.
