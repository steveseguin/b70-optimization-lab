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

## Joint-N ownership result

The closed result above applied to one work-item owning one N16 tile. A
materially different mapping now makes one split-8 ESIMD work-item own two
adjacent N16 tiles. For each K block it loads the Mx32 Q8 vector and M
activation scales once, reuses them across two DPAS operations, and applies the
16 per-output Q4 scales with native ESIMD vector arithmetic. The packed weight
bytes are unchanged. Joint-4 was also tested to bound the idea; it was slower
on every shape because its larger accumulator footprint raises register
pressure.

Thirty-iteration 5120x5120 result on a reserved B70:

- M=4: joint-2 `14.062 us` device / `22.733 us` wall versus vector
  `140.313 us` / `148.109 us`, or `6.515x` by the promotion metric;
- M=8: joint-2 `13.230 us` device / `21.290 us` wall versus vector
  `271.354 us` / `278.353 us`, or `13.074x`;
- all joint-2, joint-4, split, original-DPAS, repeated-vector, and sampled CPU
  comparisons reported maximum absolute difference `0.000`.

The two real FFN shapes were then run concurrently on four otherwise idle
B70s for 20 iterations each:

- 5120x17408: `4.838x` at M=4 and `6.926x` at M=8;
- 17408x5120: `5.737x` at M=4 and `9.197x` at M=8;
- all correctness comparisons again reported maximum absolute difference
  `0.000`.

The authoritative square-shape log is
`/mnt/fast-ai/bench-results/qwen27-xe2-verifier/run-20260712T200914Z.log`,
SHA-256
`a9e776f15469afef67f2b812dd7fbc43d9d8db43603c8d4f604f0abdd3a6145e`.

## Runtime integration interface

Integration should remain narrowly guarded to Q4_0 x Q8_1, Xe2/Battlemage,
and verifier widths 4 or 8:

1. Add `ggml_sycl_op_mul_mat_q4_0_xe2_verifier(...)` beside
   `ggml_sycl_op_mul_mat_q(...)` in `mmq.hpp/mmq.cpp`. Its contract is the
   already-quantized Q8_1 device pointer, packed Q4 nibbles, FP16 Q4 scales,
   output pointer, K/N, source-row stride, and fixed M specialization.
2. In `ggml_sycl_mul_mat()` select it before the generic MMVQ branch only when
   `src0->type == GGML_TYPE_Q4_0`, `src1->ne[1]` is 4 or 8, the tensor is
   contiguous 2D, and the device architecture is Xe2/BMG. Keep M=1 and every
   unsupported shape on the current reordered MMVQ path.
3. Allocate one fixed split-8 FP32 partial buffer from graph-stable context
   storage, not the transient pool. The reduction submission and addresses
   must be stable for direct graph replay. A later fusion can fold the
   reduction into the projection epilogue, but it is not required to clear the
   kernel gate.
4. Add exact width-4/8 backend tests against current MMVQ before any end-to-end
   MTP run. The standalone benchmark's synthetic equality is necessary but
   does not cover tensor strides, graph capture, or real GGUF scale decoding.

## Offline pack artifact

The production pack should be keyed by source GGUF SHA-256, tensor name and
shape, Q4_0 block size, pack-layout version, target `bmg-g31`, and compiler
ABI. Per tensor it stores:

```text
header: magic/version, K, N, QK=32, Ntile=16, nibble convention, checksums
qs:     [K/32][N/16][K/8][N lane][8 signed nibbles]
d:      [K/32][N] FP16
```

The nibble pack XORs bit 3 once to convert GGUF Q4_0 bias to DPAS signed-s4.
Keeping scales as FP16 makes the packed payload exactly the same logical
`18 bytes / 32 weights` as ordinary Q4_0; the benchmark used FP32 scales only
for experimental clarity. The current SYCL reorder already separates Q4
nibbles and FP16 scales in-place in `reorder_qw_q4_0()`, but remains
output-row-major. The native packer should transpose that operation into the
K-block-major layout above and cache it on disk. Initial integration can keep
this as a second device allocation in `ggml_tensor_extra_gpu`; the memory-final
version should teach M=1 reordered MMVQ to consume the same VNNI artifact and
replace, rather than duplicate, the ordinary Q4 tensor allocation.

Build and square-shape validation command:

```bash
ZE_AFFINITY_MASK=<reserved-card> \
  experiments/qwen27-dflash-sycl-b70/xe2-verifier/build-and-run.sh
```

## Comparator correction and final disposition

The repeated-vector comparator above rereads weights for every M row. The
active reordered llama.cpp `ncols<4/8>` MMVQ instead loads each weight block
once and accumulates all verifier rows, so the apparent `4.8-13.1x` result did
**not** clear the production integration gate.

An apples-to-apples harness now calls the exact production reordered kernel and
includes activation quantization, joint-2 compute, reduction, submissions, and
wall completion. Its M=4 totals were only `1.407x` at 5120x5120 and `1.374x`
at 5120x17408. The 17408x5120 case reached `1.662x` but missed the correctness
criterion, while M=8 square reached `1.925x`. Current production MTP3 depends
on M=4, so the verifier v2 integration is rejected. No runtime dispatch flag
was added. See `2026-07-12-xe2-verifier-v2-comparator-audit.md` for the corrected
evidence.
