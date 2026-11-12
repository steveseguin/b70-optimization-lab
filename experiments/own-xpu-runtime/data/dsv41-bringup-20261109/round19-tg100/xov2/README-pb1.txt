pb-1: faster prompt reading in blocks of 128 / 256 tokens (and the H16 rows at 9-64), bit for bit
=====================================================================================================
Patch: /home/steve/dsv41-work/pb256/pb-1.patch (3 files, 614 lines; `cd engine && git apply --check pb-1.patch` OK
against the tree as of 20:04 2026-11-11 = tp99 + qb-off guard + xperm-1 + wa-2). Opt-in: OWN_PB=1 (= mask 0x1e) or
OWN_PB=<mask>; unset / 0 = every launch exactly as before. Decode and check steps (1-8 tokens) are never touched.

In plain words
--------------
Blocks of 256 tokens were supposed to be faster per token than blocks of 64, but several kernels got slower per token
as the block grew. pb-1 fixes that, kernel by kernel, without changing any number the model computes:
  * the matrix kernels walk the 256 tokens in chunks of 32 (or 64) so the weights stay hot in cache;
  * each matrix role gets the tile shape that the bench measured fastest at 128 / 256 tokens;
  * the router / compressor / indexer rows (16-bit weights) get a weight-reusing kernel (2.6-4x faster);
  * the expert grouping is done in parallel (6-15x faster);
  * the 6-bit kernels get a variant without a per-thread scratch array, which also dodges the tp97 slowdown
    (that array sits in slow global memory in the dense module; see README-private-mem.txt), and at 9-64 tokens
    (today's block size 64) the fastest such form per role: 1.2-1.7x on the 6-bit matrices at 64 tokens.
Predicted: about 1.0-1.1 s less card-2 kernel time per 3K read at blocks of 256 (about 0.9 s at 128, about 0.5 s at
64 - the 64 figure was 0.25 s before the 9-64 token 6-bit picks were added at 20:00).

Switch bits (each independent, each gives the production outputs bit for bit)
  2   H16 rows (router 384 rows, compressor kv/gate 512, indexer q_b 4,096) in WS forms (WsH16, form T8 R4) at 9-256
      tokens; the indexer proj (32 rows) and router / compressor at 9-16 tokens keep the engine form (faster there)
  4   expert grouping by a counting sort in local memory (ExpertGroupPM), every block size where ExpertGroupM ran
  8   Q6_K forms without the private scale array (WsQ6S): at 9-64 tokens the fastest S form per role and token
      class (16 / 32 / 64, table below; kv and the 512-row output-a keep WsTab's form at 9-16); at 128 / 256 the S
      picks below
  16  blocks of 65-256 tokens: per-role form + token chunk (DenseRowsWSC) for every Q8_0 / Q6_K / Q5_K role
Code: sycl_v41.hpp (DenseRowsWSC, WsQ6S, WsH16, WsPb<fmt, cols, kind> tables, ws_rows), backend_sycl_v41_mt.inc
(ExpertGroupPM launch), own_run_v41.cpp (OWN_PB parse).

Why it is bit-exact
  * DenseRowsWSC makes the same rowt calls as DenseRowsWS on the same (row group, token group) pairs; only which
    sub-group handles which pair changes. Every output element is the same sum in the same order.
  * WsQ6S reads the 6-bit scales per segment from the weights instead of a private array: same values, same order.
  * WsH16 forms: GemvH16P's lane sum order (segments ascending, then the sub-group reduction), per token.
  * ExpertGroupPM: counting sort; every grp word equal to ExpertGroupM's (expert ids, offsets, token order).

Per-kernel times, card 2 (0000:43:00.0), real GGUF rows, us per launch, sequential weights (bench PART_PICK / PART_EG)
production form -> pb-1 pick (form, token chunk); bench module keeps private arrays in scratch (the engine's dense
module does not: there the WsQ6 production forms are ~23 % slower than shown, the S picks are not)
  role (rows x cols)            64                    128                      256
  Q8 q_a 1280x5120              134 (kept)            402 -> 227 X16R2 ch32    667 -> 489 X16R2 ch64
  Q8 kv 512x5120                53.9 (kept)           153 -> 90.0 X16R2 ch32   266 -> 184 X16R2 ch32
  Q8 q_b 6144x1280              152 (kept)            314 -> 299 X16R2 ch32    720 -> 626 X16R2 ch32
  Q8 o_a 1024x4096              87.5 (kept)           197 -> 155 X16R2 ch32    398 -> 310 X16R2 ch32
  Q8 o_a 512x4096               42.9 (kept)           97.1 -> 77.9             196 -> 155
  Q8 o_b 864x8192               162 (kept)            415 -> 277 X8R2L ch32    724 -> 532 X16R2 ch32
  Q8 shared gate+up 384 (pair)  77.9 (kept)           234 -> 136 X16R2 ch32    390 -> 281 X16R2 ch32
  Q8 shared down 864x2304       57.2 (kept)           104 -> 80.6 X16R2 ch32   210 -> 144 X16R2 ch32
  Q6 q_a 1280x5120              see Q6 9-64 below     267 -> 246 (S 254)       877 -> 495 K16R2S ch32
  Q6 kv 512x5120                                      188 -> 102 K16R2S ch32   350 -> 199 K16R2S ch32
  Q6 q_b 6144x1280              (kept)                338 -> 312 K16R2 ch32    783 -> 644 K16R2 ch32
  Q6 o_a 1024x4096              (kept)                253 -> 160 K16R2 ch32    553 -> 316 K16R2 ch32
  Q6 o_a 512x4096               (kept)                127 -> 78.6              273 -> 160
  Q6 o_b 864x8192                                     479 -> 307 K16R2S ch32   988 -> 545 K16R2S ch32
  Q6 engram 4267x6144                                 1111 -> 1108 K16R2S ch64 3695 -> 2081 K16R2S ch64
  Q5 shared gate+up 384 (pair)  (kept)                260 -> 151 K16R2 ch32    542 -> 303 K16R2 ch32
  Q5 shared down 864x2304       (kept)                117 -> 91.8 K16R2 ch32   267 -> 163 K16R2 ch32
  H16 router 384x5120           67.8 -> 36.7 H8R4 c32 189 -> 72.2 H8R4 ch32    450 -> 111 H8R4 ch32
  H16 compressor kv 512x5120    92.0 -> 38.8          258 -> 75.1              607 -> 150
  H16 indexer q_b 4096x1280     292 -> 81.5           635 -> 165               1251 -> 345
  expert grouping (zipf / unif) 38.6 / 31.2 -> 5.5 / 4.7   86.6 / 66.1 -> 12.7 / 10.8   297 / 249 -> 29.7 / 16.5
  H16 at 32 tokens: router 40.1 -> 25.7, kv 41.4 -> 26.2, q_b 131 -> 42.2; at 16: q_b 66.9 -> 24.9 (router / kv kept)
  (S = WsQ6S; without bit 8 the non-S K16R2 form with the same chunk is used: q_a 493, kv 194, o_b 585, engram 2152 at
  256; engram at 128 is kept without bit 8)
  Q6 at 9-64 tokens with bit 8 (bench dense3, production form -> pb-1 pick, us per launch; T = tokens per group;
  S forms have no private array, so their times hold in the engine's global-memory module, where the production
  forms are slower than here: pp97 at 64 tokens, output-b 317 us in the engine against 242 here):
    role                16                    32                    64
    q_a 1280x5120       49.1 -> 45.3 T16 S    85.4 -> 79.3 T8 S     204 -> 135 T8 S ch32
    kv 512x5120         18.0 (kept)           34.8 -> 27.5 T8 S     81.2 -> 48.1 T16 S
    o_a 1024x4096       27.4 -> 21.4 T8 S     55.6 -> 36.9 T16 S    91.9 -> 74.1 T16 S ch32
    o_a 512x4096        14.7 (kept)           28.6 -> 21.4 T8 S     65.0 -> 37.7 T16 S
    o_b 864x8192        39.5 -> 39.5 T8 S     83.4 -> 70.2 T16 S    242 -> 147 T16 S ch32
    engram 4267x6144    155 -> 152 T8 S       278 -> 260 T16 S      589 -> 506 T16 S
    q_b 6144x1280       (kept: no S form for 1,280 columns; the best other form is within 1-4 %)
  (pks2: every T4 / T8 / T16 form, S and not, chunk 0 / 32, at 16 / 32 / 64 tokens: 270 candidates, 0 differ)

Bitwise checks done (card 2, all memcmp of every output float against the production form)
  * PART_PICK: 595 candidates at 128 / 256 tokens (every role, every candidate form x chunk 0/32/64/128) - 0 differ;
    184 candidates at 16 / 32 / 64 (Q8 / Q5 / H16) - 0 differ
  * PART_DENSE (the engine's ws_rows with OWN_PB masks 0x10 / 0x50 / 0x8 / 0x18 / 0x2): 320 compares - 0 differ
  * PART_EG: 2,400 grouping cases + 10 timed shapes - 0 words differ
  * final tables (dense2, 19:56): masks 0x2 0x8 0x10 0x18 0x1e at M = 9 16 17 32 33 64 65 96 128 129 192 256, every
    role: 1,260 compares, 0 differ; after the 9-64 token Q6 picks (dense3, 20:02): Q6 roles at M = 9 12 16 17 24
    32 33 48 64 (masks 0x8 0x18 0x1e) 189 compares and at 65 128 129 256 (0x8 0x10 0x18 0x1e) 112 compares, 0 differ

Predicted saving (pp97 card-2 kernel table x bench ratio per role; 3K read = 3,323 tokens)
  block 256: ~1.08 s of card-2 kernel time (H16 0.29, grouping 0.16, Q8 roles 0.28, Q6/Q5 roles 0.36)
  block 128: ~0.94 s;   block 64: ~0.49 s (H16 + grouping 0.25 s; Q6 9-64 picks 0.24 s: output-b 676 launches
  317 -> 147 us = 0.115 s, q_a + kv 0.067 s, the two output-a 0.037 s, engram 0.017 s)
  pp97 profiled reads: 7.21 s (64), 7.03 (128), 6.89 (256). If the other five cards save alike and the exchanges do
  not absorb it, a 3K read at 256 moves from ~6.9 s toward ~5.9 s. Best block size with pb-1: 256 (128 close behind).
  Caveats: the 128 / 256 Q6 savings assume the dense module keeps its private arrays in global memory (tp97-tp100);
  if gp-1 later moves them back to scratch the 128 / 256 S picks are 1-4 % slower than the non-S forms (the OWN_PB=0x16
  arm below covers that). The 9-64 token S picks win in either placement (times above are against scratch).

Gate arms wanted (tp100 with pb-1; TB / PL / T1 / T5 = the tg99c settings)
  1. prompt traces vs the reference, OWN_PB=1: blocks 1 (T1), 5 (T5), 64, 128, 256 (TB + OWN_PROMPT_BLOCK=b);
     at 128 and 256 also one arm per bit: OWN_PB=0x2, 0x4, 0x8, 0x10
  2. 3K traces vs runs/gm64/t3k_ref: OWN_PROMPT_BLOCK=64 OWN_PB=1 and OWN_PROMPT_BLOCK=256 OWN_PB=1 (TB)
  3. 3K reads (whole times), PL with OWN_PROMPT_BLOCK=64 / 128 / 256, each OWN_PB unset and OWN_PB=1 (back to back);
     if time allows, at 256: OWN_PB=0x16 (no WsQ6S) to choose bit 8, and at 64: OWN_PB=0x8 alone (the 9-64 Q6 picks)
