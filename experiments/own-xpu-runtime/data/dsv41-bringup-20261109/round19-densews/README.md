# densews: why the prompt dense rows (DenseRowsWSC) run at ~55 % of the exact ceiling, and what to change (2026-11-17)

Study only: no builds, no GPU runs, nothing else edited. Sources (cited as [S1]..[S7]):
- [S1] `runs/tlp2-20261116T1503/tlp_p3k.txt`: tp122 timeline, 3K read in 512-token blocks (two halves of 256, `OWN_PX=1
  OWN_PX_BIG=1`), card 2 (12 heads), step 20003; per-kernel sums over that step (step 20004 agrees within 0.3 %).
- [S2] `runs/tg103/tlp_base.txt`: tp103 timeline, 256-token blocks, card 2, step 20003 (the 2026-11-12 budget's file).
- [S3] engine ISA `rux6/isa/eng/OCL_asm57439b9a59167bcf_simd32_entry_*.asm` (2026-11-13). The whole WS section of
  `sycl_v41.hpp` (WsQ8 .. ws_rows) is identical in rux6/tree and tp121 (diffed). Loop counts: `rux6/tools/mix6.py`.
- [S4] `rux6/out/run-port2a.txt`: port bench, card 1. [S5] `pb256/README-pb1.txt`: pb-1 bench, card 2.
- [S6] `runs/c130-20261117T0705/summary.txt`: rux9 bench. [S7] `prompt97/README.md` (rates table).
Code below = `tp121/experiments/own-xpu-runtime/engine/src/stage2/packet3/`, `K` = `kernels/sycl_v41.hpp`.

## In plain words
- The dense prompt rows wait on reading the activations (x), not on multiplying. Each sub-group reads 2 bytes of x
  per multiply-add (only 2 rows share each x read), and at the 256-register mode the load path gives ~11.2 bytes per
  clock per engine. That predicts 3.61 T pairs/s; the kernels measure 3.54-3.61 (q_b, q_a, o_b). Their own float work
  would allow ~5.0 T.
- Best change: 4 rows per x read (T8 R4 or T16 R4, 1 byte of x per pair) with per-segment scales, so nothing lands in
  private memory. Same products in the same order. Expected ~4.0-4.25 T on Q8_0 rows: about -30 to -40 ms of the
  741 ms 512-token block on card 2 (-4 to -5.5 %).
- Staging x in local memory (rux9's idea) is the second option, but rux9 itself gained 0 % on the expert kernels.

## 1. How DenseRowsWSC works now
- Launch: `dense_m` (backend_sycl_v41_mt.inc:642) -> `launch_rows<0>` (backend_sycl_v41.hpp:2321): work-groups of
  512 items = 16 sub-groups of 32, NO local memory; `RowsP` gives each sub-group ONE position = one `rowt` call.
- Position (K:3037): R rows x T tokens, all columns; lane l takes columns 32c + l. DenseRowsWSC orders positions in
  token chunks: chunk (cg token groups), then row block, then token group, so a work-group = 8 row blocks x 2 token
  groups (chunk 32). The picks at 256 tokens (WsPb, K:3617-3780): **T16 R2**, chunk 32 (engram, Q8 q_a: chunk 64).
- Per 256 columns (Q8_0 XW 2 = one "word group"; Q6_K / Q5_K: one block) each sub-group loads R x 2 quant words
  (128 B each), decodes R x 8 values per lane ONCE (Q8: `d * float(int8)`), then for each of 16 tokens one 1 KB x
  block (`sg_bloadN<8>` = four 256-byte `d32x64t` reads) and 2 x 8 multiply-adds per lane into `sum[j*T+t]`.
  Per pair: 2.0 B of x + 0.066 B of weights; decode 1/16 per pair.
- Order to keep (per row j, token t): lane sum from 0, chunks / blocks ascending, element order as the block read,
  `sum = sum + value * x` (separate multiply and add), value = Q8 `d * float(q)`, Q6 `(d*scale) * float(code-32)`,
  Q5 `f * float(code) - o`, H16 `float(w << 16)`; then `ws_reduce_store` / `ws_tree32_steps` (K:2703) = sg_tree32's
  pairs (lower lane + upper lane, w = 1..16) via `select_from_group` (xor shuffles get rewritten by IGC: K:2673).
- Shapes per 512-token block on card 2 [S1] (every launch sees M = 256; 27 Q8_0 layers, 12 of 13 Q6_K/Q5_K layers:
  layer 39 runs only its kept key rows, OWN_SKIP39). Pairs = rows x cols x 256 x launches.

| role, rows x cols | form | launches | ms | T pairs/s |
|---|---|---|---|---|
| q_b Q8, 6144 x 1280 | X16R2 | 54 | 30.7 | 3.54 |
| o_a Q8, 1024 + 512 x 4096 (x groups of 1024) | X16R2 | 108 (388 / 200 us) | 32.9 | 2.64 |
| o_b Q8, 864 x 8192 | X16R2 (2 KB private array) | 54 | 30.0 | 3.26 |
| shared down Q8, 864 x 2304 | X16R2 | 54 | 9.1 | 3.04 |
| q_b / o_a / o_b Q6 | K16R2 / K16R2 (2 KB private) / K16R2S | 24 / 48 / 24 | 14.2 / 16.2 / 13.9 | 3.41 / 2.39 / 3.13 |
| engram Q6, 4267 x 6144; shared down Q5 | K16R2S; K16R2 | 4; 24 | 7.5; 4.9 | 3.59; 2.50 |
| **all nine** | | | **159.3** | **3.08** |

  Not in the table: shared gate + up (2 x 384 x 5120, WSC T16R2 pairs inside `RoutePMRows`) 15.7 (Q8) + 8.0 (Q5) ms;
  q_a + kv now run at M = 32 on card 2 (OWN_PRT=3 token split, weights 3,2,2,3,3,3) as `DenseRowsWS` X8R2L, 8.4 ms;
  H16 rows (T8 R4) 6.2 ms. Step span 741 ms, of it XchgWaitB 156 ms; WSC rows 130-160 ms on every card [S1].
  (tg103 at 256-token blocks: 112.7 ms WSC incl. H16, 3.29 T on the Q8/Q6/Q5 rows incl. q_a + kv [S2] = the
  2026-11-12 budget.)

## 2. The bound: x reads through the load port (R = 2), not the float pipe
- ISA, hot loop of X16R2 Q8 (entry_0322, WsQ8<160>; entry_0272 / 0370 identical per word group) [S3]: per word group
  544 float-pipe SIMD32 instructions (512 products + 16 int8->float `mov` + 16 scale `mul`) = 1,088 pipe clocks; ~84
  integer instructions; 68 sends (64 x reads + 4 quant words) = 16.9 KB. Per pair: 2.13 float + 0.33 int + 0.27 send
  instructions, 2.06 B loaded; 0 `mad` in the loop (6 scalar `mad` in the prologue, likely the position division).
  Float pipe = 94 % products. K16R2S Q6 (entry_0482): 562 float (50 decode:
  `mov`, `sel`, `mul`) and 74 sends per block, 2.05 B per pair. H16 T8R4 (entry_0164): 512 float, 40 sends, 1.25 B/pair.
- Port bench [S4] (2.6 GHz: FP mode 10.69 T float ops/s): L1-resident block reads 14,006 B/ns at 128 registers and
  7,466 B/ns at 256 (= 11.2 B per clock per engine; 4 threads per engine); SLM block reads 15,480 B/ns at 256.
  Every WSC kernel above runs at 256 registers (`numGRF=256` in all dumps).
- Model per engine (4 threads x one word group): float 4,352 clocks; loads 4 x 16.9 KB / 11.2 = 6,034 clocks ->
  load bound -> **3.61 T pairs/s predicted**; measured q_a + kv 3.56, q_b 3.54-3.58, o_b 3.61 (tg103) [S1, S2].
  Same model for H16 T8R4: float 4,096 > loads 3,657 -> float bound; measured ~4.5 T (router 111 us, compressor kv
  150 us at 256 tokens [S5]) = 85 % of the 2.6 GHz float rate. So the R = 2 suspicion holds, by model and by the R4
  H16 contrast; a direct "no x reads" timing has never been run on these kernels (bench plan below adds it).
- Below the model, unexplained: o_a (2.64 Q8 / 2.39 Q6) with the same form as q_b. Its x stride is `g.qh * g.hd`
  floats (backend_sycl_v41_mt.inc:2564), q_b's is `g.qrank` (2841); o_b's x comes from the pushed arena. Test in bench.
- Ceilings: 5.73 T is the 2.8 GHz nominal rate [S7]; the port bench measured 5.19-5.35 T (G256 / G128 FP mode) [S4].

| form | float floor of its code (2.6 GHz) | load bound | expected | of 5.73 T |
|---|---|---|---|---|
| today X16R2 / K16R2, x from L1 | 5.0 | 3.61 | 3.08 avg, 3.54 best (measured) | 54 % / 62 % |
| T8 R4 (1.13 B/pair) | 4.73 (Q8), ~4.5 (Q6: 3 float decode ops/value) | 6.6 | 3.8-4.0 (85 % of floor) | 66-70 % |
| T16 R4 XW1 (1.07 B/pair) | 5.0 | 7.0 | ~4.25 if no spill | 74 % |
| T16 R2 + x in SLM | 5.0 | 7.7 (SLM rate) | <= 4.25; rux9 measured 0 % | <= 74 % |

## 3. Redesigns (every one keeps every output's bits)
**R1 (first): four rows per x read, scales per segment.** WsQ8 (K:2752) gets a segment-scale path (as LOOP 1: one
`ds[R]` per 32 chunks from the same `iq3::half` word; quant words one word group ahead; XW 1), selected like WsQ6S by
PF >= 100 through `WsWk` (K:3606). Registers (estimates): T8R4 ~72 floats/lane, T16R4 ~104. Q6: WsQ6S already has
segment scales, so `WsF<8,4,1,0,100>` / `WsF<16,4,1,0,100>` are template instantiations; Q5: `WsF<8,4>`. Picks:
WsPb<8 / 6 / 5, ..> (K:3617-3780); `ws_rows` (K:3785) already chunks any T >= 4, R >= 2 form. Gain: Q8 rows (102.7
ms, 3.13 T) at 4.0-4.25 T -> -22..-27 ms; Q6/Q5 (56.6 ms, 3.0 T) at 3.6-4.0 T -> -9..-14 ms; **total -30..-40 ms per
512-token block on card 2** (+ the shared gate/up pairs). Bits: each (row, token) chain is rowt's (same value, same x,
same order, same tree); only which sums advance together changes, as for every WsTab form (pb-1: 595 + 1,260
candidates, 0 differ [S5]). Risks: spills / private arrays (T4R4 on 8192 columns already has 4 KB private, entry_0380)
cost time, not bits; check 0 `mad` in the loop. Check: memcmp per (row, token) against production and the one-token rows.

**R2 (probe after R1): x staged once per work-group in SLM, T16 R2 kept.** New `DenseRowsWSS` beside DenseRowsWSC
(K:3037): work-group = 16 row blocks x 1 token group; per 256-column stage sub-group s copies token s's 1 KB as
uint32 (bitwise) into a 2 x 16 KB double buffer, one `barrier(local_space)` per stage; WsQ8 `word_group` / WsQ6S /
WsQ5 / WsH16 take an x-source policy (global or local `sg.load<8>`). Idle sub-groups past `rows` still fill and hit
every barrier (rux9's rule; today a row block past `rows` must not be read). Launch through `launch_rows<SLM>`
(backend_sycl_v41.hpp:2321 already passes a local pointer). Upside: SLM reads at 2.07x the L1 rate [S4], tokens
packed (no stride effect, cf. o_a). Against: rux9, the same idea on IQ2_S gate + up, measured +0.1 % / -1.2 % vs
production (predicted -26..-38 %), its 512-item form +60 % [S6]. Stop if < 10 % over the best R1 form.

**R3 (quick): no private scale arrays in the 256-token picks.** X16R2 on 8192 columns (o_b Q8) keeps `dv[2][8]` as a
2,048-B private array (entry_0370), K16R2 on o_a Q6 likewise (entry_0490). Placement decides 0..+23 %
(`pb256/README-private-mem.txt`). o_a Q6 -> K16R2S is one line in WsPb<6, 4096> (K:3709); o_b Q8 -> R1's segment
form. Small: o_b Q8 ran 3.61 T in tg103 vs 3.26 now (<= ~3 ms); the private cost in tp122 is not known.

## 4. One-card bench plan
- Extend `engine/tools/bench/bench_dense_ws.cpp` (memcmp per (row, token) vs one-token rows + 0xff stray-write check,
  cold flush, `REAL=1`): add a part that ports `pb256/bench_pb.cpp` PART_PICK's card-2 role list (lines 572-592: blk.2
  Q8, blk.30 Q6/Q5, blk.1 engram, 12-head rows) and chunk loop, candidates per role: production pick, T8R4 / T16R4
  segment forms, K16R2S for o_a Q6, later WSS; WS_SHARED for the gate + up pair.
- M = 256 (the halves), 192 and 129 (short last group), 128; chunks 0 / 32 / 64; rows 4267 and 384 for tails.
- Bitwise: whole output buffer memcmp vs production and one-token rows; any difference = exit 1, nothing timed.
- ISA gate per candidate (IGC dump): private 0, spill 0, `numGRF`, mix6.py float / int / send per word group, 0 loop `mad`,
  `rux6/tools/sendcheck6.py` PASS.
- Timing: REPS=21 cold medians, forms alternated; report us and T pairs/s. Diagnostics (timing only, not compared):
  "no x" (one x read per row instead of per word group) to measure the x share; o_a with x packed (stride 4096) vs
  the engine stride.
- Pass: bitwise PASS and >= 5 % faster at 129 / 192 / 256 for that role. Then picks behind a new OWN_PB bit (default
  off), six-card 3K trace identity with c131.sh's P5 (`OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1`) and a tlp timeline.
