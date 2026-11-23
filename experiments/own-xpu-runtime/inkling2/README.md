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
| fused multiply-add, baseline v3 (card 3) | 642.7-643.2 tok/s; 31K prompt 530.6 (was 446.6, card 2) | short 12.28 ms, 3K 13.18 (was 12.31-12.36, 13.35; card 4) | every sum of products through `mac()` (below) |
| reads issued together, weights warmed (card 3) | | short 11.61-11.63 ms (was 12.31-12.33 for the build before) | small kernels without a branch around each read; the mix warms L2 (below) |
| expert inputs in lane order (card 3) | | short 11.38-11.40 ms (was 11.54-11.58) | gate\|up and down products read their input 4 cache lines per load, not 16 (below) |
| long rows 64 reads per round (card 3) | | 100K: 20.78 ms (was 21.24); 403K: 24.87 tok/s (was 23.53, card 5) | full layers' softmax and block sums past 16K keys (below) |
| job pointers as global, small steps (card 2) | | short 11.42 ms (was 11.61-11.62); steps of 2 / 3 / 4 tokens 15.65-15.67 / 18.26-18.29 / 21.42-21.56 ms (were 20.14-20.15 / 24.09-24.16 / 28.61-28.75) | pointers read from job tables cast to global; 2-4 token steps with one launch per kind (below) |
| DSpark drafter guesses (card 2) | | code 256 tokens 109.68 tok/s with 2 guesses (plain 87.70), haiku 128 94.66 (plain 88.05) | the drafter on the card, guesses checked exactly (below) |
| control modules batched for 2-4 tokens (card 2) | | steps of 2 / 3 / 4 tokens 14.92-14.93 / 17.36-17.38 / 20.39-20.40 ms (were 15.69-15.73 / 18.27-18.30 / 21.42-21.52) | norms, down products and gain\|forget outputs of all modules and tokens in 3 launches (below) |

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
- The check step's output rows: the final norm writes lane-order rows for steps of 1-4 tokens; 4 rows 1,291 ->
  944 µs (multi_m), one row 676 -> 655 (bench_gemv, card 3). Greedy choice in two launches (`ops::argmax_rows2`,
  same index; one work-group per row took 56-63 µs).

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

