# Inkling-2 engine (one B70 card)

Our own SYCL inference engine for Thinking Machines' Inkling-2-Mini, Unsloth `UD-IQ4_XS` GGUF, on one Intel Arc
Pro B70. Started 2026-11-22. The reference is Unsloth's llama.cpp release `b12588-mix-c0c3de8` on the CPU (read for
the model's math, never used as our code).

- `src/gguf.hpp`: GGUF v3 header reader (pread, no mmap).
- `src/device.hpp`: one card, one context, in-order queue; weights uploaded in 32 MiB copies into 1 GiB arenas.
- `src/formats.hpp`: device decoders for F32, F16, BF16, Q8_0, Q5_0, IQ4_NL, IQ4_XS, Q4_K, Q5_K, Q6_K, NVFP4
  (32 values at a time, same float operations as ggml's dequantization).
- `src/gemv.hpp`: matrix-vector products (1-8 vectors, plain and expert-routed), fixed summation order.
- `src/ops.hpp`: norms, clips, depth mixing, short convolutions, attention with the relative bias and sinks, expert
  routing, SITU, expert combine. `src/model.hpp`: hyperparameters, the 48-application schedule, weight binding.
- `src/engine.hpp`: the forward pass (one sequence; FP16 K/V cache and F32 conv state per application).
  `src/dump.hpp`: `INK_DUMP=<dir>` saves the reference's named tensors.
- `tools/ink_run.cpp`: greedy generation (`ids: ...`), like `tools/ref_gen.cpp` for the reference.
- `tools/test_formats.cpp`, `tools/test_gemv.cpp`: checks against the reference library; `tools/ref_dump.cpp`: saves
  the reference's intermediate tensors; `tools/compare_dumps.py`: lines two dumps up; `tools/detok.py`: ids to text;
  `tools/ink_load.cpp`: card list and upload test.
- `src/planar.hpp`, `src/gemv2.hpp`: card-side regrouped ("planar") rows for Q8_0, NVFP4 and Q6_K and the products
  over them (same per-value arithmetic, aligned vector loads); `tools/bench_gemv.cpp` times variants and checks each
  one bit for bit against the first kernels.
- `scripts/build.sh <tool>`: the one build command (strict IEEE single precision on the card, see below).
- `scripts/check-exact.sh <ink_run>`: the gate for every engine change, three cards in parallel: all 426 dumped
  tensors of a 5-token prompt and the greedy ids of two prompts must equal `/home/steve/inkling-work/baseline`.
- `scripts/on-card.sh <card> <cmd>`: runs one job on one card under that card's lock (cards 1-5).
- `patches/oracle-f32-activations.patch`: a high-precision build of the reference for checking (F32 activations and
  double sums for every weight type; run with `GGML_CPU_F32_ACT=1 REF_FA=0 REF_NO_REPACK=1`). Never shipped.
- `notes/inkling2-forward.md`: the model's forward pass as the reference computes it, with file and line citations.

Checks so far (card 1, 2026-11-22): all decoders bit-identical to ggml on sampled rows of every tensor type in the
file; matrix-vector results within 3e-8 of double precision (relative to the sum of term sizes), identical across
runs and across 1 vs 8 vectors.

First full forward pass (card 1, 2026-11-22), 5-token prompt, against the high-precision reference: final scores
within 1.38e-05 (relative L2), worst of 378 intermediate tensors 1.03e-04. The normal CPU reference (8-bit activations)
is 1.38e-02 from the same high-precision run, so our engine is about a thousand times closer to the exact math. Greedy
answers follow the normal reference for 14, 42 and 65 tokens on three prompts, then branch at near-ties (at the coding
prompt's branch the reference disagrees with itself between its prompt and decode paths).

Speed of this first, unoptimized version (one card): writing 19.57 tok/s (short prompt), 12.97 tok/s at 3K context;
reading a 3,127-token prompt 43.3 s (72.1 tok/s). The CPU reference: 6.29 tok/s writing, 126.4 s for the same prompt.

## Speed work (2026-11-22)

| version | writing (short prompt) | per step | what changed |
|---|---|---|---|
| first | 19.57 tok/s | | |
| parallel expert routing | 25.81 tok/s | 37.1 ms | top 8 of 128 picked by one work-group per token (was 275 µs per call) |
| planar weights | 41.31 tok/s | 21.9 ms | regrouped Q8_0 / NVFP4 / Q6_K rows, R rows per sub-group (output head 4.86 -> 0.97 ms) |
| strict build + split mix + 4-bit decode | 48.15 tok/s | 18.8 ms | FP4 values and scales decoded from bits; depth mix in two parallel launches |

Every row was checked bit for bit against the row before it, except the strict build, which became a new
baseline. Default icpx builds use the fast floating-point model: the compiler may regroup sums and use approximate
division and square roots, so two kernels with the same written arithmetic gave different bits (the split depth mix
differed from the one-launch mix). `scripts/build.sh` uses `-fp-model=precise -ffp-contract=off` with correctly
rounded division and square root, and the two mixes then agree bit for bit. New baseline against the high-precision
reference: final scores 7.80e-06 apart on the 5-token prompt (was 1.38e-05), worst of 378 tensors 1.08e-04; on a
141-token prompt the median position is 3.70e-05 apart (fast build 7.90e-05). Greedy ids: the haiku prompt is
unchanged; the coding answer changes at token 102, where the reference prefers its word by only 0.027 (27.668 vs
27.642) and the strict build by -0.014 the other way.

