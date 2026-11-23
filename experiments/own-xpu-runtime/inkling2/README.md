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
  tensors of a 5-token prompt and the greedy ids of two prompts must equal `/home/steve/inkling-work/baseline`
  (6 checks on cards 1-5); `scripts/make-baseline.sh <ink_run> <dir>` makes a new baseline through the general kernels
  (only after a sum order change that was checked against the high-precision reference).
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
| fused attention prep and tails | 49.77 tok/s | | Q/K/V/R preparation in one launch, attention and FFN tails fused |
| mix + norm, paired controls | 53.46 tok/s | | depth mix and its norm in one pass; gain/forget rows and SITU gate/up rows in one sub-group |
| argmax on the card | 55.75 tok/s | | next token picked on the card, positions precomputed |
| parallel attention | 58.04-60.46 tok/s | | scores one key per thread across many work-groups, P.V 16 channels per group |
| NVFP4 through half bits | 61.22-64.50 tok/s | | an E2M1 code placed in a half's bits is the value x 2^-15 exactly; two codes per 32-bit op |
| Q6_K four values per op | 65.17-65.42 tok/s | 15.1 ms | 6-bit codes of four values assembled with one shift/mask; output head 939 -> 720 µs |
| attention inputs in one launch | 67.08-67.13 tok/s | 15.00 ms | q, k, v, rel, sink, gate (+ the conv projections) of a layer: one launch with a job table (`src/multi.hpp`) |
| loop mixes per pass, batched controls | 70.77-72.25 tok/s | 13.78 ms | the looped layers' mixes read states fixed for the whole pass: all 48 at the pass start; 3 controls in 3 launches, not 9 |
| small-kernel rewrites | 73.13-74.66 tok/s | 13.26 ms | bias table one entry per thread (10.75 -> 3.52 µs), control outputs one row per work-item, routing in one sub-group |
| saved-state mix scores | 75.50-77.13 tok/s | 12.90 ms | a saved state never changes: its mix scores go into a table once; 96 launches fewer per step |
| decode copies for layers 20-23 | 79.07-80.98 tok/s | 12.34 ms | K-quant / IQ4 experts regrouped for wide loads: 2.3-3.9x per kernel (Q5_0 down 141.9 -> 36.5 µs) |
| transposed value cache | 80.17-82.44 tok/s | 12.26 ms | below |

Prompt reading and long context (3,127-token prompt, then 32 tokens; ids identical in every row):

| version | prompt | writing at 3K context | what changed |
|---|---|---|---|
| first | 72.1 tok/s | 12.97 tok/s | |
| grouped experts + batched products | 162.8 tok/s | 20.59 tok/s | each chosen expert decoded once per 8 slots; R rows x M tokens per sub-group |
| parallel attention | 172.0 tok/s | 47.64 tok/s | as above (attention was 23.5 of 44 ms per step at 3K) |
| token-parallel expert tiles | 294.8 tok/s | 52.41 tok/s | steps of >= 128 tokens: one expert's slots across the 16 lanes (below) |
| dense tiles + parallel grouping | 379.3 tok/s | | steps of >= 16 tokens: dense matrices one token per lane too; expert grouping 572 -> 14.5 µs |
| tiles for every expert format | 415.5 tok/s | 51.11 tok/s | layers 20-23 too (IQ4_XS gate|up 41.5 -> 7.9 ms at 512 tokens) |
| writing-speed work above (card 3) | 445.8-446.4 tok/s | 62.2 tok/s | 3K writing step 16.08 ms (card 2) |
| transposed value cache (card 3) | 468.4-468.8 tok/s | 71.7 tok/s | 3K writing step 13.95 ms (card 2) |
| attention tiles (card 3) | 531.7-532.8 tok/s | | steps of >= 16 tokens: 8 queries x 3 heads per tile, bias in place (below) |
| writing-step attention (card 2) | | 31K: 17.4-18.1 ms per step (was 19.4-20.0) | scores 3 heads per key read; softmax sums only; P.V normalizes as it reads |
| block-order P.V, baseline v2 (card 2) | 494.1-496.1 tok/s (card 5, unchanged) | 31K: 16.1-16.7 ms (was 17.5-18.1) | keys summed in blocks of 128 positions, then the blocks (below) |
| ring caches, unrolled block sums (card 2) | | 31K: 15.5-16.0 ms | windowed layers keep 2,048 positions; full layers' block sums 92 -> 23 µs |
| one copy of layers 20-23's experts (card 3) | 542.2-542.5 tok/s (was 532.7-534.4) | | prompt tiles read the decode copies; file layout never uploaded (below) |

Attention tiles (`src/attn_tiles.hpp`, bench `BENCH_TILE=1 bench_attn <card> <pos> <win> <ntok>`, card 2, 1024
tokens at position 4096, every value equal to the one-token kernels'): windowed scores 2249 -> 966 µs and P.V 3003 ->
701 µs; full-attention scores 12266 -> 3199 µs and P.V 9113 -> 3106 µs (4.6 TMAC/s). A lane keeps the 24 sums of 8
queries x 3 heads; each sum keeps its order (dimensions or keys ascending from 0); keys outside a row's range add
exact zeros. 16 queries per tile spill registers and run ~8x slower.

Block order, baseline v2 (2026-11-23, `attn_pv_bo_part` / `attn_pv_bo_sum` in `src/fused.hpp`, the tiles of
`src/attn_tiles.hpp`): every P.V sum adds the keys of each block of 128 absolute positions in order from 0, then the
block sums in order from 0. A one-token step can then use one thread per (head, block, channel) instead of one per
(head, channel): full-layer P.V at 31K 400 -> 139 µs. This changes the bits, so it is a new baseline
(`/home/steve/inkling-work/baseline`, made by `scripts/make-baseline.sh <ink_run>` through the general kernels; the
old one is kept as `baseline-v1`). Accuracy against double precision (`BENCH_ACC=1 BENCH_TILE=1 bench_attn`, random
data): 31,000 keys 3.3-3.4e-07 relative vs 2.8-3.1e-06 for the key-by-key order, 8,000 keys 2.4-2.6e-07 vs
1.2-1.5e-06, the 1,024 window 1.8-2.1e-07 vs 5.4-5.5e-07, prompt steps 2.2e-07 vs 5.7-6.3e-07; the block order is
closer on every row. Against the high-precision reference on a 300-token prompt, layers 0-5 are as close as v1
(each order closer at 82-89 of the 171 positions that differ); at the last layer v1 happens to be closer (final scores
median 4.21e-03 vs 3.47e-03, the same top token as the reference at 97.33 % of positions for both): a rounding
difference of 8e-08 at layer 0 doubles about every layer whichever order made it, so per-kernel accuracy is the
measure. The ids of the gate prompts did not change.

Ring caches (`INK_RING=0` turns them off): the 40 windowed layer applications keep only the last 2,048 positions
(the smallest power of two >= window + step + 128), slot = position & 2047; every cache read and write goes through
that mask, and a 16-key read never wraps because 2,048 is a multiple of the 128-position block. At 31,400 positions
this frees ~4.5 GiB; logits of 4 steps after the 31,270-token prompt are bit-identical with and without the rings.
A one-launch P.V (the last work-group adds the blocks) measured slower than the two launches at every length
(31,000 keys 199 vs 157 µs, 3,134 with the window 10.2 vs 8.9 µs) and was dropped.

Context length on one card (2026-11-23): the score buffer P now holds a bounded number of query rows (`INK_P_MB`,
default 512 MiB; a step's attention runs in chunks of that many tokens, the same bits: 16- and 48-row chunks at 3K
and the default 176 rows at 31K reproduce the unchunked logits). Layers 20-23's experts were on the card twice (the
file layout for prompt tiles, decode copies for the rest); the prompt tiles now read the decode copies through lane
decoders with the same per-value expressions (bench_moe: same bits, gate|up 13.2-14.6 -> 8.5-8.9 ms per 512 tokens on
layers 20-22), and `ink_run` leaves those 8 tensors (2.57 GB) in the file: `planarize` fetches each into a scratch
buffer and keeps only its decode copy. Card memory at 4,200 positions 19.12 -> 16.56 GiB; each position costs ~34
KiB (the 8 full-attention caches 32 KiB, score rows and block sums the rest), so one card holds 420,000 positions
(30.29 of 31.89 GiB). `Device::alloc` refuses to pass the card's size minus `INK_MEM_RESERVE_MB` (default 1024):
xe does not fail an over-large allocation, it moves card memory out to host RAM.

The cards are not equally fast: card 3 reads the 3,127-token prompt ~8 % faster than cards 2 and 4 (448.5 vs
413.6-416.0 tok/s for the same build), so speeds are compared on one card.

Transposed value cache (`attn_pv_t`, `tools/bench_attn.cpp`): the attention's P.V sum ran one lane per channel and
read one 2-byte value per key; a thread keeps only ~16 reads in flight, so the sum waited on memory about once per
key (45 ns per key, 37-45 GB/s, 3.55 ms per step at 3K). Wider reads, block reads and longer batches on the same
layout stayed at 40-60 GB/s. Storing the cache channel-major (`[kv channel][position]`) gives each lane 8 keys of
its channel per 16-byte read; each channel still adds its keys in order, so the bits are unchanged. bench_attn:
1,024-key window 85.7 -> 13.6 µs, 3,135 keys 200.9 -> 28.9 µs. `scripts/check-exact.sh` gained card E: the
3,127-token prompt + 16 tokens, all 16 steps' score rows bit for bit (the baseline equals the early build's).

Token-parallel expert tiles (`src/moe_group.hpp`, `tools/bench_moe.cpp`): in a step of many tokens, a sub-group takes
up to 16 slots that chose the same expert, one per lane, and each lane computes its slot's whole product. The weights
are decoded once per sub-group (lane l decodes byte l of a chunk) and read back by index from the register, which
costs nothing extra. To keep the bits of the lane-per-chunk kernels, each lane replays their fixed order: the 16
virtual lanes' chunk sums in bit-reversed order, combined in the same pairs as the xor butterfly (v with v + 8, + 4,
+ 2, + 1). The inputs of a tile are transposed (column-major across the 16 lanes) so each chunk is read with four
sub-group block reads, and the gate|up kernel writes its output straight into the down kernel's transposed layout.
bench_moe, one layer at 512 tokens: gate|up 18.76 -> 8.84 ms, down 9.37 -> 3.63-3.86 ms, all outputs bit-identical;
the old kernels stay faster below ~128 tokens per step (fewer slots per expert leave lanes idle). Checked in
`scripts/check-exact.sh` (card D): a 300-token one-step prompt, all 426 dumped tensors equal to the grouped kernels'.

DSpark guessing (the reference's `llama-speculative-simple`, CPU, greedy): code prompt 52 % of 3 guesses accepted
(~2.6 tokens per round), 31 % of 7 (~3.2); haiku prompt 34 % of 3 (~2.0), 19 % of 7 (~2.3). Checking 4 tokens at once
costs 34.7 ms against 15.1 ms for one (each extra token wakes other experts), so guessing would break even at best on
code and lose on prose. Set aside.

Every row was checked bit for bit against the row before it, except the strict build, which became a new
baseline. Default icpx builds use the fast floating-point model: the compiler may regroup sums and use approximate
division and square roots, so two kernels with the same written arithmetic gave different bits (the split depth mix
differed from the one-launch mix). `scripts/build.sh` uses `-fp-model=precise -ffp-contract=off` with correctly
rounded division and square root, and the two mixes then agree bit for bit. New baseline against the high-precision
reference: final scores 7.80e-06 apart on the 5-token prompt (was 1.38e-05), worst of 378 tensors 1.08e-04; on a
141-token prompt the median position is 3.70e-05 apart (fast build 7.90e-05). Greedy ids: the haiku prompt is
unchanged; the coding answer changes at token 102, where the reference prefers its word by only 0.027 (27.668 vs
27.642) and the strict build by -0.014 the other way.

