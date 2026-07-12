# 2026-07-12 Xe2 multi-token verifier experiment

## Question

Can the Qwen target verifier use Xe2 XMX/DPAS to avoid rereading Q4_0 weights
once per speculative token at real `M=4/8` widths, and does that projection
beat a repeated vector implementation by at least `1.5x` per token?

## Source audit

The active llama.cpp SYCL Q4_0 path is still subgroup/vector code:

- `ggml/src/ggml-sycl/mmvq.cpp` instantiates one template for every destination
  width from 1 through 17;
- `ggml/src/ggml-sycl/vecdotq.hpp` implements Q4_0 x Q8_1 with packed integer
  loads and vector dot products;
- there is no use of `joint_matrix`, ESIMD `dpas`, or XMX in the active
  `ggml-sycl` tree.

The installed oneAPI 2026 compiler exposes explicit-SIMD DPAS with signed
4-bit and signed 8-bit argument precision, and successfully AOT-compiles it for
the B70 target `bmg-g31`.

## Guarded implementation

The standalone experiment is in `xe2-verifier/`. It makes no llama.cpp source
or dispatch changes. One DPAS operation covers one quantization block:

```text
A: M x 32 Q8_1 signed bytes
B: 32 x 16 Q4_0 signed nibbles in Xe VNNI order
C: M x 16 signed int32 dot products
epilogue: C * activation_scale[M, block] * weight_scale[block, N]
```

The offline B pack is
`[K/32][N/16][K/8][N lane][8 K nibbles]`. It also converts Q4_0's biased
GGUF nibble to DPAS two's-complement form by XORing bit 3. Each output tile is
256 bytes (64 dwords). M=4 and M=8 are separate AOT specializations with DPAS
repeat counts 4 and 8.

The executable generates deterministic quantized data, checks every DPAS
output against a same-layout repeated-vector device kernel, checks 64 columns
against an independent CPU reference, and reports median device event time.
The repeated-vector kernel intentionally rereads each packed weight for each M
row. The experiment exits nonzero unless correctness passes and DPAS is at
least `1.5x` faster.

## Validation performed without reserving a GPU

```text
XE2_COMPILE_ONLY=1 experiments/qwen27-dflash-sycl-b70/xe2-verifier/build-and-run.sh
Compilation from IR - skipping loading of FCL
Build succeeded.
Compilation from IR - skipping loading of FCL
Build succeeded.
compiled=/mnt/fast-ai/bench-results/qwen27-xe2-verifier/xe2-int4-int8-verifier
```

Also passed `bash -n` and `git diff --check`. No GPU was used, as requested by
the parent task. The result is therefore **compile-valid but performance and
runtime-correctness unverified**. The first reserved-card run must execute both
real shapes:

```bash
ZE_AFFINITY_MASK=<reserved-card> \
  experiments/qwen27-dflash-sycl-b70/xe2-verifier/build-and-run.sh
```

## Promotion gate and caveats

- Both M=4 and M=8 must pass device/CPU correctness.
- Both must beat repeated vector by `>=1.5x` at K=N=5120.
- Then add the FFN shapes (5120x17408 and 17408x5120) before integration.
- This baseline uses FP32 scale storage for clarity. A production offline pack
  should retain compact FP16 Q4_0 scales and tune scale conversion/loading.
- The microbenchmark excludes Q8_1 production, dispatch/replay, recurrent state
  handling, sampling, and verifier integration. A kernel win is not an
  end-to-end throughput claim.
- If correctness fails, the likely first issue is the assumed VNNI lane order;
  preserve the negative result and fix the packer before measuring speed.

## GPU result and bounded rescue

GPU 1 was confirmed idle and used through `ZE_AFFINITY_MASK=1`. The original
kernel proved the VNNI packing and arithmetic exactly correct, but serialized
160 DPAS operations in each N tile:

- M=4: 463.021 us event / 470.913 us wall versus 147.086 us vector wall,
  `0.312x` wall speed;
- M=8: 933.229 us event / 941.907 us wall versus 277.911 us vector wall,
  `0.295x` wall speed.

The one permitted rescue split K across 4 or 8 ESIMD work-items per N tile,
wrote FP32 partials, and launched a dependent reduction kernel. Combined event
times include both kernels; wall times span both submissions and completion.

- M=4 split-4: 124.270 us combined event, 132.499 us wall, `1.110x` versus
  vector wall. Split-8 was 132.689 us wall, `1.109x`.
- M=8 split-8: 246.249 us combined event, 254.097 us wall, `1.094x` versus
  vector wall. Split-4 was 256.712 us wall, `1.083x`.

Every original/split/vector comparison and the sampled CPU reference reported
maximum absolute difference `0.000`. The rescue is real but far below the
required `1.5x`. The block-scaled DPAS layout is therefore **closed and must not
be integrated**. The likely limiting economics are the 160 scale epilogues per
projection plus partial-buffer traffic/reduction, not lack of work-item
parallelism alone.

Authoritative 30-iteration log:
`/mnt/fast-ai/bench-results/qwen27-xe2-verifier/run-20260712T160845Z.log`.
SHA-256:
`8710501eebfe0415d8ca166b94fb5e10141af5d6e5de028c6008cb9cbd71db54`.
