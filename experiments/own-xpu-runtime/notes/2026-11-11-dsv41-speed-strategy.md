# DeepSeek V4.1 Flash on six B70: speed strategy and scoreboard (started 2026-11-11)

Owner, 2026-11-11: "we've started to move at a crawl, trial and error optimization" ... "lets try to get token
decode rate to like 200 tok/s and much faster prompt processing." Use more helpers, more cards at once, older
code, other open-source projects, tools that predict speed without running, and big-picture changes. This file is
the plan, the idea list and the scoreboard of strategies (kept current; detailed evidence stays in the lane note
`2026-11-09-dsv41-device-load-host-memory.md`, sections cited as §N).

## Goal and the hard rule

- Answers (decode): 85 tok/s plain, 104-117 with guessing (§32) -> **200 tok/s**.
- Prompt reading: ~300 tok/s at 3K tokens (§28, §31) -> **much faster** (target 1,000+).
- **Lossless = bit-identical** to the current engine: the 3-step trace byte-identical to `runs/ab1/base.trc`, the
  40 / 128 / 256-token answers the same, guessing output the same as plain. Allowed: anything that computes the same
  floats in the same order (layout, scheduling, fusion, launch structure, overlap, proven-exact shortcuts with a
  fallback, guesses checked by the full model). Not allowed: reordered float sums without a proof, lower-precision
  activations (fp16 / bf16 / int8 activation quantization), rounding matrix units (TF32 / bf16 DPAS), any
  approximation.

## Where the time goes (start of this plan)

Card 2, answer steps, `OWN_GPROF=2` (§32; profiled step 13.7 ms, a real step 11.7 ms at 85 tok/s, so profiling
inflates the idle gaps):

| Part | ms per word | Best possible (rough) |
|---|---|---|
| Weight-reading kernels (experts, attention matrices, shared expert, head) | ~7.6 | ~3.1 for the whole step's bytes (1.69 GB per card per word at ~550 GB/s) |
| Small serial steps (norms, router, mix finish, engram, publish) | ~2.9 | well under 1 |
| Exchanges between cards (160 per word, ~13 us each) | ~2.1 | ~1 with fewer / overlapped exchanges |
| Attention core | ~1.1 | |

The cards read their weights at ~145 GB/s of ~600 (§28): the step is latency-bound (about 1,051 short launches per
card per word, each ramping up and tailing off; 160 waits on the slowest card; serial loops), not memory-bound.

What 200 tok/s needs: 5.0 ms per word plain, or ~6.8 ms plain (~148 tok/s) with guessing at today's ~1.35x. Either
way the weight reading must get close to the card's bandwidth and the exchanges and small steps must mostly hide.
That is a structural change, not more per-kernel polish.

Prompt reading: a 16-token block takes ~57 ms (§27). With each token's arithmetic fixed to the one-token order, the
ceiling is set by ALU work per weight-token (~4 instructions per weight and token in today's Q8_0 forms, §31 d2):
roughly 4x above today. Bigger blocks (weights read once per block), fewer instructions per weight-token and a
faster prompt attention are the levers.

## Guessing math (g82 logs: code / analysis / 3K prompts)

Per cycle today: 2.58 / 2.02 / 2.48 tokens (70-77 % of guesses kept, only ~1.3-1.8 guesses per cycle because the
adaptive count stops early), draft 2.2-2.3 ms + check 17-20 ms (1.5-1.7x a one-token step of 11.7 ms). tok/s =
tokens per cycle / (draft + check). For 200 tok/s at 2.6 tokens per cycle a cycle must cost ~13 ms (about one plain
step); at a 75 % keep rate, five guesses every cycle would give ~3.3 tokens per cycle (1 + 0.75 + ... + 0.75^5),
needing a cycle of ~16.5 ms. So the guessing route to 200 = a check of 5-6 tokens costing little more than a
one-token step (dense rows read once for all tokens already; the experts and per-token small steps are what grows)
+ a cheaper draft (2.2 ms = 11-13 % of a cycle) + the plain step itself faster.

## Method (replaces "take the top kernel and try variants")

1. **Budget first.** A time-vs-floor ledger for every kernel type and every part, on all six cards, including who
   waits for whom at each exchange (`b1` profiles, `tools/perf/` below). Rank by milliseconds recoverable. Rebuild
   after each batch.
2. **Fix categories, not kernels.** The biggest gaps are structural (launch count, exchange latency, weight reads
   that start only when the input is ready); one structural fix outweighs ten kernel polishes.
3. **Predict before running.** The machine-code census and floor model (`tools/perf/`) give a predicted time per
   kernel; the stall sampler (`tools/bench/pcs.hpp`) and the machine code explain a slow kernel before any variant
   is written; one hypothesis, one test.
4. **Six cards, six experiments.** One-card benches run on different cards at the same time (each A/B on its own
   card, so card-to-card clock differences do not matter); six-card runs only for gates and budgets.
5. **Batch the gates.** Several bench-proven exact changes go into one build and one gate campaign; short notes per
   lever, one full note section per batch.
6. **Read before inventing.** Other projects (llama.cpp SYCL / Vulkan, OpenVINO, IPEX-LLM, vLLM / SGLang custom
   all-reduce, Mirage / Hazy megakernels, DeepSeek's kernels) and our own older engines (the Qwen own runtime, the
   FP8 lanes) are searched for faster forms first.
7. **Value check.** Before a lever: the most it can win (its share of the budget) x the odds / hours. Under ~2 %:
   at most 30 minutes.
8. **Helpers.** Reading, surveys, tool building and bench scaffolding go to helper agents; decisions, GPU runs and
   engine edits stay in the main thread.
9. **Syntax check before every full build** (`icpx -fsycl -fsyntax-only ... own_run_v41.cpp`, 16 s on this host): a
   full build takes ~8 minutes and its gate waits for it (tp88's first build failed after 8 s on a misplaced helper,
   found only because its log was read at once).
10. **Card sharing** (`/home/steve/dsv41-work/card-share-README.txt`): six-card gates create `six.active` and wait for
   the helpers' `locks/`; helpers run one-card benches (each on its own card) only between gates.

## Ideas (ranked by expected size; status in the scoreboard)

Structural (decode):
- S1. (CLOSED for the dense chain by pc1, see the scoreboard; may still matter for chains of tiny serial steps.)
  **Persistent layer kernels ("megakernel")**: one long-running kernel per layer phase (or per word) instead of
  ~26 launches per layer; each work-group loads its weight rows **before** waiting on the flag for its input, so
  weight reading overlaps the previous step's tail and the exchanges. Same arithmetic per output. First a one-card
  bench of one layer's dense chain: separate launches vs one persistent kernel with weights-first loads.
- S2. **Exchanges**: fewer per layer (merge, or compute redundantly where cheaper), overlapped with independent
  work, and cheaper inside a persistent kernel (no launch, flag wait overlapped with weight loads).
- S3. **Launch overhead without fusion**: recorded command lists / SYCL graph replay of a whole word; measure the
  real (unprofiled) launch tax first.
- S4. **Card balance**: who arrives last at each exchange; even the slow card (0000:e3 clocks lower, §26).

Guessing:
- G1. Cheaper checks (a block of 4 costs ~1.8x a one-token step, §21-24): with S1 the extra tokens of a check cost
  little more than their weight reads.
- G2. Better guesses: more tokens per round, tree guesses, acceptance by prompt class.
- G3. **The draft's own cost (2.2 ms = 11 % of a round)**: launches, exchanges and the vocab head per draft token;
  draft-only shortcuts are allowed because they change guesses, never answers (e.g. a smaller candidate vocabulary
  for the draft's head). Helper (draft, `/home/steve/dsv41-work/draft/`), 2026-11-11.
- G4. **Guess-count rule under cheaper checks**: model tok/s from the per-round logs (confidences of all 5
  positions are logged) for today's and for cheaper check costs; TAU and a per-size rule (draft helper).

Host and step structure (from tl85, 2026-11-11):
- H1. **Engram rows off the critical path**: the card waits 2 x ~40 us per step for the host's engram rows (warm
  page cache; real answers read them from disk: p85 cold vs p84 warm 86.5 vs 87.5 tok/s). Host only bench
  (`tools/bench/engram_rows_host_bench.cpp`, `round19-engb1-engram-rows-host.txt`): 48 rows per step take 57-90 us
  warm (pread one thread 57, mmap six threads 87 median), 6.5-8 ms cold when read one by one (the engine's
  madvise prefetch at step start runs them in parallel). Fix: layer 1's 24 rows first (only they are needed after
  layer 0; layer 14's have ~3 ms of slack), read once for all cards by one thread started as soon as the token is
  known; expect ~0.08 ms per step warm, more cold.
  Constraint (lane note, e72-e73): no pinned host buffers (`malloc_host`) for the rows: the one run with them
  faulted (suspend fence, GT reset), and the host's memory compaction moves 5,000-260,000 pages per run, which forces
  the driver to remap pinned pages while our spinning jobs cannot pause. Today each of the six card threads reads the
  same 48 rows itself ("engram rows 236-314 us per step and card" on the host), then makes two small copies (one per
  engram layer). Safe forms: one reader for all cards, one copy of both layers' rows (48 x 176 B) instead of two, or
  the rows passed by value in a few launches' arguments (~2 KB each) so no copy runs at all. Worth ~0.7-1 %.
- H2. **Attention head imbalance** (8 groups of 8 heads on 6 cards: 16, 16 on cards 2 / 5): the other four cards
  wait ~14 us per layer in the output-a exchange (0.56 ms per step, tl85). The 12/12/12/12/8/8 split was measured
  before (e79): one-token steps lose (pair exchanges); stays closed unless a pair exchange gets cheap. Faster
  per-head attention shrinks the gap a little.
- H3. (CLOSED by arithmetic, 2026-11-11 ~04:45) **Balance without splitting heads**: the replicated q_a + kv rows
  (X ~17.5 us per layer) split over the cards with one extra pull (E ~11 us) before their norms. The light cards
  have only ~13.8 us of slack per layer, so they would become the slow ones; the best split (16-head cards 31 %,
  8-head cards 10 % each of X) leaves the critical cards S - X + 0.31 X + E = S - 1.1 us per layer: ~0.04 ms per
  step. The extra exchange eats the gain. For prompt blocks (plan item D) X grows with the block and E barely,
  so it stays a prompt-only item.
- H4. **Cache prefetch during exchanges (`OWN_XL2`, in tp89)**: a 32-group prefetch kernel on the second queue,
  released by the exchange's producer, pulls the next matrix (output-b, router + shared, shared down, next q_a + kv)
  into the 24 MiB cache while the card waits. One compute engine: it overlaps only if queued with (not after) the
  exchange and at the same register mode (128; xov grf bench); a cache-hot 5.6 MB GEMV is 9.8 us against 12.9.
- H5. **The check path's fixed cost**: a check of one token costs 12.8 ms against a 10.9 ms plain step (tg88). Helper
  (ckpath) comparing the two paths at M = 1; fixes as opt-in switches (`ckpath-1.patch`, in tp90: `OWN_CK1`,
  `OWN_RING_ONE`, `OWN_DR_NOWAIT`, `OWN_MT_KVPAIR`, `OWN_MT_FIN_QB`, `OWN_MT_RIDE_MIN`, `OWN_MT_EU_MIN`).
- H7. **The head split for checks, again** (2026-11-11 ~07:10, tg90 check timeline): the 16-head cards' non-exchange
  work exceeds the 8-head cards' by ~0.6 ms at one token and ~0.33 ms per extra token (M = 5: 18.3-18.8 ms against
  16.5-16.9); the light cards wait it out in the exchanges. The split (OWN_TP_HEADS 3,3,3,3,2,2 with pair exchanges,
  today only for blocks of >= 16 tokens) lost for checks in §28, when the rest of a check cost more. Re-test from 2 / 3
  / 4 tokens and for the draft (tune91, runtime switches only).
- H6. **Host hand-off**: ~0.25-0.35 ms of each step's gaps are thread hand-offs on the host (ckpath helper);
  `OWN_TP_SPIN_US=300` (the threads poll before sleeping) is an arm in tg90.
- H8. **q_b offload: the light cards compute part of the heavy cards' q_b rows first and push them one way**
  (idea, 2026-11-11 ~10:10, after xw92): the four 8-head cards wait ~22 us per layer at output-a (856-916 us per
  step) while cards 2 / 5 run twice the q_b rows (8,192 x 1,280 Q8_0: 23.4 us against ~12.5) and twice the
  output-a rows (18.1 us against ~9.5). q_b's input (the normed q_a output) is replicated and bit-identical on every
  card, so a light neighbour can compute 4 of the heavy card's heads (2,048 rows, ~6 us) before its own q_b and push
  them into the heavy card's q (one way, no wait on its side); the heavy card runs q_b for 8 heads with the same
  riders and waits on the flags only before its attention reads q. Unlike H2 / H7 (head split: the pair exchange
  sits between attention and output-a) and H3 (needs an extra pull), the push overlaps the heavy card's own q_b
  (~12.5 us against ~6 + ~5.5 for rows + push). Mapping: card 2 keeps heads 16-23, cards 1 / 3 compute 24-27 /
  28-31; card 5 keeps 48-55, cards 4 / 0 compute 56-59 / 60-63. Expected: heavy card -11 us per layer, light +7.5 us
  (of ~20 us slack): ~0.4 ms per one-token step (~4 %), more in checks; the draft's stages have the same imbalance
  (q_b 52 vs 28 us, o_a 28 vs 16 per stage). Same bits: each row's chain is the same kernel form on any card. Helper
  (qboff), 2026-11-11: `qb-off-1.patch`, `OWN_QB_OFF` (heads per helper, 0 = off). **Done (patch, not run;
  `/home/steve/dsv41-work/qboff/`)**: the all-card profiles (round19-b1-profiles) correct the gap: the heavy q_b is
  23.4 / 21.7 us (Q8_0 / Q6_K) against 15.4-15.8 / 14.7-15.1 on the light cards (~7.6 us of the launch is fixed),
  so q_b is ~7.6 us per layer of the gap and o_a ~7.7 (o_a cannot move: its input exists only on the heavy card).
  The heavy card keeps its middle 16 - 2k heads (k = 4: card 2 keeps 20-27, cards 1 / 3 compute 16-19 / 28-31;
  card 5 keeps 52-59, cards 4 / 0 compute 48-51 / 60-63; cards 1 / 4 already hold those rows, cards 3 / 0 get
  ~103 MB more), the helpers rope with the same kernel and push one way into the heavy card's q (moved into the
  arena), the heavy card waits inside its existing rope launch (phase 0, before every attention form). Expected
  k = 4 ~0.30 ms per step (2.5-3 %), k = 3 ~0.23, k = 2 ~0.15, if the pushes land by the time the heavy card ends
  its own rows (~15 us); the light cards keep only ~2 us slack at k = 4. One-token steps only; checks and draft
  next if it pays. In tp95 / tg95.

Kernels (only where the budget says a kernel is far from its floor):
- K1. One reusable proven-exact "fast serial sum" helper (bracket + fallback) for every remaining serial double
  chain (mix finish, compressor pool, ...). Done so far: norms (§32), engram gate (eg1-eg2 below).
- K2. Expert kernels: decode instructions per weight (IQ2 / IQ1 / IQ3 grids); compare llama.cpp / OpenVINO forms.

Prompt reading:
- P1. Blocks larger than 16 tokens (weights read once per block), per-shape kernel forms from the predictor.
- P2. Instructions per weight-token (d2-d4 in §31): fewer converts / moves per weight.
- P3. Prompt attention and the index work at long context (§29-31).
- P4. **Dense rows decoded once per token group (`ws.patch`, `OWN_MT_WS=1`, in tp90)**: one-card bench on card 2,
  1,560 bitwise checks identical; dense launch time per block -23 % at 16 tokens, -36 % at 64, -42 % at 256; checks
  of 2-6 tokens -0.64 / -1.09 / -0.76 / -1.58 / -1.27 ms. Expected 3K read ~345 -> ~400 tok/s at 64.
- P5. **Expert kernels at 256-token blocks (`routed-r4.patch`, in tp90)**: the old 16-slot kernels ran at 256
  registers; gate+up -39-44 %, ~1 s off the 3K read at 256.
- P6. **Prompt plan items C and D** (mix dot rows split across the cards, partials riding existing pulls; the
  replicated q_a + kv / router / compressor / indexer rows split for blocks >= 64): helper (pcd), 2026-11-11.
- P7. **Prompt plan item E (exchanges on a second queue, two half-blocks in flight)**: the six-card pre-check
  passed (`runs/xov1`, 2026-11-11 05:09): 0 wrong values in 400 iterations of every shape, a stuck card reported on
  5 of 5 peers; hidden fraction 74-95 % with 16 pull groups when the pull and the compute use the same register mode
  (128 + 128 or 256 + 256), ~0 % with mixed modes; the 128-token act shape only 27-43 %. Worth +5-10 % at a large
  change; after C / D, which rework the same exchanges.
- K4. **Norms folded into their consumer** (idea, 2026-11-11): one-token steps run 77 `SkNormDotsW<8u>` launches
  at 6.9 us (0.53 ms per step, tg89 profile, card 2), each a dependent step between an exchange and a matrix.
  Each work-group of the consuming matrix launch could compute the norm's scale itself (the same bracket code
  and order, a 20 KB read from the cache) and form x * r * g on the fly with the norm kernel's exact rounding;
  the other consumers of the normalized vector (the riding mix dots) need care. Earlier "fused HcPreNorm" was
  slower (a different fusion). Worth up to ~0.25-0.3 ms per step if a launch costs ~4 us more than the work.
- K5. **The extra token of a check costs 2.8 ms (tg89 check timeline, card 2, `round19-tg89/ck-by-m-card2.txt`,
  `tools/perf/dsv41_ck_by_m.py`)**: experts 1.16 ms, dense rows ~1.1-1.25 ms (an FMA floor is ~0.1 ms: token groups
  of 1-3 re-read and re-decode the weights), exchanges ~0.35 ms, the rest ~0.1 ms. For 200 tok/s the extra token
  must cost ~1 ms (draft helper's model). Dense rows at M = 2..6: ws helper, 2026-11-11. tp90 (tg90, checks of
  M >= 2 only, `round19-tg90/ck-by-m-card2.txt`): 2.5 ms per extra token = experts 0.92, dense rows ~1.1, pull
  exchanges 0.71 (far above their bytes: ~5 KB per token and exchange; mostly waiting for peers), the rest ~0.2.
- K6. **Block-step norms in the one-token fast forms** (tg91 check timeline, card 2, 2026-11-11): in checks of
  2-5 tokens `RowsP<TokRows<NormRows<5120u, 4u>>>` runs ~60 launches at ~7.5 us, flat in the token count (0.6 ms
  per check, latency-bound), and the q_a / kv norm pair ~29 at ~4.1 us; the one-token path does norm + 25 dot rows
  in 6.4-6.6 us (`SkNormDotsW`) and the pair in 2.7 us (`SkNormPairW`). Per-token block forms of those (one
  work-group per token, the same code), fused with `SkDotsWM` where adjacent: ~0.3-0.4 ms off every check
  (+1.5-2 % guessing). Helper (skn), 2026-11-11: **`skn-1.patch` done** (`/home/steve/dsv41-work/skn/`, bench
  `tools/bench/bench_skn.cpp`): `OWN_MT_SKNORM` bits 1 (`SkNormWM`), 2 (`SkNormDotsWM`, the pre-norm fused with its
  SkDotsWM rows), 4 (`SkNormPairWM`), 8 (`SkCompressPoolWM`), `OWN_MT_HCPP=1` (`HcPostPrePM` without the emulated 64-bit
  division). One card, us per launch: norm 2-6 tokens 5.6-7.0 -> 2.7-3.2; norm + dots 10.0 -> 4.6; q_a + kv 2.8 ->
  2.0; compressor pools 31.5 -> 2.1; HcPostPrePM 1.35-1.9 -> 1.0-1.25 (64 tokens 8.4 -> 4.6). 7,988 comparisons over
  1-256 tokens incl. 11,323 forced-fallback vectors: 0 differ. Expected ~0.5-0.6 ms per check, ~1.2 ms per 64-token
  prompt block. In tp93 (opt-in), gate tg93.
- K7. **Stream-mix dot partials computed by each card over its own output slice and carried by the exchange that
  already gathers that output** (idea, 2026-11-11): every card reads the whole `hc_*_fn` (F32 20480 x 24, 2 per
  layer, 152 MB per card per step, 0.28 ms at the floor; `SkNormDotsW` 0.53 ms per step on card 2). Before the
  output-b / down exchange a card holds the new output for its own 848-864 dims and the old streams in full, so
  it can form its slice of the new streams and the 25 dot partials (and the norm's sum of squares) over those
  columns, and ride them in the same pull as a second region (pcd-1's `XchgPull2` pattern). The finish already
  accepts other partials with the same bits (bracket + fallback; the fallback has the full streams after the
  exchange). SkDotsFF's proof already covers any split of the sum: each card sends (T_c, E_c) from the same
  float-float blocks, the receiver adds six doubles (a few more roundings in the bound) and runs the same check;
  failing rows (~1 %) recompute production's partials from the gathered streams. The 5,120 norm stays after the
  exchange (its input needs the finish), so `SkNormDotsW` 6.6 us becomes a norm alone (~3.5 us) plus a ~1 us
  partial step before the exchange: ~0.15-0.3 ms per plain step (1.5-3 %), more in checks of 2-6 tokens (the
  token split leaves cards idle there, the column split does not). Queued after K6 and the dense / attention work.
- Closed 2026-11-11 ~10:34 by arithmetic: **tree guesses** (check a second draft candidate at the least certain
  position, tree attention mask). Every extra token in a check costs ~2 ms here (14 % of an analysis round: its
  experts are new bytes), and a second candidate rescues only the misses at that position (analysis: 13 of 40
  one-guess rounds miss the first guess; at a typical ~30 % top-2 hit rate that is +0.1 token per round for +2 ms).
  Trees pay where an extra check token is nearly free; revisit only if the extra token falls under ~0.5 ms.
- Closed 2026-11-11: storing `hc_*_fn` in 16 bits. Unlike the router (`ffn_gate_inp`, 100 % exact in bf16, already
  stored as upper halves), `hc_attn_fn` / `hc_ffn_fn` are true F32 (4-15 of 491,520 values per tensor exact in
  bf16, layers 0 / 1 / 20 checked). The norm weights are bf16-exact but tiny.
- K3. **Sparse attention near its floor** (predictor: ~0.67 ms per step above, only 16-24 sub-groups busy): loads
  issued ahead of the fixed-order adds, shared loads across columns / heads; helper (attn), 2026-11-11.

## Path to 200 tok/s: the budget after tp88 (2026-11-11 ~03:50 EST)

Card 2's one-token launches (g82 profile against the machine-code predictor's floors, `/home/steve/dsv41-work/perf/
table.csv`): 9.29 ms of launches per step, 3.53 ms of it above the floors. Plus the exchanges (~1.88 ms, tl85) and
the in-step idle time (0.47 ms, tg87). What each lever is worth per step, from measured benches (not guesses):

| Lever | Above floor (per step) | Measured so far | Expected saving |
|---|---|---|---|
| Routed experts, fewer integer instructions per weight (routed helper, `routed-r2.patch` + `routed-r3.patch`, card 3 bench in the gate configuration: the stream mix's finish row rides in the gate+up launch; random rows at 6 / 12 slots, 16 / 256-token slot-major blocks, real rows, the finish row's outputs: all bit for bit) | 1.93 ms | gate+up IQ2_S 40.0 -> 27.6 us, IQ1_S 47.5 -> 27.4, IQ2_XXS 28.9 -> 24.0, IQ2_XS 44.4 -> 29.9, IQ3_XXS 44.0 -> 39.8; downs IQ2_S 21.9 -> 17.2, IQ3_XXS 22.8 -> 18.7, IQ2_XS 19.6 -> 15.1, IQ2_XXS 15.3 -> 12.6. r2 alone lost most of its gain with the finish row (it fell back to slow forms: IQ2_S 33.1); r3 runs the extra rows outside the row loop | ~0.8-1.0 ms; **tg89: plain 92.0 / 92.1 -> 95.4 / 97.5 tok/s (default since tp89); the checks did not gain (they run the expert-major `RoutedU` kernels; port = `routed-r4.patch`)** |
| Small serial kernels by proven brackets (smallk helper, `smallk-1.patch`) | norms + mix dots 0.40 ms, engram gate | **tg89: 95.4 / 97.5 -> 99.6 / 99.7 tok/s on top of r3 (`OWN_SMALLK=1 OWN_SMALLK_DOTS=8`, default since tp90)** | ~0.21 ms (measured ~0.25-0.4) |
| Idle copies off the card's queue (`OWN_ENG_CQ`, `OWN_PRE_K`, tg88) | 0.47 ms idle | engram rows 242 -> 75-80 us per step and card (trace mode) | ~0.2 ms |
| Attention score + softmax per size (tp87) | 0.47 ms | done | 0.29 ms at short context |
| Attention output `SparseOutJC` | 0.18 ms | one column per lane already; the slot sum is a fixed serial chain | small |
| Exchanges (160 per step) | ~1.9 ms | the fabric sets ~2.4 us one way (L1) | only by merging or hiding them |

Plain step today 10.99 ms (91.0 tok/s); the first three levers -> ~9.6 ms (~104 tok/s). Guessing then gains on
top: the check (2.47 tokens) costs 1.48x a one-token step, and the dense decode-once rows (`ws.patch`) take
0.73-1.61 ms off each check. 200 tok/s at ~2.6-2.8 tokens per cycle needs a ~13-14 ms cycle: a ~9 ms step, a
check at ~1.3x and a draft under ~1.5 ms; or more tokens per cycle (copied guesses, `OWN_SPEC_NGRAM`, on
repetitive text). After tp89 the next structural item is the exchanges.

After tg89 (2026-11-11 05:04, tp89 with smallk): plain step ~10.0 ms (99.6 tok/s), one-token timeline busy 9.0 ms
(was 10.44 in tg88). The guessing rounds did not move (code 118.5 -> 118.6 tok/s, analysis 130.6 -> 131.5, 3K
117.8 -> 121.8; `round19-tg89/check-cost-by-guesses.txt`): a zero-guess check still costs 12.4 ms + the 2.2 ms
draft, so **the check path's fixed cost grew to ~2.4 ms against the faster plain step**. Next, in this order:
`ckpath-1.patch` (`OWN_CK1`: a zero-guess round runs the plain step + the draft's own rows; plus 6 launch-merging
switches for small checks), `routed-r4.patch` (r3's instruction cuts in `RoutedU`), then `ws.patch` (dense rows
decoded once per block) for both checks and prompt blocks.

What a guessing round costs by its size (tg88 per-round logs, `round19-tg88/check-cost-by-guesses.txt`, code prompt;
the analysis and 3K prompts within ~1 ms): check of 1 token 12.8 ms, 2 15.8, 3 18.4, 4 20.7, 5 24.4, 6 26.5; the
draft 2.2 ms every round. Two things follow. (1) **Checking one token costs 12.8 ms on the block path against a
10.9 ms plain step**: ~1.8 ms of fixed overhead in every check (28 % of the code prompt's rounds guess nothing at
all and pay 15 ms for one token). (2) **Each extra token costs ~2.7 ms** (25 % of a step): dense rows, experts,
exchanges and attention all grow by about a third per token (tg87 kbusy). The 5-guess rounds keep 3.5-4.0 and run
at 155-174 tok/s; a round that always guesses 5 at today's keep rate would give ~3.3 tokens in ~28.7 ms = 115
tok/s, so more guesses need a flatter check (decode-once dense rows, cheaper experts) before they pay.

### The budget after tp90 (tg90, 2026-11-11 06:37)

Plain step ~10.0 ms (99 tok/s). Guessing round = draft 2.1 ms + check. Check by guesses (code, median ms; all
tg90 winners on): 0: 10.43 (the plain step's path), 1: 14.43, 2: 16.78, 3: 19.14, 4: 22.58, 5: 25.03. Two costs
decide the next 50 %: (1) the block path's fixed cost from 2 tokens on, ~1.4-2 ms (check of 2 tokens ~13.9 ms of
card time against 10.0 for one); (2) each further token ~2.4-2.5 ms on the critical card = experts 0.92, dense
rows ~1.1, pull exchanges 0.71, the rest ~0.2 (`round19-tg90/ck-by-m-card2.txt`, checks of 2-5 tokens). The draft
helper's model (`/home/steve/dsv41-work/draft/policy_model.out`): 1 ms off the empty check or off the draft = +6
tok/s; 1 ms off each extra token = +11-20 tok/s once TAU is re-tuned; 200 tok/s needs ~1 ms per extra token and
a draft under ~1 ms. Targets in flight: dense rows at 2-6 tokens (ws helper: floor ~0.1 ms per token), the
exchange growth (an OWN_XWAIT build of a check timeline would split waiting from moving; the bytes explain only
~0.15-0.2 ms per token), the draft (draft-head-1, ~0.5 ms), TAU 0.34-0.40 (+1-4 %).

### The one-token budget after tp101 (tg101 `tl_one_bg`, G128, 7 steps, 2026-11-11 22:50)

Device time per step, ms (launches per step); card 2 (16 heads, the critical card) against card 0 (8 heads). Busy
9.34 ms, span 9.50, gaps between launches 0.16; 932 launches per step on every card.

| Part | card 2 | card 0 | Floor / what bounds it |
|---|---|---|---|
| Dense rows (Q8 / Q6 / Q5 rows with riders, BF16 indexer + compressor rows) | 3.95 | 3.34 | bytes ~2.2-2.6 ms; launch ramps |
| Routed experts (2 launches per layer: gate + up, down; rows split over the six cards) | 1.90 | 1.88 | instructions (IQ grids): ~1.1 ms at the bench's instruction floor |
| Pull exchanges (83) | 1.10 (13.2 us each) | 1.60 | card 2 arrives last, so its 13 us is transport (several PCIe trips); the light cards wait |
| Push exchanges (80) | 0.59 (7.4 us each) | 0.59 | one-way ~2.4 us + launch |
| Norm + mix dots (`SkNormDotsW` 77 x 6.6 us, `SkNormPairW` 40) | 0.62 | 0.62 | well under 0.1 by bytes (K4: fold into the consumer) |
| Router rows (`RoutePRows` 40 x 10.7 us) | 0.43 | 0.44 | |
| Attention (`SparseOutF` 40 x 10.8 us) | 0.43 | 0.46 | latency-bound |
| Small launches (`HcPostPreP` 78, `MoeCombineA` 40, `SwigluBothS` 40, rope 40, ...) | ~0.35 | ~0.35 | 225 launches under 2 us take 0.27 ms in all |

Launch sizes on card 2: 225 under 2 us (0.27 ms), 54 at 2-4 (0.15), 183 at 4-8 (1.17), 256 at 8-16 (2.94), 209 at
16-32 (4.50), 4 longer (0.32). Read: there is no single big item left. 200 tok/s plain needs ~5 ms; with guessing
at ~1.4x a ~7 ms step plus a check slope near 1 ms per extra token. The step's remaining levers: dense rows over their
bytes (~1.4 ms on card 2, of which ~0.6 is the 16-head imbalance), experts over their instruction floor (~0.8 ms:
L1 / L2 in flight), the pulls' trip count (~0.5 ms: xll-1 was the one-trip form, parked by the host events), the
norm launches (~0.3 ms, K4), small-launch fusion (~0.2 ms), pushes folded into their producers (~0.2 ms).

### The prompt budget at blocks of 256 (tg103 `tlp_base`, blocks 3-4, timeline mode, 2026-11-12 00:45)

Card 2, ms per 256-token block (~430 ms in timeline mode; 13 blocks = the 5.7 s 3K read): routed experts 192 (45 %:
gate + up `RoutedUT` 133, down `RoutedU3` 53, Q2_K 6.5), dense rows 125 (29 %: `DenseRowsWSC` 113, router 12),
exchanges 74 (17 %: pulls 42 + 28, pair swaps 3.5), attention ~24 (6 %), the rest ~15. Against the exact-arithmetic
ceiling (separate multiply and add, `-ffp-contract=off`: ~5.7 T pairs/s per card measured): dense rows run ~3.2 T
pairs/s (~56 %), routed experts ~1.6 T (~28 %; ~4 tokens per expert at 256, the kernels scale with tokens, so bigger
blocks do not amortize much). Levers: hide the exchanges (17 %, the overlap work), the prompt expert kernels (rux-2),
then the dense rows.

## Scoreboard: strategies that worked, and ones that did not

Worked (all bit-identical):
| Strategy | Example | Gain |
|---|---|---|
| Replace serial loops by a proven bracket with a fallback | norm sums 14.9 -> 8.2 us (§32); engram gate 96 -> 8.7 us (eg2), 116 -> 12 us in the engine (§33) | +2.9 % (norm), ~+1 % (engram) |
| Spread serial work over more cores | norm launches 16 -> 4 rows per group (§32) | +1.7 % |
| Fewer comparisons, no branches in selection | router pick 21.4 -> 9.2 (§32) -> 2.7 us (rp3, branch-free, fixed candidate count); router launch 12.8 -> 10.9 us in the engine (§33) | +3.3 % (§32), ~+1 % (§33) |
| Stall sampler before variants | pcs1 (2026-11-11): production IQ2_XXS experts busy 48 % + ALU-pipe 22 % + send queue 17 % (issue-bound); the packed-lane form waits a third of its samples on block-start loads, which says exactly what to fix | saves the variant sweep |
| More sub-groups for serial per-head work; kernels built per size so they stay at 128 registers | one-token attention score `SparseScoreHG<512, 1>` + softmax `SparseSoftmaxP<n>` per slot count (ad4; tg86 2026-11-11, default since tp87) | prompt 1: 86.39 -> 88.11 tok/s mean of 2 (+2.0 %); 3K document 80.56 -> 81.98 (+1.8 %); traces identical, answers and guessing the same |
| Pin small hot kernels to 128 registers (check the register mode in the machine code first) | the pull exchange built at 256 registers paid ~1 us of register-mode change before and after each of its 83 launches per step; `XPullK128` (same code, `grf_size<128>`) removes it (tl85 -> tg87 timelines) | +3.1 % plain (88.2 -> 91.0 tok/s) |
| Read the draft side's code for leftovers when its output depends on something it should not | the draft picked its 3 experts from 384 router entries of which 256 were the target's leftovers (gm64's block-size dependence led to it) | guessing +6-10 % (code 105.9 -> 117.0, analysis 118.7 -> 130.0, with the exchange fix) |
| Fewer integer instructions per weight in the expert kernels, extra rows outside the row loop (routed r2 + r3, tg89) | gate+up 1.1-1.7x and downs 1.2-1.3x faster on one card, bit for bit; every engine trace identical | plain +3.7-5.8 % (92.0 -> 95.4-97.5 tok/s) |
| Proven brackets for the small serial kernels, one work-group forms (smallk-1, tg89) | norms, stream-mix dots, compressor, engram gate | plain +2-4 % on top (-> 99.6 tok/s) |
| Dense rows decoded once per token group in prompt blocks (`ws.patch`, `OWN_MT_WS=1`, tg90; picks per matrix and size from a one-card bench, never slower there) | 3K read at blocks of 64: 353.1 / 353.1 -> 416.0 / 415.9 tok/s; checks gain only ~0.1 ms (few check shapes won in the bench) | prompt +17.8 %; default since tp91 |
| r3's decode in the expert-major check / prompt kernels (`routed-r4.patch`, tg90) | guessing code 118.6 -> 123.4 tok/s, analysis 131.5 -> 136.3, 3K 121.8 -> 122.6; 3K read 339 -> 353 at 64 | +4 % guessing, +4 % prompt |
| A zero-guess check runs the plain one-token step (`OWN_CK1`, + `OWN_RING_ONE`, `OWN_DR_NOWAIT`, ckpath-1, tg90) | the 63 zero-guess code rounds: check 11.99 -> 10.43 ms (the plain step is ~10.0); all-empty rounds (TAU 1.01) 70.8 -> 80.3 tok/s | guessing +3.2 % code, +2.2 % analysis; default since tp91 |
| q_a + kv in one launch and the mix finish in q_b's launch for small blocks (`OWN_MT_KVPAIR`, `OWN_MT_FIN_QB`, tg90) | checks: code 127.42 -> 128.15 tok/s, analysis 139.34 -> 139.75; but the 3K read with ws 416 -> 390 at 64 | +0.5 % guessing; default since tp91 for blocks of <= 16 tokens only (`OWN_MT_MS_MAX`) |
| The prompt blocks' stream-mix dot rows split across the cards by tokens and gathered with the existing pulls, plus the one-token path's dot-row kernel for blocks (`OWN_MT_DSPLIT=1`, `OWN_MT_SKDOTS=8`, pcd-1 item C, tg91) | 3K read at blocks of 64: 416.3 -> 462.7 (DSPLIT) / 444.1 (SKDOTS) / 469.3 tok/s (both); in checks from 2 tokens on (`_MIN=2`): code 127.96 -> 128.81, analysis 138.74 -> 142.31 | prompt +12.7 %, guessing +0.7-2.6 %; default in tp92 |
| Attention heads split between card pairs in checks of >= 3 / 4 tokens (`OWN_TP_HEADS_MIN=3` / `4`, tune91; the prompt blocks' XchgPair split) | code 126.6 (mean of 2 default runs) -> 128.6 (hm3) / 128.1 (hm4, 2 runs), analysis 138.9 -> 140.7 / 140.5; checks of 4-6 tokens 0.2-0.4 ms shorter; 16 of 16 SAME, guess logs equal | +1.2 %; candidate default for tp93 (tg92 checks hm3 again) |
| The draft's matrices in the weight-stationary forms (`OWN_DR_WS=1`, draft-head-1, tg91) | draft 2.13 -> 1.96 ms per round; code 127.96 -> 128.41, analysis 138.74 -> 140.63 | +0.4-1.4 %; default in tp92 with `OWN_DR_ANCHOR_ARG=1` (the chain's anchor by value: 128.22 / 140.41) |
| A candidate vocabulary for the draft's head (`OWN_DR_VOCAB`, 49,897 ids + the prompt's, draft-head-1, tg91) | draft -> 1.83 ms (1.78 with DR_WS); code 128.95 (129.62 with all), analysis 141.97 (142.40), prose 107.77 -> 108.09; the guesses and answers stayed the same on all four prompts, but the trimmed head can in principle pick a different guess, so it stays opt-in (draft-only, answers always checked by the target) | +0.8-2.6 %; opt-in |
| Block-step norms in the one-token fast forms, one work-group per token (`OWN_MT_SKNORM=15`, `OWN_MT_HCPP=1`, skn-1, tg93) | checks: code 128.7-129.3 -> 132.6-132.8 tok/s, analysis 142.3-142.6 -> 147.1-147.2, 3K 127.6 -> 136.0; check 15.8 -> 15.3 ms (code) | +3.3 % guessing (+6.5 % on 3K); default from tp94 |
| The mix split + SKDOTS only from 4 tokens (`OWN_MT_DSPLIT_MIN=4`, `OWN_MT_SKDOTS_MIN=4`, tune92) | 2-token checks 15.08 -> 14.58 ms; code 129.06 -> 130.24, analysis 142.70 -> 143.59 | +0.6-0.9 %; default from tp94 |
| Attention scores and softmax in one launch with an uncached hand-over between work-groups (`OWN_ATT_T=1`, attn-a2, tg96b) | plain 99.5 / 97.9 -> 101.2 / 101.4 tok/s; writing after a 3K prompt 87.5 / 90.5 -> 92.9 / 93.0; checks -0.15 to -0.3 ms. a1 (cached hand-over) was not bitwise: L1 is not coherent across work-groups of one launch | +2-3 % plain, +3-6 % after long prompts; default in tp97 |
| Check forms that keep the riders' fast paths at 2-6 tokens (`OWN_MT_CK=1`, ck-2, tg96b): q_b WS_DOTS picks under the mix finish, the ExpertGroupM / push launches folded | 2-token check 14.07 -> 13.37 ms (13.05 with ATT); code 133.0 / 133.4 -> 137.5 / 137.5, analysis 146.9 / 148.0 -> 152.1 / 152.5; with ATT: 139.2 / 139.3 and 153.8 / 153.6, prose 111.8 -> 117.3, after 3K 131.2 -> 142.2 | +3.4 % alone, +4.2-8.4 % with ATT; default in tp97 (all sizes; skipping 3-token checks is slower) |
| Fewer instructions per weight in the prompt expert kernels (`OWN_MT_RUX=1 OWN_MT_RUX_CAP=6`, rux-1, tg96b; launches of >= 16 tokens) | 3K read 7.09 s -> 6.73 s (472 -> 497 tok/s); blocks of 128 / 256 add 0.1 / 0.4 % | +5.3 % prompt; default in tp97 |
| Small host copies off the card's queue (a second in-order queue per card, the launch waits by event) | `OWN_ENG_CQ` + `OWN_PRE_K` (tg88): engram rows 242 -> 70-80 us of host time per step; one-token timeline span 11.01 -> 10.75 ms, in-step idle 0.47 -> 0.30 ms | plain +0.3-0.5 % (91.77 -> 92.27 tok/s); default since tp89 |
| The split mix finishes ride output-b's and shared down's launches in checks of 4-6 tokens, keeping their weight-stationary forms (`OWN_MT_DRIDE`, dride-1, tg98b) | checks of 4 / 5 / 6 tokens 17.88 / 20.47 / 22.71 -> 17.17 / 19.63 / 21.97 ms (code); code 138.7 / 139.4 -> 140.7 / 140.8 tok/s, analysis 152.7 / 153.8 -> 156.0 / 155.9, after 3K 136.7 -> 143.4 | +1.2-1.8 %, +4.9 % after a 3K prompt; default in tp99 |
| Prompt blocks of 256 done right, kernel by kernel (pb-1, `OWN_PB=1`, tg100; default since tp102): 16-bit rows in weight-reusing forms, expert grouping by a counting sort, 6-bit forms without the private scale array, per-role form + token chunk at 65-256 tokens, every pick bench-checked bit for bit | 3K read 6.65 -> 5.68 s at blocks of 256 (6.73 at 64 before); router 450 -> 111 us, grouping 297 -> 30 us at 256 | **-15.6 % prompt time** |
| One-wave launches for the 16-head cards' q_b / output-a rows in checks, the next weight segment loaded while the current one multiplies (pace-1, `OWN_MT_PACE=1`, tg102) | checks of 4 / 5 / 6 tokens -0.27 / -0.58 / -0.48 ms (code) | guessing +1.2-1.4 %, +4.7 % after a 3K prompt |
| Window append per shape in checks (wa-2, `OWN_ATT_WA=2`, tg100; default since tp102) | checks of 2-6 tokens 0.15-0.37 ms cheaper (code) | +0.5 % short prompts, +4.1 % after a 3K prompt |
| Copy the routed kernels' grid tables from a constant image instead of computing them per work-group (xperm-2, `-DOWN_R2_TAB_COPY=1`, tg101) + IQ2_S gate+up at 128 registers (`OWN_PAIR_G128=1`) | IQ1_S gate+up 27.3 -> 23.5 us | plain 101.5 -> 103.9 tok/s (+2.4 %); G128 pays only with the copy |
| Riders: independent small work inside a big launch | mix dots in the norm launch, shared rows with the router (§14-18) | several % |
| Packed weight rows for sub-group block loads | §p7-p10 era, 9 -> 28 tok/s | large |
| Pull exchanges for big slices, push for tiny ones | prompt 91 -> 179 tok/s (§21) | large |
| Keep idle cards warm | 5.3 -> 9.1 tok/s (early) | large |
| Ahead-of-time build + large register mode | first run 6 min -> 30 s; fewer spills (§23, §26) | small |

Did not work (and why):
| Strategy | Why |
|---|---|
| S1 as stated: one persistent kernel for the dense weight chain (pc1, 2026-11-11, `tools/bench/bench_persist_chain.cpp`) | separate launches already run a 16-layer x 6-stage Q8_0 chain (35.3 MB per layer, 12-head card shapes) at 74.1 us per layer = 475 GB/s, 79 % of the 603 GB/s measured read floor; persistent forms with 16 / 32 / 64 work-groups of 512 were 166 / 108 / 95 us per layer (too few loads in flight), reading the next rows early made it worse (154-371 us), 128 work-groups are not all resident (waits gave up safely). Launch gaps between dependent GEMVs are ~1 us on B70, not the problem. The engine's same matrices cost ~130 us per layer (card 2 profile: q_a + q_b + o_a + o_b + shared + router groups): the extra is in riders, small steps and launch structure inside those groups, not in launching. |
| S3 / PDL emulation: launches on an out-of-order queue with no barriers, each kernel loading its weights then spinning on a counter (pc2, `bench_persist_chain` forms Q / Qi, 2026-11-11) | 215 / 184 us per layer against 74 for plain launches: one counter per stage, incremented by every sub-group, serializes the atomics; and there is little to win: `bench_launch_gap` (lg1) shows back-to-back dependent 6 us launches leave 0.12-0.28 us between them (an empty kernel costs ~1.6 us per launch). Launch gaps between big kernels are not where the 1.1 ms of idle time is. |
| K2 as packed logical lanes for IQ2_XXS (`RoutedIQ2XXSK<NB, P, STAB, PF, XB>`, kb1-kb3 + pcs1/pcs1b, 2026-11-11) | every form bitwise PASS (18,432 gate+up and 20,736 down outputs), every form slower: gate+up production 33.4 us, P = 4 35.5, P = 8 58, P = 2 42-50; loading the next block early (PF) 40.5 / 68, the block's x up front (XB) 42.3, sign masks from a table (STAB) 41.8-49.3. The machine code has ~14-30 % fewer instructions per weight, but an item needs P x values per group that the one-weight form gets from one shared block read, so it either waits on per-lane x loads (sampler: a third of samples SbidStall on the multiply that consumes x) or holds them in registers and falls to the 256-register mode with half the threads. Production is issue-bound (busy 48 %, ALU pipe 22 %, send queue 17 %); the 3 float ops per weight are fixed by the order. Revisit only with x permuted by its producer so a block read hands each item its own P values. |
| L1 transport: one shared native Level Zero context over the six cards (SC117's setup) for direct peer stores (`tools/bench/probe_shared_ctx_ram.cpp`, `tools/bench/xchg_direct_bench.cpp`, `data/.../round19-l1-transport/`, 2026-11-11) | safe but no faster. Host RAM: 6.02 GiB on six cards in one shared context moved MemAvailable by 0.05 GiB (also with peer residency, and with the default backing; peer copies correct), so the 1:1 host-RAM cost of §1 is the SYCL multi-card context, not Level Zero. Speed: the shared context and today's IPC peers give the same times to 0.1 us (pair one-way 0 B 2.36 vs 2.42 us, 3,456 B 5.20 vs 5.21, 9,728 B 6.38 vs 6.36). The fabric sets the cost: a flag one way ~2.4 us, a 3.4-9.7 KB push one way 5.5-5.7 us with 4+ work-groups; a six-card all-gather by push 10.5-14 us at 3.5-9.7 KB per card (noisy), against 11.89-13.53 us for the engine's own XchgPull of the one-token h exchange (e81b) and 12.2 us in the step ledger; all-to-all pushes of 64 KB collapse to ~9 GB/s total (208 us) while pulls keep 73 GB/s. The engine already pushes the tiny exchanges. What is left for exchanges: fewer of them (merge) or hide them behind weight reads. |
| XPF: pull exchanges' spare work-groups prefetch the next matrix's first 4 MB into the cache while they wait (`OWN_XPF` 1 / 2 / 3, tg86b 2026-11-11; removed from the engine) | slower in every form: prompt 1, 128 answers, two alternated rounds: default 85.95 / 86.83 tok/s, XPF 1 85.77 / 86.17, XPF 2 85.23 / 85.24, XPF 3 85.30 / 85.06; with the attention change 87.55 / 87.31 against the attention change alone 88.88 / 87.33. The exchange ends only when its prefetch groups do, the same lesson as the L2 prefetch riders. |
| Guesses copied from earlier text when the last 3-4 tokens repeat (`OWN_SPEC_NGRAM`, tg88) | slower on every prompt: code 116.8 -> 106.5 / 107.1 tok/s, analysis 130.0 -> 110.9 / 119.5, 3K 118.1 -> 109.3. The copied runs are long (up to 8-16 tokens) and mostly wrong (15 of 127, 74 of 275 kept), and a check of 8 tokens costs 39.7 ms against 12.8 for one. Removed from the plan; the switch stays off. |
| Prompt blocks of 256 tokens (mtx256, tg88) | the 3K read: 338 tok/s at 64, 306 at 256, 328 at 256 with the old expert groups of 6; the dense rows still decode each weight per 16-token group, so a bigger block only adds work (activations, groups). Blocks stay 64 until the rows decode once per block (`ws.patch`). Traces identical at 256. |
| The faster one-token attention forms in big prompt blocks (`OWN_ATT_M`, tg88) | identical, but 301 against 306 tok/s at 256 (more sub-groups where there was already enough parallelism); since tp89 they apply only to blocks of up to 16 tokens (`OWN_ATT_M_MAX`): the guess checks |
| Expert-kernel forms that did not pay (routed helper, 2026-11-11) | per-lane gathers (address math and wait chains cost more than the decode they save); fused 16-lane multiply / half-precision mixed add (the compiler splits them into 2-3 instructions); an 8-bit table for IQ1_S (slower); fully unrolled row pairs at 20 blocks (spills); row pairs for IQ1_S (instruction-bound, not load-bound); one sign-word formula miscompiles on the card while the host check passes (shift-and-xor parity used instead). 96 work-groups lose with the finish row on (r3 IQ2_S 27.6 -> 32.4 us). |
| Cache prefetch of the next matrix during exchanges on the copy queue (`OWN_XL2=15`, H4, tg89) | plain 95.4 / 97.5 -> 82.7 / 82.8 tok/s. The engram copies waited behind the prefetch launches (80 -> 257 us), and the timeline shows a 11-15 us gap before every exchange (MoeCombineA -> XchgP 40 x 14.7 us, GemvQ8P -> XchgP/XchgPull 27 x 14-15 us): the prefetch submission sits between the producer and the exchange. Moved to its own queue (`pfq`, in the tree, untested); stays off unless a timeline shows no gap. |
| XL2 on its own queue (`pfq`, tg90) | still slower: 84.5 / 84.7 against 97.9 / 99.2 tok/s; removed from the plan |
| The host threads poll 300 us before sleeping (`OWN_TP_SPIN_US=300`, tg90) | neutral: 99.6 / 98.6 against 97.9 / 99.2 tok/s plain, 127.9 vs 128.2 guessing |
| The argmax readback on the copy queue (`OWN_HEAD_CQ=1`, tg90) | slower: 125.1 against 127.4 tok/s (code) |
| Old small forms for checks (`OWN_MT_RIDE_MIN=7`, `OWN_MT_EU_MIN=7`, tg90) | neutral to slower (code 127.1-128.0 vs 128.2, together 127.4) |
| 256-token prompt blocks after r4 + ws (tg90) | 396.6 vs 416.0 tok/s at 64; blocks stay at 64 |
| Pull exchanges with 96 work-groups (`OWN_PAIR_WG=96`, tg89) | neutral for plain (96.4 / 96.8 vs 95.4 / 97.5), slower for the 3K read at 256-token blocks (t3k: 294.9 vs 320.3 tok/s) |
| Lower guess-acceptance threshold (`OWN_SPEC_TAU` 0.34 / 0.40 against 0.5, tg91) | mixed: code 127.96 -> 131.77 / 131.08, analysis 138.74 -> 130.92 / 137.31 (more guesses tried, more thrown away; the check got 1-2 ms longer). TAU stays 0.5; revisit when each extra token is cheaper |
| The draft's rows at 5 work-groups per row (`OWN_DR_TGW=5`, tg91) | slower: code 127.28, analysis 139.06 |
| Attention heads split between card pairs from 2 tokens on (`OWN_TP_HEADS_MIN=2`, tune91) | neutral: the pair exchange costs about what it saves at 2 tokens (check of 1 guess 14.54-14.64 -> 14.74-14.78 ms); from 3 / 4 tokens on it wins +1.2 % (scoreboard) |
| q_b offload inside the checks' q_b launch with an in-launch cross-card wait (qb-off-2 tg97, qb-off-3 tg98) | both hung cards 2 and 5 at their first run (driver job timeouts 14:02 and 16:25; probes passed). qb-off-3 fixed the 256-lanes-per-flag polling and added a 1 s in-kernel timeout, which never reported, so the cause is elsewhere. Parked (~1-2 % on guessing); a retry needs a short six-card bench of the hand-over first, as xll-1 did |
| Head-balance weights for prompt blocks (`OWN_MT_DSPLIT_WA=0,0,0,0,1,1`, tg98b) | 3K read 6.77 / 6.85 s against 6.78 / 6.79: neutral |
| q_b offload: the light cards compute 2-4 of each 16-head card's query heads first and push them (`OWN_QB_OFF=k`, qb-off-1, H8, tg95b) | bitwise, no gain (plain within noise; zero-guess checks 10.54 -> 10.56 ms). Timelines (qboff/qbdiag.py, tg93 vs tg95b zero-guess checks): the heavy cards were last at output-a by 13.1 us per layer (89 %); k = 4 saved them 6.7 us (q_b 23.7 -> 15.8) but cost each light card 13.1 us (rows 7.9, rope 1.0, push 4.0, gaps 0.4), so the light cards became last; layer -1.75 us. A row moved out of a big launch saves ~1.9 ns, the same row in a small helper launch costs ~3.8 ns, plus ~5.3 us fixed per layer: best case ~1 % (k = 2 / 3). The whole output-a imbalance is ~13 us per layer (~0.5 ms per step). Closed. |
| K7: the stream mix's dot sums ride the exchanges (`OWN_K7`; k7-1 tg96, k7-2 tg97b) | k7-1 timed out in every run (sums sharing cache lines with lines the receiver wrote, read in the launch that waited). k7-2 (XchgP-style transport, read one launch later) is bitwise in every trace but plain 100.4 / 100.6 -> 98.3 / 99.2 tok/s and guessing neutral: the sender's +2.7 us per exchange lands on the critical path. In the tree, off |
| Looser guess threshold after the cheaper checks (`OWN_SPEC_TAU` 0.45 / 0.40, tg97b) | code 138.4-139.2 -> 141.7 / 140.5, analysis 150.5-153.0 -> 149.4 / 150.0: neutral on average; TAU stays 0.5 (a per-prompt-class rule might take the code gain) |
| Runtime switches on top of ck-2 (tg96b: `OWN_MT_XPUSH=0/2`, `OWN_XPULL_MIN=6912`, `OWN_MT_SKDOTS_MIN=2/3`, `OWN_MT_FIN_QB=0`) | within +-0.2 % of ck alone or slower (XPUSH=2 -3.9 %, FIN_QB=0 -0.9 %); the current values stay |
| eg-fold-1: the expert grouping (`ExpertGroupM`, its own launch in checks) folded into the gate + up launch (`OWN_MT_EGF`, `dsv41-work/egf/`, card 5 bench 13:34-13:35, bitwise) | slower: per check UF1 -0.35 / -0.68 / -0.92 / -1.08 / -1.59 ms and UF2 -0.03 / -0.04 / -0.01 / +0.01 / -0.25 ms at 2-6 tokens (IQ2_S and IQ1_S UF1 +14-65 us per layer; IQ2_XXS UF2 +1.7-9 us). Even free grouping would save only 0.11-0.30 ms per check. Closed |
| Exact restructured dequant for the routed experts ("T form": a table of signed magnitudes per 4-weight half group; xperm helper 2026-11-11 ~20:20, `dsv41-work/xperm/README.md` section 4) | the per-weight math d*s*g is exact in FP32 for IQ2_XXS / IQ2_XS / IQ2_S / IQ3_XXS / IQ1_S (every fp16 d, scale and grid value checked on the CPU; Q2_K is not exact), so any order gives the same bits, and the T form cuts the instructions per 64 weights 21-23 %. But on card 5 it is slower (IQ2_XXS 23.4 -> 28.7 us, IQ1_S 27.4 -> 31.1): the per-work-group table build and SLM bank conflicts; with both removed only 2 % faster. The integer ops are not the critical path of the expert kernels |
| Private arrays back in scratch for the decode image (gp-1, img7) and the pull image (gp-a, img4) (pb256 / attn helpers, 2026-11-11 ~20:10) | A/B builds: placement changes every kernel's code by 1-2 % with mixed sign; under 0.05 ms per step or check. The real trigger is zero-initialized local arrays (program-scope private globals) |
| Prefetching the routed experts' weight rows ahead of use (L1, `OWN_R2_PF`, xperm helper 2026-11-11 ~23:15, card 5; `dsv41-work/xperm/README-ledger.txt` sections 8-9) | bit-identical in every form, slower in every form and cache state: whole rows +5.9 to +9.5 us per one-token launch, first lines only +1.5 to +1.8 us, checks +1.4 to +13 us. Each prefetch message asks for 32 cache lines and costs the load pipeline about what the real loads do; the kernels have no idle memory time. The engine-over-bench gap (L2) is cold caches at kernel start (dependent table-fill reads), mostly removed by xperm-2; xperm-3 extends the copy to IQ2_XXS / IQ3_XXS (~13 us per step) |
| pace-2: one-wave forms for every card's q_a + kv, output-b, shared down, shared gate + up at 2-6 tokens (`OWN_MT_PACE_ROLES=127`, tg103) | card 3 bench 1.05-1.4x per launch, 720 compares 0 differ, predicted 0.12-0.56 ms per check; in the engine checks moved -0.3 to +0.2 ms and guessing did not change (code 143.6 vs 143.8, analysis 159.4 vs 160.0). Cause (attn helper, tg103 check timeline): pace-2's forms are 256-register kernels, and every 256-register launch among 128-register ones costs ~1.7 us of idle card time (two mode switches of ~0.84-0.94 us): +200 us per 2-token check on every card, eating the ~0.2 ms the kernels saved. Rule: count the mode switch in every bench pick; checks today already have 54-60 (2 tokens) to 140-163 (5 tokens) switches. Next: re-pick check forms with the switch counted |
| The overlap as built (px-1/1b, `OWN_PX=1`, tg103): two half-blocks, pulls on a second queue | exact, but 3K 5.68-5.71 s vs 5.71: it hides ~0.4 s (one-queue form 6.10) and the 128-token halves cost ~0.4 s; kernels beside a pull run 13-76 % slower. (The timeline's one-launch overlap was a profiling artefact.) Open: halves of 256 (`OWN_PX_BIG`), fewer pull groups |
| Routed expert kernels: pre-touching the table image / x / ids before the launch; x read once per row pair in checks (L3); one reduction per row pair (L4) (xperm helper, 2026-11-12 ~01:00, card 5; `dsv41-work/xperm/README-ledger.txt` sections 10-11) | pre-touch: the engine already has x and ids warm, the table image gains nothing, a touch kernel costs +0.2-0.3 ms per step. L3 +3 to +21 % slower at 2-6 tokens (most check rows have one slot). L4 exact only after shuffling the uint32 bits (IGC rewrote the float chain into a different reduction order), and then no faster. Found instead: the lane-sum butterfly written with `permute_group_by_xor` lowers to halving adds in the same order (exact; ~-70 us per step, ~-115 us per check) and no pair code below 16 tokens (~-20 us per check): patch next |
| Trusting one-card bench winners blindly | Q8_0 5120 / 4096-column forms lost inside the engine (riders, fewer rows, §31) |
| L2 prefetch riders | a launch ends only when its prefetch groups do (§15-18) |
| Fused softmax into the attention output | slower (§31 s6) |
| Row-block-free head | the 230 W cards drop clocks (§24-25) |
| Split checks / draft across card pairs | each pair exchange costs more than it saves (§28) |
| Trial-and-error variant sweeps | slow; the stall sampler or machine code answers in one run |

## Work in flight (2026-11-11, updated 2026-11-12 11:10 EST)

- 19:20 (2026-11-12) **iommu=pt did not fix the resets; b300 3 of 4; no out-of-range access in the code.** tg105pt
  (after pt): all identical, speeds unchanged, card stores still ~1 GB/s (the store slowness is the cards', not the
  IOMMU's). b300 retried under pt: pass, then reset (16:05, pci_conf1_read again). Static hunt
  (`dsv41-work/b300hunt/FINDINGS.md`): every pull of halves of 150 stays in range with more headroom than 512 / 256;
  unique to 150: token groups of 16 leave 10 spare tokens whose reads touch half B's slots while its pulls write them
  (local, harmless), the 25-per-card even split, engram pieces 256 + 44. Side lever: the engram pull is copied twice
  per block (layers 1 and 14, ~49 MiB per card each), dropping the second changes nothing. Mitigations now: owner OK'd
  the cards' audio functions kept awake (PME config-read polling ~7/s -> ~1/s, USB 45:00.4 left); the gates' GPU
  sampler is off (120 card-register reads/s). Next build tp105 = tp104 + xorP compiled in + fl-1 (`OWN_FL`) +
  `OWN_U3_NOPAIR` + sw (`OWN_MT_SW`), gate tg105 (`dsv41-work/tp105-readiness.md`); tg105v = draft vocabulary on all
  five prompts.
- 11:10 (2026-11-12) **Host resets: the stuck instruction found; iommu=pt reboot (owner approved).** tg104's
  t3k_b300 (blocks of 300 = overlapped halves of 150) reset the host twice (01:14, 09:24), early in its prompt; no
  other run did. Every reset's BERT (8 events) is a core watchdog (bank 5, EX, extended code 0); the two newest and
  11-11 15:17 resolve to `pci_mmcfg_read` / `pci_conf1_read`: a CPU waiting on a PCI config read (kernel PME scan of
  the cards' sleeping audio functions ~7/s; our run start's dma-buf attach). So card-to-card READ traffic stalls the
  fabric past the core watchdog (long reads, xll, PX overlap; decode pushes never did). IOMMU was Translated (DMA-FQ).
  b300 banned; tg104c ran the rest (`data/.../round19-tg104/`): all identical, **px-512 3K 5.56 s vs 5.71 (-2.8 %)**,
  steady state -11 % per token, first 512 block 0.87 s; w8 / w4 worse, move ~0, serial 5.93. Peer benches before
  the reboot (`dsv41-work/runs/pt/bench-before.txt`): EU stores into a peer ~1.0-1.1 GB/s per card, pulls 39 GB/s
  (64 work-groups, 640 KiB), copy engine 27 GB/s (all six at once; 51 alone). After the reboot the one-shot unit
  `dsv41-postboot-pt` runs the probe, the benches and gate tg105pt (same tp104: traces, plain, 3K reads base / px-512
  / stores `OWN_XPULL=0`, guessing with and without stores). **If stores get fast with pt, the exchange design flips
  to pushes (posted writes: no read round trip, and no read traffic to stall the fabric).** The copy engine at
  27-51 GB/s is the other transport to try for big prompt slices (no EU time, posted writes).

- 00:34 tg103 done (`data/.../round19-tg103/`): 28 traces identical (the overlap now exact), 21 guessing runs the same
  text, plain +0.3 % (xperm-3: 104.11 / 104.42 tok/s). Overlap neutral (3K 5.68-5.71 s vs 5.71): a pull overlaps only
  the one compute launch queued after it (prompt timelines, 1,438 of 1,438 cases); one compute engine per card (Level
  Zero ordinal 0, 1 engine), so the suspect is the compute-queue barrier before each pull; pb256 helper benches fire /
  wait styles on card 2, then `OWN_PX_MOVE` + halves of 256 (`OWN_PX_BIG`) for tp104. pace-2 neutral (stays off).
  TAU 0.40 mixed again (code +2.3 %, analysis -1.0 %). Correction 00:55 (pb256 engbench, card 2): the one-launch
  overlap is an artefact of queue profiling (timeline mode); speed runs overlap the whole window in every fire / wait
  style. **Multi-queue overlap read from OWN_TIMELINE / OWN_GPROF under-counts it: only speed alternations count.**
  PX's real limits: the halves' cost (+0.39 s serial vs base) and kernels slowed beside pulls; `OWN_PX_MOVE` ~0.
- 23:40 build tp103 = tp102 + px-1b (pb256: the halves' fused-router base, 4 sites) + `OWN_TIMELINE_PROMPT` (pb256:
  prompt-block timelines on both queues + `pb256/tlp/tools/tl_prompt.py`) + xperm-3 compiled in (IQ2_XXS / IQ3_XXS
  table copy, ~13 us per step) + pace-2 (attn: one-wave forms for every card's q_a + kv, output-b, shared down, shared
  gate + up with the router at 2-6 tokens, `OWN_MT_PACE_ROLES` 8 / 16 / 32 / 64, opt-in; card 3 bench 720 compares, 0
  differ; predicted 0.12-0.56 ms per check, code +1 %, analysis +1.3-1.5 %) + defaults G128 and pace-1. Gate tg103
  follows (`dsv41-work/tg103.sh`): 18 prompt-1 traces incl. pace-2 at 2-6 and the overlap at blocks of 36 (halves of
  18: the old prompt-1 PX arms never ran halves), 3K traces incl. PX x3 with `OWN_PX_CHECK`, 3K reads base / PX / PX
  serial / PX WG32 alternated x2 (pb256 predicts PX 5.28-5.45 s against 5.71; serial minus base >= 0.12 s decides
  halves of 256), prompt timelines, guessing A / B / B + pace-2, vocabulary, TAU 0.40, one-token + check timelines.
- 23:05 tg102 + tg102b done (`data/.../round19-tg102/`): every trace identical without the overlap; pace-1 pays in
  checks (4-6 tokens -0.26 to -0.58 ms; code 142.4 -> 144.1 tok/s, analysis 157.8 -> 159.9, after 3K 140.9 -> 147.5);
  with the draft vocabulary code 144.72, analysis 162.43 (best so far). Plain 103-104 (G128 +0.4 % on the mean of
  four runs each). px-1 not exact: the fused router read the block's first row instead of the half's
  (`route_shared_m` `scm[c][0]`), so half B of each block never wrote its expert ids, probabilities or shared rows;
  first differing record step 1 layer 2 `cidx` (runs/pxdbg). Fix px-1b (pb256 helper, 4 sites) -> tp103; the PX
  read times (5.28 s) are not valid. Exact check without a rebuild (`OWN_MT_RFUSE=0`): PX identical twice, but 3K
  5.81 / 5.84 s against 5.87 / 5.88 without PX: -1 % only (predicted ~-10 %); suspect the halves' 128-token forms;
  pb256 helper asked for halves of 256 (blocks of 512) and a per-layer account first. Next tree tp103: px-1b, pace-1 and G128 on by default, pace-2 / L1 prefetch /
  rux-2 as they land. New helper fl (card 1): fold the norm launches into their consumers (K4) and the tiny launches
  into neighbours, predicted ~0.5 ms per step together.

- 20:07 build tp100 = tp99 + qb-off compiled out (needs `-DOWN41_QBOFF_M`) + xperm-1 (`OWN_PAIR_G128=1`) + wa-2
  (`OWN_ATT_WA=2`, per-shape window-append choice) + pb-1 (`OWN_PB=1` = mask 0x1e, prompt blocks of 9-256: 16-bit
  rows in weight-reusing forms, expert grouping by counting sort, 6-bit forms without the private scale array,
  per-role form + token chunk at 65-256; helper predicts card-2 kernel time per 3K read -0.49 s at 64, -0.94 at
  128, -1.08 at 256). All opt-in. Gate tg100 (`dsv41-work/tg100.sh`) follows: traces for every arm and each pb bit
  alone at 128 / 256, 3K traces, 3K reads back to back at 64 / 128 / 256, guessing with wa-1 / wa-2 / draft vocab /
  all. Next: gp-1 / gp-a (explicit address spaces so the dense and XPull images keep scratch) and the exact
  dequant study (xperm helper) for tp101.
- Check budget after tp99 (CPU, tg99c `tl_ck` code checks 19-26, tools `dsv41-work/tools/ck_by_m.py` (fixed: it
  imported dsv41_kbusy, which runs its own comparison at import) + `ck_groups.py` + `ck_cards.py` + `ck_names.py`).
  Busy per check, every card: 1 token 9.8 ms, 2 tokens 12.4, 4 16.3, 5 18.9. On the pace card 5, per token
  from 2 to 5: experts 1.03 ms, dense rows 0.56, exchanges 0.32, attention 0.14, other 0.12 (= 2.17). Light card 0:
  experts 0.89, dense 0.42, exchanges 0.70 (its waits). Cards 2 / 5 do 0.64-0.79 ms more non-exchange work at 1
  token and 1.2-1.8 ms at 5 (q_b / o_a rows of the two extra head groups + attention), and card 5's experts run
  7 % slower than card 0's at 5 tokens (6.34 vs 5.90 ms; 2 % at 1 token). So the experts are the largest per-token
  cost. The xperm helper's exact-dequant study is the lever for them. Next is the pace cards' q_b / o_a rows at
  2-6 tokens: q_b Q8 34 us per launch at 5 tokens vs ~23 us one-token.
- gp-1 on img7 CLOSED (pb256 helper, 20:10, card 2, A/B builds forcing the module's private arrays into scratch or
  global, 99 configurations, hashes identical): the one-token step does not move (+-2 %), and checks move at most
  0.05 ms per cycle, with mixed sign (global placement changes every kernel's code by 1-2 %: some forms +10-30 %,
  Q8 G2R4 40-50 % faster). Placement only matters for the prompt WsQ6 forms, which pb-1's bit 8 avoids. Helper
  moved to the prompt exchange-overlap design (`pb256/README-overlap.txt`).
- 21:50 tp102 queued (after tg101 + a health probe for the 21:24 card-5 bench fault): tp101 + draft slots padded +
  pace-1 + pb-1 / wa-2 as defaults (`OWN_PB=0`, `OWN_ATT_WA=0` switch them off). pace-1 (attn helper,
  `dsv41-work/attn/pace/`, `OWN_MT_PACE=1`, roles `OWN_MT_PACE_ROLES` 1 Q8 q_b / 2 Q6 q_b / 4 Q8 output-a):
  persistent one-wave launches for the pace cards' q_b / output-a rows in checks, the next quant-word segment loaded
  while the current one multiplies, the HcFinish rider in its own work-group. Card 3, real rows, us per launch:
  q_b Q8 at 2-6 tokens 25.4 / 29.2 / 28.4 / 32.6 / 34.4 -> 21.4 / 21.9 / 20.9 / 21.6 / 23.0; q_b Q6 at 4-6 26.8 /
  28.8 / 31.2 -> 22.9 / 25.1 / 27.2; output-a Q8 at 2 and 4-6 -1 to -2 us; 635 compares, 0 differ. Predicted per
  check: 0.135 ms at 2 tokens, 0.20 at 3, 0.28 at 4, 0.41 at 5-6.
- Expert-kernel time ledger (xperm helper, `dsv41-work/xperm/README-ledger.txt`): one-token IQ2_S gate+up, bench
  29.6 us / engine 35.6. Launch + table fill 3.3 us; math ~15.5 (instruction floor 18.1); x reads 2.4 exposed
  (52 MB from L1 per launch, 7x the weight bytes); reduction + write 1.4; weights not hidden 6.7. Each sub-group
  loads its row words right before use, 4 dependent memory trips per row pair, all threads in lockstep. The engine
  is +6 us over the bench, not from weight pages. Ranked: L1 prefetch of the rows ahead of use (~-0.21 ms per step,
  ~-0.1 ms per extra check token, spread over kinds), L2 find the engine-over-bench gap (up to ~-0.24 ms per step),
  L3 checks read x once for two rows (~-0.1 ms per extra token), L4 one reduction per row pair. L2 sampler run, then
  L1 (`OWN_R2_PF`) next.
- 21:30 rare stale read in the draft head's exchange (guess logs of every code / analysis / prose run since tg88,
  same draft settings grouped): 2 odd rounds in ~50,000. tg100 code_w2_2 round 66 had a first confidence of 0.9049
  where 107 other runs had 0.9759; tg93 prose_d93 round 182 differed in positions 2-3. Both times the guesses and the
  text were the same; only how many guesses were tried could change. Suspect: the 6 cards' 4-float slots
  (best, index, sum-exp) sit side by side, so each card's own slot writes share 64-byte lines with the slots its
  peers push. That is k7-1's failure ("sums sharing cache lines with lines the receiver wrote"). Also, all six cards
  have PCIe Relaxed Ordering on (DevCtl RlxdOrd+, read with lspci). Fix in the tree for tp102: each card's slot
  padded to 32 floats (128 B), rows 128-byte aligned (`DR_SLOT`, draft.inc + mt_offsets). A helper
  (`dsv41-work/linebench/`) audits every main-model exchange for line sharing / push-then-flag ordering and writes
  a six-card stress bench of the pattern (4-float vs padded slots).
- xperm-2 for tp101 (xperm helper, 20:20, `dsv41-work/xperm/xperm-2.patch`, compile switch `-DOWN_R2_TAB_COPY=1`): every work-group copies its 16-32 KB grid table from a compile-time constant image instead of computing it. Same bits (every image word checked). Card 5: IQ1_S gate+up 27.34 -> 23.50 us, IQ2_S gate+up (xperm-1) 30.09 -> 28.96, IQ2_S down 17.97 -> 16.88; about -73 us per one-token step (~0.7 %), and checks use the same fills. Also: the expert hot loops keep no private arrays, so the global placement costs them nothing. The helper is now writing a time ledger for the expert kernels (bytes, x traffic, launch ramp, latency, reduction) before any more variants.
- tp100 audit (pb256 helper): guarding qb-off out moved the dense prompt module (img8) back to scratch (94 kernels, 0 global), so the default 6-bit prompt forms are fast again at 64 tokens (o_b ~245 us, not 317). pb-1's 9-64 token picks will gain ~0.1 s, not 0.24, and `OWN_PB=0x16` at 256 decides bit 8 there.
- gp-a on img4 CLOSED (attn helper, 20:15, card 3, XPullK128 in both placements, 2000 launches per shape, copies
  checked word for word): global placement costs +0.3-0.5 us per pull, ~0.035 ms per one-token step (83 pulls).
  Under the bar. The real trigger for img4 is not generic pointers. llvm-spirv writes a zero-initialized local array
  (`uint32_t a[4] = {}`, `V4 w(0u)`) as a function-scope variable with an initializer, and IGC turns it into a
  program-scope private global. Any module holding one keeps all its private arrays in global memory. Per tp99 image
  (`dsv41-work/attn/gp/tools/spvinit.py`): img4 32, img5 8, img7 7, img10 12, img12 5; img8 0 (another trigger),
  img11 0 (scratch). Fix written and parked (`dsv41-work/attn/gp/c/`: drop the SparseOutF initializers, build
  XchgPullL::pack's words as values). Helper moved to the pace cards' q_b / o_a check rows at 2-6 tokens.
- 19:18 boot after the 17:59 freeze: the I210 non-fatal setting is NOT re-applied (it turned the self-reset into a
  hang); `OWN_XLL` banned (the last three host events coincided with one-trip pulls); helpers one card only.

- Found (pb256 helper, 2026-11-11 ~18:00, ISA of tp92 / tp97 / tp99 + card-2 benches): **a kernel that accesses
  memory through a generic pointer (address space known only at run time: local-or-global, private-or-global) makes
  the compiler put EVERY private array of its whole device image in global memory** instead of scratch (IGC's
  ForcePrivateMemoryToGlobalOnGeneric behaviour). Same code, only the image differs: Q6 o_b 864 x 8192 247 -> 304 us
  at 64 tokens (+23 %), 468 -> 582 at 128; kernels without private arrays unchanged. This is the tp97 slowdown of
  the unchanged 6-bit kernels (QbmHeavyK joined the dense image), and the XPull image moved when SparseOutFK
  (dynamic local memory) joined it in tp96. In tp99 only img11 keeps scratch; img7 (598 kernels: the routed decode
  kernels, route_with_shared, DenseRowsWS<WsQ6>, DenseRowsGR<GemvQ6KP>, GemvQ8P GR) was global already in tp92.
  Private size per thread is not the trigger (an 8,960-byte kernel does not move its image). Lever: explicit
  address spaces in the generic-pointer kernels (never the IGC switch in a build); ~+20-25 % on launches with a
  private array in a hot loop. Helper measuring the decode kernels in both placements, then gp-1.
- Correction (xll helper): the torn-store positive control in `xll/verify.sh` (v1-2) counted nothing (the compiler
  merged its four word stores into one 16-byte store), so it proved nothing; fixed in `xll_bench.cpp`, re-run
  pending (`xll/check2.sh`). The 1.8 M real exchanges with 0 wrong / 0 torn stand.
- Fifth host reset 17:17 (routine short gate runs); owner approved the I210 completion timeout as non-fatal +
  17-64 s (`dsv41-work/i210-nonfatal.sh`, after every boot). tg99 traces before the reset all identical (defaults,
  11 wa-1 arms, xll h1 / h4); tg99b resumed 17:55.

- Host reset 15:17:25 (4th; a helper's back-to-back ~50 s six-card stress runs; `dsv41-work/faults/
  host-reset-20261111T1517/`). New rule for every multi-card run: at most ~30 s of continuous peer traffic, then
  >= 30 s idle, no stress loops; longer runs only inside the main thread's gates. tg98 lost its 10K reads.
- Done (prompt97, CPU study, `data/.../round19-pp97/prompt97-study/`): the 3K read (6.80 s) is ~2.5x its hard
  floor (separate multiply + add at 5.73 T/s per card = ~2.0 s, plus ~0.7 s of exchange bytes), not 5x (that
  counted FMA, which rounds differently). Time: experts 2.7 s, other matrices 2.0, exchanges 1.0 (all exposed),
  rest 1.0. Prompt pace = the 12-head 230 W cards (layout 12,12,12,12,8,8). Ranked levers (central saving, s):
  (1) exchanges overlapped with compute (two half-blocks, mode-matched pulls or riders) 0.62, large;
  (2) blocks of 256 done right (router 420 us at 256 vs 67 at 64, grouping, engram rows, q_a / q_b / o_a picks)
  0.44; (3) faster prompt expert kernels 0.40, low confidence; (4) three lagging matrix kernels (router-type
  weight-reusing form 0.14, 6 / 5-bit layers, a tp97 o_b slowdown 244 -> 317 us of an unchanged kernel) 0.30;
  (5) no repeated q_a / kv rows on every card 0.23; (6) wider tiles 0.08; (7) parallel grouping kernel 0.08;
  (8) head balance 0.06 (free test `OWN_MT_DSPLIT_WA=0,0,0,0,1,1`). All eight: ~4.6 s (~720 tok/s, 630-870).
  Helper pb256 (card 2) took (2) + (4) + (7).
- Ready for tp99: wa-1 v3 (`OWN_ATT_WA=1`, attn helper; first form bitwise but +50 us per check at short
  context, v3 fixes the divergent index loads, bench queued after tg98) and xll-1 (`OWN_XLL=1`,
  `OWN_XLL_QUICK=K`, one-trip pulls: ~1.8 M six-card exchanges, 6.2 G early reads, 0 wrong; predicted 0.05-0.3 ms
  per step, up to 0.6 per check; `xll/verify.sh` = 4 short six-card steps queued after tg98).

- Done (tg97 13:56-14:07 + tg97b 14:09-14:33, tp97; `data/.../round19-tg97/`): the tp96 winners hold as defaults
  (every trace identical, 16 / 16 guessing SAME): plain 100.4 / 100.6, code 138.4 / 139.2, analysis 153.0 / 150.5,
  prose 117.2, after 3K 141.3. qb-off-2 hung both 16-head cards (driver job timeouts 14:02, probe passed; qb-off-3
  with its helper). k7-2 bitwise but -1.5 % plain (closed). TAU 0.45 / 0.40 neutral. The 3K read takes the same
  whole time on tp96 and tp97 (6.80 s; the printed rate leaves out the first step, whose one-time cost moved).
  tg97c: `OWN_MT_DSPLIT_FIN=1` neutral (code +1 %, analysis -0.5 %), `OWN_TP_HEADS_MIN=4` slower (closed).
- Done (tg96 11:57-12:36 + tg96b to 13:31:22, tp96; `data/.../round19-tg96/`): attn-a2 (`OWN_ATT_T=1`), ck-2
  (`OWN_MT_CK=1`) and rux-1 (`OWN_MT_RUX=1`) all bitwise (38 / 38 guessing SAME, 34 guess logs equal). Best now:
  plain 101.2 / 101.4 tok/s, code 139.2 / 139.3, analysis 153.8 / 153.6, prose 117.3, guessing after 3K 142.2,
  3K read 497 (6.73 s). Check ms by guesses (code, ATT + CK): 10.41 / 13.05 / 15.45 / 17.59 / 20.28 / 22.66. K7-1
  timed out in every run (k7-2 in its bench). Next: tp97 with the three as defaults, plus k7-2, qb-off-2 (heavy
  cards' q_b rows shared in checks, est. 0.29-0.57 ms per check) and eg-fold-1 when their one-card checks pass.
  A CPU timeline study of the remaining 2-token overhead runs in `dsv41-work/ck2tok96/`.
- Where a check's time goes after tp96 (CPU timeline study, `data/.../round19-tg96/ck2tok96/README.md`): a 2-token
  check is +2.5 ms over a one-token step, almost all real work (experts ~1.3, exchanges +0.56, other rows ~0.7); each
  token past two +2.3 ms (experts 41 % at 2.1x their bytes, exchanges ~20 % at ~3x). The 16-head cards still make
  the others wait 0.58 ms per step, 0.8-0.9 ms per 4-5-token check. Ranked levers: (1) pulls in one round trip,
  0.22-0.34 ms per step, 0.44-0.67 per check of 3-6 (helper `dsv41-work/xll/`, stale-read bench first); (2) q_b rows
  riding the light cards' own q_b launch, 0.18-0.29 per check (qb-off-3); (3) the split finishes riding o_b and
  shared down at 4-6 tokens, 0.36-0.66 per check, high confidence (helper `dsv41-work/dride/`); (4) expert kernels
  on the one-token path, 2.85x their byte floor, 0.30-0.64 per step, low confidence; (5) WindowAppendM inside the
  check attention launch, 0.05-0.09 per check (attn helper). Free re-tests for the next gate: `OWN_MT_DSPLIT_FIN=1`,
  `OWN_TP_HEADS_MIN=4`.
- Watch item (attn helper, 2026-11-11 ~13:45; probe `dsv41-work/attn/a2/xchk/`): oneAPI 2026.1 folds an
  `atomic_fence` placed in every item right before a barrier into a work-group-scope fence (`fence.ugm.none.group`);
  only the form "barrier, then item 0 fences + flag" (xchg_tail, attn-a2) keeps a real GPU-scope fence. XchgP's flag
  hand-over, XchgPull and XchgPair use the folded form. They have been exact so far (they rely on launch boundaries
  and the order of peer writes, not on those fences). Any new cross-work-group or cross-card hand-over inside one
  launch must use the xchg_tail form plus L1-uncached data; a wrong or timed-out exchange should be checked against
  this first.
- Done (tg92, 2026-11-11 08:02-08:34, tp92; `data/.../round19-tg92/`, commit 456b9bbc0): all traces identical, 20 / 20
  guessing SAME. Code 128.70 / 128.97, analysis 142.22 / 142.84; vocabulary list 130.0-130.7 / 144.9-145.0; 3K read
  469.1 (32: 426, 128: 444). Check ms by guesses (code d92): 0: 10.57, 1: 15.03-15.10, 2: 17.24, 3: 18.92-18.97,
  4: 21.86-21.94, 5: 23.71-23.77 against tp91's 10.45 / 14.44 / 16.92 / 19.19 / 22.60 / 25.30: the mix split from 2
  tokens costs +0.6 / +0.3 ms at 2 / 3 tokens and saves 0.25-1.5 ms at 4-6 (tune92 sweeps DSPLIT_MIN / SKDOTS_MIN).
  The head split (`OWN_TP_HEADS_MIN=3`) lost here (128.04-128.16 vs 128.70-128.97): it does not stack with the mix
  split; closed for now.
- Found (tg91 + tg92): the 3K guessing run right after the plain 3K runs read 7.4 MiB of engram rows from disk (its
  rejected guesses form n-grams never seen; 988 us per step against ~110 cached, ~0.9 ms per round on the check).
  The table is 135 GB, so fresh text always reads cold rows; the gate prompts are warm. cold92 measures four
  never-run prompts once cold and once warm. Lever if large: start each guessed token's row reads as soon as the
  draft proposes it (the anchor's already start during the draft, `OWN_ENG_EARLY`), with more reads in flight.
- Done (cold92, `data/.../round19-cold92/`): fresh text costs little. Four never-run prompts: plain 95.2-95.3 tok/s
  cold against 94.0-97.1 warm (75-90 MiB of engram rows read from disk per 512 tokens); guessing cold / warm: heat
  111.96 / 111.59, bash 138.30 / 141.36, tsdb 107.05 / 107.10, email 134.33 / 135.10; answers the same. The reads
  overlap the card work (`OWN_ENG_EARLY` / `OWN_ENG_LATE`); closed as a lever. The gate numbers stand for fresh text.
- Done (xw92, `data/.../round19-xw92/who-waits.md`, 63 plain steps, XWAIT build of src92): at the output-a exchange
  the four 8-head cards wait 856-916 us per step for cards 2 / 5 (16 heads: q_b + o_a bytes twice, ~16 us per layer;
  the attention kernels themselves are latency-bound and take the same time on both). At output-b, expert-act and
  FFN exchanges every card waits ~4-7 us per exchange and the last card varies (jitter, not structure). The pace
  cards 2 / 5 wait 0.70-0.78 ms per step in total. Balancing heads needs pair exchanges (one-token heads split was
  not better in e79; tune91 / tg92 at 2+ tokens neutral); fewer exchanges or less jitter are the remaining levers.
- Done (pp92, `data/.../round19-pp92/`, card 2 / card 0 kernel totals over the 3K read): experts 3.2 s of 7.0 s
  (46 %), dense rows 2.1 s (30 %), exchanges 1.0 s (14 %; card 0 1.45 s), attention 0.4 s; all flat from blocks of
  64 to 256 (each RoutedU3 launch scales with its slot count: `RoutedU3<RU3IQ2S<20u>>` 977 us x 780 at 64, 3928 us x
  195 at 256). The decode is shared per expert group already; the per-slot x loads and FMA chains re-done for every
  row are what costs, and the dense WS rows show the same. Byte and FMA floors are far below. Helper (rux,
  2026-11-11): row tiles / x staged in local memory for the prompt expert kernels, bit for bit.
- Done (tune92, `data/.../round19-tune92/`): 24 / 24 SAME, guess logs equal. Means of 2 runs (code / analysis):
  thresholds 2/2 (tp92 default) 129.06 / 142.70; 4/4 130.24 / 143.59; 3/3 130.00 / 143.46; 5/5 129.78 / 143.22;
  DSPLIT 2 + SKDOTS 4 129.46 / 143.36; DSPLIT 4 + SKDOTS 2 129.19 / 142.84. Default from tp94: both from 4 tokens
  (+0.6-0.9 %). Checks of 2 tokens: 15.08 -> 14.58 ms (code).
- Done (tg93, 2026-11-11 09:26-09:59, tp93 = tp92 + skn-1 opt-in; `data/.../round19-tg93/`, commit 44d35b860): all
  traces identical, 20 / 20 SAME, guess logs equal. `OWN_MT_SKNORM=15 OWN_MT_HCPP=1`: code 128.66 / 129.34 -> 132.80
  / 132.61, with thresholds 4/4 133.16 / 133.10; analysis 142.28 / 142.59 -> 147.12 / 147.19 (4/4: 147.51 / 147.30);
  prose 108.15 -> 111.74; 3K guessing 127.63 -> 135.96; 3K read 468.0-469.0 -> 470.5-471.2; plain unchanged. Check
  ms per round 15.8 -> 15.3 (code), 18.0 -> 17.3 (analysis). Defaults from tp94: SKNORM=15, HCPP=1, thresholds 4.
- Ready (attn-a1, `/home/steve/dsv41-work/attn/attn-a1.patch` + README, card 3): `OWN_ATT_T=1` = sparse attention in
  one launch per layer (`SparseOutF`: score tiles, then output work-groups that load their rows meanwhile and wait on a
  per-card device counter; one token also does the window append). 16 heads, us per layer: one token 15.2 -> 8.3 (128
  slots), 16.4 -> 9.4 (192), 29.1 -> 20.9 (640); checks of 2 tokens 13.3 -> 8.8, 4 tokens 15.4 -> 10.6. Expected -0.27
  ms per one-token step, -0.19-0.22 ms per check. Blocks of 5-8 at 192-576 slots: two launches (`OWN_ATT_F=0` form);
  above 8 tokens production. Register size fixed per shape (a 256-register launch costs ~1.3 us twice between
  128-register neighbours: measure next to the real neighbours). Bitwise PASS every form.
- Ready (ck, `/home/steve/dsv41-work/pa/ck.patch` + README-ck.txt, card 2): `OWN_MT_CK=1` = the checks' dense rows
  in their own forms per block size 2-6 (PF: all quant words first / L1-uncached weights), q_a + kv in
  weight-stationary forms inside the pair launch. Saved per check on card 2 (back-to-back timing): M = 2: 0.38 ms,
  3: 0.34, 4: 0.42, 5: 0.73, 6: 0.79; the extra token's cost in these launches 492 -> 388 us. 97 pick launches bitwise.
  Lesson: time forms back to back over cold weight copies ("SEQ"); a cache flush before each launch inflated K-quant
  forms up to 1.9x.
- Done (tg95 traces + tg95b, 2026-11-11 10:50-11:28, tp95 = tp93 + default flips + attn-a1 + ck + qb-off-1, all
  opt-in; `data/.../round19-tg95/`): the new defaults identical at blocks 1-256 (and the old forms). **ck and qb-off-1
  identical everywhere** (traces 2-6 / 16 tokens, RIDE=0, k = 2 / 3 / 4, WG=1, 3K at 64; 16 / 16 guessing SAME, guess
  logs equal). **attn-a1's one-launch form differs** (every ATT trace, first at layer 3 attn_o; the two-launch form
  `OWN_ATT_F=0` identical): the output work-groups read the tiles' scores through the non-coherent L1 within the
  launch and got the previous layer's (attn-a2 fixes it: uncached stores / loads, 16 counters; card-3 race bench).
  Speed: ck in the engine wins less than on one card and loses at 3 tokens: check ms code M = 2 14.17 -> 13.89,
  3 16.70 -> 16.85, 4 18.48 -> 17.90, 5 21.15 -> 20.4-20.7, 6 23.08 -> 22.57; guessing +0.5-1 % (code 132.88 /
  130.57 -> 134.12 / 132.09, analysis 146.84 / 145.90 -> 146.27 / 147.26); ck-2 (per-size mask, M = 3 picks) asked.
  **qb-off-1 gives nothing**: plain 96.98 / 97.89 vs k = 4 96.20 / 97.96 (k = 2 / 3 within noise), the zero-guess
  checks (one-token path) 10.54 / 10.55 vs 10.52 / 10.60 ms; helper diagnosing (who reaches output-a last).
  Lesson: a one-card bench of a structural balance change cannot show the new critical path; run a six-card
  timeline before building the full patch.
- Done (ck2tok, 2026-11-11 ~11:55, CPU analysis of the tg95b check timeline, `/home/steve/dsv41-work/ck2tok/README.md`):
  1-token step 10.28 ms -> 2-token check 13.45 ms (+3.17) on the pace cards (2 / 5). New work: experts +1.05 ms
  (10.5 distinct experts instead of 6), the rest ~0.7. Path overhead: q_b falls back to the GR R4 form when the
  mix finish rides (no 1,280-column WS_DOTS entry; ~0.44 ms, ck-2 fixes it), exchanges +0.43 (165 -> 245 launches:
  each 2-token push is two launches), ExpertGroupM +0.16, the 16-head cards' q_b share ~0.32 (they reach output-a
  0.85 ms after the light cards at 2 tokens: 22.9 us per layer against 2.1 on a 1-token step), lost pairing /
  riders / o_b ~0.2-0.3. For 3+ tokens the pull exchanges grow ~3.5 us per extra token each (~0.5 ms per token).
  Fixes ranked: ck-2 (-0.45 at 2, -0.6 at 3); q_b offload in block checks (~3 heads, -0.2-0.4: in checks the
  imbalance is 0.85 ms, unlike 1-token steps); one-launch 2-token push (runtime: OWN_MT_XPUSH=0 / 2,
  OWN_XPULL_MIN=6912; -0.15-0.3); ExpertGroupM folded into gate+up (-0.14-0.22); OWN_MT_SKDOTS_MIN=2 (-0.1-0.2).
  Expected 2-token check ~12.6 ms after all; the rest is expert bytes and the head imbalance. Runtime arms in tg96.
- In flight (2026-11-11 ~10:30): tp94 built (defaults + attn) but not gated; tp95 = tp94 + ck building, gate tg95
  (both opt-in arms, traces at blocks 1-256 incl. 2-6 with CK, 3K traces, plain, 3K read, 22 guessing runs, profile +
  check timeline). Helpers: qboff (H8), k7 (K7), rux (prompt experts).

### Earlier entries (07:41)

- Done (tg91, 2026-11-11 06:56-07:37, tp91; `data/.../round19-tg91/`): 23 of 23 prompt-1 traces and 6 of 6 3K traces identical, 26 of 26 guessing runs SAME AS the plain run, every guess log equal. Plain 97.8-99.3 tok/s. Prompt items C + SKDOTS: 3K read 469 tok/s. The 3K guessing run of the default (125.87) lost to its own outlier rounds: that run read 7.4 MiB of engram rows from disk (962 us per step against ~116 when cached), not a code change.
- Done (tune91, 2026-11-11 07:38-07:47, tp91; `data/.../round19-tune91/`): 16 of 16 SAME, guess logs equal; the head
  split for checks from 3 / 4 tokens on +1.2 %, from 2 neutral (scoreboard).
- Running: build of tp92 (DSPLIT + SKDOTS from 2 tokens, DR_WS, DR_ANCHOR_ARG on), then gate tg92 (traces, 3K
  blocks 32 / 128, head split 3, vocabulary list, a check timeline with its guess log). Helpers: dense rows in
  checks (ws), sparse attention (attn, one-card benches), block-step norms (skn, K6).
- Next: tp92 = tp91 + `OWN_MT_DSPLIT=1` and `OWN_MT_SKDOTS=8` from 2 tokens on, `OWN_DR_WS=1`, `OWN_DR_ANCHOR_ARG=1` as defaults (+ the head split if tune91 shows a win); then the ws helper's dense rows for checks and the attention helper's sparse attention.

### Earlier entries

- Done (tg90, 2026-11-11 05:51-06:37, tp90; `data/.../round19-tg90/`): 20 of 20 prompt-1 traces and 7 of 7 3K
  traces identical, 28 of 28 guessing runs SAME AS the plain run, guess counts unchanged. Results in the scoreboard.
  Check cost by guesses with everything on (code, median ms): 0: 10.43, 1: 14.43, 2: 16.78, 3: 19.14, 4: 22.58,
  5: 25.03. The first guess still costs ~4 ms (the block path's fixed cost from M = 2 on), each further one ~2.4.
- Next: tp91 = tp90 + new defaults (ws, CK1, RING_ONE, DR_NOWAIT, KVPAIR + FIN_QB up to 16 tokens) + draft-head-1
  (opt-in) + pcd-1 (prompt item C + `OWN_MT_SKDOTS`, opt-in); a TAU sweep (draft helper's model: 0.34-0.40).
- Helpers: draft cost + guess-count model (G3 / G4), sparse attention (K3), prompt items C / D (P6).
- Queued: P7 (item E) after C / D; a TAU sweep with the new check costs; bigger blocks if ws + r4 make 256 win.


- Done (tg86 + tg86b + tg86c, 2026-11-11, ended 02:40, tp86): the attention change passed everything (10 of 10 traces
  identical, 128-token answers the same, 3K document 4 of 4 the same, guessing SAME AS the plain run 3 of 3:
  code 105.85 tok/s, analysis 118.70, 3K 112.13); now the default. XPF lost and is removed (scoreboard).
- Found (helper, 2026-11-11 02:37, code reading): **the draft (guessing) model picked its experts from the
  target's 384-wide router rows** although it has 128 experts: entries 128-383 were leftovers from the target's
  last prompt block (so the guesses depended on how the prompt was cut into blocks: the gm64 difference), with
  biases read past the end of its 128-float bias (the first floats of `ffn_gate_inp.weight`), and picks past 127
  ran expert 0. Fix: `RouteP{dne, 3}` with dne = the draft's own expert count, plus a size check
  (`dr-route128.patch`, in tp87). The target's answers cannot change; the draft's guesses will (perhaps better).
- Done (tg87, 2026-11-11 02:50-03:03, tp87 = tp86 + attention defaults + `OWN_XPULL_GRF=128` + 64-token prompt
  blocks + the draft router fix; `data/.../round19-tg87/`): 8 of 8 traces identical (blocks 16 / 5 / 1 / 64, each
  with and without the exchange fix, and the old attention forms), all answers the same, guessing SAME AS the plain
  run 6 of 6. **Plain answers 87.44 / 89.01 -> 90.96 / 90.99 tok/s with `OWN_XPULL_GRF=128` (+3.1 %; default
  from tp88)**. **Guessing with the router fix (+ the exchange fix): code 105.85 -> 116.86 / 117.00 tok/s (2.02 ->
  2.29 tokens per round, 76.6 -> 78.9 % kept), analysis 118.70 -> 129.55 / 129.99 (2.58 -> 2.84), 3K 112.13 ->
  117.77 (blocks of 16) / 121.86 (64)**; guess counts now identical at blocks of 16 and 64. 3K document read
  300.5 / 299.3 -> 338.8 / 338.4 tok/s (blocks of 64 + exchange fix), its answer 81.15 / 81.27 -> 83.64 / 83.76.
- Found (tg87 timelines, device clock): one-token step busy 10.53 ms, in-step idle 0.47 ms; the register-mode gaps
  around the 83 pull exchanges are gone (0.12 us each now). What is left idle: the engram rows' two small host
  copies (a small copy from host memory runs only after the card's queue drains: the card thread waits for layer
  0, then the card waits for the copy) and the 16-byte pre-mix copy (~24 us per step). The guessing check (2.47
  tokens on average): busy 15.55 ms = 1.48x a one-token step, spread evenly (dense rows 1.46x: the check path's
  rows decode the weights once per token, `DenseRowsG<..., 1>`; experts 1.54x; exchanges 1.48x; attention 1.51x);
  in-step idle 0.45 ms: the same copies, the old attention forms (register-mode gaps, ~75 us), and the argmax
  readback before the draft's injection (~59 us). Fixes written for tp88, all opt-in: `OWN_ENG_CQ` (the engram
  copies on a second queue per card, the decode launch waits by event), `OWN_PRE_K` (the pre-mix weights written by
  the broadcast launch), `OWN_HEAD_CQ` (a check's argmax readback on that queue, after the injection is queued),
  `OWN_ATT_M` (the faster attention forms in blocks too), `OWN_SPEC_NGRAM` (guesses copied from earlier text when
  the last n tokens appeared before; the draft skips that round). `tools/perf/dsv41_kbusy.py` compares two
  timelines per kernel family.
- tg88 first run (2026-11-11 03:22-03:28, tp88 = tp87 + mtx256 + the opt-in fixes): prompt-1 traces identical at blocks
  16 / 5 / 1 / 64 / 256 (one block of 36), the old exchange form, the fallback and slot-major forms at 256, and with
  the new options on one-token blocks; **blocks of 5 / 16 / 64 with the new options differed** and the gate stopped.
  Bisect (bis88): `OWN_ENG_CQ` and `OWN_PRE_K` alone identical; `OWN_ATT_M` differed: my dispatch ran the old
  640-slot softmax again after the per-size one (an if / else fall-through). Fixed; tp88 rebuilt, tg88 rerun.
  Lesson kept: opt-in switches + a gate that tries each one catch my own slips before they reach a default.
- Found (dense decode-once helper, `/home/steve/dsv41-work/pa/`, card 2): weight-stationary rows (`rowt<T, R>`,
  every weight decoded once for T tokens) are bit-identical everywhere (354 + 330 + 610 checks) and 2.1-2.8x
  faster on the big matrices (q_b, head, engram, Q5_K shared, most Q6_K) but 0.75-0.97x on the small Q8_0 ones at
  16 tokens (too few threads; 256-register forms). Per-matrix choice, never slower: 16-token block -4.3 ms of
  17.2 (-25 % of dense), 64-token block -25.3 ms of 64.8 (-39 %), checks of 2-6 tokens -0.73 to -1.61 ms
  (10-16 %). Compiler trap: two chained `permute_group_by_xor` additions were rewritten by IGC into its own
  reduction with a different order (36 % of values differed): use `select_from_group((lane + W) % 32)` as in
  `sg_tree32`. Settings finding: the check configuration's token groups of 3 (`OWN_MT_TGM` 3:3, 5:3, 6:3) are slow
  for Q6_K (o_b 66.9 us at 3 tokens against 19.1 at 2). Per-matrix patch being written (`OWN_MT_WS`).
- Running (helpers, one card each between six-card gates, `/home/steve/dsv41-work/card-share-README.txt`): routed
  expert kernels with fewer instructions per weight (card 3; ~1.9 ms per step above their floor by the predictor);
  small serial kernels still above floor (card 4); prompt rows decoded once per block (dense decode-once).
- Tool (helper, 2026-11-11 01:25, `tools/perf/` README / isa_census.py / predict.py / calib.json): a
  machine-code speed predictor: typical error 12 % on 175 measured launches, 33 % on engine launches it was not
  fitted on (routed experts and `SparseOutJC` 2-4x off: no local-memory bench in its fit). Ranking of time above
  floor per step (card 2, partly older profile): routed experts ~1.9 ms, attention ~0.67 ms (partly fixed now),
  norms + mix dots ~0.4 ms.

- Done: g83 gate (router branch-free + engram gate over 16 sub-groups, §33): 85.2 -> 86-87 tok/s, bit-identical.
- Done: the ledger (`2026-11-11-dsv41-step-budget.md`), our older code and other projects
  (`2026-11-11-dsv41-ideas-local.md`), the prompt-reading plan (`2026-11-11-dsv41-prefill-plan.md`).
- K2 expert kernels, packed logical lanes (`tools/bench/bench_routed_m1.cpp` `RoutedIQ2XXSK<NB, P, STAB, PF>`): v1
  bitwise PASS (18,432 pair outputs, 20,736 down) but slower (P = 8: 58 us, P = 4: 35.5 against production 33.5);
  stall samples show block-start load waits; v2 loads block blk + 1 while computing blk (running).
- Found (gs1, `tools/bench/bench_grf_switch.cpp`, `round19-gs1-grf-switch-card3/4.txt`): **a 256-register kernel
  between 128-register kernels costs ~2.9 us extra** (host clock; profiling gap 1.10 vs 0.12 us per launch): a
  2.1 MB Q8_0 step followed by a tiny step is 6.86 us per pair with the tiny step at 128 registers and 9.80 us at
  256. Local memory size changes cost nothing. In the plain step only `SparseSoftmaxPN` (38 per step) runs at 256
  registers: ~0.11 ms per step (~1 %), fix = build it for 128 registers (or slim it). Checks and prompt blocks have
  many more 256-register kernels (83 of 180 in `bench_dense_m16`'s dump): count the mode changes per block there.
  Also seen: a chain of tiny kernels alone runs at ~2.0 us per launch (the card's launch rate), while a tiny
  kernel right after a 6 us kernel adds only ~0.8 us (its setup overlaps the long kernel).
- Found (ad1-ad4, `tools/bench/bench_attn_dec.cpp`, card 3, 2026-11-11 ~02:00): the one-token attention's score +
  softmax per layer runs **13.8 -> 6.1 us** at short lists (n = 160) and 13.1 -> 10.8-11.0 us at 640 slots, every
  output bit-identical: (a) `SparseScoreHG<512, 1>` instead of `<512, 4>` (4x the sub-groups, the same per-(head,
  slot) sum; 7.1 -> 4.2 us at n = 160); (b) the trimmed lists' softmax as `SparseSoftmaxP<n>` built for each slot
  count (n = 160 ... 608) instead of `SparseSoftmaxPN<640>{n}`: 128 registers, 3.9 -> 1.7 us, and no register-mode
  change around it (the chain saves another ~2.8 us, as gs1 predicted). The "bit-mask" slim form tried first still
  built at 256 registers (flag spills) and was dropped; a lean runtime-loop form is 128 registers but slower at 640.
  In the engine as `OWN_ATT_HG=1 OWN_ATT_PK=1` (opt-in, tp86; gate tg86 queued). Expected ~0.29 ms per step at
  short context (~2.5 %), ~0.08 ms at 3K+. Lesson: check the register mode in the dump before calling a fix done.
- Done (gm64, 2026-11-11 02:24, `data/dsv41-bringup-20261109/round19-gm64/`): **prompt blocks of up to 64 tokens**
  (`mtx64.patch`, helper-written: capacities only, `MTX` = 64; blocks past 16 run the same per-token groups
  spread over sub-groups). Every target trace byte-identical (prompt 1 at 64 / 33 / 32 / 16 / 5 / 1 and the
  fallback forms; the 3K document at 64 / 37 / 32 / 16), all 256-token answers the same, guessing SAME AS the plain
  run 5 of 5. **3K read 300.9-301.2 tok/s (blocks of 16) -> 338.5-339.0 (64), +12.6 %**; 32: 333.2-333.4. Card
  memory after load -0.08 GiB. Open: the draft's guesses change slightly at blocks of 64 (code 259 / 338 kept at 16
  vs 258 / 337 at 64; analysis 314 / 446 vs 313 / 454; the answers are the same): some draft-side computation
  depends on the block size; being traced (helper). Applied to the repo for tp87.
- Found (tl85, `OWN_TIMELINE` on tp85 = tp84 + the timeline patch, answer steps 20-27 of prompt 1, all six cards,
  `data/dsv41-bringup-20261109/round19-tl85-timeline/`; device clock only, since the host/device clock mapping came
  out implausible and the copies carry no profiling times): per card and step **busy 10.75 ms, idle inside the
  step 0.47 ms, idle between steps 0.44 ms** (of which ~0.28 ms was the timeline's own per-step clock calibration:
  six cards x four 12.5 us brackets; now done at the window's edges only). Inside the step: **~0.26 ms are
  register-mode changes**: the pull exchange kernel (the `xchg()` lambda, 83 per step) is built at 256 registers,
  so every exchange is entered and left with a ~1 us device gap (166 per step), and `SparseSoftmaxPN` adds 76 more;
  every other launch follows its predecessor by ~0.12 us. The rest: the engram rows' uploads (`EngRowsA` waits
  2 x 42 us per step: the host's row reads come after layer 0's launches) and the pre-mix copy (`HcPreA`, 3 x 8.6
  us). Fix in hand: `OWN_XPULL_GRF=128` (`XPullK128`, the same code pinned to 128 registers; 256 bytes of spill,
  `tools/perf/xpull_grf_tu.cpp`) for tp87. Exchanges in the profile: XchgPull 16.5 us x 83 + XchgP 6.35 us x 80
  = 1.88 ms per step (17 %).
- Done: S2 transport L1 (shared native context, direct stores): safe for host RAM, but no faster than today's
  setup; closed (scoreboard). Exchanges can only shrink by merging or hiding them.
- Gaps: a per-launch timeline on all cards + who waits for whom (`OWN_TIMELINE`, `OWN_XWAIT`; helper writing the
  patch) - the 1.1 ms between kernels is not launch cost (lg1), so it must be waits or host-side delays.
- Prompt: the plan's first steps (decode each shared weight once per 8-16 tokens; 64-token steps; measure the
  distinct experts per step first).
