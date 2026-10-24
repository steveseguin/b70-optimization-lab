# External review: vllm-xpu-kernels PR #22 and Strata, against our Flash-Next engine (2026-10-24)

Sources (read-only clones on this host: `/dev/shm/research/vxk` branch `pr22`, `/dev/shm/research/strata`):
- [analytics-zoo/vllm-xpu-kernels PR #22](https://github.com/analytics-zoo/vllm-xpu-kernels/pull/22): "Enable
  Qwen3.8-flash-next 8 cards fp8 & int4". It covers the same geometry as ours: HC 4×2560, E512 top-10, QSA head dim
  256, GDN 48×128×128. It uses FP16 activations and SSM state, INT4/FP8 weights and TP4/TP8 on 8× B70, and does not
  claim determinism.
- [Niko1221/Strata](https://github.com/Niko1221/Strata) (MIT): a model-specific engine for this family. It is CUDA
  first, with a SYCLomatic port tested on an Arc Pro B70. Its B70 figures are for the Coder IQ1_M on one card: decode
  78 tok/s, prompt 790 tok/s at 2K tokens (`docs/INTEL.md`).
  - Strata's guarantee is "speculative output equals plain greedy in its own arithmetic", and that arithmetic uses q8_1
    int8 activations.
  - Its prefill is not bit-exact against its decode.

Under the own-runtime rule we reimplement ideas with credit; no code is copied.

Our own records were surveyed for comparison. Current two-card BF16 record: 63.61 tok/s (packet195). One-card record:
37.60 (packet196).

## Transferable and exact (keep each output's operation order)

| # | Idea | Source | Fits our bottleneck |
|---|---|---|---|
| 1 | **Small register tiles for multi-token linear.** Each subgroup holds Rows×Tokens ≤ 8 accumulators (4×1, 2×2, 2×4, 1×8), decodes each weight once, applies it to its token tile, and reads activations straight from global (no local tile). | PR `csrc/qwen38/int4.cpp` `launch_linear<Rows,Tokens>` | Batched prefill GEMV (≈75% of a row). Our attempts used 16 tokens per subgroup (`MultiplyRows`) or 2×16 with a local tile (`MultiplyTiled`), and both were slower. Same lane partition as our M=1 kernel, so exact. |
| 2 | **Aligned loads for GGUF blocks.** Blocks are only 2-byte aligned (110/210/136/18/34 B), and the B70 splits misaligned 16-byte loads. Use two aligned loads plus a shift (`load16_a2`), or repack at load. | Strata `sycl/.../native_mmvq.dp.cpp`; `docs/INTEL.md` "Decode round 2": Q6_K 160 → 493 GB/s, Q8_0 4–6×, decode 53.9 → 76.1 tok/s across bitwise-identical steps | Our packed kernels (gsqn, dense block, IQ3 block, kopt routed) read bytes and halves individually. Our dense Q6/Q8 sites already use the aligned expanded layout. |
| 3 | **IQ4_NL expert dots with the codebook in registers** and weights as aligned 4-byte loads. Bitwise the same. | Strata, same table: 640→2560 dot 28 → 6.6 µs | Expert down, the IQ4_NL routed GEMV (1.7–2.2 ms per row per card at prefill). |
| 4 | **MoE in about 3 launches per layer.** Gate+up of all 10 routed experts plus the shared expert in one launch with SiLU·up in the epilogue; then down with a fixed-order weighted combine. | PR `moe_sycl_block.h` `launch_up`/`launch_down`; Strata `native_expert_grouped` | Launch count and occupancy. Our own packet193 found that fusing the epilogue alone gave nothing, so this is worth it only as the whole layer's MoE. |
| 5 | **Exact top-k with packed keys.** Score and inverted id packed into one integer key, one subgroup max per rank, ties to the lower id. | PR `moe_sycl.cpp` `launch_topk_packed_subgroup`; QSA `selection_score_key` | Route (5 phases now) and QSA select. Only comparisons change. |
| 6 | **GDN verify without state writes, plus async commit replay.** Verify keeps state in registers across the draft rows; the accepted rows replay from cached qkv/gate/beta. | Strata `verify_kernels.dp.cpp`, `Verifier::commit`: +12% decode on the B70 | Our MTP decode uses snapshot/restore banks. Exact, because each row's math is unchanged. |
| 7 | **Fused HC prefill glue** (norm, combine+norm, gate-mix), FP32 with the same rounding points. | PR `hc_sycl.cpp`: their largest prefill gain (8K TTFT 3.2 → 1.8 s) | Our HC ops already run multi-row; fusing them further cuts launches. |
| 8 | **Reduced-vocabulary MTP draft head** (40,525 tokens) plus a confidence stop. Verification keeps the output exact. | Strata `mtp.cpp` `--draft-vocab`, `--spec-min-p` | Draft cost per step; acceptance must be re-measured. We already keep a draft-prefix head (packets 56/114). |
| 9 | **Device-side expert plan** for large prefill chunks: count prefix and active-expert list built on the device, no host sync. | PR `launch_prefix`; Strata `resident_plan` (parallel; one thread took 73 µs per layer) | Only for chunks much larger than 16 tokens. At 16 rows the experts barely overlap (about 0.3 tokens per expert). |

## Fast but numerics-changing (not for the exact F32 line; possible for BF16 lines only with the owner's decision)

- XMX/DPAS GEMMs with FP16/BF16 operands and 2D block loads (PR `int4_small_m.cpp`, `moe_sycl_prefill.cpp`). DPAS needs
  SG16. Strata found `joint_matrix` dequant+GEMM 4–5× slower, and XMX at 1–6 rows 1.4–3× slower (one version hung the
  GPU).
- int8 (q8_1) activations with dp4a or int8 DPAS (Strata's whole decode, and its ESIMD prefill at +12–21%).
- Chunked WY GDN, large prompt chunks with FP16 dequant into oneMKL. Strata notes that the chunk boundary moves
  rounding.

## B70 hazards Strata reports (worth checking against our engine)

- **Two 2 MiB pages of one 22 GiB allocation mapped to the same memory by the xe driver.** Strata tags every 64 KiB of
  allocations ≥ 32 MiB and verifies the tags (`malloc_device_guarded`). Our weight arena makes large allocations.
- **An unbounded device spin caused an xe GPU reset that needed a reboot.** Every spin must be bounded. Our p58as spin
  wait should be checked for this.
- Host-to-device flag visibility during a running kernel was reliable only with system-scope atomics.
- Level Zero v2 runs every SYCL queue on the compute engine. Real copy overlap needs an L0 copy queue (ordinal 1)
  wrapped with `sycl::make_queue` (`sycl/include/strata/copy_queue.hpp`). This matches our memory note that only the
  copy engine (bcs) overlaps.

## Dead on the B70 per Strata (do not retry without a new reason)

SIMD16 retune of decode kernels; `joint_matrix` fused dequant GEMM; XMX for decode experts; multiple compute queues.

## Proposed order for our engine

1. Prefill linear with small tiles (idea 1): our existing token-row kernels with 4 tokens per subgroup instead of 16.
   This is the cheapest test.
2. Aligned-load audit and fixes in the packed and expert kernels (ideas 2 and 3). These help decode and prefill.
3. Exact packed-key top-k for route and QSA select (idea 5).
4. MoE in about 3 launches (idea 4) and HC glue fusion (idea 7).
5. GDN verify without writes plus commit replay (idea 6), for MTP decode.
6. Guarded large allocations and bounded spins (hazards), as a safety audit.
