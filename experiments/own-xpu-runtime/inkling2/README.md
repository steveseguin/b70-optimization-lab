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
- `scripts/on-card.sh <card> <cmd>`: runs one job on one card under that card's lock (cards 1-5; refuses card 0 and an
  empty card).
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
| fused multiply-add, baseline v3 (card 3) | 642.7-643.2 tok/s; 31K prompt 530.6 (was 446.6, card 2) | short 12.28 ms, 3K 13.18 (was 12.31-12.36, 13.35; card 4) | every sum of products through `mac()` (below) |
| reads issued together, weights warmed (card 3) | | short 11.61-11.63 ms (was 12.31-12.33 for the build before) | small kernels without a branch around each read; the mix warms L2 (below) |
| expert inputs in lane order (card 3) | | short 11.38-11.40 ms (was 11.54-11.58) | gate\|up and down products read their input 4 cache lines per load, not 16 (below) |
| long rows 64 reads per round (card 3) | | 100K: 20.78 ms (was 21.24); 403K: 24.87 tok/s (was 23.53, card 5) | full layers' softmax and block sums past 16K keys (below) |
| job pointers as global, small steps (card 2) | | short 11.42 ms (was 11.61-11.62); steps of 2 / 3 / 4 tokens 15.65-15.67 / 18.26-18.29 / 21.42-21.56 ms (were 20.14-20.15 / 24.09-24.16 / 28.61-28.75) | pointers read from job tables cast to global; 2-4 token steps with one launch per kind (below) |
| DSpark drafter guesses (card 2) | | code 256 tokens 109.68 tok/s with 2 guesses (plain 87.70), haiku 128 94.66 (plain 88.05) | the drafter on the card, guesses checked exactly (below) |
| guesses per check chosen from the drafter's probabilities (card 2) | | code 118.41 tok/s (plain 88.22), haiku 96.94 (88.60), 3K prompt 98.22 (83.20) | `INK_SPEC=3`, adaptive count (below) |
| gate|up tiles decode NVFP4 through tables; prompt steps of 1,024 tokens (card 3) | 8K 641.6-645.7 -> 683.3-685.4 tok/s; 3K 670.6 (was 643); 31K 599.0 -> 616.8 (card 2 with the drafter: 570.6, was ~539) | | same bits (below) |
| drafter attention by key spans; checks read long-range keys once for all tokens (card 2) | | after 31K: 97.25 tok/s with guesses (plain 70.48; before 59.97); after 8K 113.75 (plain 80.05); 3K 105.32 | below |
| control modules batched for 2-4 tokens (card 2) | | steps of 2 / 3 / 4 tokens 14.92-14.93 / 17.36-17.38 / 20.39-20.40 ms (were 15.69-15.73 / 18.27-18.30 / 21.42-21.52) | norms, down products and gain\|forget outputs of all modules and tokens in 3 launches (below) |
| checks of up to 8 tokens; the drafter's guesses 4-7 only after strong chains (cards 1, 3, 4, 5) | level | after 200K: code 70.04 -> 75.96 tok/s, haiku 62.63 -> 65.40; short code 128.5 -> 134.0, haiku 104.7 -> 108.1 | `INK_SPEC=7` (below) |

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

Context length on one card (2026-11-23; the row count is now chosen from free card memory, see "Long prompts" below):
the score buffer P now holds a bounded number of query rows (`INK_P_MB`,
default 512 MiB; a step's attention runs in chunks of that many tokens, the same bits: 16- and 48-row chunks at 3K
and the default 176 rows at 31K reproduce the unchunked logits). Layers 20-23's experts were on the card twice (the
file layout for prompt tiles, decode copies for the rest); the prompt tiles now read the decode copies through lane
decoders with the same per-value expressions (bench_moe: same bits, gate|up 13.2-14.6 -> 8.5-8.9 ms per 512 tokens on
layers 20-22), and `ink_run` leaves those 8 tensors (2.57 GB) in the file: `planarize` fetches each into a scratch
buffer and keeps only its decode copy. Card memory at 4,200 positions 19.12 -> 16.56 GiB; each position costs ~34
KiB (the 8 full-attention caches 32 KiB, score rows and block sums the rest), so one card holds 420,000 positions
(30.29 of 31.89 GiB). `Device::alloc` refuses to pass the card's size minus `INK_MEM_RESERVE_MB` (default 1024; 512 since 2026-11-24):
xe does not fail an over-large allocation, it moves card memory out to host RAM.

Fused multiply-add, baseline v3 (2026-11-23): every sum of products in the kernels (74 sites: matrix products,
attention scores and P.V, norms, mixes, convolutions) adds its terms through `mac()` (`src/formats.hpp`), one
rounding per term; every kernel that computes the same sum uses it at the same place, so all paths still agree (gate
6/6 against `baseline`, made through the alternative paths with `scripts/make-baseline.sh`). Decoders and elementwise
formulas are unchanged. `INK_CFLAGS=-DINK_NO_FMA scripts/build.sh ...` builds the old arithmetic, which reproduces
baseline v2 (`baseline-v2`) bit for bit. Accuracy: matrix products against double precision (`test_gemv`, worst error
/ sum of term sizes) lower on 12 of 17 tensor types (e.g. NVFP4 gate|up 1.92e-08 -> 1.63e-08, IQ4_NL 2.85e-08 ->
2.36e-08); P.V at 31,000 keys 3.31e-07 -> 3.20e-07; against the high-precision reference on the 300-token prompt the
two are equally close (each closer at about half the positions in every layer; final scores median 4.21e-03 -> 3.80e-03,
the same top token as the reference at 97.0 vs 97.3 % of positions, one position). The coding prompt's answer changes
at token 102, the near-tie described below. Speed: prompt +19 % (3,127 tokens 542 -> 643 tok/s on card 3; 31,270
tokens 447 -> 531 on card 2); a 512-token step's expert gate|up 357 -> 304 ms.

Prompt expert tiles, what limits them (2026-11-23, `bench_moe` 512 tokens, card 3): gate|up 6.7 ms and down 3.5
per launch, ~30 % of the card's plain multiply-add rate. Builds with parts removed (wrong results, timing only):
without the cross-lane weight selects 6.71 (the constant-index selects are free), without the input reads 6.16,
without the weight reads and decoding 3.41. The weight side is the cost, but not its arithmetic: decoding through
tables in local memory (the 16 code values, the 256 scale bytes; the same floats) takes gate|up to 6.35-6.40 and
makes down slower (3.66-3.69), so only gate|up uses it (`INK_TILE_LUT`; 8K prompt +2.3 %). Loading each virtual
lane's weight bytes first: 6.9-8.3. One weight row per lane with the tokens in a loop (the same bits): 13.3-13.9 /
4.4-7.1 ms (each lane reads 16 bytes of a different row per chunk, and the fixed order visits a row's chunks 16
apart). Prompt steps of 1,024 tokens fill the 16-slot tiles better: the default up to 300,000 positions (+1.09 GiB;
longer contexts keep 512); 2,048 adds only 0.6 % more.

Long prompts (2026-11-23): at very long contexts the score buffer holds only 16 query rows (420K positions), and the
block kernels re-read the value cache once per token. `attn_pv_tile_part` (`src/attn_tiles.hpp`) splits the tiles by
128-key blocks instead (8 queries x 3 heads x one block per work-group, query blocks fastest so a value block is read
once for all of them) and leaves the blocks' sum to `attn_pv_bo_sum`: the same values (bench_attn 100K keys x 16
tokens 6.6 -> 1.4 ms; x 64 tokens 6.4 -> 4.6 ms against the tiles). The prompt score tiles run query blocks fastest
from 16K keys (100K x 512 tokens 34.8 -> 31.8 ms). A 31,270-token prompt with 16-row chunks: 434 -> 543 tok/s, the
same speed as 176-row chunks; logits bit-identical to the FMA reference build in both cases.

At 403,372 tokens (one card, 404,000 positions; a needle test, prompts/needle.tokens: 1.3M characters of lab notes
with two one-line notes hidden at 3 % and 55 % and the question at the end) the prompt reads at 173.0 tok/s (2,332 s;
the build before these long-prompt kernels: 83.4 tok/s, 4,835 s) and writing runs at 23.5 tok/s. The model answers
"Vault code: 7351-QX-4829; meeting room: Juniper-12." (both right; its thinking names the sections they sat in).

Long rows (2026-11-23): the writing step's softmax (`attn_softmax_sum`) and block sums (`attn_pv_bo_sum`) give a row
one work-group of 128 threads, which waits for each round of reads. Past 16K keys they now issue 64 reads per round
(the maxima 16), then 8, then one by one; every sum keeps its order. `BENCH_SM=1 bench_attn <card> <pos> 0` (card 3,
all variants identical to the 8-per-round kernel): 400K keys softmax 268 -> 159 µs, block sum 246 -> 132; 200K 98 -> 64
and 137 -> 67; 32 or 128 per round are no better. In the engine at 100K (card 3, `INK_PROF`): softmax 60.4 -> 36.2 µs,
block sum 64.1 -> 37.2 per full layer, step 21.24 -> 20.78 ms; the 32 written tokens unchanged. The 403K needle test
(card 5): writing 23.53 -> 24.87 tok/s, prompt 173.0 -> 173.3, the 258-token answer identical. Short rows (the
windowed layers) keep 8 per round and the one-by-one tail: bigger rounds or a predicated last round made them slower.

Long prompts and long writing (2026-11-23 evening):
- Prompt tiles of the full-attention layers now write each row's maximum per 16 keys while scoring, the softmax keeps
  the exponentials and 1 / total (`attn_softmax_sum`, as the writing step), and the P.V tiles multiply as they read
  (`INK_TILE_SM`, default on). P is read and written twice instead of five times; the values are the normalizing
  softmax's (product P * inv as read). Card 3, back to back, last-row logits identical: 100K prompt 394.5 -> 429.7
  tok/s, 31K 585.5 -> 594.0, 8K unchanged.
- Writing-step score kernels run the 8 KV heads of a key block one after another (`INK_ATT_KVF`, default on; same
  values): `BENCH_KVF=1 bench_attn 3 100000 0 4` 1 token 404.8 -> 401.2 µs (506 -> 511 GB/s, 84 % of a plain read),
  4 tokens 564.3 -> 545.8. One-token P.V parts are at 501 GB/s (408.5 µs): little is left in the one-token attention.
- The drafter's full-context attention (24 rows per KV head: 8 slots x 3 heads) is limited by FP32 arithmetic, not
  memory: `bench_dsp 3 100000` (tools/bench_dsp.cpp, the engine's own kernel `dsp_attn_span`) 3.65 ms vs a plain read
  of its keys and values in 0.68 ms. Fused multiply-adds (the build turns contraction off; the drafter only picks
  guesses, so its arithmetic may change) and the pass's cache values staged in local memory: 2.58 ms
  (`INK_DSP_AVAR=3`, default). Guessing kept the same guesses on code, haiku, 3K and 31K (ids identical); 31K writing
  97.1 -> 98.2-98.7 tok/s (card 4). After a 100K prompt (card 2): plain 52.46 tok/s, guessing 55.84 -> 57.61
  (drafting 0.871 -> 0.734 s per 256 tokens), ids identical to the plain run.
- The drafter's full-context layer now runs on the matrix engines (`dsp_attn_span_x`, DPAS through `joint_matrix`, fp16
  inputs and fp32 sums; `INK_DSP_AVAR=4`, default; the windowed layers keep variant 3). The block's 8 key / value rows
  are written into the cache after the context (`dsp_block_to_cache`; the full layer's cache has 8 + 128 zeroed rows
  of room), so every tile is a plain strided load. `bench_dsp 3 100000`: 2.59 -> 0.88 ms (463 GB/s; 31K 0.84 -> 0.29),
  combined output within 1.2e-4 of the fp32 kernel (largest value 0.37). The same guesses are kept on code, haiku,
  3K, 31K and 100K (ids identical); 31K writing 98.5 -> 100.5 tok/s (card 4); after a 100K prompt (card 2) 57.58 ->
  60.59 tok/s (drafting 0.735 -> 0.488 s), plain 52.46. Short texts unchanged (the full layer there is tiny).
- The drafter's folded correction table (W_lm Wh)^T is int8 with one scale per vocabulary column (`INK_DSP_PT8`,
  default 1; 103 -> 51 MB, read once per guess): `dsp_corr` 187.6 -> 97.9 µs (card 3). Card 2, same guesses kept,
  ids identical: code 118.3 -> 119.8 tok/s, haiku 106.2 -> 107.4, 3K 105.0 -> 106.1; 31K (card 4) 100.4 -> 101.3.
  The drafter now costs ~2.45 ms per round at short contexts: the W_lm pass for the guess slots 0.75 (380 MB at
  ~508 GB/s), the corrections 0.32, its FFN 0.80 and q/k/v/o 0.31 (8-row Q8_0 products at ~200-300 GB/s).
- The drafter's 8-slot products (q, k, v, o, gate, up, down) on the matrix engines (`dsp_mm_x`, `INK_DSP_MMX`,
  default 1): the Q8_0 weights repacked at load into tiles of 16 rows x 32 columns (int8 values, then the 16 scales),
  each lane decodes one row's 32 values to fp16 pairs in the engines' packed order (two local buffers, the next
  block's bytes read first), the slots' inputs are fp16 rows (the norms, the attention combine and SiLU write them),
  fp32 sums; 2 sub-groups split a row range's columns for the 9,216-row products, 8 for the others. `bench_dsp`
  (`BENCH_MM=1`, card 3): 9216 x 2304 48.9 µs (461 GB/s), 2304 x 9216 47.1, 3072 x 2304 16.4, 2304 x 3072 17.3,
  1024 x 2304 8.2; in the drafter gate / up / down 74.7 / 73.3 / 93.6 -> 51.2 / 49.5 / 47.3 µs, q 34 -> 17.5, o 33 ->
  18.7. Only the repacked copies go on the card (`Weights::upload` skip + `planarize` own): card memory 18.42 GiB
  with or without. Same guesses kept everywhere (code 155, haiku 145, 3K 147, 31K 156), ids identical; card 2 code
  119.6 -> 122.0 tok/s, haiku 107.1 -> 108.9, 3K (card 1) 106.0 -> 107.3, 31K (card 4) 101.3 -> 102.9; 100K
  60.51 (card 2, off) / 61.58 (card 4, on). Drafting per run 0.249 -> 0.203 s (code).
- Step costs on card 3 (`INK_BENCH_REAL=1 INK_BENCH_STEP=1,1,2,3,4`), ms for 1 / 2 / 3 / 4 tokens: at 3,119 positions
  11.90 / 15.59 / 19.12 / 21.74; 7,992: 12.34 / 16.76 / 19.91 / 23.01; 31,262: 13.90 / 18.49 / 22.48 / 25.69; 99,992:
  18.80 / 24.56 / 28.40 / 33.09. The ratios to one token barely move with context, so the guess-count rule's fixed
  table still ranks the counts right; drafting costs 2.7 ms per round at short contexts, 3.7 at 31K, ~5.6 at 100K.

Plain reads (`bench_read <card>`, card 2, back-to-back launches over different buffers): 8 MB 14.2 µs (564 GB/s),
12 MB 21.1, 21 MB 36.2, 24 MB 41.2 (583 GB/s), 380 MB 631 (602 GB/s). Against these the one-token products are at
gate|up 54.4 µs for 23.9 MB, down 29.2 for 11.9 MB, attention input 43.6 for 21.1 MB, attention output 17.2 for 7.5 MB
(`INK_PROF`, card 2): ~1.6 ms of the 11.42 ms step above the plain-read time, the rest of the step is ~700 small kernels.

Step size does not change the results: a 48-token prompt's last scores are bit-identical in steps of 1, 2, 3, 4, 8,
16 or 48 tokens (`INK_UBATCH`, `INK_SAVE_LOGITS`), so guesses checked in one step give exactly the one-token text.

Pointers read from a job table (2026-11-23): a kernel that takes its matrix, input and output pointers from an array
in its arguments sees them as generic pointers, and loads through generic pointers are slow. `gptr()` (gemv.hpp)
casts them to global. The one-token attention inputs (multi.hpp GemvMulti): 43.3 -> 40.9 µs, step 11.34-11.36 ->
11.13 ms (`INK_PROF`, card 3). The job must be copied out with fixed indexes (`pick_job`); taken by reference with a
run-time index the gain is lost (44.0 µs). The same cast in the mix and the three-input norm gave nothing (mix 9.69 ->
9.92 µs, step equal) and is not used. Before the cause was found, a larger register file, the job table in card
memory, one row count per kernel and broadcasting the job's fields from one lane all changed nothing.

Small steps of 2-4 tokens (checking guesses), `INK_SB=0` off. Real tokens (`INK_BENCH_REAL=1 INK_BENCH_STEP=1,2,3,4`,
the prompt's last 8 tokens, card 2): 1 / 2 / 3 / 4 tokens 11.42 / 15.65-15.67 / 18.26-18.29 / 21.42-21.56 ms (were
11.61-11.62 / 20.14-20.15 / 24.09-24.16 / 28.61-28.75). The norms also write their outputs in lane order and:
- the eight attention input matrices run as one launch for all tokens (multi.hpp `gemv_multi_m`, each matrix row read
  once for every token);
- the experts (moe_group.hpp): each chosen expert's rows are decoded once for all the tokens that chose it
  (`GroupedPairS` / `GroupedRowsS`; NVFP4 layers `GroupedPairT` / `GroupedRowsT`, 8 values decoded at a time
  (`NVFP4P::dec8`), each work-group runs the code for its own token count). 4 tokens choose ~20 distinct experts per
  layer, not 32 (`INK_ROUTE_STATS=1`). Gate|up / down per layer (`INK_PROF`): 2 tokens 76.1 / 46.7 µs, 3 tokens 96.5 /
  62.7, 4 tokens 124.3 / 79.3; with one code for all counts 4 tokens took 149.0 / 92.1; two row pairs per sub-group
  (`INK_SB_NP=2`) 82.6 at 2 tokens, four down rows (`INK_SB_DR=4`) 49.3.
Every sum keeps gemv1_rows' order: steps of 2, 3 and 4 tokens give last scores bit-identical to one-token steps on
two prompts (48 and 36 tokens); gate 6/6.
- The loop control modules (`Engine::control_multi`): for 1-4 tokens, the norms, the down products and the
  gain|forget outputs of all modules and tokens take three launches (one-token kernels: `gemv_multi_m` with plain
  inputs, `CtlRows` with a token per group of rows). Was one set of three per module and step: steps of 2 / 3 / 4
  tokens 15.69-15.73 / 18.27-18.30 / 21.42-21.52 -> 14.92-14.93 / 17.36-17.38 / 20.39-20.40 ms (card 2); same bits.

Checking guesses (`Engine::check` / `accept`, `ink_run` with `INK_SPEC=<1-3>`): one step runs the last chosen token
and up to 3 guessed tokens, scores every row, and the card picks the greedy token of each row (`ops::argmax_rows`).
Guesses are kept while they equal the model's choices. Rolling back is exact: the windowed key rings already hold a
window plus a whole step, so `n_past` goes back; for the convolution states (the last 3 inputs of each channel in
every application, 3.8 MB) every token of a checking step but the last also writes its state to its own slot, and a
rejection copies the last kept token's slot back. The guesser for now is prompt lookup (the most recent earlier
occurrence of the last 4, 3 or 2 tokens; `INK_SPEC_MAXN`, `INK_SPEC_MINN`). Text and every chosen scores row equal
plain generation byte for byte (code 256 and haiku 128 tokens with 1, 2 and 3 guesses, card 2; gate checks 7-9). On
fresh text it rarely has a guess: code 256 tokens 87.10-87.16 tok/s plain, 88.42-88.51 with 1 guess (52 checks, 27
of 52 guesses kept, 176 steps without a guess), 86.77-86.87 with 2, 83.48-83.59 with 3. A one-token step is
unchanged (11.36-11.43 ms).

DSpark drafter (`src/dspark.hpp`, `INK_DRAFT=<dspark-Inkling-2-Mini-Q8_0.gguf> INK_SPEC=<1-3>`; graph and references
in `/home/steve/inkling-work/notes/dspark-spec.md`). Unsloth's 318M drafter for this model, on the same card: the
target copies the stream entering visits 5, 23 and 41 and its final normed rows into a feature buffer every step;
the drafter turns each row into context keys/values for its 3 layers (`inject`), and each round runs an 8-slot
block (the last chosen token, then 7 mask slots; non-causal; layers 0 and 2 see the 1024 positions before, layer 1
all) and a chained head that makes one guess at a time from the previous one. Its numbers only decide which guesses
the target keeps; the text is the one-token text (gate check 10: ids and every chosen scores row). Keep rate on code
57.5 % of 3 guesses (the reference build: 52 %).
- Speed (card 2, 256 code tokens / 128 haiku tokens): plain 87.70 / 88.05 tok/s; 1 guess 99.32 / 89.23 (77.6 / 59.5 %
  kept); 2 guesses **109.68 / 94.66** (68.4 / 51.2 %, 2.36 / 2.02 tokens per check); 3 guesses 108.00 / 88.25 (57.5
  / 40.1 %).
- Drafting, ~2.5 ms per round with 2 guesses: the head's correction goes through the output layer only via a
  256-wide latent, so (W_lm Wh)^T is computed once at load (the engine's own products over Wh's 256 columns, 103 MB
  BF16, 0.15 s) and each guess reads that table (189 µs) instead of the 380 MB output layer; the guess slots' output
  products share one read (`gemv_multi_m`, 793 µs for 3); the 8-slot products take lane-order inputs in blocks of 8
  (ffn_gate 81 µs, ffn_down 103; the tile kernels took 116 and 212; the first version's blocks 172 for ffn_gate).
- How many guesses to check (`INK_SPEC_ADAPT`, default on with the drafter): the drafter makes 3 and gives each its
  own softmax probability (`ops::argmax_p_rows`). Its probability tracks the keep rate: guesses at 0.9+ were kept 283
  of 304 times (code, haiku, 3K prompt), 0.8-0.9 35 of 57, below 0.5 10-37 %. Each round checks the count k (0-3)
  with the most expected tokens per ms (keep chance from those buckets, step costs 11.4 / 14.9 / 17.4 / 20.4 ms,
  `INK_SPEC_COST`). Card 2, `INK_SPEC=3`: code 256 tokens 88.22 tok/s plain -> 109.92 with 2 fixed guesses ->
  **118.41** adaptive; haiku 128 88.60 -> 94.85 -> **96.94**; the 3,127-token prompt + 256 tokens 83.20 -> 95.31 ->
  **98.22**. Same ids as plain in all.
- Long contexts. The drafter's middle layer attends to every earlier position; its first kernel (one work-group per
  query row) read each key 24 times: 4.86 ms per launch after 31K, so guessing was slower than plain (59.97 vs 70.48
  tok/s). `Drafter::attend_split` gives each work-group a span of keys of one key head for all 24 rows that use it
  (running max / sum / P.V per row, then a combine launch): same guesses, 0.45 ms average per launch, 31K **87.14**
  tok/s. The target's checks then read the long-range layers' keys and values once per token: `attn_scores_full` 375
  µs and `attn_pv_full` 393 per layer for ~2.7 tokens against 134 / 139 for one. `fz::attn_scores_gt` (one thread
  per key for all tokens) and `fz::attn_pv_bo_part_t` (one work-group per key head and block for all tokens) keep
  each row's order (dot products by dimension from 0.0f; P.V by key per block): 166 and 212 µs, 31K **97.25** tok/s
  (+38 % over plain), the same rows as one-token steps (gate check 6, `INK_ATT_SHARE_MIN=0`). Only in layers without
  a window and from 4,096 keys (`INK_ATT_SHARE_MIN`): the windowed layers' P.V went 15 -> 29 µs (too few blocks per
  launch), and short contexts lose the same way (code at ~400 keys P.V 7.7 -> 18.4 µs; 3K and 8K even).
- How many guesses at most: a study mode drafts 7 guesses per round and logs how many lead the plain run's text
  (`INK_DRAFT_LOG=<file> INK_ORACLE=<plain ids>`); `tools/spec-sim.py` replays guess-count rules on those logs. Up to 4
  guesses: code +4 %, haiku / 3K / 8K texts even; up to 5: code +6 %, the others -1 to -2 % (checks of 5+ tokens
  touch many more experts: ~2.8 ms per extra token). Not built (checks of 5-8 tokens would need the small-step
  kernels widened; today they fall to the prompt path at 34.8-46.4 ms).
- The check step's output rows: the final norm writes lane-order rows for steps of 1-4 tokens; 4 rows 1,291 ->
  944 µs (multi_m), one row 676 -> 655 (bench_gemv, card 3). Greedy choice in two launches (`ops::argmax_rows2`,
  same index; one work-group per row took 56-63 µs).

Windowed attention of the small steps in one launch (2026-11-23 evening, `fz::attn_win_fused`, `INK_ATT_WINF=0` off):
the windowed layers (window 1,024) of steps of 1-4 tokens ran four kernels (scores, softmax sums, P.V block parts,
block sum; 23.7 µs per layer at 3K in `INK_PROF`). One work-group of 1,024 threads per (token, KV head) keeps its 3 rows'
window in local memory and repeats every value: the dot products in d order with the same 16-lane q reads, the
maximum with the sink, the 128-thread lane-strided exponential sums with the sub-group xor sums and the 8 partials in
order, the block parts (P times 1 / total, keys ascending from 0 per block of 128) and the blocks in order times the
gate. A window that does not start at a block boundary touches 9 blocks; the two partial ends hold 128 keys together,
so one thread takes both (one pass of 1,024 threads). For 1-2 tokens 2 work-groups per KV head split the channels of
P.V (each computes the scores and softmax itself), so the value reads spread over twice the cores. The partial blocks
of the P.V parts (`attn_pv_bo_part`, every layer) read 16 keys per load except in the two edge groups (they read one
2-byte value per key; same order). `bench_attn` (`BENCH_WINF=1`, card 3, ring of 2,048, bit-identical to the four
kernels): full window 1 token 18.75 (four kernels, old partial blocks) -> 16.0 (new partial blocks) -> 15.2 µs (fused,
2 splits); 4 tokens 25.1 -> 22.3 -> 18.1 (fused); 400 keys 1 token 10.4 -> 7.5, 4 tokens 12.0 -> 8.4. Not better: one
head per work-group (1 token 22.0 µs; 2-4 tokens 39-58, more work-groups than cores), 4 channel splits, 32-byte key
reads (no change). Steps (`INK_BENCH_STEP`, card 3, 3,119 positions) 1 / 2 / 3 / 4 tokens 11.84-11.91 / 15.58-15.66 /
19.09-19.21 / 21.91-21.92 -> 11.53-11.55 / 15.34-15.36 / 18.84-18.87 / 21.45-21.53 ms (partial blocks alone 11.76 /
15.51 / 19.05 / 21.73). With the drafter, same guesses kept and ids identical: code 122.05-122.34 -> 123.41-124.20
tok/s, haiku 109.28-109.40 -> 111.25-111.48 (card 2), 3K 107.54-108.29 -> 110.45-110.73 (card 4), 31K 101.79-101.86
-> 103.74-103.95 (card 5); after a 100K prompt 60.51 -> 62.11 tok/s (card 2), plain 53.50 (card 4). Gate 11/11.

Prompt attention and expert tiles, more work per register (2026-11-23 night; every value the same, gate 11/11):
- P.V tiles: a lane now keeps 2 channels (`attn_pv_tile<4,3,2>`, 4 queries x 3 heads; each loaded P value serves both
  channels' sums, keys ascending as before) and the block-split tiles 4 channels (`attn_pv_tile_part<4,3,4>`).
  `BENCH_TILE=1 bench_attn 3 <pos> <win> <ntok>` (card 3): 31K x 176 tokens 5,530 -> 3,273 µs, 3K x 512 1,132 -> 802,
  windowed 31K x 512 497 -> 355; block-split 100K x 16 1,687 -> 1,474. Full layers' score tiles take 4 sub-groups per
  work-group (`attn_scores_tile<8,3,4>`; 100K x 64 3,323 -> 3,209 µs, 3K x 512 856 -> 818; the windowed layers keep 8).
- Past 32K keys the block-split P.V takes up to 64 score rows per launch (`INK_PV_ROWS`, default min(score rows, 64);
  16 = before): 100K x 64 rows in one launch 4,870 µs vs 4 x 1,474. The block sums buffer grows with it (100K: card
  memory 20.99 -> 21.28 GiB; at 420K the score rows are 16, so nothing changes there). After a 100K prompt the logits
  rows of 8 steps are bit-identical to the build before.
- NVFP4 prompt expert tiles (`INK_TILE_V2`, default on; layers 0-19): gate|up runs pairs of tiles of one expert per
  sub-group (`slot_pair_g2`, `tile_dots2`: every decoded weight serves 32 slots, each slot's sums in tile_dots' order),
  down 4 rows per sub-group with two tiles one after another (`slot_rows_g2`). `bench_moe` 1,024 tokens (card 3):
  gate|up 11,730 -> 11,289 µs, down 6,448 -> 5,723. Pairs gain only 4 %: decoding the weights is not what holds the
  tiles at ~34 % of the multiply-add rate. Not better: pairs for down (2 rows 7,602, 4 rows 6,734), 8 gate|up rows
  (11,943-12,182), 256 registers (every variant slower, e.g. down 4 rows 9,865).
- Prompt reading, the same card before -> after (ids identical): 3K 659.5 -> 681.1 tok/s (card 3), 618.9 -> 638.2
  (card 1); 31K 591.6 -> 623.5 (card 3), 555.3 -> 591.3 (card 1); 100K 419.5 -> 440.6 (card 4), 411.8 -> 421.9 (card
  5, attention changes only).

What holds the FP32 tile kernels back (2026-11-24, `tools/bench_fma.cpp`, `tools/isa_tiles.cpp`):
- `bench_fma <card>`: K independent multiply-add chains per lane, the multiplier broadcast from another lane as in the
  tiles. Card 3, TMAC/s for work-groups of 16 / 128 / 256 lanes: K 1 5.19 / 5.22 / 5.20, K 4 6.19 / 6.18 / 6.17, K 8
  6.44 / 11.21 / 11.21, K 16 11.30 at every size (the card's peak, 32 cores x 8 x 16 lanes at 2.8 GHz). A lane needs
  16 chains in flight (8 with work-groups of >= 128 lanes) or the multiply-adds run at half speed.
- `IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=<dir> scripts/build.sh isa_tiles <out>` dumps the machine code of the
  hot prompt kernels (2.5 GB for every kernel the headers instantiate; find them by name in the `.asm` files). The
  share of multiply-adds in a kernel matches its speed: expert down 36 %, gate|up 38 %, P.V block tiles 34 % (each
  ~34-35 % of peak); score tiles 53 % (53-64 %). The gate|up tile keeps 4 chains (acc0-acc3, one per row).
- The NVFP4 expert tiles ran one sub-group per work-group, and every work-group first fills the decode tables (272
  values) behind a barrier: one fill per 16 tokens x 2 rows. 32 sub-groups per work-group (`INK_TILE_SGW2`, default
  32; each takes its own rows of the tile) and the tables for down too: `bench_moe` 1,024 tokens (card 3) gate|up
  11,275 -> 7,594 µs (4 rows, two tiles one after another; 8 sub-groups 7,798, 16 7,724), down 5,723 -> 3,989 (4 rows
  with the tables; without 5,432); 512 tokens gate|up 6,369 -> 4,194, down 3,230 -> 2,195. Same values (bench and gate
  11/11; logits rows after a 100K prompt bit-identical). Tile pairs lose once the tables are shared (gate|up 9,884 at
  32 sub-groups), so gate|up no longer pairs.
- Prompt reading, the same card before -> after (ids identical): 3K 680.5 -> 812.5 tok/s (card 3), 643.6 -> 756.1
  (card 1); 31K 627.1 -> 735.2 (card 3), 588.8 -> 693.0 (card 1), 586.1 -> 684.9 (card 2); 100K 440.6 -> 495.9
  (card 4).
- Writing steps need no graph replay: the host submits a one-token step in 1.99 ms while it runs 12.22 ms (card 5),
  and the card is busy 11.456 of 11.570 ms per step (`INK_PROF`).
- Dense prompt products (Q8_0 / Q6_K tiles from 64 tokens: attn_q, k, v, gate, rel, output) the same way: 4 rows per
  sub-group (4 sums going, was 2) and 32 sub-groups per work-group (`INK_DENSE_R`, `INK_DENSE_SGW`). `INK_PROF` 3K
  prompt (card 3): attn_output 1,323 -> 999 µs per launch with 4 rows, 935 with 32 sub-groups too; the whole prompt
  3,811 -> 3,613 ms. Prompt reading, the same card (ids identical; logits rows after 100K bit-identical): 3K 811.4 ->
  858.4 tok/s (card 3), 763.1 -> 798.9 (card 1); 31K 739.4 -> 770.3 (card 3); 100K 495.9 -> 513.0 (card 4). The
  layers 20-23 expert tiles (other formats, no tables) gain nothing from bigger work-groups (`INK_TILE_SGW=32`: gate|up
  6,714 -> 6,675 µs, down 3,429 -> 3,455).
- More than 4 sums per lane in the expert tiles is slower in every form tried with 32 sub-groups (1,024 tokens, card
  3; best 4 rows 7,448 / 3,940 µs): two chunks at a time 10,075 / 6,108 (8 sums, no spills, 59 % multiply-adds),
  8 rows with 256 registers 9,515, two chunks with 256 registers 9,834 / 5,672. With 128 registers the compiler has
  4 accumulator registers (`numAcc=4`; 8 with 256) and chains the 4 rows' sums through them.
  The rows interleaved in the source (value outer, row inner) change nothing (8 rows 11,405 vs 11,006); pairs of
  tiles with 2 rows (4 sums, the weights decoded once for 32 tokens) 11,922 / 6,272 vs 7,439 / 3,933; one table of
  the 4,096 code x scale products (the same floats, 2 lookups and no multiplications) 7,902 / 4,119-4,133 vs
  7,537-7,600 / 3,937-3,974 (the fill of 16 KiB per work-group costs more).

Long prompts, attention in larger chunks and the exponentials computed once (2026-11-24, card 3/4/5). At 100K the
prompt was 189 s: experts 62 s, the full-attention layers 76 s (scores 25.0, P.V 28.1 + block sums 7.1, softmax
15.4: reading and writing the score rows P, ~500 GB/s). Three changes, the same values throughout:
- Score rows from free card memory: P holds as many rows as 512 MiB, or up to 256 (`INK_P_ROWS`) while the card keeps
  6 GiB (`INK_P_FREE_GB`) for the later allocations and the drafter (`INK_P_MB` still sets it outright). At 100K 48 ->
  256 rows: keys and values read 5x less often, and from 128 rows P.V runs without block parts. 100K, `INK_P_ROWS`:
  128 rows 532.5 / 521.7 tok/s, 256 555.3 / 549.7, 512 542.0 / 539.4 (cards 4 / 5; 48 rows 513.2 / 504.5). 200K gets
  128 rows (27.02 GiB in use, the drafter fits: 28.47): 338.5 -> 366.0 tok/s, logits rows identical; past ~300K the
  512 MiB floor as before (one card still holds 420K positions).
- The softmax of the prompt tiles writes no exponentials, only each row's maximum (`attn_softmax_sum` mout) next to
  1 / total; P.V computes exp(score - maximum) * (1 / total) as it reads, the softmax's own expression (`INK_PV_EXP=0`
  off). 100K x 256 rows (bench_attn `BENCH_PVEX`): softmax 9,860 -> 4,315 µs.
- In P.V each of the 4 sub-groups of a work-group computed all 12 rows' exponentials (+28 % P.V: 11,379 -> 14,265
  µs); `attn_pv_tile_xs` lets sub-group s compute rows 3s..3s+2 into local memory (two buffers, one barrier per 16
  keys): 11,743 µs. Softmax + P.V at 100K x 256 21,239 -> 16,058 µs, 31K x 256 6,578 -> 4,883. Other shapes with the
  exponentials on read: <2,3,4> 13,103 (each computed twice), xs<2,3,4> 13,364, xs<4,3,4> 41,259, xs<8,3,2> 34,467.
- Prompt reading, the same card (ids identical, logits rows after 100K bit-identical to the old engine): 100K 512.7 ->
  577.0 tok/s (card 4), 504.5 -> 574.4 (card 5); 31K 774.2 -> 797.6 (card 3), 723.2 -> 747.7 (card 1), 718.1 -> 744.3
  (card 2); 3K level (860.0 / 859.7). Under load the cards run at ~2,350-2,500 MHz of 2,800, held by the short-term
  power limit (`throttle/reason_pl2`), so fewer instructions per result also keep the clock up.

Energy, not time, decides a long prompt (2026-11-24). `Device::energy_j()` reads the card's energy counter (hwmon
`energy1_input`, read-only); bench_attn, bench_moe and bench_fma (`BENCH_FMA_ENERGY=1`) print J per launch. A prompt
keeps the card at its power limit (clock 2.35-2.65 GHz), so a kernel that only waits less (same work) gains nothing
in the engine: score tiles with 4 queries past 34K keys were 11-18 % faster alone (100K x 256 rows 17,982 -> 14,773
µs) but used only 6 % less energy (5.10 -> 4.81 J), and the 100K prompt did not change (574.2 vs 575.2 tok/s card 1,
609.4 vs 616.0 card 3, 574.0 vs 580.9 card 4, 572.9 vs 571.3 card 5; logits identical). The floor (card 3): a lane's
fp32 multiply-add costs 17 pJ (16 chains, 11.3 TMAC/s, 190 W: not at the limit) and 22 pJ with the tiles' broadcast
pattern (10.5 TMAC/s, 235 W); the NVFP4 expert tiles cost ~57 pJ (gate|up 1,024 tokens 2.47-2.53 J for 43.5 G) and
the full-attention score tiles ~65 pJ (5.10 J for 78.5 G). Reading the code bytes as sub-group block reads (no
per-lane 64-bit addresses) changed neither time nor energy (2.50-2.54 vs 2.47-2.53 J).
Expert gate|up energy budget (card 3, 1,024 tokens, bench-only builds with `-DINK_ABL`, wrong values on purpose):
full 7,415-7,522 µs / 2.458-2.501 J; without the NVFP4 decode (constant weights) 6,231-6,235 µs / 1.913-1.920 J;
without the input loads (each chunk reuses the first chunk's inputs) 6,344 µs / 2.067 J; without both 6,223 µs /
1.872 J. So the multiply-add core (broadcasts, sums, the butterfly) holds three quarters of the energy; decode and
loads overlap with it. A compile-time chunk count (72 / 36 chunks, no loop-exit tests) was level (2.457-2.468 vs
2.466-2.501 J). The `INK_ABL` switches were removed again after the measurement.
Full-attention chain at 100K keys x 256 query rows (card 3, bench_attn BENCH_TILE/BENCH_WMAX/BENCH_PVEX): scores
`attn_scores_tile<8,3,4>` 17,987 µs, softmax (maxima only) 4,326 µs (reads the 2.46 GB of scores at ~570 GB/s), P.V
`attn_pv_tile_xs<4,3,2>` 12,272 µs: 34.6 ms. Score-tile budget (same bench-only `-DINK_ABL` method): full
18,020-18,096 µs / 5.05-5.08 J; keys of the first 16 channels for all channels 14,762 µs / 4.26 J; queries likewise
16,818 µs / 4.71 J; no score stores (maxima kept) 13,134 µs / 3.77 J; all three 10,679 µs / 3.07 J (7.4 TMAC/s). The
stores of the 2.46 GB of scores are the largest part, and not through the caches: uncached stores 26,338 µs,
streaming 18,018 µs, block writes of 64 contiguous bytes 1.5-2.5 % faster. Keeping the scores out of memory would
need softmax and P.V fused with a running maximum, which changes rounding (a new baseline for every attention path,
the writing steps included, since the prompt and writing paths give the same bits today).

Running maximum, baseline v4 (2026-11-24, `src/attn_flash.hpp`; `INK_FLASH=0` gives baseline v3, kept as
`baseline-v3`, bit for bit). The 8 full-attention layer applications now take softmax and P.V per block of 128 keys:
the block's own maximum, its exponentials, their sum (lanes over keys, then a fixed xor-shuffle sum) and its P.V
(keys ascending); the blocks fold in order into a state that starts from the sink (maximum = sink, total = 1):
each block multiplies the state by exp(old maximum - new maximum) and its own parts by exp(block maximum - new
maximum), and the output divides by the total at the end. A prompt step of >= 128 tokens never writes its scores:
one work-group (8 queries x 3 heads x 128 channels, `attn_flash_tile<8,3,1>`) computes a block's scores into local
memory, turns them into exponentials and block sums, does the block's P.V and moves on. Writing steps and short
pieces keep the scores in P and run `attn_flash_part` (per block) and `attn_flash_sum` (the fold: the running
maximum is a prefix maximum, exact in any order, so one work-group scan gives every block's two factors and the lanes
compute them in parallel). Every path computes the same expressions in the same order, so they agree bit for bit:
gate 11/11 against `baseline` (made by `make-baseline.sh` through the general kernels); the 3,127-token prompt read
through the fused tiles, through scores + block parts (`INK_FLASH_MIN=100000`) and without tiles (`INK_ATT_TILE=0`)
gives identical logits for all 16 following steps, and so do the fused and block-part prompts at 100K. Windowed
layers are unchanged.
Accuracy: against double precision (bench_attn `BENCH_FLASH=1`, random data, 12 rows) 3K keys max error 2.83e-08 vs
v3 3.08e-08 (rms 4.42e-09 vs 4.07e-09), 100K keys 7.79e-09 vs 6.41e-09 (rms 1.27e-09 vs 1.02e-09); against the
high-precision reference on the 300-token prompt (`oracle/p300`) final scores median 3.796e-03 -> 3.761e-03 (v4
closer at 165 of 300 positions), the same top token as the reference at 98.0 vs 97.0 % of positions, layer 11's
attention output 2.97e-03 -> 1.87e-04. The gate prompts' ids are unchanged (haiku, code, 3,127 + 16). After long
prompts near-ties can go either way, as with every earlier baseline: the logits right after the 3,127-token prompt
move by up to 7.44 (mean 1.05) between v3 and v4, as they did between v1 and v3 (8.15, mean 1.28) and v2 and v3
(3.21, mean 0.50); after the 100K test prompt the first token changes (v3: 11 at p 0.246, 196975 at 0.148; v4:
196975 at 0.356, 11 at 0.230), while a 5-token prompt's final scores move by at most 3.6e-04.
Speed (bench_attn, card 3, 100K keys): 256 rows 33.5 -> 23.1 ms (scores + softmax + P.V vs the fused tile), 128 rows
17.9 -> 14.9 (`<4,3,2>`); one-token step 499 -> 468 µs per layer, 4-token checks 879 -> 862. Prompts (same binary,
same card, both orders): 200K 403.9 -> 507.4 tok/s (card 4), 397.2 -> 499.3 (card 5); 100K 614.9 -> 691.6 (card 3),
581.1 -> 645.7 (card 4); 31K 743.9 -> 785.2 (card 1), 796.3 -> 839.8 (card 3); 3K level (803.4 / 802.4, 857.8 /
862.6). Writing: at 200K 38.04 -> 39.96 tok/s, at 100K 52.75 -> 53.06, after the code prompt level (89.90-89.95 /
89.51-90.01). Fused-tile shapes: `<8,3,1>` 23.1 ms at 100K x 256, `<4,3,2>` 25.4, `<8,3,2>` 49.2, `<4,3,4>` 46.8,
`<2,3,4>` 67.4 (the last three spill or starve). `prow` (the score rows P holds) can shrink now that long prompts no
longer keep full-layer scores.
Fused-kernel code shape (2026-11-24, same values: every variant "vs ref same", gate 11/11). The kernel is not limited
by memory: keys and values from a 2,048-key ring that fits the cache take 22.9 vs 23.1 ms (100K x 256). Its machine
code (`IGC_ShaderDumpEnable`) showed the compiler turning P.V's 24 independent sums into one 16-long dependent chain
per row in acc0 (the slow pattern: bench_fma 1 chain = 5.0 TMAC/s); loading the next key group's exponentials one
group ahead (`attn_flash_tile` VAR 4) makes it interleave them: 100K x 256 23.1 -> 20.7-21.1 ms, 3K x 1,024 4.0 ->
3.6-3.7 ms; prompts (same card, both orders, logits identical) 100K 649.2 -> 656.7 (card 4), 637.7 -> 651.1 (card 5),
31K 787.8 -> 792.5 (card 1), 842.3 -> 854.0 (card 3), 3K level. The block loop is now ~59 % multiply-adds: per block
a sub-group issues 192 Q loads at ~5 instructions each (64-bit addresses), 512 half-to-float moves (two per value) and
24 sub-group maxima. Closed (DO-NOT-REPEAT): two score buffers, Q block loads, constant Q offsets, local block loads,
unrolling, compiler settings against the accumulator chains.
Lean prompt attention (2026-11-24, `attn_flash_tile` VAR 1052, `INK_FLASH_LEAN=0` = before). Budget first
(bench_attn `BENCH_BUDGET`: builds that drop one part, wrong values on purpose; card 3, 100K keys x 256 rows, 20.7 ms
/ 6.0 J in all): score products 8.8 ms, P.V products 8.9 ms (each alone ~79 % of the multiply-add peak), everything
else (maxima, exponentials, barriers) 4.0 ms / 0.70 J, of which the exponentials 1.15 ms; loading Q once instead of
per block is slower (22.3 ms: 24 more live registers). Each sub-group now takes the block maximum of its own 3 rows
from the scores in local memory (3 sub-group reductions per block, not 24; a maximum is the same in any order), and
the two shapes closed alone (constant Q offsets, local block loads of the exponentials) come back with it: 20.46-21.05
ms / 5.86-6.21 J -> 20.06-20.12 ms / 5.53-5.60 J, vs ref same. Prompts (same card, both orders, logits rows and ids
identical): 200K 555.8 -> 566.5 tok/s (card 3), 518.8 -> 531.3 (card 4); 100K 655.3 -> 663.8 (card 1), 649.9 -> 661.6
(card 5). Not kept (DO-NOT-REPEAT): 256 registers, Q in local memory, the rescale factors as 3 lane loads (faster
alone, more energy), skipping the masks of far blocks; 8 rows or tile pairs for the dense Q8_0 prompt tiles.
Dense products by weight format (`INK_PROF_TYPES=1` adds the format to profile labels; 3K prompt, card 3, per launch
of 1,024 tokens, attn_q's shape): Q8_0 928 µs, Q6_K 1,703, Q5_K 7,660 through the generic multi-vector kernel ->
2,550 as tiles (layer 22's attn_q is the only Q5_K dense matrix; `INK_Q5K_TILES=0` = before; gate 11/11, the 300-token
dumps cover it): 3K prompt 3.595 -> 3.573 s.
Writing steps without scores in memory (2026-11-24, `attn_flash_dec`, `INK_FLASH_DEC=0` = before): a work-group
computes one block's scores into local memory with `attn_scores_gt`'s expressions (the relative-bias table), then runs
`attn_flash_part`'s code on them, so P is neither written nor read and the keys and values are read in one launch.
Writing (same card, both orders, logits of all 64 steps identical): after 100K 53.41 -> 54.91 tok/s (card 4), 53.07 ->
54.60 (card 5); after 31K 70.04 -> 71.07 (card 1), 72.22 -> 73.33 (card 3); prompts level. Before (100K, card 3,
`INK_PROF`): scores 408 µs + parts 440 + fold 46 per layer, the keys and values each at ~500 GB/s. Gate 11/11 (spec
checks of 2-16 rows included). Q6_K weights now stay off the card's upload (only the padded planar copy goes on:
`INK_Q6K_SKIP=0` = both copies): 0.41 GiB less card memory (100K: 23.41 -> 23.00 GiB).
Then all full-layer steps below the fused prompt tile (`INK_FLASH_MIN`, 128 tokens) take `attn_flash_dec`; with tiles it
adds the relative bias from `Rc` and `rel_bias` as `attn_scores_tile` does (i ascending, the same bits). Only the windowed
layers still use P, and they store each row from its window's start (column j - lo), so P's rows are the window wide
(1,024) instead of the context, and the block-sum buffer keeps full-context rows only for `INK_DEC_ROWS` rows (16 up to
128K positions, else 4). Card memory at 100K 23.00 -> 20.23 GiB (score rows 256 -> 1,024 per chunk, so the windowed
layers' prompt attention runs in one chunk per step), speed level (card 3 706.3 vs 703.4 tok/s prompt, 55.81 vs 55.84
writing; logits of 64 steps identical on cards 3 and 4). One card now holds 480,000 positions (30.71 of 31.89 GiB;
500,000 refused), was 420,000. Gate 11/11.

Longest context on one card (2026-11-24): 521,000 positions (was 480,000), from four changes, each gated (11/11) and
each leaving speed level (same card, both orders):
- The token embedding table stays in host memory (`Engine::embed`; `INK_EMBD_HOST=0` = on the card): each step's
  rows are decoded on the host with the kernel's expression (Q8_0: q * d, one multiply) and copied in queue order; the
  host already reads every chosen token back, and the drafter takes its anchor token on the host too. -0.46 GiB.
- The loop layers' 48 mixes per pass are precomputed only for steps of up to 16 tokens (`INK_LOOP_PRE_TOK`): longer
  steps mix per layer (the same values). -216 MiB at 512-token steps, -432 MiB at 1,024.
- `INK_MEM_RESERVE_MB` default 1024 -> 512: the runtime holds ~0.26 GiB beside our allocations (driver free memory at
  the end of runs from 3K to 515K positions, with and without the drafter), so 512 MiB leaves ~0.25 GiB untouched.
- `ink_run` and the engine report the driver's free memory at the start and at the end; `INK_MEM_LOG=<MiB>` lists
  every allocation of at least that size.
Needle tests (two one-line notes in lab notes, the question at the end, 512 tokens allowed): 470,949 tokens on card 3
read in 1,310.6 s (359.3 tok/s; the 403K test on 2026-11-23 read at 173.0), writing 24.64 tok/s; 514,670 tokens on
card 2 (515,198 positions, 0.50 GiB free at the end) read in 1,644.2 s (313.0 tok/s), writing 22.98 tok/s. Both answer
"Vault code: 7351-QX-4829; meeting room: Juniper-12." (their thinking names the sections the notes sat in).

The drafter at long contexts: its full layer kept every position (4 KiB each) and a score buffer only the one-row path
uses held 768 B more per position. The buffer is now allocated only for that path (`INK_DSP_SPLIT=0`), and the full
layer keeps a ring of 16,384 slots (`INK_DSP_WIN`, default ~15K positions; 0 = every position): 64 MiB instead of 2.3
GiB at 471K. Guesses only, the text cannot change: 100K prompt, 256 tokens, tokens per check 2.54 (every position) /
2.49 (64K) / 2.46 (32K) / 2.53 (8K), drafting 0.32 -> 0.24 s with 8K, text identical in all four. 31K prompt, 256
tokens, same card both orders: the default ring 2.61 tokens per check vs 2.59, writing 103.02 -> 105.50 tok/s (card 4)
and 101.57 -> 104.60 (card 5), text identical.
With the ring, guessing fits beside a 471K context (drafter +0.55 GiB): the 470,949-token needle on card 3 writes
at 41.00 tok/s against 24.64 without guesses (2.34 tokens per check), ids identical to the plain run.

Checks of up to 8 tokens (2026-11-24; `INK_SPEC` up to 7). Steps of 5-8 tokens used to fall back to the general
kernels: 34.7 / 40.5 / 45.5 / 48.1 ms at 3K against 21.3 for 4 tokens (card 3). The small-step paths now take up to
8 tokens (`Engine::SB_MAX` 8). The attention inputs go in one launch (`gemv_multi_m`, 5-8 vectors at one row per
sub-group). The experts run in passes of up to 4 slots per chosen expert (`GroupedPairT` / `GroupedRowsT` / `...S`),
along with the fused windowed attention, the batched control modules and the lane-order output rows. The result is
24.8 / 28.4 / 31.4 / 34.0 ms, and each token keeps its one-token values.
The checking attention (`attn_flash_dec` VAR 1) now has each sub-group take its own 16 keys' share of every row's
block maximum (through local memory; a maximum is the same in any order) and their exponentials once. Before, all 8
sub-groups computed all of them. bench_attn card 3, 200K keys + `attn_flash_sum`: 4 rows 1,618-1,628 -> 1,579-1,595
us; 8 rows in one launch 2,348-2,360, against 2,854-2,876 without VAR 1 and 3,590-3,650 as two 4-row launches (the
cache read twice); vs ref same. `dec_rows` is 8 up to 480K positions (0.75 KB per position) and 4 past that, so the
longest context is unchanged.
Choosing the guess count (`ink_run`): step costs for 5-8 tokens are 23.9 / 27.5 / 30.5 / 33.1 ms. Every cost grows
with the context: 6.2e-5 ms per position for the cache read (`INK_SPEC_KV`; a second read when a check has more rows
than `dec_rows`) plus 3.85e-6 ms per position for each further token (`INK_SPEC_KVX`, card 3 profile at 200K: 1-token
attention 12.5 ms, 4 tokens 14.8).
Drafting 7 guesses cost more than the checks gained at short contexts (3K prompt + 256 tokens 107.1 -> 100.2 tok/s).
The drafter's output-layer read for 7 slots takes 1,219 us against 776 for 3, and each guess runs its own chain of
kernels. Three changes fix this:
- Slots 1-3 are read first. The host then reads guesses 1-3's probabilities and submits slots 4-7 (a second read,
  855 us) and guesses 4-7 only when their chain of keep chances is at least r / (0.93 - 3 r), where r is a 5-token
  step's extra cost over 4 (`Drafter::stop_hi`, set each round). Below that, a 4th guess can never be worth its check.
- A guess whose chain fell below 0.1 skips its 51 MB correction read (`INK_DSP_STOP`; draft() returns only the
  guesses before it).
- Skipping the stopped guesses' kernels on the card did not help (their ~20 launches cost ~0.25 ms per round), and
  neither did one 7-slot read with a skip flag. The host decision did.
Writing with the drafter (same card, both orders, ids identical; `INK_SPEC=7` against the build before with
`INK_SPEC=3`):
- 200K prompt ending in the code request, 256 tokens: 70.04 -> 75.96 tok/s (card 3) and 68.35 -> 73.92 (card 4);
  3.14 tokens per check, was 2.67.
- The same prompt ending in the haiku request, 128 tokens: 62.63 -> 65.40 (card 1) and 62.35 -> 65.15 (card 5).
- Short prompts (cards 3 / 4, two runs each): code 256 128.5 -> 134.0 / 123.4 -> 129.5; haiku 128 104.7 -> 108.1 /
  100.4 -> 103.4; the 3K prompt + 256 107.2 -> 106.4 / 103.4 -> 102.5 (-0.8 %: few of its chains reach a 4th guess).
- Prompts level (200K: 566.4 vs 565.8 tok/s on card 3).
Gate 12/12; new checks: haiku with 7 guesses checked every round (steps of 8 tokens, every chosen logits row), and
code with 0-7 guesses.
The drafter seeing all 200K positions (`INK_DSP_WIN=0`) kept a few more guesses but wrote slower (DO-NOT-REPEAT).
Prompt step, small products (2026-11-24, INK_PROF 3K prompt, card 3: 3,428 ms of kernels, of which experts 2,011,
dense matrices ~715, windowed attention 203, the rest ~460):
- The attention inputs' products now run grouped by input, and the dense tiles gather each input once (`xd_keep`,
  `INK_XD_KEEP=0` = before). The windowed layers' 6 products share one input. 1,968 -> 1,424 gathers, 58.0 -> 45.5 ms.
- F32 / BF16 tiles from 64 tokens take 4 rows per sub-group and 32 sub-groups (`INK_DENSE_RF`, `1,1` = before; the
  same values): the loop down products 137-140 -> 66-69 us per launch, the expert router 86.9 -> 34.0.
Prompts (same card, both orders, the prompt's logits row identical): 100K 666.8 -> 671.6 tok/s (card 1) and 661.6 ->
670.8 (card 5); 31K 862.5 / 858.4 -> 867.8 / 867.6 (card 3) and 806.8 / 801.7 -> 820.3 / 812.7 (card 4); 3K 802.9-813.0
-> 818.9-822.2 (card 2). Gate 12/12.
- The loop controls' gain|forget outputs (`ctl_out`, 64 columns, the op reads two values and writes one per pair of sums)
  go through local memory first, so each sub-group applies the op to 16 consecutive rows of one token
  (`DensePairTS`, `INK_CTL_T`, `0,0` = before): 199.2 -> 146.5 us per launch.
- F32 / BF16 products from 16 rows take the tiles (`INK_DENSE_MINROWS_F`, 64 = before; 2 rows x 4 sub-groups under 64
  rows, `INK_DENSE_RFS`): the 24-row sink product 61.7 -> 22.5 us. Its input is already gathered for the others.
Prompts (same card, both orders, logits identical): 100K 673.2 -> 678.5 tok/s (card 1) and 668.2 -> 677.3 (card 5); 31K
867.7 / 867.9 -> 878.7 / 877.5 (card 3) and 814.7 / 811.0 -> 825.9 / 819.6 (card 4); 3K 820.8-822.5 -> 827.1-830.4
(card 2). Gate 12/12.
- The expert tiles' input copy (`moe_tiles`) takes one slot per lane: 16-byte loads of the slot's row, each column's
  store the 16 lanes' 64 consecutive bytes (`tile_gather_l`, `INK_TG`, 0 = before): 401.5 -> 200.8 us per launch.
- Attention prep at prompt steps takes one sub-group per row (`attn_prep_sg`, `INK_PREP_SG`, 0 = before): lane l holds
  channels l + 16 k, so the 8 partial sums are the old sub-groups' sums in the old order; no local memory or
  barriers, and a 16-value R row takes one sub-group instead of 8. 209.5 -> 88.3 us.
- The feed-forward tail slides along 8 tokens per thread (`ffn_tail_s`, `INK_FT`, 0 = before): each token's
  combine of the 8 expert outputs is computed about once instead of 4 times. 242.0 -> 172.7 us.
Prompts (same card, both orders, logits identical), gather + prep: 100K 679.5 -> 685.6 tok/s (card 1) and 672.9 ->
683.3 (card 5); 31K 878.9 / 878.0 -> 890.0 / 887.7 (card 3) and 821.9 / 819.9 -> 835.9 / 829.9 (card 4); 3K 828.1-829.9
-> 835.4-840.8 (card 2). Then the tail: 100K 686.4 -> 688.5 and 680.6 -> 687.7; 31K 895.2 / 890.4 -> 894.2 / 892.2
(card 3) and 835.9 / 830.1 -> 843.0 / 835.9 (card 4); 3K 839.2-840.8 -> 842.0-844.9. Gate 12/12 each.
- The 18 dense Q6_K matrices (layers 2-23: some attn_q / attn_gate / attn_k / attn_rel) ran 1.8x slower than Q8_0 in
  the prompt tiles (6 loads and the bit extraction per row and chunk). They now get a prompt copy (`pl::Q6_KU`, built
  on the card from the Q6_KP copy: the codes - 32 as bytes, each 16 values' d * sc as a float, the same multiply), read
  only by `dense_t` (`INK_Q6KU=0` off, none past `INK_Q6KU_CAP` = 500,000 positions, so the longest context is
  unchanged): 97.0 MB. INK_PROF 3K prompt, card 3, us per launch: attn_q 1,708 -> 923, attn_gate 1,700 -> 898, attn_k
  568 -> 320, attn_rel 217 -> 124 (Q8_0: 928 / 904 / 311 / 126); kernels 3,249.7 -> 3,210.9 ms.
- Layers 20-23's down experts (Q5_0, IQ4_NL) take 4 rows per sub-group, two tiles one after another, 8 sub-groups
  (`slot_rows_x2`, `INK_TILE_X2`; the same sums): Q5_0 6,638 -> 4,853 us, IQ4_NL 6,265 -> 4,593 (card 1). Pairs of
  tiles and 4-row gate|up were slower (DO-NOT-REPEAT). `INK_PROF_TYPES` now splits the expert kernels by format:
  per 1,024-token launch (card 1) gate|up NVFP4 8,529 us, Q5_K 13,926, IQ4_XS 11,026, Q4_K 9,854; down NVFP4 4,305.
Prompts (same card, both orders, logits identical): 100K 689.6 -> 697.7 tok/s (card 1) and 683.3 -> 696.2 (card 5); 31K
897.8 / 894.1 -> 907.3 / 906.0 (card 3) and 837.9 / 832.8 -> 852.9 / 847.3 (card 4); 3K 834.2-845.7 -> 854.2-856.6
(card 2). Gate 12/12.
At 403K positions 512-token steps stay faster than 1,024 (410.9 vs 405.0 tok/s card 3, 383.0 vs 377.8 card 4; at 200K
1,024 is +1.3-1.9 %), so the 300K switch stays (DO-NOT-REPEAT).

Windowed prompt attention in one launch (2026-11-24, `attn_win_tile`, `INK_WIN_TILE=0` = the three kernels before).
The 40 windowed layers ran scores (`attn_scores_tile<8,3,8>`), softmax (`attn_softmax_norm`) and P.V
(`attn_pv_tile<4,3,2>`), with 102 MB of scores written and read back between them per layer-step. Now one work-group of
128 threads takes 4 queries x the 3 heads of one KV head and does all three in turn, with each value computed by the
same expression in the same order: the scores as the score tile; the row maximum taken in the score loop (a maximum is
the same in any order); the exponentials and their total as the softmax's 128 threads (one sub-group per row, lane l
playing threads l, 16 + l, ... in the same order); P.V per channel with keys ascending inside 128-key blocks. P.V
multiplies each exponential by 1 / total as it reads it, the same product the softmax stored, so two passes over the
rows are gone. The rows live in the work-group's own slice of `P` (mostly served from the cache); in local memory they
take 50 KB per work-group and run 2.7x slower (too few work-groups per core). INK_PROF 3K prompt, card 3, per
layer-step: three kernels 1,269 us -> 827 (2 queries 1,205, 5 850, 6 906, 8 883); windowed attention 203 -> 132 ms per
prompt. By the multiply-add count (about 3.3 billion each for scores and P.V per layer-step) 827 us is ~85 % of the
card's FP32 peak at its loaded clock. `P` grows 3 MB.
Prompts (same card, both orders, logits identical): 100K 697.9 -> 706.9 tok/s (card 1) and 692.1 -> 707.8 (card 5); 31K
911.2 / 907.5 -> 926.8 / 922.4 (card 3) and 852.2 / 846.2 -> 869.9 / 866.0 (card 4); 3K 825.0-855.4 -> 868.3-870.6
(card 2). Gate 12/12.

Loop controls at prompt steps (2026-11-24; same values, INK_PROF 3K prompt, card 3):
- The gain|forget outputs (64-column F32 rows) have their own kernel (`ctl_out_r64`, `INK_CTL64=0` = before). A
  sub-group takes 16 tokens (lane = token, its 64 inputs read once into registers) and 16 rows. Each weight row arrives
  as 4 sub-group block reads per matrix, one row ahead, and each product takes its weight with a constant-index select.
  The 64-column sum is the tile order, (0 + s0) + (0 + s1), and the op goes through local memory as before. The
  gather of the inputs is gone. 146.5 -> 119.4 us per launch. Two rows per pass, op reads first, the op loop
  unrolled, 32 rows per sub-group, 256 registers and branch-sorted tanh arguments were all slower (DO-NOT-REPEAT).
- The two control norms write the down product's tile input directly (`ctl_norm_tiles`, `INK_CTL_NT=0` = before).
  Each of 16 sub-groups takes one token and replays the norm's sum order, then the work-group writes 16 tokens per
  store. That removes the norm's write and the gather's read and write: 48.1 + 2 gathers -> 56.1 us per launch, 1,040
  -> 752 gathers per prompt, kernels 3,144 -> 3,122 ms.
Prompts against the commit before (both orders, logits identical): 100K 708.4 -> 713.2 tok/s (card 1) and 703.1 -> 712.2
(card 5); 31K 926.9 / 922.3 -> 932.2 / 929.0 (card 3) and 868.3 / 863.9 -> 877.9 / 872.3 (card 4); 3K 869.1-870.2 ->
876.0-878.8 (card 2). Gate 12/12.

Loop mixes and the block fold (2026-11-24; same values):
- Prompt steps now score the pass's loop bank once at the pass start (`mix_scores_many`, as writing steps already did;
  `INK_LOOP_SC=0` = per layer call). A looping layer's two loop mixes (2 + 2 queries) then come from that table in one
  pass over the bank (`mix_out4`, `INK_MIX4=0` = two `ops::mix_out`). Each (token, query) softmax is computed once
  instead of once per output value, and each state value is read once for the four outputs. 3K prompt (INK_PROF): 192
  mix_scores (12.7 ms) -> 8 loop_mix_scores (7.3 ms), 192 loop mix_out (23.8 ms) -> 96 loop_mix_out (7.5 ms).
- The fold of a writing step's full-attention blocks (`attn_flash_sum`, one work-group per row: 24 at a one-token
  step) takes each 128-block chunk's prefix maxima from 16-lane scans and the 8 sub-group maxima through local memory
  instead of two 128-wide scans and a broadcast (a maximum is the same in any order), and loads 32 blocks' partial
  values together (`INK_SUM_U`, 8 = before). At 100K, us per launch: 46.1-46.2 -> 36.4-38.9.
Against the commit before (both orders, logits identical): 100K 711.9 -> 714.4 tok/s (card 1), 705.6 -> 712.9 (card 5),
writing the next 256 tokens 54.89 -> 55.20 and 54.94 -> 55.08 tok/s; 31K 937.5 / 931.4 -> 939.0 / 935.3 (card 3), 872.8 /
870.9 -> 882.4 / 873.4 (card 4); 3K 876.3-878.7 -> 878.7-883.8 (card 2). Gate 12/12.
Power (2026-11-24, `powlog` of every card's energy counter, clock and throttle reasons, read-only): a 200K prompt holds
the card at 230 W with `pl2` set and 2,217-2,250 MHz of 2,800 for its whole 6 minutes (200K profile: full attention
154.7 s of 357.9, experts 125.3, dense products ~46, the rest ~32). One-token writing after 200K: 23.9 ms of kernels,
of which the full layers' keys and values 11.9 ms (6.55 GB at 551 GB/s). The windowed layers' one-token attention
(`attn_win_fused`, 16 work-groups of 1,024 threads) is 15-20 us per layer although it reads 4 MB: scores ~7.7 us, P.V
~9.4, the rest ~3 (bench_attn `BENCH_WINF`). Each work-group must read all of its KV head's window for the exact
maximum and total, so only a key split across work-groups (waits between them) would use more cores.

Prompt step size by context (2026-11-25; every size gives the same bits, logits compared at each): `ink_run` takes
steps of 4,096 tokens up to 65,536 positions, 2,048 up to 131,072, 1,024 up to 300,000 and 512 past that
(`INK_UBATCH=<n>`: that size only). Bigger steps fill the expert tiles better; at long contexts the attention takes
most of the time and they stop paying. tok/s for steps of 1,024 / 2,048 / 4,096 (`INK_UBATCH`): 3K 869-884 / 941-945 /
965-967 (card 2), 31K 935-943 / 956-966 / 969-971 (card 3), 100K 712-718 / 719-723 / 717-718 (cards 1, 5), 200K
559-563 / 553-554 / - (cards 1, 5). Card memory at 100K: 19.46 / 20.70 / 23.79 GiB. If a size does not fit beside the
context, the engine is built again with half the steps (down to 512; above 512 it must leave 1 GiB for the drafter),
so the longest context is unchanged. When the last step would be under 512 tokens the prompt goes in steps of one size
(4,150 tokens as 2,080 + 2,070, not 4,096 + 54: 937.6-941.4 -> 955.5-961.3 tok/s, card 2). The gate's drafter run on
the 3K prompt keeps steps of 1,024 (`INK_UBATCH=1024`) so the windowed caches across steps stay covered.
Against the commit before (both orders, logits identical, gate 12/12): 3K 866.7-882.8 -> 964.9-967.4 tok/s (card 2),
5K 929.4-933.9 -> 962.5-971.4 (card 2), 31K 934.4-940.2 -> 969.5 (card 3) and 872.7-874.8 -> 905.1-915.4 (card 4),
100K 716.3 -> 716.1 (card 1) and 708.5 -> 716.0 (card 5); writing after 100K level (55.04-55.16 vs 55.15-55.34).

Kernel programs loaded before the prompt (2026-11-25): the runtime loads a kernel's program on its first launch, so
the first prompt step waited 145 ms before the first attention-input product and 25 ms after the first embedding copy
(card idle 171 of 3,229 ms at 3K; `INK_PROF_GAPS=<n>` lists a step's n longest idle gaps between launches). `ink_run`
now loads all 2,978 kernels at model load (`sycl::get_kernel_bundle<executable>`, 0.2 s; `INK_PRELOAD=0` = on first
use): idle 8.8 ms. Card memory the same (11.85 vs 11.84 GiB free), host peak +53 MB. Against the commit before (both
orders, logits identical, gate 12/12): 3K 958.6-963.1 -> 1,015.1-1,018.7 tok/s, 5K 965.0-966.6 -> 997.4-1,000.1 (card
2), a 39-token prompt 0.32-0.35 -> 0.16 s; 31K 970.0-977.3 -> 976.2-979.2 (card 3), 910.3-915.9 -> 912.5-922.8 (card
4); 100K level (713.7-717.0 vs 716.9-718.1, cards 1 and 5).
Longest contexts again on this build (6a816734d9, 2026-11-25; the same answers, ids identical to the earlier runs):
514,670-token needle on card 2 read at 332.9 tok/s (was 313.0), writing 23.20 tok/s (22.98), 0.47 GiB free at the end;
470,949 tokens with the drafter (`INK_SPEC=7`) on card 3 read at 383.2 tok/s (359.3), writing 43.57 tok/s (41.00
with guesses, 2.72 tokens per check). At 520K positions the card holds the weights (15.0 GiB: the file without the
host-side embedding table, rows padded to 16 bytes), the full layers' keys and values (15.9 GiB) and ~0.9 GiB of step
buffers (`INK_MEM_LOG=16`): one card is at its limit there.
`INK_PROF_SEQ=<k>` prints the k-th profiled step's launches in order with their time and the idle before each. One-token
step after 3K (card 1): a layer is mix_norm 9-11 us, attention inputs 40, attn_prep 3.3, attn_win 19, attention output
16, attn_tail 1.6, mix_norm 10, router 5.2, moe_route 4.7, gate|up 53, down 28.5, ffn_tail 4.4, with 0.1-0.2 us
between launches.

Prompt lookup beside the drafter (2026-11-25, `ink_run`, `INK_SPEC_LOOKUP=0` = the drafter alone). At long contexts a
check costs mostly the read of the keys and values, so writing speed follows the tokens kept per check. The drafter
sees only its 16K ring, while an answer often quotes the context (the needle answers quote the notes they found).
Each round now also takes prompt lookup's guesses (the tokens after the most recent earlier occurrence of the last 4,
3 or 2 tokens, through an n-gram index built on a host thread while the card reads the prompt) and checks whichever
of the drafter's guesses or lookup's promises more tokens per ms under the existing count rule. Lookup's keep chance
per match length is learned from every round, checked or not (the round's tokens are the model's, so lookup's guesses
are scored against them; counts decay by 0.9 a round, from 1 kept of 4). Where lookup and the drafter guess the same
token the better chance counts; at their first difference lookup's chance is at most 1 - the drafter's. With a
4-token match, at least 4 guesses and a learned chance of 0.8 or more the drafter is not run that round
(`INK_SPEC_LK_SKIP`; its context rows come from every step, not from drafting). The text cannot change: every guess
is checked. Same card, ids identical in every pair:
- 470,949-token needle (card 3): writing 43.73 -> 53.44 tok/s (+22 %), 2.72 -> 3.57 tokens per check; 14 rounds
  checked lookup's guesses (13 without drafting), 61 of 69 lookup guesses kept.
- 200K prompt + haiku (card 4, its thinking quotes the document): 66.02 -> 67.13 tok/s.
- Level (within 0.3 %): code 124.16 / 124.16 -> 124.23 / 124.14, haiku 103.42 / 103.30 -> 103.59 / 103.32, 3K 101.69 /
  101.48 -> 101.38 / 101.17 (card 5); 31K 104.35 -> 104.00 (card 1); 200K code 73.87 -> 73.73 (card 2). Gate 12/12.
The first version learned lookup's chance only from checked guesses (from 1 of 2): +19 % on the needle, but 0.1-1.5 %
slower on every other task (lookup gambled before it had evidence). `INK_DRAFT_LOG2=<file>` (with `INK_DRAFT_LOG` and
`INK_ORACLE`) logs each round's output index, lead count, guesses and probabilities for replaying such rules offline.
Without the drafter (`INK_SPEC` alone, e.g. at 515K where the drafter does not fit) lookup's guesses go through the
same learned rule against a plain step (2026-11-25; `INK_SPEC_LOOKUP=0` = every lookup match checked, as before). Same
card, ids identical to plain writing in every run: 515K needle (card 2) 23.20 -> 34.23 tok/s (+48 %, 82 of 114 lookup
guesses kept); 200K + haiku (card 4) 41.99 -> 48.13; 200K + code (card 3) 42.43 -> 43.31; 31K (card 1) 73.27 -> 73.91;
code (card 5) 90.81 / 90.13 -> 91.87 / 91.12; haiku 91.22 / 90.26 -> 90.04 / 89.20; 3K 84.85 / 84.17 -> 84.04 / 83.54.
The old rule (every match checked) lost up to 27 % on the same tasks (31K 56.73, 3K 62.48 / 62.07). The gate keeps
its two lookup checks on the old rule (`INK_SPEC_LOOKUP=0`), so steps of 2-4 tokens are still exercised there.
Lookup guesses from the text itself are "n-gram/history acceleration" under the lab's realistic-gate rules
(AGENTS.md, Quality Rules): any public headline speed is measured with `INK_SPEC_LOOKUP=0`; the numbers above are
lane measurements.

The drafter's head over a token list (2026-11-25, `Drafter::make_fold`, `INK_DSP_VOCAB=0` = the full vocabulary). Each
round the drafter reads the output layer's rows for every candidate token (~800 µs for the 201,024 rows) and a
correction table per guess. It now reads only the rows of a built-in list of 47,912 tokens (`src/dsp_vocab.hpp`,
from `data/dsp-vocab-freq.txt`: every token the model's tokenizer produced over ~18M tokens of local text - lab
notes, man pages, package READMEs, the Python standard library, llama.cpp sources, site text, JSON records and a word
list; `tools/dsp_vocab_hdr.py`), plus the prompt's own tokens and the special tokens (ids >= 199,990). The rows are
copied at load (91 MB; the correction table drops from 51 to 12 MB, so +52 MB in all); the argmax maps a column back
to its token id. A token outside the list is never guessed; every guess is still checked, so the text cannot change.
99.6 % of 3,269 tokens from earlier answers are in the list. `INK_DSP_VOCAB=<file>` takes a list from a file (first
number per line, most frequent first) and `INK_DSP_VOCAB_K` its first K entries.
Same card, both orders, text identical in every comparison (drafter + lookup, `INK_SPEC=7`), writing tok/s: code
(card 5) 124.08 / 123.78 -> 130.57 / 129.88 (+5.2 %), haiku 103.66 / 103.25 -> 109.59 / 108.76 (+5.6 %), a 256-token
answer 101.08 / 100.94 -> 106.29 / 105.93 (+5.0 %), a French / German / Spanish answer 89.82 / 89.73 -> 91.86 /
91.48 (+2.2 %; 9 of its tokens came from the prompt, tokens per check 1.85 -> 1.82); after 31K (card 1) 104.25 /
103.70 -> 108.78 / 108.73 (+4.6 %); after 200K (card 4, one order) haiku 67.12 -> 68.83, code 74.11 -> 76.88. Drafting
time per answer: code 0.109 -> 0.061 s, the 256-token answer 0.279 -> 0.166 s. The 32,768 most frequent tokens only:
haiku 103.4 -> 101.9 (tokens per check 2.30 -> 2.00), so the whole list stays.

Card memory at the longest contexts (2026-11-25). At 520K positions the card held 14,624 MiB of weights, 16,250 MiB
of full-layer keys and values, 280 MiB of windowed rings and 898 MiB of step buffers (`INK_MEM_LOG`); several of
those buffers were sized for a whole 512-token step although only small steps, or nothing, use them:
- `gu` (36 MiB at 512-token steps, 288 MiB at 4,096) was never read: removed.
- The relative-bias table `tab` (48 MiB) is written and read only by steps below the attention tiles (`att_tile`, 16
  tokens; the tiles compute the bias in place): it now holds `att_tile - 1` tokens (at least `SB_MAX`).
- The SITU outputs `hb` (24 MiB) are used only below the expert tiles (`tile_min`, 128 tokens; the tiles keep theirs
  in `Ht`): `tile_min - 1` tokens.
- The checking attention's block parts past 491,520 positions held 4 rows of the context (190.5 MiB at 520K); a
  check of 5-8 tokens went through them as two 4-row launches, reading the keys and values twice. Checks of 2-8
  tokens now go through a buffer of one context row (`INK_DEC_MEM`, 0.1 KB per position, rounded up to whole pieces
  of 8 rows x 128 blocks) in pieces of whole 128-block groups, the fold's state carried from piece to piece
  (`attn_flash_dec` b0, `attn_flash_sum` st / from / to), so the keys and values are read once and every value is the
  same (`INK_DEC_CHUNK=0` = before). 31K prompt + 64 tokens with an 8-token check every round, contexts of 40K
  (4 rows) and 140K (1 row): ids and all 64 logits rows identical to the unchunked run.
  515K needle with lookup (`INK_SPEC=7`), same card, both orders, ids = plain: pieces of 4 rows vs two launches 34.28
  -> 34.97 tok/s (card 2), 34.55 -> 36.02 (card 3); the count rule now sees 5-8 token checks as one read (61 checks
  of 2.34 tokens -> 52 of 2.79). One row vs four rows: 34.61 vs 35.25 (card 2), 35.35 vs 35.98 (card 3), -1.8 %: each
  extra piece costs ~40 us (200K profile with one row forced: 13 pieces per 8-token check +1.59 ms per step, 7
  pieces after the rounding +0.98 ms; at 515K 11 -> 8 pieces). The one-row buffer is what lets the drafter fit there.
520K now takes 31.06 GiB (was 31.30); one card holds **530,000 positions** (was 521,000; 531,000 refused; 0.24 GiB free
at the end). Needle at the new length: the 515K needle plus 42,467 characters of other lab notes before the question
(528,996 tokens, `prompts/needle530.tokens` in the work directory) on card 4 read in 1,595.7 s (331.5 tok/s), writing
34.18 tok/s with lookup and 22.81 plain (card 5), ids identical, answer "Vault code: 7351-QX-4829; meeting room:
Juniper-12.", 0.25 GiB free at the end.
The drafter beside the longest contexts. It needed ~614 MiB at 512-token steps and did not fit past ~500K. Now:
- `markov_w1` (103 MB, one 256-value row per token) stays in host memory. The card holds the list's rows (23 MiB, a
  guess's row found by its head column) and the round's anchor row, copied from the host each round.
- The load-time head product runs over the list's rows only (the temporary 196 -> 47 MiB).
- A step's rows are taken 128 at a time (`INK_DSP_INJ`; -16.5 MiB).
- The full layer's ring is allocated last and halved while it does not fit (16,384 slots normally; 4,096 beside the
  515K needle, 3,320 positions; `INK_DSP_WIN` fixes it).
Guesses and text are identical to before at short contexts (code / haiku / 256-token / French answers, both orders),
prompts level (3K 1,016.5-1,020.3 vs 1,017.2-1,018.4 tok/s, 31K 907.3-911.6 vs 907.2-907.3). The 515K needle with
the drafter + lookup (card 1): 45.80 tok/s, 3.36 tokens per check, ids = plain, 0.22 GiB free at the end, read at
335.8 tok/s.

Follow-up turns (2026-11-25, `ink_run`, `INK_TURNS=<file>`: one turn per line of token ids). After an answer its last
token (the chat template keeps the end token `<|content_model_end_sampling|>` at the end of the model's message, so an
answer that ended there is complete as written) and the next turn go through the cache as one small prompt step and
the turn is answered from there: one `ids:` line per turn. 3K prompt + two questions of 17 and 19 tokens, 256-token
answers: each later turn's prompt step 3-5 ms (a fresh run of the conversation as one prompt: 3.1-3.6 s at 3.4-3.7K);
plain, lookup only and drafter + lookup give the same ids; each turn's ids equal a fresh run of the whole conversation
(3,400 and 3,675 tokens) on another card. The drafter carries on from the cache too (turns 1 and 2 109.6 / 113.8 tok/s
vs 83.3 / 83.0 plain). At 515K the first read takes ~25 minutes; every later question then costs only its own tokens.

A read prompt saved to a file (2026-11-25, `ink_run`, `src/cache_file.hpp`): `INK_SAVE_CACHE=<file>` writes the state
after the prompt, `INK_LOAD_CACHE=<file>` starts a later run from it (that run's prompt must start with the file's; only
the rest is read; with the whole prompt loaded the answer starts at once). The file holds the prompt's tokens, its last
logits row, the convolution states, every full layer's keys and values, the windowed layers' last ring of positions and,
with the drafter, its three layers' cached positions and last context row, all copied as they are and stored by
position, so a run with another context size (another step size, ring size or V row length) loads the same file.
Written and read with O_DIRECT in 64 MiB pieces (no page cache, 64 MiB of host memory). 3K prompt (3,127 tokens,
658 MB file; 32 KiB per full-layer position plus the windowed rings, ~16.4 GB at 515K): saved in 0.63 s, loaded in
0.14-0.21 s (3.1-4.6 GB/s) instead of a 2.84 s read; loaded with the drafter: ids and every guess count identical to
the run that saved it (107 checks, 134 kept); loaded and continued with 273 more tokens: ids = a fresh read of all
3,400; loaded into a 300,001-position engine (512-token steps, another ring size and V stride): ids identical.
515K needle (514,670 tokens, drafter + lookup, card 1): saved 17.24 GB in 3.52 s (4.9 GB/s) after the 1,532.8 s read;
loaded on card 2 in 3.19 s (5.4 GB/s): writing 46.50 tok/s with every guess count identical (58 checks, 137 kept),
ids = plain; loaded on card 3 into a 520,000-position engine without the drafter: 23.49 tok/s, ids = plain.

Serving (2026-11-25, `ink_run` `INK_SERVE=1`, `serve/`): requests on stdin and answers on stdout in the DeepSeek
server's protocol (G / S / Q, `@@READY` / `@@P` / `@@T` / `@@D` / `@@R` / `@@E`) plus `W <id> <file>` (save what has
been read; the kept row's logits go with it). The engine keeps the conversation it has read: a request that extends
it is read from there; any other starts over (reset in milliseconds), from the longest saved prompt in
`INK_SERVE_CACHES=<dir>` that the request starts with. `serve/server.py` is the DeepSeek server adapted to this model
(its chat template, its message parts by special token: thinking, text, tool calls; reasoning effort; a library of
saved prompts: `/admin/prefill`, `/admin/save`, `/admin/library`); `serve/install.sh` installs it in
`/home/steve/inkling-serve`. Checks (card 4, drafter + lookup): a 3K prompt with two follow-ups (each read 18-20
tokens), a new conversation, a conversation saved by `W` and reloaded from the library after another one (3,930
tokens in 0.24 s, then 18 read), and a stop after the first answer line: every answer = a fresh run of its whole
conversation (a stopped one = the fresh run's start). Through the API (card 5): follow-ups keep the cache when the
client drops the thinking (turn 2: 514 of 524 tokens cached, turn 3: 1,716 of 1,732); a 22K-token document saved by
`/admin/prefill` loads in 0.34-0.43 s (read: 23.3 s) after other conversations, and its answer equals the full read's.
The server runs the engine at the smallest of `ctx_tiers` (64K / 128K / 300K / 515K) that holds the conversation and
its answer, so short conversations get the big prompt steps; a conversation that outgrows it is saved (`W`), the
engine restarted larger and the save loaded back (8,192 -> 65,536 mid-conversation: 4.1 s, then 514 tokens loaded and
10,811 read; thinking and answer identical to a server that never changed size).
The server runs one engine per card (`cards`, default 1-5; ~1.3 GB host memory each at any context size): a
follow-up goes to the card that holds its conversation, a new one to a free card, and the server remembers its recent
answers in full (thinking included) to put them back when a client resends a conversation without them, so a
follow-up renders the same on any card. Checked: two conversations at once on cards 4 and 5 (both answers overlap in
time) and the same turns on one card switching between the conversations both equal one conversation at a time on a
third card (thinking and answers, 5 of 5 turns each, incl. a 7K-token document saved by one card and loaded by the
other).
Recall at 480K (2026-11-25, `tools/recall/`, card 1, the API server, most likely token, effort "none"): 20 facts ("the
vault combination for project <name> is <5 digits>") at 2-97 % depth of a 480,641-token haystack of this repository's
notes, plus one project that is not there. Read once in 1,376.5 s (349 tok/s) and saved (16.1 GB, 3.3 s); each
question then loaded the save (2.6 s) and read ~30 tokens. 17 of 21 right: every fact from 32 % to 97 % and the
"not found"; the 4 misses (2, 12, 22, 27 %) are thinking loops to the 3,000-token limit, not retrieval: a miss's
thinking lists 17 of the 20 facts with the right codes and documents, then repeats its list. The model file names
temperature 1.0 sampling (`general.sampling.temp 1.0`, top_k 0, top_p 1.0, min_p 0.0) and its card warns about
reasoning loops. The same 21 questions with temperature 1.0 (seed 1000 + question number, sampling below): **21 of 21
right**, every answer in 5-20 s (the "not found" 52 s).

Sampling (2026-11-25, `ops::sample_rows`, `INK_SAMPLE="<T> <top_p> <top_k> <min_p> <seed>"`, serving `P` lines):
one token per row from softmax(x / T) over the kept tokens (min_p, top_k and top_p as thresholds on the row's values,
top_k and top_p by 32-step bisection), with the uniform number `sample_u(seed, position)` of the token's position:
the first index whose running sum in index order passes u times the kept sum (each of 1,024 lanes sums a contiguous
slice in order, lane 0 adds the slices in lane order, the lane holding the target walks its slice again). A check row
equals a one-token step's row, so a sampled text is the same with or without guessing. Checked (card 2, code and 3K
prompts, 256 tokens, T 1.0 with seeds 11 / 12, T 1.0 min_p 0.05, T 0.7 top_p 0.95 top_k 20): 8 of 8 texts identical
plain / guessing / guessing again; seeds give different texts. Speed: plain 82.6-89.5 tok/s (top_p + top_k ~0.9 ms
per token; T alone ~0), guessing 109-129 on code, 99-118 after 3K. Greedy unchanged (gate 12/12).

State copies for serving (2026-11-25, `src/snapshot.hpp`): before a request's last message (and, when a second copy
fits, before the conversation's first message after the system messages) the engine copies on the card what later
positions overwrite: the 40 windowed rings, the short convolutions' state, the drafter's rings and context row (1,415
MiB at 64K / 4,096-token steps; full-context caches need no copy, nothing writes below the copy's position). A request
that starts with a copy's tokens restores it (~0.02 s) and reads only the rest; a copy that does not fit is skipped
(none at 515K). Checked against `INK_SNAP=0` through the API (cards 4/5 vs 3): regenerate, edited last message,
follow-up, new question after the same 8.7K-token document, a short new conversation, seeded sampling: 13 of 13
answers identical, those reads 7-15 tokens in 0.04-0.08 s instead of 8.3-8.8 s.
When the conversation's only message (after the system messages) is the last one and it is 1,024 tokens or more, the
last-message copy would duplicate the first-message one, so it goes before the prompt's last token instead
(2026-11-26): a regenerated answer reads 1 token, and a follow-up whose answer part differs from ours (an answer cut at
its length limit, of which the client sends back only the visible part) reads only what follows the prompt.
`tools/serve_check.py` requests 7-9 (card 3, plain and with the drafter): 8 of 8 answers equal fresh runs; the
regenerate read 1 token in 0.012 s and the cut-answer follow-up 18 in 0.12 s (the prompt alone: 1.64 s).

Pictures (2026-11-25, `src/vision.hpp`, `INK_VISION=<mmproj-BF16.gguf>`; the reference's math in
`notes/inkling2-vision.md`): Unsloth's image encoder (`mmproj-BF16.gguf`, 318M parameters, sha256 2c165c78...)
runs on the target's card in F32 with fixed summation orders: pad to multiples of 40 pixels, normalize, F16 pixels
as the reference's im2col, 20-pixel patches + the bilinear-resized 32 x 32 position table, a CLS row, 23 LayerNorm /
2D-RoPE attention / GELU blocks with layer scales, 2 x 2 merge, the 4096 -> 4096 -> 2304 projector. Each 40 x 40
pixel block becomes one row the text model reads without the token norm, between `<|message_user|><|content_image|>`
and `<|end_message|>`. Ids from 2^30 stand for picture rows (`Engine::xrow`); serving registers a picture with a
`V <id> <key> <w> <h> <rgb file>` line (the 30-bit key from the server's hash of the pixels picks its ids). Checked
against the reference in its high-precision mode (`tools/ref_vision.cpp`, `GGML_CPU_F32_ACT=1 REF_FA=0`): a 640 x 360
test card (144 rows) within 2.1e-6 relative L2 (worst row 9.5e-6), a 1024 x 640 photo (416 rows, padded, both
table axes resized) within 3.4e-6; identical across processes and cards (2, 3); the card's question answered with
the reference's 100 greedy tokens exactly (`tools/vision/engine_e2e.py`, card 2: it reads "CODE 4729-K", the green
circle and the yellow square). Encoding: 0.038 s for 144 rows, 0.13 s for 416, 3.3 s for the largest picture (2920 x 2200, 4,015 rows: 16,061
patches; attention is 90 % of it) with the attention as register tiles in one launch (`attention_rt`, the layout of
`attn_flash.hpp`: 16 query rows per sub-group, 32-key blocks, running maximum); separate launches took 23.8 s and a
first one-launch version 7.6 s (`INK_VISION_ATTN=split` / `fused1` keep them). A 1290 x 810 picture (both position
table axes enlarged) matches the reference within 4.7e-6 (the reference: 1.1 s on the CPU for the card);
1.07 GiB on the card (weights + buffers for 4,096 rows), loaded only when it fits after the state copies. The gate
(`scripts/check-exact.sh`) now has 14 checks: the test card's 144 rows bit-identical to the baseline's
(`baseline/vision/rows.f32`, made with `attention_rt`) and its 100 greedy ids equal to the reference's.

Several conversations per card (2026-11-25, `INK_SEQS=<n>`, n <= 8; `Engine::bind`, `step_rows`, `next_rows`): the
engine holds n sequences (caches, convolution states, position, sampling); a shared step takes one token of each
writing sequence. The row-wise parts run as a step of n tokens (steps of 2-8 tokens give each row its one-token values,
as the guess checks); the convolutions and cache stores read each row's own state through a per-row table
(`fz::SeqRow`: every row is the only token of its own step), and each row's attention runs the one-token kernels
against its own caches. Checked: every id and every step's logits row bit-identical to each conversation written alone
(`INK_SEQS_TEST`: 4 conversations card 2, 8 conversations card 3 with the 3,127- and 1,000-token prompts; now gate check
15). Speed of the shared steps (greedy, 8K context): 4 conversations 143.2 tok/s in total against 87.3 for one; 8
conversations 183.4 against 87.6 (71 of 127 steps with all 8 rows); the steps are GPU-bound (kernels busy 97 %), mostly
the extra experts the rows choose. Memory: with prompt steps of 896 tokens (`INK_UBATCH=896`, windowed rings of 2,048
positions) 8 conversations of 8K took 19.87 GiB, 4 of 16K 18.60 GiB (one of 8K with 4,096-token steps: 20.02).
One launch for all rows' attention (2026-11-25, `INK_MR_BATCH=0` keeps one launch per row): `attn_win_fused` and
`attn_flash_dec` / `attn_flash_sum` take the per-row table too (each row's position and caches; the full layers run
over the most blocks of any row, a row's blocks past its position write nothing and its sum reads only its own), so a
step makes 842 launches instead of 1,234 with 8 rows; the same values (gate check 15, `INK_SEQS_TEST` 8 conversations
up to 2,500-token prompts identical). Card 3, 256 shared steps, both orders: 4 conversations 144.4 -> 148.3 tok/s, 8
conversations 175.8 -> 183.7 (profiled 8-row step 44.3 -> 42.2 ms: the experts 22.2 ms, 39 different experts per layer
on average against 8 for one token; the expert kernels already run each expert's own number of rows).
Steps of 2-8 tokens, dense products (2026-11-25, the same values; guess checks and several conversations): the
attention input matrices and the output layer through `gemv_multi_m` with the large register file and 2 rows per
sub-group (`INK_MM_BIG`, `INK_MM_R`, `INK_MM_R4`, `INK_MM_OUT_R`; 1 x 8 vectors loaded 8 floats of x per weight), and
the attention output product from a lane-order copy of its input (`INK_MM_WO=2`, one 2 µs relayout launch; it took
gemv_v's blocks of vectors with plain inputs). 8-row step (profiled, card 3): attention inputs 78.6 -> 72.8 µs, output
layer 1,238 -> 1,020, attention output 50.1 -> 31.1; step 41.8 -> 40.9 ms. Drafter writing (256 tokens, cards 4 and 5,
both orders, ids identical): code 137.0 -> 138.1 / 135.0 -> 136.5 tok/s, haiku 117.7 -> 118.8 / 116.6 -> 117.3, 3K
level (107.7 -> 107.9 / 106.3 -> 106.3). Variants that lost: 4 rows per sub-group (8 rows: 75.3 µs; 2-4 rows: -0.5 to
-0.8 % writing), the old kernels for 2-4 rows (`INK_MM_BIG=2`: -0.4 to -1.2 %), any 2-8 row product through
`gemv_multi_m` with plain inputs (`INK_MM_MULTI`: attention output 50 -> 67-84 µs).
Serving (`INK_SERVE=1` with `INK_SEQS`): `C <id> <s>` before a G line puts the request on sequence s; a prompt is read in
pieces of `INK_SEQS_CHUNK` (512) tokens between shared steps while others write; no guessing, state copies, saved
prompts or W lines there. Engine serving test: 4 requests at once (two sampled, one 3,127-token prompt) and a
follow-up gave the same tokens as one at a time (5/5). Server: `seqs_per_card` (and `seq_ctx`, `seq_ubatch`) in
config.json; 2 cards x 4 places, 8 chat requests at once 6.4 s against 13.5 s one by one, 12/12 answers identical
(first round and follow-ups, one picture, two sampled).

## Matrix engines with exact products (study, 2026-11-25)

The prompt runs at the card's power limit in FP32 (~57 pJ per expert multiply-add, ~65 per attention score). The
matrix engines (DPAS through `joint_matrix`, bf16 inputs, fp32 sums) cost ~6.5 pJ per multiply-add. Splitting each
fp32 input into three bf16 parts (x1 = bf16(x), x2 = bf16(x - x1), x3 = bf16(x - x1 - x2); x = x1 + x2 + x3 exactly)
against weights that are exactly bf16 (NVFP4: an E2M1 value times an E4M3 scale has at most 6 significant bits) makes
every product exact; only the order and rounding of the sums change. Measured (card 3):
- `tools/bench_xmx.cpp`: the card offers bf16 tiles of 1-8 x 16 x 16 (also fp16, tf32 8 deep). One instruction
  D = C + 16 products is deterministic and does not depend on the other rows of its tile; its sum matches the exact
  sum rounded once at 93.6 % / 80.0 % of elements (exponents within +-6 / +-20), not an fp32 chain (51-62 %) nor any
  alignment model tried. Error against the exact sum: mean 0.76-0.78 ulp (fp32 chain 1.25-3.6). The split was exact
  for 2,000,000 values (exponents +-60). A plain bf16 product 4096 x 4608 x 2304 ran at 44-47 T multiply-adds/s,
  6.0-6.9 pJ each.
- `tools/bench_xdot.cpp`: 65,536 dot products of 2,304 (NVFP4-like weights, inputs N(0,1) with 1 in 64 x20), error
  relative to 2^-24 x sum |w x| (mean / max): FP32 order today 0.148 / 1.59; one accumulator over all K 0.372 / 6.30
  (worse: 432 roundings in a row); one per part 0.203 / 3.12; segments of 256 inputs added in order into a total
  0.159 / 1.76; segments of 144 0.144 / 1.50; segments of 256 with one accumulator per part 0.110 / 1.21; the same with
  parts 2 and 3 sharing an accumulator ("segp23") 0.105 / 1.22; segments of 256, one accumulator, all third parts
  first, then second, then first ("segr16") 0.101 / 1.21. In ulps of the exact value: today mean 8.3 / median 1.30,
  segp23 4.7 / 0.91, segr16 4.3 / 0.87. Segmented sums on the matrix engines are more accurate than today's order.
- `tools/bench_xm1.cpp`: tiles of 1, 2 and 4 rows give exactly the 8-row tile's rows (16 steps x 3 parts, 65,536
  values); the accumulator holds one column per lane; the two-matrix `joint_matrix_apply` adds element by element.
So one arithmetic can serve writing (1-row tiles), checks and several conversations (2-8) and prompts (8-row tiles)
with identical results: guesses stay equal to plain writing and a continued conversation to a fresh read. Prompt time
by kernel (3,127 tokens, 2.83 s, card 3): expert products 60 %, other matrix products 28 %, attention 6 %, the rest
4 %; 31K: 54 / 24 / 16 / 4 %. Plan: the NVFP4 layers' experts first (all step sizes), then the Q8_0 / Q6_K products
(int8 / 6-bit values exact in bf16, their block scales applied between blocks), then attention; each a new baseline
checked against the high-precision reference as v2-v4 were.

NVFP4 experts on the matrix engines (`src/xmx_moe.hpp`, `INK_XMX`; baseline v5, 2026-11-25). **On by default since
2026-11-25 ~19:30** (`INK_XMX=0`: the FP32 expert kernels, baseline v4 in `baseline-v4`; v5 in `baseline-v5` since
the gate's `baseline` became v6 with the attention matrices on the matrix engines, 2026-11-26).
Arithmetic, the same for every step size: each input row in three bf16 parts; per segment of 256 inputs (16 steps of
16) one accumulator takes part 1, a second takes parts 2 then 3 at each step; the segment's sum is the two added
(two-matrix apply), and the segments are added in order into a total that starts at 0. The decoded weight (E2M1 x
E4M3, exact in bf16) is its top 16 bits. At load the 40 NVFP4 expert tensors are rewritten in place into a tile layout
(same bytes: per expert, per block of 16 rows, per step of 16 inputs, the 16 rows' 8 code bytes then their 16 scale
bytes; 0.11 s for 20 layers), which only these kernels read.
- Prompt kernel (`XProd2`, `tools/bench_xmoe.cpp`, real weights of layers 0-19, 3,127 tokens, 1,627 tiles of 16
  slots, card 3): a work-group of 16 sub-groups takes up to 4 consecutive tiles of one expert ("super-tile") x 4
  blocks of 16 rows; per chunk of 4 steps each sub-group decodes 2 of the 32 weight tiles into local memory (double
  buffered) and runs 4 x 2 x 3 x 2 instructions. gate|up 21.57 ms -> 10.83 ms (6.16 -> 12.26 T exact multiply-adds/s,
  48.1 -> 24.3 pJ each, ~296 W both), down 11.09 -> 5.16 ms; the input split and gather 0.79 -> 1.05 ms. Error against
  double (2^-24 x sum |w x|, 3,000 samples): gate|up mean 0.063 / max 0.44, down 0.014 / 0.18. All variants give the
  same bits (sub-groups per tile 1/2/4, row blocks 2/4, chunks 4/8). Slower: one sub-group decoding for one tile
  (SM1 33.1 ms, SM2 14.3), chunks of 8 steps (64 KB of local memory per work-group: 17.0 ms).
- What made it fast: a branch on "is there a next chunk" or "is this the segment's last step" inside the step loop
  made the compiler copy the accumulators around it (1,557 instructions per 48 matrix instructions, 492 of them
  register moves); with the loop split so that no branch sits between matrix instructions, 716. Fetching the weights
  further ahead (two chunks, or loads before the math and decodes after) changed nothing before that.
- Building the weight operand in registers: `joint_matrix_apply` with coordinates on a B matrix that was never loaded
  (`tools/bench_xm2.cpp`) hung the card twice (engine reset on card 3, which then checked fine). The plain apply (no
  coordinates) on a B loaded once from a zero tile works (`tools/bench_xm3.cpp`): lane n holds column n and visits
  k = 0..15 in order, so each lane writes its own decoded column; D = A x B identical to the local-memory route (0 of
  65,536 differ), 538 vs 563 µs. Used by the small kernels below (`DV = 2`); the prompt kernel keeps local memory.
- Steps of 1-8 tokens (`XSmall`, `tools/bench_xsmall.cpp`, card 3, µs per layer, gate|up + down): one sub-group per
  (tile, block of 16 rows, segment), its segment sum stored, then a pass that adds the segments in order (and for
  gate|up applies SITU and splits H). Every row equals the prompt kernel's (0 of 18,432 to 147,456 values differ).
  1 token 92.0 (today 88.4), 2 tokens 156.3 (142.9), 4: 325.0 (292.4), 8: 604.7 (521.3), so not yet faster.
- Engine (`INK_XMX=1`): 1 token: tile k = the token's expert k, its input split once; 2-8 tokens: tiles of the groups
  and the small kernels; 9 and more: super-tiles and `XProd2` (the old tile buffers share the new buffers' memory).
  3,127-token prompt 2.855 -> 2.142 s (1,095 -> 1,460 tok/s, card 3). The same prompt in steps of 8 tokens (the
  small kernels) and in one step give identical logits for the 16 following steps; `make-baseline.sh` now reads its
  3K prompt in steps of 8, so the gate (one step) checks the two kernel families against each other. Gate 15/15 against
  baseline v5 with `INK_XMX=1`; the default path 15/15 against v4. Against the high-precision reference on the 300-token
  prompt (`oracle/p300`): layer outputs closer than v4's at 74 of 88 tensors (error ratio geometric mean 0.913; layer
  47 3.42e-02 -> 3.02e-02); final scores median 1.662e-02 -> 1.683e-02, mean 5.91e-02 -> 4.57e-02, closer at 132 of
  300 positions, the same top token as the reference at 97.7 vs 98.0 % (one position). Gate texts haiku, code and
  3K + 16 unchanged; the drafter tests' haiku and 3K texts change. Writing with the drafter (code, same text):
  141.6 -> 135.0 tok/s, so the small kernels must get faster before this becomes the default.
- Small steps, later forms (all rows equal the prompt kernel's; µs per layer, gate|up + fold + down):
  `XSmall3` = XSmall's shape, weights fetched one pass ahead, rows per tile by its count (1/2/4/8), inputs and H
  packed by sorted position (no empty rows), the norm writes the one-token input split itself and `ffn_tail` adds
  the down product's segments in order (no down fold): 1 token 91.2, 8 tokens 533.8 (card 5; today 88.4 / 533.1).
  With the weight tiles built in registers (`DV = 2`): 1 token 86.8, 2: 151.8, 4: 299.0, 8: 501.9 (today 88.4,
  141.9, 295.0, 533.1). `XFull` (one sub-group per expert and 16 rows over all inputs, the segments added in
  registers in the same order, so no fold and no segment sums): 1 token 85.5 (gate|up 56.3, down 29.2) but 2-8
  tokens slower (196 / 339 / 491). The engine uses XFull for one token and XSmall3 for 2-8.
  Closed (same bits, not faster): a work-group per row block's segments (XSmall2), fetching 2 or 4 passes ahead,
  16-bit decode (half pairs), gate|up's fold computed inside the down kernel (down 39.7-49.7 vs 34.2), 8 or 2 row
  blocks per work-group, the last-arriving work-group doing the fold with device fences (correct, slower), XFull
  with 8 steps ahead or the large register file (fewer threads: 1 token 144 µs).
- Engine, card 3, code 64 tokens, `INK_PROF` (ms per plain step): XSmall3 11.73 vs default 10.97; + registers-built
  tiles 11.48 vs 10.95; + XFull for one token 11.23 vs 10.99 (gate|up 57.1 vs 52.6 µs, down 29.1 vs 28.3, ffn_tail
  4.9 vs 4.9). Gate 15/15 against v5 (`INK_XMX=1`) and 15/15 against v4 (default). Writing, card 3, both orders:
  with the drafter, code 141.2 vs 141.5 tok/s (same text); plain code 256: 88.9 vs 91.3 (-2.7 %). The remaining
  gap is the one-token gate|up kernel: 1,152 sub-groups (about half the card's threads) each with 4 steps of weights
  in flight read ~420 GB/s; today's scalar kernel ~455.
- Closing the one-token gap: an L1 cache prefetch 8 steps ahead in the one-token kernel (`full_prod<..., PD 8, L1>`;
  bench 16 / 32 / 64 steps ahead and L3 were slower) brought the plain step to 11.04 ms (from 11.22; default 10.99).
  Splitting each 16-row block's inputs over 2 or 3 sub-groups (`XFullK`, part 0 keeps the total in registers, the
  others store each segment's sum, added in order after a barrier; same bits) was slower: 1 token 117.8 / 93.1 µs vs
  84.6 (more sub-groups than the card holds at once). The one-token kernel's machine code: ~170 instructions per step
  of 16 inputs, ~110 of them turning the 4-bit codes into 16-bit values (unpack, half to float, multiply, pack): it is
  limited by instructions, not memory. Writing, card 3, both orders: with the drafter code 141.1 vs 141.5 tok/s (same
  text), plain 90.3 vs 91.3 (-1.1 %).
- Memory: xP / xHp (6 bytes per value) live in the attention scores' buffer `P` (one allocation of the larger of the
  two): every kernel that uses them runs in a layer's expert part, after its attention, on the same in-order queue
  (the one-token input split is written by the FFN norm). The segment sums of 2-8 token steps sit in xP past those
  steps' input parts. 530K positions on one card: 0.25 GiB free at the end (default path 0.24); 531K refused on both,
  as before. (Separate buffers needed ~81 MiB more and did not fit at 530K. Expert passes of 256 tokens in 512-token
  steps fit too, with identical tensors, but cost 1,095 -> 888 tok/s on a 5K prompt: too few rows per expert to share
  each weight decode; `INK_XMX_CHUNK` keeps that option for tests.)
- Prompts with the new default (same card, both orders, x7 build):

  | prompt | default before (v4) | matrix engines (v5) | |
  |---|---|---|---|
  | 3K (card 3) | 1,093.2 / 1,095.1 tok/s | 1,463.4 / 1,463.7 | +34 % |
  | 31K (card 3) | 975.8 / 974.7 | 1,274.2 / 1,270.1 | +30 % |
  | 100K (card 5) | 720.2 / 719.7 | 880.3 / 874.3 | +22 % |
  | 200K (card 1) | 560.0 / 560.2 | 644.5 / 642.8 | +15 % |
  | 5K in 512-token steps (card 4) | 904.7 | 1,094.0 / 1,096.1 | +21 % |

  Past 300K the steps are 512 tokens and attention takes most of the time, so the gain there is smaller.
- Saved prompt files (`INK_SAVE_CACHE`) carry the arithmetic in their model id (top bit set for v5): a file saved with
  the other arithmetic is refused ("saved by another model or engine"), since its continuation would not equal a fresh
  read (checked both ways, card 5). The LAN server's copy in `/home/steve/inkling-serve/bin` is still the 14:14 build
  (old default); its library was empty.

Q8_0 attention matrices on the matrix engines, exact (`INK_XMX_DENSE=1`, 2026-11-25/26; `src/xmx_dense.hpp`,
`src/xmx_esimd.hpp`, `tools/bench_xe.cpp`, `tools/bench_xdense.cpp`, `tools/bench_xa.cpp`, `tools/isa_xd.cpp`,
`tools/isa_xe.cpp`):
- Arithmetic: inputs in three bf16 parts (split3); the int8 code is exact in bf16 and the block scale (fp16, per 32
  inputs) is applied to the block's sum: per block one DPAS chain from 0 (x1, x2, x3 per step), group sum = fma(d,
  block sum, group sum) over 8 blocks, groups of 256 inputs added in order into the total. Error against double (2^-24
  x sum |w x|, 2,000 samples, attn_q): 0.083 / max 0.47 (today's FP32 order 0.106 / 0.74; without groups 0.136; with
  c1 | c23 as the experts 0.075 but 20 % slower). The bf16 matrices (sink, k / v conv projections) the same way with
  scale 1. No lean (BENCH_BIAS, 16,384 bf16 products, inputs around 0 and around 1): mean signed error -0.0002 /
  +0.0004 against a mean size of 0.040-0.042 (a plain FP32 running sum: 0.32-0.33). Every step size gives the same
  bits (1, 2, 4, 5, 8 tokens and every prompt-kernel shape).
- Layout Q8E (the same bytes as Q8_0, repacked in place at load): per 16-row block and group of 8 blocks 4,352 bytes;
  the code of input k, row n, block j at 512j + 64(k/4) + 4n + k%4, the 16 rows' scales of block j at 4096 + 32j. A
  4-dword sub-group read at 512j + 256s gives lane n its row's 16 codes (the prompt kernel, `XDense` LE) and in ESIMD
  input k's 16 codes are one strided register region. (The first form, [k][n], made the prompt kernel 26 % slower.)
  The bf16 matrices get BFE copies, rows padded to 32: each step's 512 bytes are the DPAS weight operand.
- The A operand's layout (`bench_xa`): for 1, 2, 4 and 8 rows lane n holds column n and visits rows in order.
- Prompts: `XDense<4,4,2,2,4,false,8,false,true>` on parts split once per input (3,127 tokens, card 3: attn_q 3.65 ->
  1.53 ms, attn_output 3.34 -> 1.55, attn_k 1.24 -> 0.60, plus 0.27-0.35 ms per input split; splitting inside: 8.0).
- Steps of 1-8 tokens: one ESIMD launch (`xd::dgroupej`) for all of a layer's Q8E and BFE attention inputs (work-group
  = one 16-row block, one thread per group of 256 inputs, folded in local memory). The int8 -> bf16 decode is 3 moves
  per 16 codes in ESIMD (944 instructions per group; ~1,750-2,600 through joint_matrix, which closed the first study).
  One token reads the fp32 input and splits it 16 values at a time right before use (all 256 at once: 51 us per launch
  instead of 36, registers); 2-8 tokens read parts made by one small launch per input. bf16 and Q8 jobs in one loop
  cost the Q8 path 10 % (40.5 -> 45 us); they are two template functions now. bench_xe (card 3, the five attention
  inputs, 21 MB): 1 token 41.1 us (parts made elsewhere: 40.3; today's kernel 43.1), 2 tokens 44.8, 4: 44.9, 8: 47.0
  (today's 65); the attention output alone 17.1 us (16.0 on parts; today's ~16.6 in the engine).
- IGC 2026.1 crashed (ocloc -11) compiling the ESIMD kernel with a second int member after `cols`: both are packed in
  one int. The repacks' temporary buffers (this one and the expert repack) were freed twice at exit: `d.release`.
- The kernels after these run slower: with the path on, the expert kernels take ~2 % longer (moe_gate_up 2.61 -> 2.67
  ms per step) on every prompt tried (code, haiku, fr, 3K). Not the clock (2,800 MHz in both, sampled every 10 ms),
  not where the buffers sit (allocated last: the same), not the cache warming (INK_WARM=0: the same), not the driver's
  systolic mode (NEO OverrideSystolicPipelineSelect / OverrideSystolicInComputeWalker: the same), not ESIMD as such
  (one-work-group dummy kernels: nothing). bench_xe BENCH_FOLLOW shows it with a plain 16 MB read right after the
  launch (28.5 -> 30.0 us); L1-streaming + L2-uncached weight loads fix that read in the bench, but in the engine they
  only move the loss (norms faster, experts slower): writing 88.7 tok/s without hints, 88.6 / 88.6 / 88.4 with three
  hinted forms, 85.4 with L1 + L2 uncached.
- Two cheaper splits that did not pay: splitting inside the kernel for 2-8 tokens (each block's MR x 32 inputs loaded
  and split before use) gives the same bits but 50.7 / 64.7 / 81.9 us at 2 / 4 / 8 tokens against 45.9 / 46.8 / 49.1
  on parts, so 2-8 tokens keep one small split launch per input; and the 1-token split of all 256 inputs at once (above).
- Speed (`INK_XMX_DENSE=1` against 0, the same card, both orders, same answers unless noted):

  | | off | on | |
  |---|---|---|---|
  | prompt 3,127 tokens (card 1) | 1,381.7 / 1,382.8 tok/s | 1,659.1 / 1,657.8 | +20 % |
  | prompt 31,270 (card 2) | 1,187.4 / 1,178.4 | 1,390.5 / 1,387.6 | +17 % |
  | prompt 100K (card 5; the 4 tokens written after it differ) | 882.1 / 875.1 | 980.4 / 979.6 | +11 % |
  | prompt 200K (cards 4 and 5) | 652.4 / 641.0 | 703.9 / 696.5 | +8 % |
  | writing, code 128 (card 3) | 90.40 / 90.46 | 88.85 / 88.84 | -1.7 % |
  | writing with the drafter (INK_SPEC=7, lookup off, code 256) | 141.11 / 141.50 | 140.14 / 141.24 | -0.4 % |

  530K positions still fit on one card (31.35 vs 31.34 GiB in use, 0.29 GiB free at the end). In a writing step the
  attention inputs cost the same as before (36 us in one launch + 15 leftover Q6_K launches of 15 us, against 41 us),
  the attention output 17-18 us against 16.6, and the kernels after them ~0.08 ms (above).
- Accuracy against the high-precision reference (double sums): on the 1,000-token prompt (`oracle/p1000`, new, 827 s
  on the CPU) the layer outputs are closer at 81 of 88 tensors (error ratio geometric mean 0.624; layer 23 2.58e-2 ->
  1.97e-2, layer 11's attention output 4.47e-3 -> 3.48e-4), closer at most positions in every layer (677 / 775 / 543 of
  1,000 at layers 0 / 11 / 47), final scores median 1.358e-2 -> 1.125e-2, mean 2.54e-2 -> 2.35e-2, max 0.517 -> 0.377;
  the same top token as the reference at 96.0 vs 96.6 % (near ties: 13 positions only v6 matches, 19 only v5). On the
  300-token prompt the first layers are closer (198 / 187 of 300 positions at layers 0 / 1) but from layer 12 on v6
  sits further away (closer at 7 of 88 tensors, ratio 1.10; final scores median 3.64e-3 -> 4.08e-3, mean 1.046e-2 ->
  1.041e-2, max 0.332 -> 0.095, top token 97.33 vs 97.67 %); the jump at layer 12 looks like one near tie going the
  other way (not traced).
- Default since 2026-11-26 (`INK_XMX_DENSE=0` = old). Gate: default 15/15 against new baseline v6 (made with it), the
  old path 15/15 against v5; the picture answer equals the reference's 100 ids both ways. Saved prompt files carry the
  arithmetic in their model id (bit 62).

Q6_K attention matrices on the matrix engines, exact (`INK_XMX_Q6`, default since 2026-11-26, baseline v7;
`INK_XMX_Q6=0` = v6; `src/xmx_esimd.hpp` Q6E, `tools/bench_xq6.cpp`). 18 attention inputs are Q6_K (attn_q of layers 1,
18-21, 23; attn_gate 20, 22, 23; attn_k 20-23; attn_rel 2, 5, 7, 13, 23); they ran the FP32 tile kernels in prompt
steps (~2x the Q8E time: attn_q of layers 18-21 3.3-3.5 ms per 3K prompt against 1.6) and 15 separate launches per
writing step.
- Arithmetic: the weight (d x sc) x (q - 32) is exact (d x sc at most 18 bits, a float made once at load as Q6_KU does;
  the code exact in bf16). Per step of 16 inputs one DPAS chain from 0 (parts 1, 2, 3), group sum = fma(scale, step
  sum, group sum) over the 16 steps of a group of 256, groups added in order into a total from 0: Q8E's with blocks
  of 16. Layout Q6E: Q8E's code places, a float per (step, row) at 4096 + 64 s + 4 n (5,120 bytes per 16 rows x 256
  inputs; 10 bits per weight), made at load from the Q6_KU rows; the Q6_K planar copies are freed and no Q6_KU prompt
  copy is kept for them (card memory 18.93 -> 18.87 GiB at 3K; +33 MB past 500K positions, where no prompt copy was
  made).
- Kernels: XDense's `Q6` variant (prompts) and a third job kind in `dgroupej` (1-8 tokens, `EK_Q6`), so these matrices
  join the one ESIMD launch of a writing step's attention inputs. `bench_xq6` (card 3, 3,127 tokens): the same bits for
  1, 2, 3, 4, 5, 8 tokens and the prompt kernel, also in one launch with a Q8E job; prompt attn_gate 3,509 -> 1,653 us,
  attn_k 1,214 -> 608, attn_rel 479 -> 271 (plus the shared input split).
- Accuracy: error against double per product (units 2^-24 x sum |w x|, 2,000 samples): random inputs 0.087-0.090 (max
  0.63-0.80) against today's 0.108-0.110 (0.55-0.63); the model's own hidden states (`BENCH_X`: rows of l_out-1 / 17 /
  41 of the 300-token dump at unit RMS) lower mean error in all 12 cases (e.g. attn_q from l_out-17 0.1115 -> 0.0772,
  max 1.40 -> 0.61), lower max in 8. Against the high-precision reference: 300 tokens even (layer errors ratio 1.005,
  same top token 97.33 %, final scores closer at 159 of 300 positions); 1,000 tokens equal through layer 12 (ratio
  1.00), then one position (442) takes another branch at application 13 where v6 matched the reference, and the
  later layers sit further (ratio 1.035, top token 95.6 vs 96.0 %). By position v6 is the closer one slightly more
  often (51-58 %) at every layer; the per-product measurements decide it.
- Speed (same card, both orders, same ids): 3K prompt 1,743.1 / 1,742.7 -> 1,770.1 / 1,771.5 tok/s (card 3), writing
  after it 81.3 -> 81.9. Gate: default 15/15 against v7, `INK_XMX_Q6=0` 15/15 against v6, `INK_XMX_DENSE=0` 15/15
  against v5. Saved prompt files carry it in their model id (bit 61). Not done: attn_q of layer 22 (Q5_K, the scale
  has a minimum term), still on its FP32 tiles (10.0 ms per 3K prompt).

Same values, faster (2026-11-26): `xd::split` (the prompt input parts) loads 16 bytes and stores 16 bytes per part
(it stored 2 bytes at a time, ~250 GB/s): 3K prompt 1,764.8 / 1,769.4 -> 1,797.2 / 1,796.7 tok/s (card 3), 31K
1,457.8 / 1,441.6 -> 1,463.6 / 1,457.8 (card 1). Prompt steps again by context with the matrix-engine kernels
(`tools/ink_run.cpp`; logits identical): 8,192 tokens up to 64K positions (31K +1.4-2.1 %, 25.75 vs 20.60 GiB), 4,096
up to 128K (100K +0.2-0.9 %), 1,024 up to 300K (200K: 2,048 was 0.6 % slower), never more than the context needs.

Layers 20-23's experts on the matrix engines, exact (`INK_XMX_Q`, default since 2026-11-26, baseline v8; `INK_XMX_Q=0`
= v7; `src/xmx_q.hpp`, `tools/bench_xq.cpp`). These four layers keep their experts in other formats (gate|up Q5_K,
Q5_K, Q4_K, IQ4_XS; down Q5_0, Q5_0, Q5_0, IQ4_NL) and ran the FP32 tile kernels from their planar decode copies:
~5 % of a 3K prompt.
- Arithmetic: a weight is s x c + o with c a small integer (Q5_0, Q5_K: q - 16; Q4_K: q - 8; IQ4: the IQ4_NL table
  value), exact in bf16, and s the block's scale (exact in fp32); o only for Q4_K / Q5_K (o = fma(s, 16 or 8, -dmin x
  m), the same s and m1 as the planar decoders). Per block of 32 inputs one DPAS chain from 0 over its two steps
  (parts 1, 2, 3), group sum = fma(s, chain, group sum), then for Q4_K / Q5_K group sum = fma(o, X, group sum) with X
  the block's input sum (Neumaier-compensated fp32 sum in input order, one small launch); groups of 8 blocks added in
  order into a total from 0. Centred codes matter: with the codes q themselves s x A and m1 x X nearly cancel (error
  0.18 against today's 0.11).
- Layout XQ: made in place from the planar decode copies at load (same bytes per row; card memory 18.87 -> 18.88 GiB
  at 3K, the block-sum buffers). Kernels: `XProdQ` (prompt steps, xmx_moe's super-tiles and passes) and `XFullQ` (1-8
  tokens, one sub-group per tile and 16 rows); a 1 KB local table turns a byte of codes (plus the Q5 high bits) into
  two bf16 pairs for the 1-8 token kernel and for IQ4 in prompts (Q4_K / Q5_K prompts decode with arithmetic: the table
  was slower there).
- `bench_xq` (card 3, 3,127 tokens): the same bits for the prompt kernel, 8 tokens and 1 token in all four layers;
  prompt gate|up 15.37 / 15.41 / 14.44 / 14.26 ms, down 6.58-6.66 ms; one token gate|up 54.9 / 55.2 / 47.1 / 43.4 us,
  down 20.3-22.5 us.
- Accuracy (error against double per product, units as above, 2,000 samples): random inputs gate|up 0.093-0.095 for
  Q4_K / Q5_K and 0.083 for IQ4_XS against today's 0.110-0.112, down 0.079-0.081 against 0.106-0.115; the model's own
  hidden states (`BENCH_X`: ffn_inp-44 and ffn_inp-47 of the 300-token dump at unit RMS) lower mean error in all 16
  cases (gate|up 0.048-0.072 against 0.060-0.077, down 0.074-0.089 against 0.102-0.123).
- Speed (same card, both orders, same ids): 3K prompt 1,797.3 / 1,794.6 -> 1,889.8 / 1,887.8 tok/s (card 3), 31K
  1,464.5 / 1,452.3 -> 1,531.4 / 1,527.3 (card 1), 100K 1,006.4 / 998.8 -> 1,035.4 / 1,034.4 (card 2), 200K
  715.7 / 711.2 -> 727.8 / 726.8 (card 4). Writing: code 256 plain 88.90 / 89.00 -> 88.83 / 88.75 tok/s, with the
  drafter 141.22 / 141.30 -> 143.06 / 143.14 (card 3; at one token the weights come from memory, so the kernels time
  like the old ones). Tried and dropped: the router launch making the block sums (one launch less, but its extra
  work-groups cost more: 88.55 tok/s), the one-token gate|up kernel making them itself (54 -> 65-69 us), an L1
  prefetch 2-8 blocks ahead (no gain). Gate: default 15/15 against v8, `INK_XMX_Q=0` 15/15 against v7. Saved prompt files carry it in their model id (bit 60).

530K positions on one card again (2026-11-26). The Q6E copies (baseline v7) take 31 MiB more than the planar Q6_K
copies they replace, and v7 refused 530K at load ("8 MiB more would pass the card's memory"; 520K: 31.09 GiB in
use against v6's 31.06). Now: each planar copy is freed before its Q6E copy is made (a lower peak), a step size that
does not fit is halved down to 256 tokens instead of 512 (the same bits), and such a retry loads the weights again
(~3-4 s): the failed first try had already laid weights out in place (NVFP4 tiles, XQ, Q8E) and freed the Q6E
matrices' planar copies, so the retry read freed memory (device lost, card 3; the card ran the next job normally).
530K: steps of 256 tokens, 31.16 GiB in use, 0.40 GiB free at the end (was 0.24 with 512-token steps); haiku 32 ids
equal to a short-context run. Needle at 530K (`prompts/needle530.tokens`, 528,996 tokens, card 4, plain writing with
`INK_SPEC_LOOKUP=0`): both hidden notes found ("Vault code: 7351-QX-4829; meeting room: Juniper-12."), prompt 1,504.7 s
(351.6 tok/s), writing 22.5 tok/s.
Where a card's memory goes at 530K (`INK_MEM_LOG=48`, card 3, 2026-11-26): weights 14.3 GiB (the file's 14.65 GiB
less the embedding table, which stays in host memory; the layouts made at load replace their tensors, none doubles),
the cache 16.2 GiB (8 full-context applications x keys and values, 1,035 MiB each), everything else ~0.6 GiB (rings,
256-token step buffers, routing). 236 MiB stay under the allocation limit, ~7K positions. Nothing sizable is left to
move off the card without changing the arithmetic or the cache's 16 bits; past ~537K, two cards (below).

Attention scores on the matrix engines with fp16 parts (tried and closed, 2026-11-26). The keys are fp16 in the cache,
so one operand is already exact; a query row scaled by a power of two (its largest value into [2^14, 2^15)) splits
into three fp16 parts, and a key times a part is exact in the engine. `tools/bench_f16dpas.cpp` (card 3): fp16
subnormal operands are used exactly (no flush); one instruction's 16-product sum errs 0.37 against an fp32 FMA chain's
0.62 (mean, units of 2^-24 x sum |p|); fp16 46.7 T multiply-adds/s at 6.3-7.2 pJ, bf16 the same, tf32 22 T/s at
12.4-13.2 pJ, fp16 with the second operand read column-major 31.9 T/s. Scores alone (`tools/bench_qkx.cpp`, 100K
keys): mean error 0.11 against the exact dot vs 0.33 for the FP32 tile. In the fused prompt kernel (bench_attn card 3,
100K keys, the engine's `attn_flash_tile<8, 3, 1, 1052>`) the score products are 58 % of the energy (without them:
10.6 ms 2.4 J of 19.8 ms 5.7 J), but:
- `joint_matrix`: 24.4 ms 7.3 J at 256 rows (the query tiles' 2-D loads: one tile for all products 13.3 ms; tiles in
  local memory 37.7 ms; L1 cache hints on the loads no change).
- The card's instruction called directly (OpenCL `intel_sub_group_f16_f16_matrix_mad_k16`, which IGC supplies;
  `tools/test_mad16.cpp`: a[m] = A[m][lane], b = the lane's 16 consecutive halfs, so a key row as the FP32 products
  already load it, result one key per lane): 256 rows 16.6 ms 5.2 J vs 19.8 / 5.8, but 512 rows 46.1 ms 12.9 J vs
  41.1 / 11.8. The 256-row gain is a launch of one wave of work-groups; the engine's steps are larger.
- Scores of 2 or 4 key blocks per query load (same values): 17.7 / 27.2 ms with 256 registers, 31.3 / 75.9 with 128.
- With one scale per row, 2.8e-5 of the values of Gaussian rows fall under fp16's 2^-24 and would need a fourth part.
The three parts triple the engine's work, and this kernel shape (3 accumulators per sub-group) keeps the engines busy
about 40 % of the time. Not adopted; the code is in `patches/attn-scores-fp16-dpas.patch`.

Where the prompt's time goes now (v8, 100K prompt, card 1, `INK_PROF`): full-layer attention 41 %, experts 31 %,
attention matrices 13 %, windowed attention 5 %, the rest ~9 %. Each big part is near a floor on one card:
- Prompt attention (`attn_flash_tile`): the multiply-adds run at ~79 % of the FP32 peak; keys and values from a
  2,048-key ring that fits the cache take 6.32 J vs 6.59 J (100K x 256, card 3), so moving them is ~4 % of its energy.
- Experts (`XProd2`, `tools/bench_xmoe.cpp` `BENCH_ABL2`, timing-only switches, real weights, 3,127 tokens, card 3):
  gate|up 10.8 ms / 24.2 pJ per exact multiply-add; without the weight decode 8.2 ms / 17.7 pJ (the decode and its
  weight reads), inputs loaded once per chunk 9.8 / 20.8, weight tiles loaded once 10.5 / 23.2, without the matrix
  instructions 7.95 / 15.2, loop and epilogue alone 3.0 ms. Eight token tiles per decoded weight tile (`BENCH_SM8`,
  same bits) instead of four: bench 4,096 tokens gate|up 13.9 vs 13.5 ms at 4 % less energy, but whole prompts
  (same card, both orders, same ids) 3K 1,710 vs 1,789 tok/s, 31K level (1,522 vs 1,523), 100K 1,022 vs 1,036,
  200K 676.5 vs 731.1: not kept. An integer decode straight to bf16 would take ~12 instructions per value against
  today's ~6-7 (half conversion and one multiply).
- Writing after long prompts: the attention kernel reads keys and values at 518 GB/s (100K) and 533 GB/s (400K).
- The 4-bit decode against the CPU (`tools/test_fp4dec.cpp`, ideas I23): every code at every place x all 256 scale
  bytes, 65,536 values equal; only code 8 differs in the sign of zero (the card's -0 against the integer product's
  +0), which cannot change a sum that is not zero. Half subnormals (codes 1 and 9) are converted exactly.

Where a writing step's time goes (v8, 2026-11-26, code 256 plain, card 3, `INK_PROF`): 11.21 ms span, 10.99 ms of
kernels, 791 launches. Experts 4.01 ms (gate|up 55.2 us per layer for 23.9 MB = 432 GB/s, down 28.4 us for 11.9 MB)
against the plain-read times above (41.2 / ~21 us): ~1.0 ms over the floor. Attention inputs 1.87 ms (39.0 us for 21.1
MB, floor 36.2), attention output 0.87, output head 0.65 (at the 380 MB read floor), the ~700 small kernels ~3.3 ms (the
mixes also warm the next matrix into L2). The expert gap is the weight decode (~110 of ~170 instructions per 16 inputs):
the exact weight (code x block scale, a bf16) takes a half conversion, a multiply and a pack per value, and the integer
forms (the exponent added to the bits of the scale and of 1.5 x the scale; fp16 products turned into bf16 by shifts)
take as many instructions because of the zero and the half-subnormal codes. In prompts the decode is ~6.5 of 24.2 pJ per
exact multiply-add of gate|up (above), and the experts are 54 % of a 3K prompt (`INK_PROF_PROMPT`, card 3: gate|up 579
ms, down 266, of 1,642). A cheaper decode needs the scale outside the products (the matrix engine sums the codes'
products, then one multiply-add by the scale per row and block of 16): another arithmetic for every expert kernel, so a
new baseline and a reference check. Prototyped and closed (`tools/bench_xs.cpp`, DO-NOT-REPEAT): one token, 8 experts,
card 3: the engine's gate|up kernel alone takes 49.4 us (490 GB/s), down 25.7; with the scale outside the products
47.9-50.6 / 24.4-24.8 us and 2.6x the error per product (gate|up mean 0.061 -> 0.159 against double). So the decode is
not the limit at one token. Spread over 20 layers' weights as in a writing step, the same kernel takes 53.1-53.3 us
(the step: 55.2); plain reads (`tools/bench_tlb.cpp`) lose only ~1 us from 1 GB to 12 GB of spread, whatever the
allocation's alignment, so the rest is the kernel's read pattern (1,152 streams of 20 KB at once).

XProd2's epilogue accumulators reuse the weight tiles' local memory after the final chunk barrier (2026-11-27). This cuts
local storage at the production 4,4,4 shape from 48 to 32 KiB per work-group without changing any arithmetic. Same-card
old/new/new/old runs on card 3: the 3K prompt improved from 1,897.9 / 1,893.6 to 1,905.5 / 1,904.8 tok/s (about 0.5 %);
at 100K the final matched pair improved 1,113.9 -> 1,118.0 tok/s (0.37 %). Ids were identical and the full gate passed.
The microbenchmark-only patch and earlier controls remain in `patches/xprod2-slm-alias.patch` and
`/mnt/fast-ai/inkling-cache/tests/bin/slm-alias-engine/`.
The two-card split gate passed too: 100K 1,969.4 / 1,966.5 tok/s against 1,961.5 / 1,962.3 before, and 200K
1,426.7 / 1,426.0 against 1,425.5 / 1,424.6, with identical ids. Log:
`/mnt/fast-ai/inkling-cache/tests/kimi-alias-split-20261127T091656/run.txt`.

Process end: `Device` waits for its queue before freeing its memory and then pauses 20 ms (other B70 projects saw
copy-engine resets when a process ended within ~2 ms of its last copy; ideas file pick 1). Gate 15/15.

Another B70 Inkling-2 project (github.com/Danmoreng/intel-b70-inkling2-mini-vllm, read 2026-11-25; vLLM + own XPU
kernels, one card at 180 W, peaks at 230 W): third-party EXL3 4-bit experts (its maker: 97.47 % next-token agreement
with the original on code), BF16 dense weights and activations on the matrix engines, FP8 K/V, probabilistic
speculative sampling (texts differ at a matched seed), their faster prompt path 29 of 30 top tokens against their own
reference. Published: prompt 3,281 tok/s at 8K, 2,822 at 77K, 1,843 at 240K; writing 82.8 tok/s at 4K with DSpark
(58.5 without), 74.5 at 77K, 51.1 at 231K, all sampled; peaks 166.7 / 199.9 tok/s on copy tasks (97 % of guesses kept).
Longest context 262K; up to 4 requests per card. Against this engine: their prompt reading is 3-4x faster (16-bit
matrix engines; ours is exact FP32 at ~85 % of the card's FP32 rate), our writing is faster on comparable tasks.
The prompt's time in `ink_run` now ends with a wait for the card (`feed` returns once its launches are queued; a
1,261-token piece in serving showed 0.008 s); the 3K and 1K prompts time the same as before (3.032 vs 3.033 s, 0.975
vs 0.973 s, card 4).

`check-exact.sh` now refuses fewer than five distinct cards and `on-card.sh` refuses an empty card or card 0
(`INK_ALLOW_CARD0=1`): with four cards listed the gate gave its 3K-prompt checks an empty card, which locked
`card.lock` and ran them on card 0 (twice on 2026-11-24; they passed).

Writing step, small kernels (2026-11-23): a latency-bound kernel with a branch around each read and its use (a loop
of unknown trip count, or `if (s < count) { read; add }` per state) waits for each read before the next. Reads first
(unrolled, clamped indexes past the end), then the same operations in the same order: norms 5.1-5.6 -> 2.1-3.0 µs,
expert routing 6.1 -> 4.3, the mix 10.0 -> 9.0 (`INK_PROF`, card 3). The gate|up kernel reads the expert scale
before the row and evaluates its two tanh in one pass (lanes 0 and 1), one sub-group per work-group.
Warm weights: the attention mix (fz::mix_fused) carries 12 extra work-groups that read the first 3 MB of the next
attention input weights into L2 (`src/warm.hpp`; INK_WARM=0 off, INK_WARM_WG, INK_WARM_MB); the attention input
product 47.7 -> 43.4 µs, step 11.80 -> 11.66 ms. A warm kernel on a second queue does not run beside the main queue on
this card (reads of weights nobody needs cost their full time), and warm work-groups in the 2-3 µs norms cost more than
they save. Bench caution: a card under continuous big reads boosts to 2,800 MHz and the short power limit (PL2) pulls
it to ~2,333 MHz within a second or two, so a kernel timed late in a bench_gemv run is ~9 % slower than the same kernel
timed first; compare variants interleaved. Writing itself stays at 2,667-2,800 MHz.
Lane order (`src/xlane.hpp`): the matrix kernels give chunk c (32 values) of a row to lane c % 16, so each float4 load
of the input vector by 16 lanes touched 16 cache lines (lane stride 128 bytes). For 4-bit expert weights (18 bytes per
chunk against 128 of input) those loads, not the weights, set the pace. In lane order the 16 lanes' float4 sit side by
side; the same values reach the same registers, so every sum is unchanged. For one token, SITU writes the down
product's inputs in lane order and the norms before the experts write theirs only in lane order (the router reads it
too). bench_gemv (card 3, each expert its own input): down 33.1 -> 26.6 µs at one row per sub-group, gate|up pair
51.9 -> 48.7; in the engine (`INK_PROF`) down 31.5 -> 29.0, gate|up 56.4 -> 53.9-54.3, router 5.02 -> 4.88, the norms
+0.8-1.1 µs for the scattered stores; step 11.54-11.58 -> 11.38-11.40 ms (`INK_BENCH_STEP`, alternated). `INK_XL=0`
turns it off. Not used where it does not pay: the Q8_0 attention products gain 0.3-0.5 µs each (their weights are
8 bits, so the input is a smaller share of the reads), about what their norms would lose writing the copy.

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


## Two engines: the model split over two cards (2026-11-26)

The model's trained context is 1,048,576 positions (`inkling2.context_length`); its keys and values take 32 KB per
position (8 full-attention applications x K and V x 8 heads x 128 x 2 bytes), 32 GiB at 1M: more than one card holds
beside the weights (one card: 530,000 positions). Split over two engines, each runs 24 of the 48 applications and holds
four of the eight full-attention caches (16 GiB at 1M) and only the weights of the physical layers it runs.

- `Engine(..., app_lo, app_hi)`: applications app_lo .. app_hi - 1. `Engine::unused_tensor` leaves the other layers'
  tensors off the card (not their mix query rows: a block's saved mix scores cover every query of the model), the
  output matrix off the first engine, the embedding off the second. The first engine has no output; the second replays
  the first one's block bookkeeping (`carry_slots`: at 24, rows 0, 6, 12, 18 and 24 with their saved mix scores, plus
  the drafter's feature rows 5 and 23 when it runs; ~47 KB per token) and takes them through host memory each step
  (`carry_copy`; no card-to-card reads). Every application computes what it computes in one engine: the same bits.
- `ink_run` with `INK_SPLIT=24` (`INK_SPLIT_CARD=<card>`: the first engine's card, default the same): this card's
  engine is the second, its `step()` runs the first's part first (`Engine::prev`), `accept()` / `reset()` reach both;
  so guessing, the drafter, lookup, saved prompts and serving work as they are (below). Not with several sequences or
  pictures (refused). On two cards `feed()` runs the prompt as a pipeline: the first card reads step s + 1 while the
  second reads step s (two host buffers, a host thread for the first engine).
- `tools/ink_pipe.cpp`: the same split in a small driver; `INK_PIPE_ONLY=A|B` runs one engine alone on one card (card
  memory beside a context, the time of its steps; B's input rows are zeros there).
- Checks, both engines on one card (v8 baselines): the gate with `INK_SPLIT=24 INK_UBATCH=1024` passes all 12 checks a
  split supports (426 dumped tensors of the 5- and 300-token prompts, haiku 64 logits rows, code 128 ids, 16 logits rows
  after the 3,127-token prompt, lookup and drafter checks with their chosen rows); the other three refuse to start.
  `ink_pipe` gives the same rows split at 7, 18, 24, 30 and 42. One-engine gate: 15 of 15. Writing with both engines on
  one card: haiku 84.7-85.1 tok/s (one engine 86.2-86.6), the carry costs ~0.2 ms per token.
- Card memory beside 1,048,576 positions (`INK_PIPE_ONLY`, cards 1 and 2): applications 0-23 26.97 / 27.51 / 28.29 GiB
  with steps of 512 / 1,024 / 2,048 tokens (3.48 GiB free at 2,048), 24-47 27.67 / 28.23 / 29.03 GiB (2.72 free). One
  card at 530K needs steps of 256.
- Chains of more engines: `INK_SPLIT=<S1>,<S2>,...` with `INK_SPLIT_CARDS=<c1>,<c2>,...` (the engines before this
  card's). Each engine passes on the rows later engines read (they are always among the rows it took or wrote), and
  the drafter's feature rows go along the chain (`Engine::extra_rows`). With every engine on its own card `feed()` runs
  them as a pipeline, one host thread per engine before the last, two host buffers per link. Four engines (0-11,
  12-23, 24-35, 36-47) hold two full-attention caches each; the middle two hold the whole core (7.35 GB). Gate with
  three engines on one card (`INK_SPLIT=6,42`: prelude, core, coda; and `3,44`), `INK_UBATCH=1024`: the same 12 checks
  pass (drafter rows 5, 23 and 41 carried along); writing haiku 83.4 tok/s (one engine 86.6).
- Saved prompts and serving with a split: a saved prompt is the same file as one engine's (`src/cache_file.hpp` reads
  and writes each application's rows and convolution state through the engine that runs it; `CacheIO::set_queue`), and
  serving copies (`src/snapshot.hpp`) hold every engine's share on its own card. Checks on one card (3,127-token
  prompt): the files saved by one engine and by a split (`24`; `6,42` with the drafter) are byte-identical (619 MB / 658
  MB); a split loading one engine's file and one engine loading a split's file write the baseline's 16 logits rows
  (plain and with the drafter). `tools/serve_check.py <ink_run> <card> <ink_run> <out>`: a served session (a long
  prompt, a follow-up read from the held state, a new conversation, a `W` save, both conversations again) against
  fresh one-engine runs of each whole conversation: 5 of 5 identical with `INK_SPLIT=24`, and with the drafter (writing
  96-147 tok/s). The one-engine gate passes 15 of 15 (its picture answer goes through the server).
- `scripts/two-card-run.sh <ink_run> <cardA> <cardB> <out>`: the two-card run in one unattended pass (the gate's split
  checks, 100K and 200K prompts against one engine in both orders, writing after 200K with and without shared caches,
  the 1M needle with its first 200 tokens shared), stopping at the first card fault line in the kernel log.
- Shared caches (2026-11-26, `INK_SHARD=<S>` with a two-engine split; `Engine::shard_start` / `shard_attn` /
  `shard_end`; design in `notes/2026-11-26-two-card-1m-plan.md`). In a split's writing step one card waits while the
  other works, and past ~200K most of a step is reading the eight full-context caches. After the prompt each engine
  moves positions S .. n - 1 of its full-context applications down by S inside the same buffers (its kernels then
  read them through a base pointer S positions back) and stores the other engine's positions 0 .. S - 1 in the freed
  end of the paired buffer (applications paired in order, four a card at cut 25): no card memory is added; one
  application's S positions at a time cross through host memory (0.17 s for S = 16,384 on one card). A writing step's
  rows (at S + 1,024 or later) then send their queries and sinks to the other engine, which reads blocks 0 .. S/128 - 1
  and folds them into the attention state (`attn_flash_dec` + `attn_flash_sum` to = 1); the state comes back and the
  owner folds its own blocks from it. These are the values of one engine: blocks of 128 keys folded in order, the
  state carried at a boundary of 128-block groups (S a multiple of 16,384), as the chunked fold at long contexts
  already does. `shard_end` moves everything back (before steps sharing cannot take: prompts, saves; a reset only puts
  the buffers' places back). Checks on card 3, both engines on it, the 31,270-token prompt, S = 16,384, 64 tokens: all
  64 logits rows byte-identical to one engine with sharing, with `INK_SHARD_END=32` (back after 32 tokens), and with
  the drafter (ids and chosen rows); the second engine runs its 4 attention launches plus 4 for the first. Gate 15/15.
  On one card it only costs (67.0 vs 70.1 tok/s); on two cards the waiting card reads half: expected ~1.4x writing at
  500K and ~1.55x at 1M (hand-overs ~0.2 ms each, 16 a step). The moves go 32,768 positions at a time (keys, then
  value rows of 64 KB through the scratch buffer `P`), so any S fits: 100K prompt, S = 49,152, back after 32 tokens: 64
  rows identical; 200K, S = 98,304: 128 rows identical, moves 0.82 s (both on one card).
  Hand-over cost (`INK_SHARD_HOST=1`: the queries, sinks and states through host memory even on one card, as between
  two cards; 200K loaded from a saved prompt, card 3, 128 tokens, both orders): plain 3.125 / 3.129 s, shared 3.229 /
  3.285, shared through host 3.234 / 3.238, all 128 rows identical. Sharing adds ~0.8 ms a token on one card in all
  (16 hand-overs and the extra launches), and host copies add nothing measurable. With the one-engine profile (a
  writing step 11.2 ms plus ~6.25 ms of full-context attention per 100K positions) two cards should write ~1.3x
  faster at 200K, ~1.5x at 500K and ~1.7x at 1M.
- Shared copies (`INK_SHARD_COPY=<s>`, any number of engines; `Engine::shard_copy_start`): each engine keeps its whole
  cache, and engine k's positions r·s .. (r+1)·s - 1 of each full-context application are copied to engine
  (k + 1 + r) mod n, r = 0 .. n - 2 (card memory: (n - 1)·s positions per application on every card). A writing
  step's rows send their queries to all n - 1 partners at once; each reads its slice (all cards at the same time),
  then the fold goes slice by slice in block order (partner 0 from the sinks, each next one from the state before it,
  then the owner's own blocks), so the values are one engine's. Nothing moves: long reads, saves and turns run as
  usual and keep the copies; only a rewind below them drops them. Moved positions (`INK_SHARD`) are the two-engine
  case of the same fold, for when copies do not fit (two cards at 1M). Engines may hold different numbers of
  full-context applications (three engines: 2 / 3 / 3). Checks (each on one card, against the same split without
  sharing): two engines 31K, s = 16,384, plain, dropped after 32 tokens and with the drafter, 64 rows identical each;
  three engines (cuts 16, 32) on a 36K prompt, s = 16,384, with and without the drafter, 64 rows identical; 200K with
  the drafter and a one-row parts buffer (`INK_DEC_ROWS=4 INK_DEC_MEM=1`: 8-row checks fold each slice in pieces),
  128 rows identical (moved too). Four engines do not fit on one card (each loads its own copy of the middle layers it
  runs). Serving (`INK_SHARD_SERVE=1`, `INK_SHARD_MODE=auto` by default: copies of n_past / n positions each when they
  fit, shared again with larger slices once the context has grown by half and there is room, else moved with two
  engines): `serve_check.py` with `INK_SHARD_MODE=copy` and `SERVE_CHECK_GROW=1` (a follow-up of 18,500 tokens: the
  copies grow from 16,384 to 32,768 positions each at 50,313), 11 of 11 identical to fresh runs with and without the
  drafter; the moved layout (`INK_SHARD_MODE=move`, drafter) 11 of 11 too.
- Shared caches in serving (`INK_SHARD_SERVE=1` with a two-engine split; `tools/ink_run.cpp`): once an answer has
  `INK_SHARD_AFTER` (448) tokens and the context `INK_SHARD_MIN` (300,000) positions, the oldest half of each
  engine's full-context positions (the nearest multiple of 16,384) is shared; it stays shared across turns. Follow-ups
  of up to `INK_SHARD_FEED` (256) tokens are read through the shared path in steps of `dec_rows` (any step size gives
  the same values); a longer read, a save (`W`) or a copy below S + 1,024 moves them back first, a reset only puts the
  views back, a copy above that restores while shared. Check (`tools/serve_check.py` with `SERVE_CHECK_SHARD=1`,
  `SERVE_CHECK_PROMPT=prompts/long10.tokens`, both engines on one card, `INK_SHARD_MIN=20000 INK_SHARD_AFTER=16`): 10
  of 10 answers identical to fresh one-engine runs, with the drafter (card 4) and without (card 5), through every path
  (shared mid-answer, a shared 12-token follow-up, a save, a load, a copy below and above, reads of 3,117 tokens).
- `tools/make_needle_long.py`: a longer needle prompt from a shorter one (other lab notes before the question; files
  that mention the hidden values left out). `prompts/needle1m.tokens` = the 530K needle + 513,085 tokens of 299 notes
  files (`prompts/needle1m.files`): 1,042,081 tokens, the hidden notes ~1M positions before the question.
