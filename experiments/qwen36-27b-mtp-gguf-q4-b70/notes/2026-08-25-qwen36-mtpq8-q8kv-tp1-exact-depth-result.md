# Qwen3.6 embedded-MTP Q8_0 q8_0-KV TP1 exact-depth result

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
| 0 | 19.405539 | 901.976592 |
| 2K | 18.272969 | 890.547903 |
| 4K | 17.344880 | 863.295379 |
| 8K | 15.714150 | 823.429981 |
| 16K | 12.878391 | 753.248427 |
| 24K | 10.963382 | 701.091278 |
| 32K | 9.568731 | 653.030632 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. The file can carry MTP, but this curve deliberately ran
MTP0 with no speculator: it is target-only raw-engine shape evidence, not an
intrinsic-MTP curve and not an HTTP serving rate. No new model-quality battery
ran.

Publication may fill only the seven matching Qwen3.6 embedded-MTP Q8_0,
TP1/MTP0/graph-off/q8_0-KV cells. There is no speed floor and no new quality,
strict-suite, serving, LocalMaxxing, or record claim. Existing featured speeds
remain immutable.
