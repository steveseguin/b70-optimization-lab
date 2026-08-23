# Ornith 1.5 35B-A3B: native SYCL flash attention is slower at depth zero

Date: 2026-08-23 EDT

Status: **CLOSED PERFORMANCE NEGATIVE — retain oneDNN flash attention**

The accepted `--flash-attn auto` recipe uses the oneDNN flash-attention
implementation by default. The Qwen-derived backend alternative was screened
by setting `GGML_SYCL_FA_ONEDNN=0` while leaving flash attention and the full
accepted Ornith stack enabled.

The native path preserved the canonical fixed-seed 128-token transcript
SHA-256
`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`.
It therefore advanced to a mirrored seven-sample engine comparison:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| oneDNN flash control | `133.510948`, `133.324520` | **133.417734** |
| native SYCL flash | `133.243139`, `132.575595` | **132.909367** |

The native path was **0.381% slower**, and both candidates were below both
controls. No fresh-server test was justified. This conclusion applies to the
measured depth-zero `tg128` point; it is not extrapolated to long contexts.
The accepted user packet keeps oneDNN flash attention.

Raw correctness and engine records are under `../data/ornith-fa-native*`; the
structured result is
`../data/2026-08-23-ornith35b-native-flash-attention-summary.json`.
