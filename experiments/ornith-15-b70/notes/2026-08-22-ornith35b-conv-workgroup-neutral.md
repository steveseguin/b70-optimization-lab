# Ornith 1.5 35B-A3B: convolution/SiLU work-group sweep

Date: 2026-08-22 EDT

Status: **CLOSED NEUTRAL — keep WG256**

The accepted recurrent convolution/SiLU kernel assigns one independent output
channel per work-item. A same-binary runtime selector screened work-group sizes
64, 128, 256, and 512 without changing graph structure or per-channel
arithmetic.

The first `llama-bench p0/n128/d0/r5` screen measured:

| Work-group | tok/s |
| ---: | ---: |
| 64 | 109.570251 |
| 128 | 108.179645 |
| 256 | 109.145019 |
| 512 | 109.242443 |

WG64's small apparent lead was within run variation, so it was preregistered
for a mirrored `WG256-A / WG64-A / WG64-B / WG256-B` repeat at seven samples
per process:

| Arm | Runs | Mean tok/s |
| --- | --- | ---: |
| current WG256 | `110.010011`, `109.971844` | **109.990928** |
| candidate WG64 | `109.940571`, `109.345045` | **109.642808** |

WG64 was **0.3165% slower**. This is not a serving candidate, so no server
suite or package update was run. Keep the published WG256 kernel. The exact
screen-only source is archived as
`../patches/llamacpp-ornith15-conv-silu-workgroup-sweep-neutral-20260822.patch`;
structured and raw results are under `../data/`.
