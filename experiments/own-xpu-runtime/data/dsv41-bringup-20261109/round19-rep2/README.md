# rep2: the replicated router rows and hc fn rows (helper rep2, 2026-11-13)

Status (keep current): **DONE 11:35 -- stopped at the measured ledger (sections 4-5): no option reaches the 0.15 ms (one token) / 0.2 ms (check) line. No engine build, no six-card runs, no speed A/B. `rep2-1.patch` = record only (syntax-checked, never built for the GPU or run; its FFN part measured to lose).**

## In plain words

Every card still reads two sets of the same rows in every layer: the router rows (`ffn_gate_inp`, 384 x 5,120, 16-bit
halves, 3.93 MB per layer) and the two stream-mix dot matrices (`hc_attn_fn`, `hc_ffn_fn`, 24 x 20,480 F32 = 1.97 MB
each). The question: does splitting them across the six cards pay, and how, without changing a bit?

Answer (measured on one card): no. These launches are short and run all their rows side by side, so their length is set
by one row's work, not by how many rows there are. Giving each card a fifth of the dot rows saves 0.1 us per layer in
the attention launch and 1.3-1.6 us in the FFN launch; moving the FFN mix's finish to make room costs more than that.
Splitting the router rows saves ~5 us per layer but needs a new exchange per layer that costs about as much. Best case
anywhere: ~0.06-0.08 ms per one-token step, under 0.2 ms per 3-token check, and -0.08 .. +0.15 ms per check of 4-6
tokens for a router split (one bench reading reaches 0.22 at 4 tokens); checks of 3-6 tokens are under 40 % of all
checks. Under the brief's lines, so no engine build or six-card runs were made.

## 1. Ledger (today: tp109 timelines; tp110 = tp109 + qkv-1, which does not touch these launches at one token)

Sources: `runs/tg109/tl_one.txt` (8 one-token steps, OWN_TIMELINE, kernel times valid, overlap not) through
`rep2/tools/fam_cards.py` -> `rep2/logs/ledger-tl_one-fams.txt`; layer order from `rep2/tools/tl_seq.py` (card 2, step 3).
Checks: `round19-tg109/ck-by-m-card2.txt` through `rep2/tools/bym_fam.py` -> `rep2/logs/ledger-ck-fams-card2.txt`.

### One-token step, the launches that read the rows (per step, all six cards within 0.2 us)

| launch | what it reads | per step | us each (card 2) | us per step |
|---|---|---|---|---|
| `FlNormK<5120,16,25,8,0,NoRows,FlH16Rows<160>>` (phase 3) | FFN pre-norm + FFN mix's 25 dot rows (hc_ffn_fn 1.97 MB) + router rows (3.93 MB) | 40 | 13.45 | 538 |
| `SkNormDotsW<8>` (phase 0) | attention pre-norm + attention mix's 25 dot rows (hc_attn_fn 1.97 MB) | 37 | 6.75 | 250 |
| q_a (+kv) launch with `HcDotsRows` rider (layers 0, 1, 14: no collapsed x yet) | attention mix's dot rows as a rider | 3 | 23.35 (tp109; tp110: rides the qkv share, 7.81 vs 5.73 us in qkv's bench) | 70 |
| `RoutePRows<RowsPair<HcFinishRows, shared gate+up>>` | reads the router logits (not the rows); the FFN mix's finish rides here | 40 | 10.89 | 436 |
| `FlDownComb<GemvQ8P<72>,6>` (phase 4) | shared down rows + combine | 40 | 7.38 | 295 |
| `XchgQ` (expert act exchange, phase 3 end) | | 40 | 8.45 | 338 |

Layer order (card 2): HcPostPreP, **SkNormDotsW 6.6**, q_a+kv 19 (tp110: share ~5.7 + XchgP QKV), SkNormPairW 2.5,
q_b + **attention finish** + rope 23, rope, SparseOutF 9, o_a 18, XchgP(output-a), o_b 16, XchgP(h), HcPostPreP,
**FlNormK 13.1**, RoutePRows (+ **FFN finish**) 10.8, RoutedUQ gate+up 24.5, SwigluBothS, **XchgQ(act)** 7.4, RoutedUQ
down 18-21, FlDownComb 7, XchgP(h), (next layer).

Dependencies:
- Router: input = the FFN pre-norm of the collapsed stream (needs output-b's gathered rows); consumer = RouteP
  (work-group 0 of RoutePRows, right after FlNormK). **No exchange lies between them**: a row split of the router needs
  a new gather per layer. Riding partial dots on output-b's exchange (b) is not possible bit for bit: the router rows
  are float chains (`fl_h16_sum`: `sum = sum + w * x` per lane, then a tree), whose float result cannot be rebuilt from
  partial sums in another order (unlike the mix dots, whose finish uses `float(t)` of a double chain).
- Attention mix dot rows (phase 0): input = the streams after the previous FFN's post; consumer = the attention mix
  finish (rides q_b, phase 0), whose outputs are first read in phase 3. **qkv-1's QKV exchange lies between the dot
  rows and q_b**: row-split dot rows can ride it.
- FFN mix dot rows (phase 3, in FlNormK): consumer = the FFN finish (rides RoutePRows), outputs first read in phase 5
  (HcPostPreP after the ffn-rows exchange). **The expert act exchange (XchgQ) lies between FlNormK and phase 4**:
  row-split dot rows can ride it if the finish moves to a phase-4 launch (FlDownComb, the last one before the h
  exchange).

### Calibration from qkv-1 (measured, not paper)

qkv-1's bench predicted 467 us of kernel time saved per step against 40 new exchanges (4.3-5.5 us each, xlat2 table):
0.25-0.29 ms. Measured (`runs/qsp110/summary.txt`): plain s0 109.11 / 107.78 tok/s (s0_2 read 22.8 MiB from disk),
s1 111.04 / 111.42: 0.16-0.30 ms per step, best-arm comparison 109.11 -> 111.23 (mean s1) = 0.175 ms. So **one new
exchange per layer costs ~6-7.5 us in the engine** ((467 - 175..230) / 40), not the 4.3-5.5 us of the bench table.
Use 7 us per added exchange per layer below.

### Checks of 2-6 tokens (card 2, median us per check, tp109)

| family | M=2 | M=3 | M=4 | M=5 | M=6 |
|---|---|---|---|---|---|
| FlNormKM<2,1,1> (ck2: norm + dots + router, 2 tokens) | 592 | | | | |
| RowsDotsK (router + FFN dots, 3 tokens) | | 595 | | | |
| router rows alone (DenseRowsG + GemvH16P; dots split by token under OWN_MT_DSPLIT) | (97: draft) | (103) | 575 | 619 | 630 |
| SkNormDotsWM (pre-norm + this card's tokens' dot rows, DSPLIT) | | | 443 | 572 | 460 |
| q_a launch with TokRows<HcDotsRows> rider (tp109; tp110 moves these to SkDotsWM / SkNormDotsWM) | 988 | 1109 | | | |
| act exchange (XchgPull at 2-3, XchgPull2 + DSPLIT at 4-6) | 721 | 1333 | 1724 | 1941 | 2560 |

At 4-6 tokens the mix dot rows are already split (by token, OWN_MT_DSPLIT); only the router rows are replicated there.

## 2. Design options and predictions (written before coding; numbers marked "bench" are filled in from rep2's bench)

(a) Router rows split by output row (64 per card) + a new gather of the logits before RouteP: saves the router's bytes
(3.28 MB per card per layer, ~6-7 us at the timeline's FlNormK rate) and adds one exchange per layer (~7 us, qkv-1's
calibration). **Predicted ~0 +- 0.04 ms per one-token step: below the stop line.** At 2-6 tokens the router launch is
~14.4-15.9 us (575-630 / 40) and the gather of M x 384 logits ~7.5-9 us (XchgQ / pull at M tokens): ~0.1-0.2 ms per
check at best, before a share's own fixed cost: below the 0.2 ms line. To be confirmed by the bench (router share time).

(b) hc dot rows split by row, riding EXISTING exchanges (no new exchange): card c computes dot rows [4c, 4c + 4)
(card 5: 20..24, the 25th row being the sum of squares), each row by the same SkDotsFF<8> work-group code as today (so
the same 8 partial words per row as the full launch), into an arena region; the pieces ride
- the attention mix: qkv-1's QKV exchange (XchgP at one token) as a second range; q_b's finish reads the gathered rows;
- the FFN mix: the expert act exchange (XchgQ at one token) as a second range; the FFN finish moves from RoutePRows to
  FlDownComb (one extra sub-group, rider first).
Prediction from the ledger: SkNormDotsW 6.75 -> ~3.3-3.8 us (norm alone 2.4-3.2; bench), x 37 = ~0.11-0.13 ms;
FlNormK 13.45 -> ~9.5-10 us (1.64 MB less at the launch's 440 GB/s; bench), x 40 = ~0.14-0.16 ms; minus ~0.1-0.2 us
per exchange for 0.25-0.32 KB more per peer (xlat2: ~0.36 us per KB) = ~0.01 ms; the finish's move: bench.
(Correction 11:25: no such per-KB slope is in `xchg2/logs/xlat2-table.txt`; its XchgP column moves in uneven steps
between token counts, e.g. H 5.53 / 12.04 / 12.32 us at 1 / 2 / 3 tokens, OA 5.80 / 9.80 / 20.68. See section 4.)
**Predicted ~0.2-0.27 ms per one-token step (above the 0.15 line).** Checks of 1 token take the same path.

(c) Fold the router's gather into an existing exchange: impossible by the dependency order (above).

Checks of 2-3 tokens (the dots are replicated there, 4-6 are split by token already; 2-3 token checks were 50 of the 100
checks in the tp109 sample, `logs/ledger-ck-fams-card2.txt` last line): the same row split would need new launch forms
(SkNormDotsWM / FlNormKM / RowsDotsK with a row range), XchgP2 with per-token slots (the QKV exchange at 2-3 tokens is
XchgP) and the act exchange's pull with a second region by rows (XchgPull2-like). Prediction (10:30, before measuring):
the attention mix's SkNormDotsWM at 2-3 tokens ~6-9 us -> ~3-4 us, FFN FlNormKM (2) / RowsDotsK (3) ~14.8 us -> ~11-12;
~6-8 us per layer, ~0.25-0.3 ms per check before the exchanges' extra cost (the pull's second region: unknown; DSPLIT
by token "loses at 2-3", OWN_MT_DSPLIT_MIN's comment). Measured first: `src/bench_rep2m.cpp` (full launch vs no dot
rows vs one card's rows, bitwise shares).

## 3. Design as written (rep2-1, opt-in `OWN_REP2`, default 0 = today's engine)

`OWN_REP2` bits: 2 = the attention mix's dot rows, 4 = the FFN mix's dot rows; `=1` means both (6). One-token steps
only (tp_phase: decode steps, checks of 1 token, prompt blocks of 1); the draft's block steps, checks of 2-6 tokens and
prompt blocks never take it.

- Rows per card: `ops41sycl::rep2_rows` = [0,4) [4,8) [8,12) [12,16) [16,20) [20,25) on six cards (row 24 = the
  streams' sum of squares). Arena: two 200-double regions (`xhA`, `xhF`) after qkv-1's `xqk`, 64-byte aligned, so each
  row's 8 partial doubles are one 64-byte line of their own.
- Attention (bit 2; needs qkv-1's one-token split, `OWN_QKV_SPLIT` bit 2, default on in tp110): case 0's pre-norm launch
  `SkNormDotsW<8>` (26 work-groups) becomes `SkNormDotsWS<8>` (1 + this card's 4-5 work-groups, the same SkDotsFF<8>
  code per row) writing into `xhA`; the QKV exchange (XchgP, 1 slot) becomes `XchgP2` with the card's rows as a second
  range; q_b's finish rider (HcFinishRows) reads `xhA`.
- FFN (bit 4; needs the act exchange as XchgQ (`OWN_XPUSH2` bit 4), `OWN_FL` 3, no `OWN_DOWN_EX`): case 3's
  `FlNormK<5120,16,25,...>` becomes `FlNormKS` (this card's dot work-groups + every router work-group unchanged), into
  `xhF`; `RoutePRows` runs without the finish rider; the act exchange (XchgQ, 7 slots) becomes `XchgQ2` with the second
  range; case 4's `FlDownComb` becomes `FlDownCombF` (the finish as sub-group row 0, reading `xhF`); a layer without
  fl-1's down form gets a separate `RowsP<HcFinishRows>` launch.
- Serial trace steps: phase 3's records (streams, the FFN mix's pre, the FFN input) are read after phase 4 (the finish
  runs there; nothing phase 4 writes is among them), as fin_move's records are.
- Off conditions (start-up line "OWN_REP2: off (...)"): OWN_TP outside 2-6, model shape, OWN_K7, OWN_XTAIL, OWN_XLL,
  OWN_FIN_MOVE, OWN_XWAIT, OWN_XPUSH2=0, the one-token fused forms off; per part as above. Per layer: the same
  conditions as the launches it replaces (norm_dots_sk's / fl_f1's), all from options, shapes and uploads, so every card
  makes the same choice.
- Exchange reuse: `xhA` is read by q_b's launch, `xhF` by phase 4's down launch, both before the card's next exchange
  (output-a / the h exchange); a peer stores into them again only at the next layer's QKV / act exchange, after waiting
  for this card's later flags (XchgP's / XchgQ's rule).
- Why the bits are the same: each row's 8 partial words come from the same SkDotsFF<8>::run code on the same inputs as
  the full launch's work-group for that row (no cross-work-group state); the exchange copies words; the finish
  (HcMixFinishSG) reads the same 200 words in the same order. The router rows and the norm are FlNormK's code unchanged.
  The bench checks every word of every share against the full launch.

## 4. One-token result (bench, measured): stop

`src/bench_rep2.cpp` -> `bin/b1`, run `logs/out-t1.txt` (card 3, 10:40, kernel journal lines during the run: 0,
`logs/kj-t1.txt`). Layers 0 (shared expert Q8_0) and 27 (Q5_K); kernel us, median of 5 rounds x 39, 8 weight copies
cycled; "share" = the slowest of the six cards' shares.

| launch | L0 | L27 | what it says |
|---|---|---|---|
| A `SkNormDotsW<8>` full / share (norm + 4-5 rows) / norm alone | 4.48 / 4.38 / 2.50 | 4.48 / 4.38 / 2.50 | the launch is ONE dot work-group long (a row of 80 KB), not the 25 rows' bytes: a share saves 0.10 us |
| B `FlNormK` full / Bd (dot share, all router rows) / B0 (no dot rows) | 11.88 / 10.62 / 10.52 | 11.77 / 10.21 / 9.58 | the FFN dot rows cost 1.3-1.6 us of the launch |
| B Bdr (dot share + router rows [64s, 64s+64)) | 5.52 | 5.52 | router share: a further 4.7-5.1 us |
| C `RoutePRows` with / without the FFN finish | 9.17 / 9.06 | 9.38 / 9.48 | the finish rides there for free (it overlaps the shared rows) |
| D `FlDownComb` plain / with the finish (FlDownCombF) / the finish alone | 4.17 / 7.81 / 6.25 | 5.00 / 7.40 / 6.25 | the finish is a 6.25 us serial chain: in the short down launch it adds 2.4-3.6 us |

Bitwise: every share of A and B (dot words, norm output, router words), B0, C and D with / without the finish, the
finish vs `RowsP<HcFinishRows>` alone, and the XchgP2 / XchgQ2 indexing test (4 cases x 6 cards x 6 buffers): 416
comparisons, 0 differ ("ALL: 416 comparisons, 0 failing -> PASS").

Per one-token step (counts from section 1: 37 SkNormDotsW, 40 FlNormK / RoutePRows / FlDownComb per step):
- (b) attention mix on the QKV exchange: 0.10 us x 37 = **0.004 ms** saved, before the second range's cost (not measured on six cards:
  the card's 16-20 extra vec4 join the QKV share's 72-76 in XchgP's single store round of 256 items). Nothing to gain: a row split cannot shorten the one row a work-group streams.
- (b) FFN mix on the act exchange, as written (finish in FlDownCombF): (1.26 + 0.11 - 3.64) / (1.56 - 0.10 - 2.40) us
  per layer = **0.04-0.09 ms LOST** per step. With the finish riding a long launch for free (e.g. the routed down
  launch; not written): 1.37-1.46 us per layer = **~0.055-0.058 ms** saved before the second range's bytes.
- (a) router split + a new gather: 4.69-5.10 us per layer saved against 4.3-7.5 us per gather (xlat2 table .. qkv-1's
  engine calibration): **-0.11 .. +0.03 ms** per step.
- (a) + (b) in one new gather (dot share + router share in FlNormK, 6.25-6.36 us saved; the finish stays in RoutePRows
  after the gather): **-0.05 .. +0.08 ms** per step.

Prediction vs measurement: (a) predicted ~0 +- 0.04 ms, measured -0.11 .. +0.03; (b) predicted 0.2-0.27 ms, measured
0.004 (attention) + 0.055 at best (FFN): the prediction assumed the launches were byte-bound (25 rows' 1.97 MB at the
launch's rate); they are latency-bound (one work-group per row, all rows in parallel), so dropping 20 of 25 rows
saves almost nothing. Every option is under the 0.15 ms line: per the brief, no engine build, no six-card runs.

## 5. Checks of 2-6 tokens (bench, measured): stop

`src/bench_rep2m.cpp` -> `bin/m1`, run `logs/out-k1.txt` (card 3, 11:11, kernel journal lines 0, `logs/kj-k1.txt`),
layer 3, kernel us, median of 5 rounds x 39, 8 weight copies; the engine's check forms; "share" = card s's rows
(SkNormDotsWMS / RowsDotsKS, written in the bench) of every token, the slowest of six. Bitwise: every share's partial
words, norm outputs and router words against the full launch: 63 comparisons, 0 differ.

| launch | M = 2 | M = 3 |
|---|---|---|
| attention `SkNormDotsWM<8>` full / share / norm only | 6.04 / 4.69 / 2.60 | 8.02 / 4.69 / 2.60 |
| FFN `FlNormKM<2,1,1>` full / no dot rows (M = 2); `RowsDotsK<DenseRowsG<GemvH16P<160>,3>>` full / share / no dot rows (M = 3) | 12.92 / - / 11.77 | 13.75 / 10.73 / 10.21 |

Per check (x 40 layers): M = 2: attention 0.054 ms + FFN at most 0.046 (no dot rows at all) = **<= 0.10 ms**; M = 3:
attention 0.133 + FFN 0.121 = **0.254 ms gross**, before the costs:
- attention: rides qkv-1's QKV exchange (XchgP below 5 tokens) as per-token second ranges (5 rows x 3 tokens x 64 B =
  0.96 KB more per peer; at 3 tokens the store loop grows from 228 to 288 vec4, past XchgP's 256 items, and xlat2's
  XchgP column steps by +0.28 (H) to +10.88 us (OA) from 2 to 3 tokens, so this cost is not known); its finish already
  rides q_b's launch after that exchange. At most 0.133 ms per 3-token check, 0.054 per 2-token check.
- FFN: its finish rides the shared gate / up launch BEFORE the act exchange, so it must move after it (at one token
  that move alone cost 2.4-3.6 us per layer, section 4), and the act exchange at 2-3 tokens is a pull (it needs a second
  region by rows, XchgPull2-like). Gross 0.121 ms per 3-token check; these costs are not measured.
- The nearest measured analog is OWN_MT_DSPLIT (the dot rows split by TOKEN, the same second regions on the pulls and
  the finishes after them, a similar gross saving at 3 tokens): with OWN_MT_SKDOTS from 2 tokens it made 2-token checks
  0.6 ms and 3-token checks 0.3 ms slower than tp91 (`/home/steve/dsv41-work/tune92.sh` header, tg92), and moving its
  minimum from 4 to 3 tokens changed the check time per cycle by -0.04 .. +0.06 ms (`runs/tune92/summary.txt`, m33 vs
  m44: code 15.66 / 15.69 vs 15.66 / 15.63, analysis 17.84 / 17.80 vs 17.80 / 17.81 ms).
- Prediction: under 0.2 ms per 3-token check (0.254 gross minus costs of the kind that turned the token split's similar
  gross into nothing), at most 0.10 per 2-token check. 3-token checks were 20 and 2-token checks 30 of the 100 checks
  in tp109's sample (`logs/ledger-ck-fams-card2.txt`): even the gross is ~0.05 + ~0.03 ms per check averaged (checks
  take 15.6-18.0 ms per cycle in tune92). Stop. At 4-6 tokens the mix dot rows are already split by token
  (OWN_MT_DSPLIT); the router rows (14.4-15.8 us per layer there) have no exchange between them and RouteP,
  so only option (a) applies there (a new gather of M x 384 logits).

Option (a) at checks of 4-6 tokens. Prediction (11:17, before `src/bench_rep2r.cpp` runs): the router launch is
14.4 / 15.5 / 15.75 us per layer at 4 / 5 / 6 tokens (`logs/ledger-ck-fams-card2.txt`: 574.5 / 618.5 / 630 us per
check over 40 layers); a card's 64 rows ~3-5 us (guess, to be measured); a new gather of 64 x M floats per card (1-1.5
KB per sender, one XchgP store round) ~5.5 (xlat2's XchgP at 1 token of H, 5.53 us) to ~7.5 us (qkv-1's engine
calibration, section 1). Net 1.9-7.3 us per layer: 0.08-0.29 ms per 4-6 token check: straddles the 0.2 line, so
measured before deciding.

Measured (`src/bench_rep2r.cpp` -> `bin/r1`, run `logs/out-r1.txt`, card 3, 11:27, kernel journal lines 0; layer 3;
RowsP<DenseRowsG<GemvH16P<160>, G>> through launch_rows<0>, G 2 at 4 tokens, 3 at 5-6; share = rows [64 s, 64 s + 64);
bitwise: every share's logits equal the full launch's, 9 comparisons, 0 differ):

| tokens | full (bench) | full (engine, tp109 timeline) | share, slowest / the other five |
|---|---|---|---|
| 4 | 19.79 | 14.4 | 8.85 / 5.21-5.62 |
| 5 | 10.94 | 15.5 | 6.56 / 6.46-6.56 |
| 6 | 10.94 | 15.75 | 6.56 / 6.46-6.56 |

The bench's full launch does not match the engine's at 4 and at 5-6 tokens (the engine may run another form there,
e.g. OWN_MT_WS's table; not traced further). With the engine's full times and the bench's slowest shares, against a
5.5-7.5 us gather: 4 tokens -2.0 .. 0.0 us per layer, 5 tokens 1.4-3.4, 6 tokens 1.7-3.7: **-0.08 .. +0.15 ms per
check of 4-6 tokens**; with the bench's full times: 4 tokens 3.4-5.4 us (0.14-0.22 ms), 5-6 tokens -3.1 .. -1.1 (a
loss). Checks of 4-6 tokens were 18 of the 100 checks in tp109's sample: at most ~0.03-0.04 ms per check averaged.
Under the line (one reading touches it at 4 tokens only): stop.

## 6. What is left (none of it above the brief's line)

- Option (a) at checks of 4-6 tokens (section 5's last table): the largest remaining piece, -0.08 .. +0.15 ms per such
  check by the engine's own router times (+0.14-0.22 at 4 tokens by the bench's form). Deciding it would need the
  engine's actual router form at 4-6 tokens benched as a share, and a six-card cost for one more 64 x M-float gather
  per layer inside checks.
- The attention half at 2-3 token checks (at most 0.133 ms per 3-token check, 0.054 per 2-token check, ~0.04 ms per
  check averaged, before XchgP2's extra store round): XchgP2 with per-token second ranges + an SkNormDotsWM row-range
  form (SkNormDotsWMS, bitwise-checked in `bench_rep2m.cpp`) in tpm_layer's qsp path. Small; its finish needs no move.
- The one-token SkNormDotsW launch is ONE SkDotsFF work-group long (4.38-4.48 us against 2.50 for the norm alone):
  only a faster per-row form shortens it, not spreading rows over cards.
- The FFN finish (HcMixFinishSG, a 6.25 us serial chain) rides RoutePRows for free today; any change that moves it
  must find a launch at least that long after the act exchange (the routed down launch), or it costs 2.4-3.6 us per
  layer (FlDownCombF measured).

## 7. Files

- `tools/fam_cards.py`, `tools/tl_seq.py`, `tools/bym_fam.py`: ledger scripts (python3 -I).
- `logs/ledger-*.txt`: their outputs.
- `src/bench_rep2.cpp` (+ `src/gguf_part.inc` from qkv): one-card bench (variants A-E, X), `build_bench.sh`, `bwait.sh`,
  `run.sh` (card 3, locks/rep2-card3).
- `src/bench_rep2m.cpp`: the checks' bench (section 5), `bin/m1`, `logs/out-k1.txt`; `src/bench_rep2r.cpp`: the router
  at 4-6 tokens, `bin/r1`, `logs/out-r1.txt`.
- `base/`, `tree/`: the lab engine at 787729bcf (git archive) and the working copy; `mkpatch.sh` -> `rep2-1.patch`
  (record only: 592 lines, `git apply --check` clean on lab HEAD 0fe63f831 (no engine change since 787729bcf),
  `build_engine.sh syn2 syntax`: "syntax ok in 42 s", `logs/build-syn2.log`; syn1 failed on a default argument of the
  nested X2R type, fixed). Never built for the GPU, never run; its FFN part measured to lose 0.04-0.09 ms per step.
- `build_engine.sh` (build110.sh's flags, locks/build-rep2), `six.sh`, `one.sh`, `drive.sh` (unit prefix rep2-),
  `plan.sh` (traces, then `qsp.sh`, the speed A/B copied from qsp110.sh): written, NOT run (the ledger stopped it).
