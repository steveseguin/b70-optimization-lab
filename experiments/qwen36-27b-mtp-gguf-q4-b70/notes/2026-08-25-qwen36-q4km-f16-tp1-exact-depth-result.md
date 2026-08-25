# Qwen3.6 Q4_K_M F16-KV TP1 exact-depth result

Date: 2026-08-25. Status: **passed; seven raw-engine cells ready**.

The frozen one-B70 campaign completed all fourteen `llama-bench` rows and the
exact-depth parser accepted every declared depth. The model, executable,
source, shared libraries, environment, selectors, and create-only lifecycle
matched the preregistration. Teardown passed and the kernel window contained no
XPU reset, device-lost, OOM, or fault evidence.

| active context | decode tok/s | prefill tok/s |
| ---: | ---: | ---: |
| 0 | 29.302760 | 826.357043 |
| 2K | 28.718264 | 891.595341 |
| 4K | 28.423839 | 869.408814 |
| 8K | 27.883558 | 830.461807 |
| 16K | 26.882685 | 760.015741 |
| 24K | 25.898142 | 704.976178 |
| 32K | 25.039506 | 655.103870 |

Each point is the runtime-reported mean of five repetitions. The zero point is
a real `n_depth=0` row. These are raw-engine shape measurements, not HTTP
serving rates, and this campaign did not run a new model-quality battery.
Artifact quality, recipe maturity, and performance remain separately graded.

The transient command stdout printed the base adapter's original Qwen3.8
terminal-schema string before the Qwen3.6 exclusive writer transformed its
copy. The immutable `terminal-receipt.json` on disk correctly uses
`neural.download.qwen36-llama-exact-depth-terminal.v1`; its SHA-256 is frozen in
the structured result. No run artifact was edited after creation.

Publication may fill only the seven matching Qwen3.6 Q4_K_M,
TP1/MTP0/graph-off/F16-KV cells. There is no speed floor, and no featured,
strict-suite, LocalMaxxing, or historical speed is replaced.
