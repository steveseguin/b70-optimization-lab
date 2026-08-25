# Qwen3.6 Q4_0 q8_0-KV TP1 exact-depth result

Date: 2026-08-25. Status: **passed; seven raw-engine cells ready**.

The clean r2 campaign completed all fourteen `llama-bench` rows and the parser
accepted every declared depth. It held all four GPU locks, repeated the idle
process census under lock, attested graph-off against the exact effective SYCL
DSO, cleaned up, and found no XPU reset, device-lost, OOM, or fault evidence in
the kernel window.

| active context | decode tok/s | prefill tok/s |
| ---: | ---: | ---: |
| 0 | 25.872387 | 634.031442 |
| 2K | 23.935981 | 299.300259 |
| 4K | 22.514384 | 284.234229 |
| 8K | 20.208918 | 256.071922 |
| 16K | 16.841132 | 203.929704 |
| 24K | 14.415549 | 168.638097 |
| 32K | 12.600315 | 144.957372 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. These are target-only raw-engine shape measurements,
not HTTP serving rates, and this campaign ran no new model-quality battery.
The strong context-dependent q8_0-KV cost is a property of this exact profile;
it does not replace or lower any featured serving or LocalMaxxing speed.

The earlier r1 was contaminated by an overlapping external GPU job and remains
quarantined. The r2 terminal receipt explicitly records `r1_evidence_reused=false`;
no r1 timing row or conclusion appears here.

Publication may fill only the seven matching Qwen3.6 Q4_0,
TP1/MTP0/graph-off/q8_0-KV cells. There is no speed floor and no new quality,
strict-suite, serving, or record claim.
