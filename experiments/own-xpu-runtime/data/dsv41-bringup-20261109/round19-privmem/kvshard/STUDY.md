# kvshard: splitting DeepSeek V4.1's per-position state across the six cards (design study)

2026-11-16. Read-only study: no GPU run, no build, no edit to any existing file. Source read: worktree
`/home/steve/dsv41-work/tp114src` at **0e826cc908** (tp118c wip; tp117's memory layout is unchanged in it). A commit
landed in `backend_sycl_v41.hpp` during the study (lines past 3904 moved by +35), so re-grep the anchors before
patching. Abbreviations used for paths below (all under `experiments/own-xpu-runtime/engine/`):

- **B** = `src/stage2/packet3/backend/backend_sycl_v41.hpp`
- **MT** = `src/stage2/packet3/backend/backend_sycl_v41_mt.inc`
- **DR** = `src/stage2/packet3/backend/backend_sycl_v41_draft.inc`
- **K** = `src/stage2/packet3/kernels/sycl_v41.hpp`, **KA** = `src/stage2/packet3/kernels/sycl_v41_attn.hpp`
- **R** = `planning/dsv41-fixtures/own_run_v41.cpp`

Numbers read from code or from logs are given as read. Numbers marked **(est.)** are estimates.

---

## In plain words

1. **Where the memory goes today.** Every card keeps a full copy of the model's memory of the text. For each
   position that is 2,560 bytes of compressed key/value rows, 640 bytes of the indexer's keys, and 463 bytes of
   scratch rows that are sized by the context length: **3,663 bytes per position on each of the six cards**. The
   measured slope on card 2 agrees (3,630-3,675 B). Card 2 has about 2.76 GiB left for this after the weights and the
   384 MiB margin, so tp117 tops out near **810K positions** (plain answers) and near **400K with guessing** (the
   draft takes another 1.39 GiB per card).
2. **Nothing forces the copies.** The attention never reads the stored rows in bulk: each token reads its 128-row
   window plus the **512 rows the indexer picked**. The indexer does read every key, but each key's score depends on
   that key alone, and the pick is "the 512 highest scores, the earlier position first on ties", which gives exactly
   the same answer when it is computed in six pieces and the pieces' winners are merged.
3. **The design.** Each card stores only every sixth chunk of 2,048 rows (round robin by position), plus a small
   copy of the newest 4,096 rows of each source on every card. Each index step: every card scores its own rows,
   picks its own top 512 (with their scores), the six short lists (24 KB) are exchanged, and every card merges them
   into the same final list. Then the 512 chosen rows are brought from the cards that own them into a staging
   buffer **in list order**, and the attention kernels run unchanged on the staging buffer. Same bytes, same order,
   same arithmetic: the outputs are bit-identical. No partial attention is merged anywhere.
4. **What it buys.** About **0.6 KB per position per card** instead of 3.66 KB. Ceiling on card 2: **~4.4M
   positions plain, ~1.9M with guessing** (worst-case staging buffers; ~4.7M / ~2.2M with smaller ones).
   **1M fits in both modes; 3M fits only without guessing.** Note: the model's rope scaling is built for 1,048,576
   positions (YaRN original 65,536 x factor 16, B:6012), so answers past 1M are outside what the model was made for.
5. **What it costs (est.).** One-token step at 1M: fetching the chosen rows costs ~0.2 ms, but the index no longer
   ships every row's score between cards (today's row-split index would move 8.3 MB of scores per step at 1M,
   ~0.4 ms), so decode is about even with today's method; and because each card now picks over 1/6 of the rows,
   the picks that make today's engine slow at long context shrink too: **~12.5-13 ms per step at 1M (~78 tok/s)**
   against ~13 ms measured at 388K today. Prompt reading: +1-2 % fixed, plus 1-8 % for the row fetches depending on
   how often the 256 tokens of a half pick the same rows (not measured yet; step 1 measures it). A 1M prompt reads in
   ~31 minutes (est.).
6. **First step.** Split only the compressed KV rows (70 % of the bytes) and leave the indexer exactly as today,
   behind `OWN_KV_SHARD=1` (default 0: nothing changes, not even an allocation), with a check mode that keeps the old
   full copy and compares every staged row on the card. That alone lifts the plain ceiling to ~1.75M. Step 2 splits
   the index keys (needed for 1M with guessing).

---

## 1. Per-position, per-card byte budget in tp117

Configuration: production prompt mode (`OWN_PX=1 OWN_PX_BIG=1`, blocks of 512 as two halves of 256), MTX = 256 (the
default: build117.sh sets no `-DOWN41_MTX`), defaults `OWN_IDX_SPLIT=1`, `OWN_IDX_ROWS=1`, `OWN_ROPE_WIN=1`,
`OWN_IDX_DSPLIT=3`, `OWN_IDX_CAND=1`, `OWN_TOPK_M=0` (R:383-432; B:549-566).

Model facts that set the shapes (`step/plan_v41.hpp`): head dim 512 (one latent row per position, shared by all 64
query heads), index keys 128 dims, list k = 512, window 128. Layers 0-1 window only; 2-19 ratio 2 (one compressed
row per 2 positions); 20-39 ratio 1. KV sources {2, 8, 14, 20}, index sources {2, 8, 14, 20, 24, 28, 32, 36}
(plan_v41.hpp:270-271, 309); a layer reads the latest source at or below it (B:2837-2850).

| # | buffer | allocated at | B / position / card | rows per position | written by | read by |
|---|---|---|---|---|---|---|
| 1 | compressed KV rows `ckv_mirror[c][0..3]` | B:705-711 | **2,560** = (3 x 1/2 + 1) x 512 x 2 B | sources 2, 8, 14: 1/2; source 20: 1 | every card: `PubAppendA` (one token, B:5602), `PubAppendAM` (blocks, MT:1332) | attention only, at the 512 listed rows per token and layer, layers 2-39 (B:5355; MT:2318, 2417) |
| 2 | index keys `ik_mirror[c][0..3]` | B:712 | **640** = 2.5 x 128 x 2 B | same | same launches | index scores: every row at layers 2/8/14/20 (B:3346-3369, `ixd_score` B:3436; MT:1466-1490, `ixm_score` MT:1598); only layer 20's <= 16,384 candidate rows at 24/28/32/36 (B:3314-3330, MT:1420-1440) |
| 3 | block index score rows | MT:453 | **344** = 86 rows x 4 B | (`OWN_IDX_ROWS`: 2 halves x 43 tokens) | `IndexerScoreBM(R)`, `IndexerScoreBCM` | the block selects (`TopKSelM*`, `MQ`, `MBQ`, `MC(Q)`) |
| 4 | block candidate marks | MT:467 | **86** = 86 rows x 1 B | | layer 20's block select | the masked / candidate selects of layers 24-36 |
| 5 | arena `xscM` (idxsplit-2 bit 2) | B:4689-4691 | **24** = 6 rows x 4 B | | each card's row share + `XchgPull` | the check selects (blocks of <= 6 tokens) |
| 6 | arena `xscD` (idxsplit-2 bit 1) | B:4686-4687 | **4** | | idem, one-token steps from 8,192 rows | the one-token selects |
| 7 | `sc.score` | B:1555 | **4** | | one-token scores (unsplit and candidate paths) | one-token selects |
| 8 | `sc.cand` | B:1577 | **1** | | one-token layer-20 block select | one-token masked selects, layers 24-36 |
| | **total** | | **3,663** | | | |

The allocations, quoted:

```cpp
// B:705-712
const size_t rows_c2 = (size_t)max_seq / 2 + 2, rows_c1 = (size_t)max_seq + 2;
    size_t rows = s == 3 ? rows_c1 : rows_c2; // layer 20 publishes at ratio 1
    ckv_mirror[t][s] = dalloc<uint16_t>(t, rows * g.hd);
    ik_mirror[t][s] = dalloc<uint16_t>(t, rows * 128);
// MT:452-453, 467 (SR = 86 with OWN_IDX_ROWS and px-512: ixr_rows() MT:47)
const size_t XR = ixr_rows(), SR = XR ? (o.px ? 2 : 1) * XR : TB;
float *score = dalloc<float>(c, ((size_t)max_seq + 64) * SR);
uint8_t *cand = dalloc<uint8_t>(c, ((size_t)max_seq + 64) * SR);
// B:4686-4691
xscD = (nfq + 15) & ~(size_t)15;  nfq = xscD + (size_t)max_seq + 64 + 128;
xscM = (nfq + 15) & ~(size_t)15;  nfq = xscM + (size_t)6 * ((size_t)max_seq + 64) + 128;
```

**Reconciliation with measurements.** tp117 gate c117 (`/home/steve/dsv41-work/runs/c117-20261115T2108/`), card 2
"free after load": p10k (max ctx 16,384) 3.08 GiB, x95k (96,256) 2.81, x200k (195,584) 2.47. Slopes: 0.27 GiB /
79,872 = 3,630 B and 0.34 GiB / 99,328 = 3,675 B (the log prints two decimals: +-55 B). Predicted 3,663 B. The notes'
tp115 figure also checks out: 3,663 + (512 - 86) x 5 B (idxrows-1) + 512 B (ropewin-1) = 6,305 B = "~6.3 KB".
Plain decode mode (blocks of 64, no PX) has SR = 43: 3,448 B.

**Fixed (not per position), for completeness:** window rings 40 x (128 + 256) rows x 1 KiB = 15 MiB (B:721-724),
rope window 2 x 8 MiB (B:6038-6039), lists `cidx_mirror` / `cidxm` (KBs), the draft's 128-row windows and block rows
(DR:52-62; confirmed: the draft never reads `ckv_mirror` / `ik_mirror`), `blm` block lists (MT:472). Opt-in extras:
`OWN_TOPK_M` 0.25 B / position (B:1579-1583), `OWN_IDX_CAND=2` and the `*_CHECK` diagnostics more.
Card 2's free memory before any per-position buffer: F0 = 2.47 + 195,584 x 3,663 / 2^30 = **3.14 GiB** plain
(x95k gives 3.138 too); with guessing (s200k: 1.07 GiB at the same max ctx) **1.74 GiB**. The other cards have more
(x200k: 3.00 / 2.82 / 2.47 / 2.82 / 2.82 / 2.64 GiB for cards 0-5).

**Host side.** `build_rope_tables` (B:6001-6005) still allocates four `max_seq x 32` float vectors (512 B / position
of host RAM, value-initialized, so resident) before it sees that the window is on: 0.5 GB at 1M, 1.5 GB at 3M during
start-up on the 15 GiB host. `h_ckv` / `h_ik` reserve 3.2 KB / position of address space (B:735-738), unused in tp
mode and never touched (virtual only). Both should be skipped at long contexts (step 3 below).

**Replicated vs already split.** Every one of the eight buffers is full length (all positions) on all six cards.
#1 and #2 (3,200 B, the notes' "3.2 KB floor") are byte-identical copies on every card; #5 and #6 are identical
after their pulls; #3, #4, #7, #8 hold different contents per card but still span every position. What is split
today is **work, not storage**: idxsplit-1 gives each card 43 of a half's tokens to index over all rows (`ix_split`
MT:1667), idxsplit-2 gives each card a contiguous share of the rows of the current length (`ixd_bounds` B:3427) and
then copies every card's scores back to every card, idxrows-1 sized #3 / #4 to the token share. No per-position byte
is held by one card only.

---

## 2. Can each replicated part be split, and what exchange does it then need

### 2.1 Compressed KV rows (#1, 2,560 B): yes. Store by owner, fetch the listed rows before the attention.

**Access pattern.** Every attention kernel finds slot i's row through the list only, with one expression:

```cpp
// KA:228 (SparseScoreT), the same form at KA:343, 566, 645 and K:566-4938 (every Sparse* kernel)
s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD
```

`kvw` is the window ring, `kvc` is `ckv_mirror[c][si]`, `wr` the window rows (128, or 128 + MTX in blocks), and the
list holds `row + 128` (`CidxFill` K:6420: `cidx[i] = i < len ? i + 128 : -1`; `WindowAppendP` K:5299 copies it
into the concatenated list). A list value is used for nothing but this address and the `< 0` skip test.

**Ownership.** `own(r) = (r / R) mod 6`, local index `l(r) = (r / 6R) x R + r mod R`, with **R = 2,048 rows**: a
multiple of 8 (a layer-20 block of 8 rows never straddles two cards), of 32 (the scores' T_ rounding) and of 4 (the
exchanges' units). It is fixed when the row is written; the shares idxsplit-2 uses (contiguous ranges of the
*current* length, B:3427-3435) cannot hold storage because their boundaries move as the context grows. Round robin
keeps every card within R rows of the others at every length (balanced scoring as the prompt grows).

**Replicated tail.** Every card also keeps the newest **TT = 4,096 rows of each source** (ring slot `r mod TT`).
Why: (1) rows published in this step or this half are read locally, so fetching rows needs no new handshake; (2) a
rejected guess's rows are rewritten after `commit_block` resets `tlen` (MT:3432): they are at most 6 positions back,
always inside the tail, so no card ever fetches a row its owner may still rewrite; (3) recent rows are picked often
(layer 20 pins the newest block, K:6452); (4) while a source has <= TT rows every card holds all of it.

**Fetch.** Once the list is final (it is the same on every card), card c fills `staging[j]` = the row of list entry
j for j < count (from its tail, its own chunk, or the owner card), and the attention gets `kvc = staging` and a slot
list `CidxFill{count, 512}` (entry j = 128 + j, then -1). Blocks and checks: token t's slot list is
`128 + t x 512 + j` (staging per token), or `128 + u(row)` with a de-duplicated union (step 3).

**Why the outputs are bit-identical.** The kernels' arithmetic is fixed by slot (KA:10-14): "score (head, slot):
acc += q[j] * bf16(k[j]) for j = 0 .. 511 in order ... softmax ... in slot order ... output o += w * x in slot
order". Each slot gets the same 1,024 bytes (a copy of BF16 words), in the same slot, with -1 at the same slots. So
every launch sees identical inputs; nothing is summed across cards. No log-sum-exp merge.

**Reuse.** The (kv source, index source) pair changes only at index layers, so a token needs **8 fetches, not 38**:
layers 2-7, 8-13, 14-19, 20-23, 24-27, 28-31, 32-35, 36-39 each read one list over one source.

### 2.2 Index keys (#2, 640 B): yes. Score own rows, pick own top-k, exchange the short lists, merge exactly.

**Scores.** `IndexerScoreB::run` (K:1281-1317) computes row j's score from the token's query and weights and row j's
key only (`d[h] += q * k` over 128 dims in fixed order, then `s += relu(d[h]) * w[h]` over 32 heads). Scoring a
card's own rows from a compact local array (key pointer = the card's chunk base, j = local index) gives the same
bits; idxsplit-2 already relies on exactly this ("item j' scores row r0 + j' ... with the same sums", B:3413-3421)
and its gate compared 24.9M rows with 0 differences (`dsv41-work/idxsplit/README.md` 8.5).

**Selects.** Every select implements one rule (K:6428-6441, TopKSelP's comment): keys `okey(score)` (-0 = +0; masked
rows -inf), larger key first, **lower position first among equal keys**, the kept positions written in ascending
order, then -1. That is a strict total order on (key, position) pairs, and keys are compared as uint32, so it holds
for any score bits (NaN included). For any partition of the rows into parts P_0..P_5:
`topk(all) = topk(union of topk(P_d))`. Proof: if x is in the global top k, fewer than k elements precede it
globally, so fewer than k precede it inside its own part, so x is in its part's top k; the union contains the global
top k and is contained in all rows, so its top k is the global top k. The list is that set in ascending position
order, so it is the same list.

The tree already has this algorithm on one card: **topk-m** (`OWN_TOPK_M`, tp118b) splits a select into
`TopKSelM1` / `TopKSelMB1` (K:7053, 7177: each group's top k) and `TopKSelQ2` / `TopKSelQB2` (K:7121, 7247: the top
k of the candidates), with this exactness argument written at K:7041-7052 ("one total order, so every member of the
global top k is in its group's top k; the candidates are in ascending position order, so the ties taken ... and the
output order are TopKSelP's"). The card split is the same algorithm with the groups on different cards:

- *Stage 1 (each card, own rows):* any existing select on the local array (local order is monotone in global order,
  so ties fall the same way), writing (key, global position) pairs: k = 512 per row select, 2,048 per block select.
- *Exchange:* the six pair lists (6 x k x 8 B).
- *Stage 2 (every card, same input):* merge the six ascending lists by position into one compact ascending array
  (pads dropped, count n), then the **unchanged** `TopKSelQ2` / `TopKSelQB2` with `p.n = n`.

Edge cases that must hold, and how: (a) k >= rows ("all"): stage 1 keeps all, the merge keeps all, Q2's own "all"
branch fires because n is the real count, then -1 to 512, as TopKSelP. (b) Masked selects past layer 20: stage 1
masks with the card's own marks. (c) Layer 20's block select (K:6450-6462: key = max over the block's 8 rows, the
newest block +inf, K:6452): R is a multiple of 8, so a block's rows live on one card; the owner of block `nb - 1` sets +inf
(it is passed the global block count); each card writes the marks of its own rows; the block list (`out[0]` =
count, then the blocks ascending) is the merged result, identical on every card. (d) The candidate-only layers 24-36
(`TopKSelC` K:6662, which falls back to the masked select over all rows when fewer than k candidates are above -inf):
both branches equal the masked top k (the `OWN_IDX_CAND=1` contract, compared bitwise by `OWN_IDX_CAND=2` in round
18 e84/e85), so stage 1 is the masked top k of the card's own rows (its own candidate blocks, with the same
fallback) and stage 2 merges as above.

Stage-2 sizes do not grow with the context: 3,072 pairs (row selects, `qsel_span` 8) or 12,288 (block select,
span 16), inside `TopKSelQ2`'s 96-span reach (K:6776). Stage 1 on a card's own rows uses `TopKSelQ<96>` up to 98,304
local rows (590K-position sources) and the topk-m two-launch forms past it.

### 2.3 Score rows and marks (#3-#8, 463 B): become local length; the arena copies (#5, #6) disappear.

With 2.2, nothing ever needs another card's scores, so #5 and #6 go (only the fixed candidate regions remain) and #7,
#8 shrink to the card's rows (5 B x N / 6). Blocks change shape: a card now scores **all** tokens of a half over its
own rows (today: its 43 tokens over all rows), so the rows must be reused in token chunks of Tc: 2 halves x Tc x 5 B /
6 per position (Tc = 43: 72 B; Tc = 16: 27 B). Layer 20's marks must survive until layers 24-36 for every token of
the half; rebuild each chunk's marks from the token's block list (`blm`, fixed size, MT:472) instead of keeping
256 tokens' marks.

### 2.4 What would change a summation order if split, and how the design avoids it

- **Attention split by positions with partial softmax + log-sum-exp merge**: changes the order of the denominator
  and output sums. Rejected; the rows move to the heads instead.
- **A KV row split by dims**: the score is one chain over j = 0..511 (KA:10-12); a dim split makes per-card partial
  sums. Rejected. There is no head axis in the KV to split (one latent row serves all 64 heads; the head split
  already covers the queries).
- **Index keys split by dims or by the indexer's 32 heads**: the row score sums all 32 x 128 terms in a fixed order
  (K:1299-1315). Rows stay whole on one card.
- **A layer-20 block across two cards**: would need a max across cards (order-free for max, but one more exchange).
  Avoided by R a multiple of 8.
- **The compressor** (pooling two positions, carried state `kv_state`) keeps running on every card as today
  (B:5567-5605, MT:1272-1335); only where its row is stored changes.
- **The selects**: comparisons only, no sums; exact under the partition (2.2).

---

## 3. Traffic and time at 1M context

Constants. Given: ~20 GB/s per card for card-to-card copies (Gen4 x16), 2.4 us one-way latency per exchange.
Measured, for cross-checks: pulls ~4 us + 17.5 KB/us inbound (idxsplit README 8.4), exchange flag floor ~4 us
(xchg2), copy engine 27-30 GB/s per card pushing to five peers with all six at once (round19-ce), index score
2.35 ns per row per card (idxsplit README 8.3), selects from `round18-q5-test-topk-q-139k.txt` (TopKSelQ ~0.63 ns /
row up to 98,304 rows; TopKSelR ~1.46 ns / row past it). Today's base: one-token step 10.17 ms at 3K (c117 p3k),
11.41 ms at 195K (x200k), 13.0 ms at 389K (lc2, tp115); prompt block of 512 ~0.75 s at short context, growing
~0.41 ms per 1,000 positions of context (c117 x95k / x200k, lc2), so **~1.16 s per block at 1M (est.)**.

### 3.1 One-token step, per card, at 1M positions (N/2 = 500K rows in sources 2/8/14, 1M in source 20)

| item | today's method (if it fit) | full design |
|---|---|---|
| row fetches: 8 lists x 512 rows x 1 KiB x 5/6 | none | **3.50 MB** in, 3.50 out: 175 us at 20 GB/s + 8 x 2.4 us = **~0.19 ms** (measured pull rate: ~0.23 ms) |
| index score copies (idxsplit-2, layers 2/8/14/20): 5/6 x 4 B x 2.5 N | **8.33 MB**: 0.42 ms + 4 x 2.4 us | none |
| candidate lists: 8 x 5 x 512 x 8 B + layer 20's blocks 5 x 2,048 x 8 B | none | **0.25 MB**: 12 us + 8 x 2.4 us = ~0.03 ms |
| exchanges per step | ~87 ("83", B:92, + 4 score copies) | +12 (8 row fetches, 4 candidate lists at layers 24-36 that today need none; layers 2/8/14/20 swap a score copy for a candidate list) |
| scores (own rows: 2.5 N / 6 x 2.35 ns) | 0.98 ms (already split) | 0.98 ms (same work) |
| selects | replicated over all rows, past the register forms' reach: ~3 x 0.73 + 1.46 + ~1.0 (block) = **~4.7 ms (est.)** | stage 1 on 83K / 167K own rows + 9 merges: **~0.5 ms (est.)** |
| **step (est.)** | ~10.2 + 0.98 + 0.43 + 4.7 + ~0.7 other growth = **~17 ms** | ~10.2 + 0.98 + 0.5 + 0.22 + ~0.7 = **~12.6 ms (~79 tok/s)** |

The row fetches sit on the critical path (the attention waits for them); their cost does not grow with context.
Most of the select saving is also available without sharding (topk-m, opt-in since tp118b); against "today +
topk-m" the shard design is about even (+0.22 ms fetches, -0.43 ms score copies, +~0.1 ms merges). At 388K the net is
~+0.1 ms (score copies there are 3.2 MB); below ~8K positions all rows sit in the tail and the fetches are local
copies (~8 x 4 us, ~+0.3 %).

**Guess checks (M tokens).** Row fetches M x 3.5 MB at 1M (less after de-duplicating the M lists); today's
idxsplit-2 bit 2 would copy M x 8.3 MB of scores. Faster than today's method at 1M for every M (est.).

### 3.2 Prompt block of 512 (two halves of 256), per card, at 1M

| item | today | full design |
|---|---|---|
| index lists exchanged (idxsplit-1) | 6.8 MB (copy engine) | none |
| candidate lists: 2 halves x (8 x 256 x 20 KB + 256 x 80 KB) | none | **126 MB**: 6.3 ms at 20 GB/s, on the copy engine beside compute |
| row fetches: 2 halves x 8 lists x U rows x 1 KiB x 5/6, U = distinct rows the half's tokens picked (<= 256 x 512) | none | worst (no overlap between tokens) **1.79 GB, 89 ms**; U = 25 %: 22 ms; U = 10 %: 9 ms **(U not measured)** |
| indexer q_b / rope / proj rows | the card's 1/6 of the tokens | all tokens: +5/6 x 6.2 ms = **+5.2 ms** (6.2 ms measured per piece, idxsplit README 1) |
| scores | 1/6 tokens x all rows | all tokens x 1/6 rows (same work) |
| selects | 43 tokens x all rows (one work-group each) | 256 tokens x own rows + merges ~+3 ms (est.) |
| exchanges per block | 16 | 48 (+32 x ~2.4 us: negligible) |
| **block (est.)** | ~1.16 s | **+15 ms fixed + 9-89 ms row fetches before overlap: +2 % to +9 %** |

The row fetches of one half can run on the copy engine beside the other half's work, as today's PX exchanges do,
so part of it hides. The size of U decides how much; step 1's check mode counts it (5.1).

**Whole reads (est., today's growth).** 1M positions: 1,953 blocks x (0.75 + 0.205) s = ~31 min (+1-5 % with the
shard). 3M: ~2.2 h, and longer if the slopes curve up. Within the "decide in hours" rule only up to ~1M.

---

## 4. The new ceiling

Usable on card 2 (the tightest card): F0 - 384 MiB = **2.762 GiB plain, 1.362 GiB with guessing** (section 1).

| design | B / position / card | fixed extra | ceiling plain | ceiling with guessing |
|---|---|---|---|---|
| tp117 today | 3,663 | - | ~810K | ~400K |
| step 1: KV rows split (#1 / 6), rest as today | 1,530 | 272 MiB (staging 256, tail 16) | **~1.75M** | ~0.77M |
| full design (#1, #2 / 6; #3-#8 local, Tc = 43) | 606 | 286 MiB | **~4.4M** | **~1.9M** |
| full + de-duplicated block staging (2 x 48 MiB) | 606 | ~126 MiB | ~4.7M | ~2.2M |
| floor (#1 + #2 split only) | 533 | - | 5.6M | 2.7M |

Per-position for the full design: 426.7 (KV) + 106.7 (keys) + 57.3 + 14.3 (block scores and marks, Tc = 43) + 0.8
(one-token) = 605.8 B. Fixed extra: block staging 2 halves x 256 tokens x 512 rows x 1 KiB = 256 MiB (worst case;
one-token 0.5 MiB and check 3 MiB staging alias it: they never run at the same time), tails 4 x 4,096 x (1 KiB +
256 B) = 20 MiB, candidate regions ~10 MiB. **1M fits in both modes (plain uses 0.84 GiB of 2.76; guessing 0.84 of
1.36). 3M fits plain (1.97 GiB) but not with guessing: it would need <= ~390-440 B per position (depending on the
staging size), below the 533 B floor of BF16 KV split six ways while the draft holds 1.39 GiB per card.** Weighting the ownership by each card's free
memory (cards 0 / 1 / 3 / 4 / 5 have 0.17-0.53 GiB more than card 2) would add ~10 % (est.).

---

## 5. Implementation plan

### 5.0 Step 0: one card, no six-card run (~1 h)

1. **`tools/bench/test_topk_shard.cpp`** (new, the pattern of `test_topk_q.cpp`): for lengths up to 3,000,000 rows,
   6 owners, R = 2,048 and 16,384, test_topk_q's five data families (normal, few values, +0 / -0, mostly -inf, NaNs):
   reference `TopKSelP` / `R` / `Q` / `BQ` / `C` / `CQ` on the whole array against stage 1 on six compact arrays +
   merge + `TopKSelQ2` / `QB2`. memcmp the lists, block lists and (mapped) marks. Also times the merge.
2. **`tools/bench/bench_attn_a1.cpp`**, one more arm: the attention over (ring, full rows, real list) against (ring,
   rows copied into staging in list order, `CidxFill` slot list), 1-16 tokens, 128-640 slots, skipped slots, stale
   NaN / inf: memcmp outputs and rope'd outputs.
3. If topk-m's `TopKSelQ2` / `QB2` have no bitwise record yet, (1) is that record.

### 5.1 Step 1, kvshard-1 (`OWN_KV_SHARD`, default 0): split the compressed KV rows only

The index (keys, scores, selects, idxsplit-1/-2) stays exactly as today; only where KV rows live and how the
attention finds them changes. Changes:

- **R:385-387**: parse `OWN_KV_SHARD` (0 off; 1 on; 2 check), `OWN_KV_SHARD_R` (2,048), `OWN_KV_TAIL` (4,096).
- **B Options (B:549-566)**: the three fields; refuse with `load_state` (B:1324, the CPU hand-off path), with
  `OWN_XLL`, and with `tp < 6`.
- **Constructor (B:705-712)**: per card one allocation holding its four sources' chunks (`rows_cap / 6` rounded up to
  R) and the tails; mode 2 also keeps `ckv_mirror`. Skip the `h_ckv` reserve (B:735-738).
- **IPC export** of that allocation to the peers, as the arena's (B:4765-4783), `touch()` included.
- **`publish_tp` (B:5567-5605)** and **`tpm_publish` (MT:1272-1335)**: `PubAppendA` / `PubAppendAM` become
  `PubAppendS` / `PubAppendSM` (new, K): every card writes the tail slot, the owner writes its chunk row (mode 2:
  also the mirror). Same `bf16b` rounding, same values.
- **One-token fetch**: in `tp_card_step` case 0 after the select (B:5312-5328), `kv_fetch(c, L)` (new) at index
  layers; case 1 (B:5331-5420): `kvc` (B:5355) = staging, the list passed to `WindowAppendP` (B:5343), `score_tw`
  (B:5364), `out_f` (B:5388), `out_je`, `SparseOutJC` (B:5397) / `JB` = the slot list.
- **Block fetch**: in `tpm_layer` after `ix_wait` / `tpm_index` (MT:2273-2296), `kv_fetch_m(c, L, half)`; in
  `PX_P1` (MT:2298-2446) `kvc` (MT:2318, 2417) = staging and `wci` (MT:2311) = per-token slot lists
  (`CidxFillT`, new: token stride 512). Staging in `mt_alloc` (MT:443): 2 halves x MTX x 512 rows.
- **Transport**: one-token steps and checks pull the rows from the owners' chunks (one kernel, no handshake: every
  fetched row is older than the tail, written at least one finished step earlier, after which every card has
  passed many exchange flags; the same visibility rule `XchgPull` relies on; the same class of traffic as
  idxsplit-2's score pulls, ~3 MB per step at 388K in production). Prompt halves: the owner packs its listed rows and
  pushes them on the copy engine (PX_BCS machinery, flags after data), because the host resets of 11-10..14 pointed
  at card-to-card *read* traffic and the prompt path has been read-free since tp107. A first commit may pull
  everywhere and gate up to 200K; the push form must be in before any run past 200K.
- **Check mode (2)**: `KvStageCmp` (new) compares every staged row with the mirror row on the card (differences
  counted in a device word, read at exit; no host wait, the lesson of idxsplit README 8.5), and counts the distinct
  rows per (half, list) (the U of 3.2, printed at exit).

**Bitwise test (gate c-kvs1, the c117 pattern: stable mode, preflight before each start, first fault, non-zero exit
or difference = STOP):**

1. `OWN_KV_SHARD=2` p3k, traced: TRACE_IDENTICAL against tp117's trace, 0 staged rows differing on all six cards.
2. `OWN_KV_SHARD=1`: p3k IDS256_SAME (e52), p10k IDS64_SAME (tg107), plain IDS128_SAME (ab1), guessing code /
   analysis SAME AS the plain run + GLOG_SAME (tg105v), x95k IDS256_SAME (e82), x200k IDS1024_SAME (lc1), s200k SAME AS
   the plain run. `OWN_KV_SHARD=2` at x95k: 0 differing, and the U counts.
3. Free memory after load must follow ~1,530 B per position (tp118c's tpd-mem lines show every card).
4. Capacity: x700k (704,773 tokens) on tp117/tp118 without the shard (fits: 2.40 of 2.76 GiB; never run yet, c117
   stopped at s200k) and with `OWN_KV_SHARD=1`: IDS1024_SAME. Then a ~1.0M prompt (planted fact) with the shard in two
   placements that move every row (`OWN_KV_SHARD_R=2048` and `16384`): IDS1024_SAME and the fact found. Card time
   ~2 x 21 + 2 x 31 min (est.).

### 5.2 Step 2, kvshard-2 (`OWN_KV_SHARD` bit 2): split the index keys

- **`dev_index` (B:3303-3410)**, **`ixd_score` / `ixd_bounds` (B:3424-3465)**: own-row scores (the same
  `IndexerScoreB` / `BC`, pointers at the card's chunk), stage-1 select, candidate pairs into a fixed arena region,
  one `XchgPull` (`ixd_pull` B:3466 already takes slots and strides), `TopKMergePos` (new, K), `TopKSelQ2` / `QB2`
  unchanged. `xscD` / `xscM` (B:4686-4691) not allocated.
- **`tpm_index` (MT:1340-1594)**: every token of the half over own rows (the `OWN_IDX_SPLIT=2` query rows), in token
  chunks of Tc; per-token stage 1, exchange, merge; `ix_split` / `ix_wait` replaced; marks rebuilt from `blm`.
- **`mt_alloc` (MT:452-467)**: score / mark rows of local length x 2 Tc.
- Check mode: also the full score and the full select (the old path) beside the new one, compared on the card
  (as `OWN_IDX_DSPLIT_CHECK`); only below the old ceiling, of course.
- Same gate as 5.1, plus a 1M run with guessing (SAME AS the plain run).

### 5.3 Step 3: refinements, each its own A/B

De-duplicated block staging (union per half and list: less traffic, 2 x 48 MiB staging) if step 1's U counts are
low; tail size; ownership weighted by free memory; the host-side `build_rope_tables` / `h_ckv` allocations skipped
when the window is on / in tp mode.

---

## Appendix: alternatives not chosen, and risks

- **Rows in host RAM instead of other cards**: the same PCIe cost per fetch, but 3.2 GB at 1M and 9.6 GB at 3M of a
  15 GiB host with an oomd history; the keys must stay on cards anyway (scanned every step).
- **Contiguous position ranges per card**: the first card fills first; the scoring and select work sit on one card
  while a prompt grows. Round robin of 2,048-row chunks balances at every length.
- **Single-row interleave**: splits layer 20's 8-row blocks across cards.
- **Risks**: (1) card-to-card traffic during prompts grows by up to ~1.8 GB per block (worst U); the resets of
  11-10..14 came during card-to-card reads, so prompt fetches go as copy-engine pushes and the first long runs
  follow the stable-mode rules. (2) Fetches sit on the decode critical path (~0.2 ms per step at any context past
  the tail). (3) Two transports (pull for decode, push for prompts) are two code paths to gate. (4) `topk-m`'s
  stage-2 kernels are opt-in and need their own bitwise record (5.0). (5) The model's YaRN design point is 1,048,576
  positions.
