# Qwen3.6 embedded-MTP Q8_0 F16-KV TP1 exact-depth result

Date: 2026-08-25. Status: **passed; seven raw-engine cells ready**.

The frozen one-B70 campaign completed all fourteen `llama-bench` rows, and the
parser accepted every declared depth. The exact embedded-MTP Q8_0 model,
runtime, shared libraries, selectors, four locks, repaired process census, and
create-only lifecycle matched the preregistration. The direct model read ran
before the ordinary read; both produced the pinned
`9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`
SHA-256. The benchmark and parser returned zero and cleanup passed.

| active context | decode tok/s | prefill tok/s |
| ---: | ---: | ---: |
| 0 | 19.834912 | 908.102030 |
| 2K | 19.637971 | 897.500019 |
| 4K | 19.504957 | 871.159456 |
| 8K | 19.268213 | 830.349728 |
| 16K | 18.814981 | 763.173586 |
| 24K | 18.387779 | 707.362149 |
| 32K | 17.981787 | 658.014356 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. The file can carry MTP, but this curve deliberately ran
MTP0 with no speculator: it is target-only raw-engine shape evidence, not an
intrinsic-MTP curve and not an HTTP serving rate. No new model-quality battery
ran.

Publication may fill only the seven matching Qwen3.6 embedded-MTP Q8_0,
TP1/MTP0/graph-off/F16-KV cells. There is no speed floor and no new quality,
strict-suite, serving, LocalMaxxing, or record claim. Existing featured speeds
remain immutable.
