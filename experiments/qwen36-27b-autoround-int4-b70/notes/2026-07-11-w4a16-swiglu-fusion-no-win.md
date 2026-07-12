# Real-weight W4A16 gate/up + SwiGLU fusion: no win

## Hypothesis

Every one of the 64 target layers materializes an FP16 `[4,17408]` dense-MLP
gate/up output, launches `silu_and_mul`, and writes `[4,8704]` before the down
projection. A paired-output W4A16 kernel could retain gate/up accumulators,
round them at the production boundary, apply SwiGLU, and avoid the intermediate
write/read and activation launch.

## Real-weight control bound

`scripts/bench-qwen27-w4a16-swiglu.py` loads the exact layer-0 AutoRound
weights, builds the production NT packed layout for TP rank 0, and compares the
complete local `gate_up -> SwiGLU -> down` boundary eagerly and under XPU graph
replay. It is a diagnostic kernel benchmark, not endpoint throughput.

Before implementing the candidate, all four B70s measured approximately:

- gate/up oneDNN W4A16: `81.8-82.1 us/layer`;
- cached standalone SwiGLU: `11.1-12.2 us/layer`;
- queued gate/up + activation: `84.0-84.7 us/layer`;
- complete eager local MLP boundary: `133.3-133.9 us/layer`.

Thus launch/activation removal alone has only a `~0.7 ms/step` upper bound
across 64 layers, and queued execution hides part of even that. Reaching the
original `2 ms/step` target requires a faster W4 producer as well.

## Prototype

The default-off `qwen27_w4a16_gateup_swiglu` operation specialized exactly:

- FP16 input `[4,5120]`;
- symmetric U4 packed NT weights `[640,17408]`;
- FP16 group-128 scales `[40,17408]`, zero point 8;
- FP16 output `[4,8704]`.

It computed paired gate/up columns in one workgroup, rounded each GEMM result
to FP16, then matched the existing half-precision SiLU and multiply order.
The exact isolated source is preserved at:

`patches/qwen36-27b-autoround-int4-b70/vllm-xpu-qwen27-w4a16-swiglu-20260711.patch.gz`

The first build accidentally used oneAPI 2026 and linked `libsycl.so.9`, while
the active torch runtime uses the oneAPI 2025.3 `libsycl.so.8` ABI. That build
was rejected before benchmarking. The prototype was rebuilt from a fresh CMake
directory with compiler 2025.3 and imported successfully under the normal
runtime. This is a build-identity lesson: never reuse a CMake directory across
oneAPI compiler major ABIs.

## Four-GPU result

Compact tracked result:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-w4a16-swiglu-4gpu-20260711.json`

Real layer weights, 20 warmups, 100 samples, four calls/sample:

| GPU | control graph pipeline | candidate graph pipeline | regression |
| --- | ---: | ---: | ---: |
| 0 | `202.64 us` | `454.25 us` | `+251.61 us` |
| 1 | `199.56 us` | `457.53 us` | `+257.97 us` |
| 2 | `202.97 us` | `454.70 us` | `+251.73 us` |
| 3 | `201.94 us` | `457.44 us` | `+255.50 us` |

The candidate was also not bit-exact: activation max absolute difference was
`0.00390625`, and the partial down-projection difference was `0.0009765625`.
The naive scalar U4 decompression/dot-product workgroups cannot approach
oneDNN's systolic JIT GEMM; removing the activation boundary does not offset
that producer loss.

## Decision

Closed without vLLM integration or an endpoint run. The source prototype and
result are preserved, its source edits were removed, and the production
extension/GDN library were restored. Do not repeat a scalar paired-column W4
kernel. A credible revisit requires adding a paired SwiGLU epilogue inside an
equally fast systolic/JIT W4 implementation, with exact production reduction
and rounding order; standalone activation fusion is too small to reach 100
tok/s by itself.
