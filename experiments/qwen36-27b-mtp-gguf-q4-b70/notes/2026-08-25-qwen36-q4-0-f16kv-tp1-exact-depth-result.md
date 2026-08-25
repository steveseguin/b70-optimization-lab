# Qwen3.6 Q4_0 F16-KV TP1 exact-depth result

Date: 2026-08-25. Status: **passed; seven raw-engine cells ready**.

The frozen one-B70 campaign completed all fourteen `llama-bench` rows and the
parser accepted every declared depth. It held all four GPU locks, repeated the
idle and exact-DSO graph-off gates before the GPU subprocess, produced a passed
terminal receipt, and reused no q8 timing row.

| active context | decode tok/s | prefill tok/s |
| ---: | ---: | ---: |
| 0 | 26.403242 | 635.640524 |
| 2K | 25.612445 | 300.209882 |
| 4K | 24.982236 | 284.812214 |
| 8K | 23.885171 | 255.794498 |
| 16K | 21.956970 | 203.909768 |
| 24K | 20.306007 | 168.950165 |
| 32K | 18.908580 | 144.909151 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. These are target-only raw-engine shape measurements,
not HTTP serving rates, and this campaign ran no new model-quality battery.

The kernel window contained no XPU reset, device-lost, OOM, or GPU fault. One
corrected, nonfatal PCIe receiver event was reported for the NVMe endpoint
`0000:01:00.0`; the kernel explicitly said hardware corrected it without
further action. The benchmark continued and completed normally. This event is
disclosed but is not misclassified as a GPU error.

Publication may fill only the seven matching Qwen3.6 Q4_0,
TP1/MTP0/graph-off/F16-KV cells. There is no speed floor and no new quality,
strict-suite, serving, LocalMaxxing, or record claim. The existing featured
speeds remain immutable.
