# DeepSeek V4.1 Flash on six B70: plan for much faster prompt reading (2026-11-11)

Companion to `2026-11-11-dsv41-speed-strategy.md` (P1-P3). Evidence: lane note
`2026-11-09-dsv41-device-load-host-memory.md` §20-32, the prompt profiles in
`data/dsv41-bringup-20261109/` (p78, e65-e80), the d1-d4 / u1 / xchg benches, and the tensor table
`engine/profiles/dsv41-iq2xxs/placement.tsv`. No GPU run and no engine change was made for this plan.

## In plain words

- Today the cards read a 3K-token document at ~300 tokens/s: 16 tokens per step, ~53 ms per step.
- Each step's time on a 12-head card: about **18 ms** in the attention and shared matrices, **19 ms** in the
  experts, **4 ms** in a double-precision "stream mix" sum that every card repeats, **7 ms** of card-to-card
  exchanges, **2 ms** attention, **2.4 ms** of small launches, **0.5 ms** index.
- The main cause: **every weight gets unpacked ("decoded") many times per step.** The shared matrices unpack
  each weight once per group of 4 tokens (4 times per 16-token step). The experts unpack each weight once per
  token that picked that expert, and 16 tokens rarely pick the same expert (about 85 different experts for 96
  picks). Unpacking takes 3-4 times as many instructions as the multiply-add itself.
- The fix: **unpack each weight once and use it for many tokens**. That means kernels that keep a decoded
  weight in registers while all of a step's tokens go past it, and much bigger steps (64, then 256 or 512
  tokens), so that many tokens share each expert. Exchanges, the repeated mix sums and the repeated small
  matrices are then the next things to remove or hide.
- Expected: ~420 tok/s after the first two changes, ~570 after five, ~760 after six, ~850-980 with the last
  three. The hard ceiling under the "same arithmetic per token" rule is ~1,870 tok/s (multiply and add only, every
  instruction slot busy); **1,000 tok/s needs steps of 512 tokens and ~75 % of the card's instruction rate.**
- Long documents (19K-95K tokens) additionally need the index work split across the cards (today all six cards
  repeat it); their six-card runs stay paused until the owner decides on the host resets (§31).

## Data used, and a note on the b1 profiles

- `runs/b1/pre_c{0..5}.log` (tp82, 3,323 tokens, one answer token) finished (257-264 tok/s while profiled)
  **but hold no kernel profile**: `own_run_v41.cpp` prints the GPU profile only when `n_prof >= 1`, i.e. after at
  least one answer step (lines ~711-781). p78 ran `- 2` (two answer tokens) for this reason. To re-profile the
  prompt, run b1's prompt arm with 2 answer tokens; the profile then covers all prompt blocks plus one step.
- So the prompt budget below is from p78 (tp78, card 2 = 12 heads, card 4 = 8 heads, `OWN_MT_W16` on/off) and
  e80 (cards 0, 5): kernel time summed and divided by the 208 blocks. tp79-82 changed the prompt path only
  slightly (W16 losers reverted, norm sums; 295.8 -> 299.9 tok/s). The b1 answer-step profiles (dec_c0..5)
  match g82.

## Units and rates used

- **Issue rate**: 32 Xe-cores x 8 XVEs x 16 lanes x 2.8 GHz = **11.5 T lane-instructions/s** per card (a SIMD32
  instruction takes 2 cycles on the SIMD16 ALU). A product is a multiply then an add, **2 instructions**: an FMA
  rounds once and is not allowed (built with `-ffp-contract=off`), so the product floor is 5.7 T products/s.
  The indexer reached 2.75 T products/s (§28) at ~3 instructions per product (BF16 key shift): ~72 % issue.
  Heavy ALU use can pull the 230 W cards to ~2.6 GHz (§24): -7 %.
- **Memory**: ~550 GB/s per card practical (608 peak).
- **Weight-tokens per token per card** (card 2, from placement.tsv): dense rows **1,646 M** (per layer: q_a 6.55 M +
  kv 2.62 + q_b 7.86 (12 heads) + o_a 6.29 + o_b 7.08 + shared gate/up 3.93 + shared down 1.99 + router 1.97;
  plus compressor 18.4 M, indexer 43.5 M, engram_kv 52.4 M). **507 M (31 %) of it is replicated** on every card
  (q_a, kv, router, compressor, indexer). Dense bytes per card: **1.74 GB per step** whatever the token count.
  Routed: 6 picks x (gate+up 3.93 M + down 1.99 M) x 40 = **1,416 M slot-weights per token per card**; one expert's
  slice on one card is **1.70 MB** per layer.
- **Distinct experts per step** (until measured, see item 0): independent picks give
  u(M) = 384 (1 - (1 - 6/384)^M): 85.5 at M = 16, 152 at 32, 244 at 64, 333 at 128, 377 at 256, 384 at 512.
  Slots per decoded expert row: 1.12, 1.26, 1.58, 2.31, 4.07, 8.0. Correlated routing in real text gives fewer
  distinct experts, so these are conservative.
- **Calibration**: the expert kernels' time at M = 16 (19.1 ms) matches 7 instructions per weight per expert
  group (decode) + 2 per slot-weight at **85 % issue** (u1: active 60 %, ALU-pipe wait 31 %: issue-bound). The
  dense rows run ~4.2 instructions per weight-token (d2 machine code: per weight a shift, three type moves, an
  indirect move and the scale multiply, per token the multiply and add) at **~54 % issue**; d2's samples
  (active 40 %, pipe wait 42 %) suggest some of those moves take more than one issue slot.

## Where a 16-token block goes, and what it would cost at 32 and 64 tokens (card 2, ms per block)

"Now" at 32 / 64 = today's kernels with bigger blocks (projected). Floors are for that block size.

| part | now M=16 | now M=32 | now M=64 | ALU floor (16 / 32 / 64) | memory floor (16 / 32 / 64) | change that gets near the floor |
| --- | --- | --- | --- | --- | --- | --- |
| dense rows (excl. mix dots) | 17.8 | ~35 | ~69 | products only 4.6 / 9.2 / 18.4; decode-once form (2.5 instr) 5.7 / 11.5 / 23.0; today's 4.2 instr 9.6 / 19.3 / 38.6 | 3.2 / 3.2 / 3.2 | decode once per 16 tokens (A), split the replicated rows (D), then issue efficiency (G) |
| stream-mix dot rows (double) | ~4 (est.) | ~8 | ~16 | 655 M / 1.3 G / 2.6 G double products; double rate unmeasured (~4 ms suggests it is near its own floor) | small | split the 200 partials per token across the cards; they ride existing exchanges (C) |
| routed experts | 19.1 | ~35.1 | ~59.9 | products only 4.0 / 7.9 / 15.9; with decode 16.3 / 29.9 / 51.1 | 10.6 / 18.8 / 30.2 | more tokens per decoded expert row: bigger blocks, groups up to 16 slots (B, F); fewer decode instructions (H) |
| attention | 2.07 | ~3.9 | ~7.0 | 0.84 / 1.7 / 3.4 (2 instr); 1.27 / 2.5 / 5.1 with the BF16 key shift; 1.8 / 3.5 / 7.0 at 2.75 T/s | < 0.1 (rows shared in L2) | already near the practical floor; bigger blocks fill the card; no big lever |
| index (3K document) | 0.45 | ~0.7 | ~1.3 | 0.12 / 0.25 / 0.5 (42.5 M products per token) | small | nothing at 3K; split across cards for long documents (I) |
| exchanges | 7.4 | ~11.3 | ~20.7 | transfer 3.1 / 6.1 / 12.3 at 24 GB/s (4.6 MB pulled per token) + 1.95 of round trips (160 pulls x ~9 us + 80 pair swaps) | - | hide behind compute: two half-blocks in flight (E) |
| small ops (norms, mix post, rope, swiglu, combine, window, grouping) | 2.42 | ~2.7 | ~3.5 | ~0 (1,350 launches per block, each a few us) | ~0 | bigger blocks amortize the launches |
| **total** | **53.2 (300 tok/s)** | **~97 (330 tok/s)** | **~178 (360 tok/s)** | | | |

Per-part notes:

- **Dense rows** are ALU-bound, not memory-bound (1.74 GB per step = 3.2 ms; ALU 17.8 ms). The 4.6 ms products-only
  floor is the absolute limit for 16 tokens; the practical target with decode-once forms is ~8 ms (2.5 instr at
  ~70 % issue). The block size alone does not help: today's forms decode per token group, so their cost per
  token is constant.
- **Routed experts** are decode-bound at ~85 % issue: at 16 tokens 75 % of their instructions unpack expert rows
  that only 1.12 slots use. Per token: 1.20 ms at M = 16, 1.10 at 32, 0.94 at 64, 0.73 at 128, 0.54 at 256, 0.42 at
  512 (model, independent picks). Their memory floor stays below the ALU cost at every size.
- **Exchanges** are mostly transfer at M = 16 (the floor is ~6.1 of the 7.4 ms; the rest is waiting for the
  8-head and the slow-clock cards). The volume (oa 8,192 + ob 5,120 + act 16,128 + moe 5,120 floats per token
  and layer) is the price of exact tensor parallelism (gather inputs, split outputs, never sum partials across
  cards), so it cannot shrink; it can only be hidden.
- **Mix dot rows**: 25 rows x 20,480 double products per token, twice per layer, on every card; each card's
  launch with them is 37-64 us longer than the matrix alone (e65/e76: q_a + dots 108.6 us vs ~55 for q_a,
  router + dots 79.4 vs ~15). ~4 ms per block (~0.25 ms per token), an estimate until benched alone.

## The questions asked

**Bigger blocks.** The per-token arithmetic does not depend on the block size (the gate checks this), so only
buffers and a few fixed sizes change.
- *Card memory*: the per-token buffers in `mt_alloc` are ~1.06 MB (q, of, obuf hold all 64 heads; attn_w
  64 x 640; expert outputs; streams; old; head logits) + the exchange arena ~0.45 MB + the index score/candidate
  rows (max_seq + 64) x 5 bytes (20 KB at 4K, 655 KB at 128K). M = 64: ~100 MB; M = 256: ~390 MB; M = 512: ~780 MB
  at 4K context. Free after load 3.8-4.3 GiB (2.44 with the draft). M = 256 fits everywhere; M = 512 fits without
  the draft or after trimming q / of / obuf / attn_w to the card's 8-12 heads (-0.45 MB per token) and keeping
  tlogm for checks only. Long contexts: run the index in sub-blocks of 64 tokens to cap the score buffers.
- *KV ring / block area*: ring rows are 128 + MTX per layer (M = 256: 393 KB x 40 layers = 16 MB, fine).
  `RingCommitM` writes ring row (pos0 + t) % 128 for every block token: past 128 tokens two tokens hit the same
  row (a race), so commit only t >= M - 128. `WindowAppendM` already maps rows past the ring into the block
  area (`win + (q - pos0)`); the compressed-list offset (`v + mtx`) must use the runtime M.
- *Engram rows*: per token 2 x 24 rows of 176 B: M = 256 is 2.2 MB of host copies and one upload per block
  (~1 ms against a ~340 ms block). `OWN_ENG_AHEAD` (16) must become >= M so the next block's rows are asked
  for during this block.
- *Fixed sizes to lift*: `MTX = 16` (compile-time, used as template sizes: replace by a runtime M with a
  compile-time maximum, and never instantiate `DenseRowsM<D, MTX>` / `GemvTM<..., MTX>` at large M); the per-token
  arrays inside kernel structs (`lens[16]` in `CidxFillM`, `IndexerScoreBM`, `TopKSel*M*`, `IndexerScoreBCM`) move
  to device memory (kernel arguments are limited to ~2 KB); `mlen[..][MTX]`, `mt_tgm[MTX + 1]`; `ExpertGroupM`
  (one 128-item group: <= 128 slots = 21 tokens) and `RUGrp::MAXU = 128` (groups) must cover 6M slots;
  `RoutedU` MT 6 -> 16 for M >= 128; the draft's block buffers (`dr_*`) or a cap of 16 while `OWN_DSPARK` is on.

**Expert-major grouping when 16-64 tokens share experts.** `RoutedU` already decodes a row once per group of
<= 6 slots of the same expert. The groups are small because the tokens share little: 1.12 slots per group at
16 tokens, 1.58 at 64 (independent picks). Below ~128 tokens grouping cannot amortize much; at 256 tokens a
group averages 4 slots (cap 6 would split ~11 % of experts: raise to 16; registers allow it). Order the groups by
slot count (heaviest first) so the long groups do not form the tail. Layer 0's Q2_K down rows (`RoutedQ2KF`) are
still slot-major (one decode per slot, 0.26 ms per block): an expert-major Q2_K form is a small (0.5 %) item.

**Decode once into registers, reuse across tokens.** Today's forms re-decode:
- dense `DenseRowsG<D, G>` / `DenseRowsGR<D, G, R>` run each token group on its own sub-group, and each one
  reloads the quant words and redoes shift, conversions, scale broadcast and multiply: 16 / G decodes per weight
  per block (G = 4: four times; the W16 rule's G = 8 on output-b: twice). `DenseRowsM`'s `rowm` also re-decodes per
  `MTG` chunk (8 tokens for Q8_0, 4 for Q6_K) on the same sub-group.
- `rowg<NT>` loads every token's activations before the products (`xv[NT]`: vec4 per token for Q8_0, **vec8 per
  token for Q6_K**), so NT = 16 needs 64-128 floats per lane: that is why d1's G16 forms were slower (register
  spills or half the threads in large-register mode), not a sign that decode-once does not pay.
- `RoutedU`: decode once per (group, row), slots from registers: right form, limited by the group sizes above.
The fix is the weight-stationary order: per quant word decode the R rows' values once (4 floats per row for Q8_0,
8 for Q6_K / IQ formats), then stream the T tokens past them (one activation block load per token, R x 4 (or 8)
multiply-adds into sum[R][T]). For every (row, token) the sum still runs over the columns in the same order with
the same expression, so it is bitwise the one-token value. Registers (SIMD32): R = 2, T = 16 needs 2 x 16 sums +
8 decoded + 8 (16) activation floats + the quant segment: ~56-64 floats, fits.

**Fewer conversions per weight-token.** Q8_0: today ~6 instructions of decode per weight per group of 4 tokens
(1.5 per weight-token) + 2 for the product; decode-once at T = 16: 0.375 + 2 + 0.06 for loads = ~2.45. Q6_K
(~10 decode instructions: two field extracts, or, subtract, convert, two scale broadcasts, select, multiply):
4.5 -> ~2.65. The BF16-exact rows (router, compressor, indexer: `GemvH16P`, one shift per weight) are already ~2.3
and gain little. d3's cheaper int8 -> float routes (+-6 %) stop mattering once the decode is shared by 16 tokens.
Experts: their grid values come from a float table in local memory (no conversion); their decode is cut only by
more slots per decode (bigger blocks) or fewer index-extraction instructions (H).

**Work-group shapes.** Keep the row-major position map (the token groups of one row in the same work-group, so a
row's quant words come from L1 once per work-group). At M = 16 the decode-once form has only rows / R sub-groups:
q_a 640, kv 256, o_b 432, shared 192-432, router 192 against ~1,024-2,048 thread slots, so small matrices keep two
token groups of 8 at M = 16 (T = 16 from M = 32 on). After the replicated-rows split (D) the slices are 1/6 as tall:
use work-groups of 4 sub-groups for them (the `OWN_MT_RWG` lesson: 16 small rows per 512-item group run on one
core). Experts: unchanged (persistent loop, table filled once per work-group).

**Exchanges per block.** 160 pulls + 80 pair swaps + 2 engram pulls per block whatever M: ~2 ms of round trips
(0.12 ms per token at M = 16, 0.03 at 64). The transfer (4.6 MB per token per card, ~0.19-0.26 ms per token) stays;
it must be overlapped. The pair swap of the split heads can join the o_a pull as a second region (-80 launches).
New exchanges from D are 2 per layer (q_a / kv slices, router logits); C adds none (partials ride existing pulls).

**Attention and index at long context.** Attention stops growing at ~2K tokens (640 slots) and sits at
~1.2x its practical floor: no big lever. The index grows: at 95K tokens ~757 M products per token (layer 20 over
all rows, layers 24-36 over 16,384 candidate rows, layers 2/8/14 over half the rows) = ~0.28 ms per token at
2.75 T/s **on every card** (the six cards repeat it), plus 8 selects; reading at 95K is 263.6 against ~300 tok/s
at 3K (+0.46 ms per token). At a 1-1.3 ms per token target that is 30-40 % on long documents. Fix (I): each card
scores 1/6 of the rows and selects its local top 512 by (value descending, position ascending), the cards swap
the 512 (value, position) pairs per token and layer (24.6 KB), and every card merges them. Under that strict
order the global top 512 is inside the union of the local ones, so the list is the same set; it is written in
ascending positions as today. NaN and -inf rules must be the select's own (bench them). The index's key rows can
also be read once per block for all tokens (keys in registers, every token's queries from local memory).

**Overlapping prompt blocks across cards.**
- *Two half-blocks in flight* (E): split a block into halves A and B; per layer each card runs A's phase, then
  B's; A's exchanges run on a second in-order queue while the compute queue runs B (and the reverse). B's
  attention needs A's key rows of the same layer, which the order already gives; A's rows are published before
  B's, so the compressed row numbers stay the same. Needs separate exchange regions per half, cross-queue events,
  and every card launching in the same order (no circular wait). Hides ~70-80 % of the exchanges.
- *Layer pipelining across cards*: rejected. The weights are row slices of every layer (decode needs that); whole
  layers per card would need a second copy of the 157 GB of experts, and answers would get ~6x slower.
- *Two groups of three cards on different blocks*: same weight-layout problem.

## Ranked plan

Expected tok/s on the 3K document, cumulative, from the model above (card 2 critical; balanced cards assumed;
each row lists the ms per token that remain). "Ranked" = execution order; by size the order is F + B (block size:
-0.98 ms per token together), A (-0.42), E (-0.28), C (-0.20), D (-0.14), G (-0.13), H (-0.06).

| # | change | expected tok/s after it | remaining ms per token (dense / dots / routed / exchanges / attn+index+small) | bench that proves it |
| --- | --- | --- | --- | --- |
| 0 | **Measure first** (no engine change): distinct experts per block u(M) from a dump of every token's 6 ids per layer during one short 3K read (extend `OWN_MT_IDSTAT` to write the ids; offline u(M) for M = 16..1024); the mix dot rows alone at 16 / 64 tokens; a per-card free-memory census at M = 64 / 256; the prompt profile rerun with 2 answer tokens | 300 | 1.11 / 0.25 / 1.20 / 0.46 / 0.31 | the dump decides how far to take B / F (correlated routing makes 32-64 pay more); `bench_dense_m16` with the `HcDotsRows` rider only |
| A | **Dense rows decode once for 8-16 tokens** (weight-stationary `rowt<T, R>` forms for Q8_0, Q6_K, Q5_K; T = 16 on matrices with >= 2,048 rows, T = 8 below, at M = 16) | **~340** | 0.73 / 0.25 / 1.20 / 0.46 / 0.31 | `tools/bench/bench_dense_m16.cpp` + the new forms at the **engine's launch shapes with riders** (q_a + dots, router + dots, `RoutePMRows`), 16 / 32 / 64 tokens, cold, bitwise per token against the one-token kernel; instructions per weight-token from the IGC dump; pass: >= 1.3x per launch on q_b, q_a, o_a, o_b and no shape slower; then engine A/B on the 3K read (two alternated runs, >= +8 %) |
| B | **Blocks of 64** (runtime M, the fixed sizes above, `ExpertGroupM` / `RUGrp` for 384 slots, ring commit of the last 128, `OWN_ENG_AHEAD >= M`) | **~420** | 0.66 / 0.25 / 0.94 / 0.34 / 0.19 | `test_routed_u.cpp` at 32 / 64 tokens and groups up to 16 (bitwise); a new `ExpertGroupM` test at 96-1,536 slots; engine gate (below) with blocks of 64 / 37 / 16 / 5 / 1; 3K read at M = 16 / 32 / 64 alternated |
| C | **Mix dot rows split across the cards**: each card computes ~34 of the 200 partials per token; the attention mix's partials ride the o_a pull, the FFN mix's the act pull (both consumers come later, in phases 3 and 5); every card runs the finish from the gathered partials | **~460** | 0.66 / 0.05 / 0.94 / 0.34 / 0.19 | `xchg_pull_test.cpp` with the extra region (0 wrong values, 2,000 iterations); engine gate; 3K read A/B |
| D | **Replicated rows split across the cards** for blocks >= 64: q_a + kv (one pull of 1,792 floats per token before the q_a / kv norms), router (one pull of 384 logits before the top-6), compressor and indexer rows; give the 8-head cards the larger slices (evens the head imbalance) | **~490** | 0.49 / 0.05 / 0.94 / 0.37 / 0.19 | `bench_dense_m16` at the split shapes (213-row q_a slices, 64 tokens); engine gate; 3K read A/B |
| E | **Exchanges overlapped**: two half-blocks in flight, exchanges on a second queue per card | **~570** | 0.49 / 0.05 / 0.94 / 0.09 / 0.19 | `xchg_lat_bench.cpp` extended: a compute kernel of known length on one queue and the pulls on another on all six cards (hidden fraction); `xchg_pull_test` with two queues (0 wrong values, no hang); engine gate; 3K read A/B |
| F | **Blocks of 256** (expert groups up to 16 slots, heaviest first; buffers trimmed to the card's heads if needed) | **~760** | 0.49 / 0.05 / 0.54 / 0.09 / 0.15 | free-memory census; `test_routed_u` at 256 tokens; engine gate with blocks of 256 / 129 / 255 / 16 / 1; 3K read at 64 / 128 / 256 alternated; clocks from `gpu_sampler.py` |
| G | **Dense issue efficiency ~54 % -> ~75 %**: stall sampler and machine-code census on the A forms; R x T register blocking, loads-first, a 16-lane sub-group holding 32 logical lanes if registers demand (the norm bench's two-half tree is bitwise, §29); optional: decode to local memory once per block for 4 token groups | **~845** | 0.36 / 0.05 / 0.54 / 0.09 / 0.15 | `tools/bench/pcs.hpp` on the new forms; `bench_dense_m16` variants; engine A/B |
| H | **Expert decode with ~25 % fewer instructions** (index extraction and sign per 8 weights shared across the lane's group; scale per block hoisted) | **~890** | 0.36 / 0.05 / 0.48 / 0.09 / 0.15 | `test_routed_u.cpp` (all 5 formats, both shapes, bitwise) with timing at 64 / 256 tokens; u1-style stall samples |
| F2 | **Blocks of 512** where memory allows (3K = 7 blocks) | **~980** | 0.36 / 0.05 / 0.39 / 0.09 / 0.13 | as F |
| I | **Long documents: index split across the cards** (local top 512 + merge) and key rows read once per block | +6-8 % at 95K today; +20-30 % at the 1-1.3 ms level | - | one-card bench of the merge select (lists identical on normal values, heavy ties, +0 / -0, mostly -inf, NaNs; 19K-130K rows, like `test_topk_q.cpp`); engine runs on 19K-95K documents **wait for the owner's decision on long six-card runs** (§31) |

Smaller items: the attention output and score at 64+ tokens (~2 %), the pair swap folded into the o_a pull
(~1 %), an expert-major Q2_K form for layer 0 (~0.5 %).

## Gates (every build, unchanged in kind)

Three-step decode traces byte-identical after prompts read in blocks of 64, 37, 16, 7, 5 and 1 (and 256 / 129 / 255
once F lands: odd sizes test the ratio-2 pairing, sizes > 128 the ring commit); 40- and 128-token answers the same;
the 3K and 10K documents' answers the same as the one-token reading; guessing runs SAME as the plain runs. Short
runs only. Each change is first proven bitwise on one card in its bench (six benches can run on six cards at
once), then batched into one gate build (strategy rule 5).

## Not planned, and why

- **Pipeline parallel across cards**: see above (weight layout fixed by decode; experts cannot be duplicated).
- **Expert parallel (whole experts per card)**: the same bytes and decode per token, more exchange volume
  (6 x 5,120 slot outputs per token instead of 7 x 2,304 + 5,120), and load imbalance per block.
- **Splitting a row's columns across sub-groups** (more parallelism for short matrices): changes the sum order.
- **A one-instruction product**: the hardware's float multiply-add is the fused FMA (the compiler implements
  OpenCL's correctly rounded `fma` with it), so it rounds differently; the product stays 2 instructions.
- **Lower precision, DPAS / XMX, TF32 or BF16 math**: not allowed.
- **More dense-form sweeps at M = 16 without decode-once**: d1 / d3 / p78 already show +-10 % at best.

## Risks

- Real routing may be less clustered than assumed for some prompts (u(M) worse than the independent model only
  if routing anti-correlates, which load-balancing bias could do mildly); item 0 measures it.
- Denser ALU work may pull the 230 W cards to ~2.6 GHz (-7 %, §24-25); watch the telemetry in every A/B.
- E is the riskiest change (two queues, spinning pulls): it goes in only after `xchg_pull_test` runs clean with
  two queues and the exchange-timeout path (`xerr`) still reports a stuck peer.
- Blocks larger than 16 change nothing in guessing checks (2-6 tokens); decode speed is unaffected by A-F except
  through shared allocations (watch the free memory with the draft loaded).
