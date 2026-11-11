# qb-off-1: query-b offload from the two 16-head cards (opt-in, `OWN_QB_OFF`)

Patch: `/home/steve/dsv41-work/qboff/qb-off-1.patch`. It applies to the repo working tree as of 2026-11-11 10:30,
with attn-a1 and ck.patch (`OWN_MT_CK`) included (`git apply --check` passes at the repo root). It touches `backend_sycl_v41.hpp`, `own_run_v41.cpp`
and adds `kernels/sycl_v41_qboff.hpp`. Syntax check: build93's icpx flags with `-fsyntax-only` on a copy in
`tree/` (`syntax.sh`): plain build exit 0 and `-DOWN41_XWAIT` exit 0. The bf16 build fails on the unpatched tree as
well, for reasons outside this patch. Nothing was run on a card.

## What changes

- Cards 2 and 5 hold 16 attention heads; the other four hold 8. In every layer the four light cards wait about 22 us
  at the output-a exchange (who-waits, xw92).
- The query-b input (`s.qn`) is the same on every card. With `OWN_QB_OFF=k`, each heavy card's two neighbours compute
  k of its heads' query-b rows first, before their own query-b. Each neighbour ropes those rows with the same rope
  kernel and stores them straight into the heavy card's query buffer. The send is one way: the light card does not
  wait.
- The heavy card runs only its middle 16 - 2k heads. It waits for the two pushes inside its existing query-rope
  launch, so it has no extra launch. That wait comes before every attention form, including the `OWN_ATT_T=1` one-
  launch `SparseOutF` and the two-launch form, because both are in phase 1.
- Who computes which heads:

  | k | Card 2 keeps | Card 1 computes | Card 3 computes | Card 5 keeps | Card 4 computes | Card 0 computes |
  |---|---|---|---|---|---|---|
  | 4 | 20-27 | 16-19 | 28-31 | 52-59 | 48-51 | 60-63 |
  | 2 | 18-29 | 16-17 | 30-31 | 50-61 | 48-49 | 62-63 |

  - This differs from the suggested split: the heavy card keeps its middle heads rather than its first 8. With the
    default `OWN_TP_HEADS_MIN` layout, cards 1 and 4 already hold the query-b rows of heads 8-23 and 40-55, so they
    need no extra memory.
  - Cards 3 and 0 get an extra copy of k x 512 rows per layer.
- `OWN_QB_OFF=0` (the default) runs today's launches with the same arguments. The new kernels are in the module but
  never launched, and the query buffer stays where it is.
- Switches:
  - `OWN_QB_OFF=k` (1..7 on six cards; the useful values are 2, 3, 4).
  - `OWN_QB_OFF_WG=1..4` sets the work-groups per push (default 2; the l1-transport bench found 2+ groups faster than
    1).
- What gets refused, loudly, at start or in the step:
  - layouts where `OWN_TP_HEADS` splits groups in one-token steps;
  - card counts with no free light neighbour;
  - the non-fused attention path (`OWN_DIET=0` and similar);
  - the bf16 build.

## Why the bits stay the same

1. **The rows.**
   - One sub-group computes each query-b output row with `GemvQ8P<40>::row` (Q8_0 layers) or `GemvQ6KP<5>::row`
     (Q6_K layers). The row reads its packed bytes at `w + r * RB` and `s.qn`, and writes `y[r]`.
   - Nothing in it depends on which rows a launch covers, how many there are, or which riders share the launch. The
     same property already makes every TP slice exact, as well as `OWN_TP_HEADS_MIN`'s second row range.
   - The helper reads the same file rows through the same `pack_row`. Its `s.qn` comes from the same replicated
     kernels.
   - It launches the same `RowsP<RowsPair<.., DenseRows<..>>>` form as the heavy card, with `NoRows` riders instead
     of the mix finish and key rope.
   - The build uses `-fp-model=precise -ffp-contract=off`.
2. **The rope.** The helper runs today's query-rope kernel `RowsP<RopeRows<ActF32>>`, the same compiled kernel, on
   its heads, with the same cos/sin row (same tables, same position). The heavy card's `QbWaitRope` calls
   `RopeRows::row` on its own heads. The rope works element by element.
3. **The push is a pure copy** (vec4 loads and stores). After the step, the attention reads all 16 heads at
   `s.q + qo`, exactly as today. Only the buffer's location moves into the arena.
4. **Safety of the exchange** (documented in the new header):
   - The protocol is the one `XchgP` and `XchgPair` use: release fence, then a flag per work-group (flag words
     `128 + 16 * sender + g`, unused today), then a poll and an acquire fence.
   - The pushed rows are read only by later launches. xchg_direct_bench found that reads inside the waiting kernel
     itself can return stale cached lines.
   - The heavy card never writes the pushed heads' lines.
   - A helper can push layer L+1 only after its own layer-L output-a exchange has seen the heavy card's flag, and the
     heavy card raises that flag after its layer-L attention.
   - A missing push times out after `XSPIN` (about 0.9 s). The host then fails with "card-to-card exchange timed out
     waiting for card N", where N is the helper. It cannot hang silently.
   - In serial (trace) steps, phase 0 now submits the helpers first (order 0,1,3,4,2,5; only when the switch is on).
     That way a heavy card's queue never waits for a card that has not been submitted yet.

## Numbers (corrected from the brief)

The b1 profiles (`data/.../round19-b1-profiles/dec-card0..5.txt`, all six cards, one token) give per-layer launch
times:

| Launch | 8-head cards | 16-head cards | Difference |
|---|---|---|---|
| Query-b + mix finish, Q8_0 (27 layers) | 15.4-15.8 us | 23.4-23.5 us | ~7.9 us |
| Query-b + mix finish, Q6_K (13 layers) | 14.7-15.1 us | 21.7-21.9 us | ~7.0 us |
| Output-a, Q8_0 | 10.2-10.4 us | 18.1 us | ~7.9 us |
| Output-a, Q6_K | 12.2-12.6 us | 19.7 us | ~7.3 us |
| Attention (per step) | 1.149 ms | 1.172 ms | about the same |

- The query-b gap is ~7.6 us per layer (0.31 ms per step), not 11. Its fixed part is ~7.6 us, so halving the rows
  saves only ~8 us.
- Most of the light cards' ~22 us wait is query-b (~7.6) + output-a (~7.7). This patch can recover the first part
  only.
- Expected saving on the heavy cards, if the pushes land in time:

  | k | Per layer | Per step | Gain at ~10-11.7 ms/step |
  |---|---|---|---|
  | 4 | ~7.5 us | ~0.30 ms | ~2.5-3 % |
  | 3 | ~5.9 us | ~0.23 ms | ~2 % |
  | 2 | ~3.9 us | ~0.15 ms | ~1.3 % |

- The cost on the helpers at k = 4 is ~12 us per layer: rows ~8 us + rope ~1 us + push launch ~3 us (estimates).
  They have ~22 us of slack, of which ~7.7 is gone once the heavy cards finish earlier. So k = 4 sits near the
  balance point, and k = 3 leaves ~6 us of margin.
- Timing race at k = 4: the push lands ~15 us after the helper starts (rows ~8 + rope ~1 + push 5.7). The heavy
  card's own 4,096 rows take ~15.5 us. If the push is late, the heavy card stalls in `QbWaitRope`; the timeline shows
  this as a long `QbWaitRope<ActF32>` launch.
- Card memory:
  - Cards 3 and 0 need ~103 MB at k = 4 (27 x 2.79 MB + 13 x 2.16 MB) and ~52 MB at k = 2.
  - Cards 1 and 4 need nothing extra (with the default `OWN_TP_HEADS_MIN` union).
  - Every card gets +128 KB of arena and helpers +8 KB of staging. The upload's preflight counts all of it.

## What the gate should test (main thread)

1. **Same bits.** The 3-step trace must be byte-identical to `runs/ab1/base.trc` for `OWN_QB_OFF=0`, 2, 3, 4, and
   for 4 with `OWN_QB_OFF_WG=1`.
   - Trace steps run serially: this also checks the helpers-first order and that every pushed head matches (the
     `TT_Q` record gathers all 64 heads).
   - The 40/128/256-token answers must be unchanged for 0, 3 and 4.
2. **Speed, plain one-token.** Compare `OWN_QB_OFF=0` / 2 / 3 / 4, two alternated runs each.
3. **Guessing (code and analysis prompts).** Zero-guess checks run the one-token path (`OWN_CK1`), so the gain
   should show there too. The guess logs must match.
4. **With `OWN_ATT_T=1`.** Repeat one trace and one speed pair, since the wait must sit before the one-launch
   attention as well.
5. **Optional diagnostics.**
   - An `OWN_XWAIT` run at the best k: the light cards' output-a wait should fall from ~22 to ~14 us per layer.
   - An `OWN_TIMELINE` step: check `QbWaitRope` length on cards 2 and 5 (stall), and the helpers' `QbPush`.
   - Check the register mode of `QbPush` and `QbWaitRope` (128 expected). A 256 mode would add ~1 us of mode change
     each.

## Not done (would grow the patch)

- **Checks and blocks of up to 16 tokens** (`OWN_QB_OFF_MS_MAX`, the `_mt.inc` path). Query-b runs there through
  `gemv_m` into the block buffer `b.q` (M x 32,768 floats per token, not in the arena), with forms chosen by row
  count and size (`mt_tgw_rows`, ws picks). The per-token bits are the same in every form by the engine's rule, but
  the following is needed:
  - an arena region for the heavy card's block query (M x 128 KB);
  - M-token pushes (up to 128 KB at k = 4, 16 tokens; the push gets slower with size);
  - a wait folded into the `TokRows<RopeRows>` launch.
  That is a separate patch once the one-token gain is measured.
- **The draft's stages** (`hl[1]`): 3 layers per round, small.

## Risks

- **Overlap does not match the estimate.** If the helper's 2,048-row launch has the same ~7 us fixed part as
  query-b, the push lands after the heavy card's own rows and the gain shrinks or turns negative at k = 4. Try k = 3
  and k = 2.
- **Light cards become the slow ones** at k = 4, since their margin is ~2 us. Card 0 also does the lead's host work.
  Card 5 (0000:e3) clocks lower; a per-card k would be the next step if the timeline asks for it.
- **New kernels in the module.** Two kernels are added, plus the `NoRows` dense form for 1,280 columns. No shared
  non-inlined helper gains a caller (`RopeRows::row` and the GEMV rows are always-inline), so other kernels' machine
  code should not change. The XWAIT note found that a second caller of a non-inlined helper can change machine code;
  a speed drop at `OWN_QB_OFF=0` against tp93 would point there.
- **Host waits in phase 0.** Serial steps rely on no host wait in a heavy card's phase 0 after its query-b:
  - true today, since `prof()` never waits in TP and `dev_index`'s `sync_rows` copies nothing in TP decode;
  - `OWN_DEV_INDEX_CHECK`-style debug waits would time out at XSPIN in trace mode (loudly);
  - the helpers-first order covers the cards; it does not cover such a wait on the heavy card itself.
- **Cache of the pushed lines.** It relies on the same platform behaviour as today's `XchgP` pushes into `s.ob` and
  `s.oa`: a later kernel sees the peer's stores. The heavy card's caches are never dirty on those lines.

## Gate result (tg95b) and why there is no gain (2026-11-11, CPU analysis)

Bits: identical everywhere. Speed: no measurable gain. Cause, from the two existing check timelines (three zero-guess
checks each = the one-token path; tg93/tl_ck.txt default, tg95b/tl_ck.txt k=4; `python3 -I qbdiag.py FILE`, outputs
diag-tg93-default.txt and diag-tg95b-k4.txt):

- Default: the two 16-head cards reach output-a 13.1 us per layer after the last light card (median); they are last 89 %.
- k=4: the heavy cards' query-b drops 23.7 -> 15.8 us (Q8_0) and 21.6 -> 14.7 us (Q6_K); the wait kernel costs
  1.8 us against the 0.9 us rope it replaces, so the heavy cards gain ~6.7 us per layer. The push is on time (ends
  1.5-2 us before the heavy card's own query-b; hypotheses b and c are out).
- But every light card now spends 13.1 us more before its own query-b: extra rows 7.9 us (2,048 rows; a small launch
  runs at ~3.8 ns per row against ~1.9 ns per row saved at the margin of the heavy card's big launch), rope 1.0 us,
  push 4.0 us, four launch gaps ~0.4 us. So the light cards are now last (5.1 us ahead of the heavy cards, median),
  the layer gets ~1.75 us shorter, the step ~0.07 ms (0.7 %) - inside the noise (hypothesis a).
- Best possible with these costs: gain(k) = min(1.9k - 0.9, 13.1 - 2.0k - 5.3 + ~1.2) us per layer -> ~3 us at k=2 or 3,
  ~0.12 ms per step, ~1.2 %. The fixed ~5.3 us per helper per layer (rope + push + gaps) eats most of the 13.1 us gap.
