# dtopk-1: the one-token index selects by candidates (OWN_IDX_DTOPK)

Status 2026-11-16: written, **not compiled, not run** (the host has 15 GiB RAM and GPU campaigns are running). Worktree
`/home/steve/dsv41-work/tp121`, detached, on top of tp120 (`ee129d837e`). Opt-in: `OWN_IDX_DTOPK` defaults to 0, and
at 0 the engine allocates, launches and exchanges exactly what it did before.

**In plain words.** With idxsplit-2, every card scores 1/6 of the index rows. Today all six cards then copy every
card's scores and each runs one big select over all of them. At long context that select is the slow part: one
work-group walks every row, which comes to about 3.2 ms per answer step at 705K. With dtopk-1 each card keeps only the
top 512 rows of its own sixth (at layer 20 also its top 2,048 blocks of 8 rows) and sends just those. Every card then
merges 6 x 512 candidates instead of the full row list. The result is bit for bit the same list, because the global
top 512 is always contained in the six local top 512s and the tie order is kept. Expected gain: about 0.4-0.6 ms per
answer step at 194K and about 3.3-3.9 ms at 705K (64 -> ~82-86 tok/s). Layer 20 is distributed too, past 2,048
blocks.

Abbreviations below: E = `experiments/own-xpu-runtime/engine`; K = E/`src/stage2/packet3/kernels/sycl_v41.hpp`;
B = E/`src/stage2/packet3/backend/backend_sycl_v41.hpp`; R = E/`planning/dsv41-fixtures/own_run_v41.cpp`;
T = E/`tools/bench/test_dtopk.cpp`. Line numbers are at `bcc7007857`.

## 1. Commits (tp121)

| commit | what |
|---|---|
| `a1cf3c41ef` | K: the four kernels (TopKSelD1, TopKSelDB1, TopKSelDQ, TopKSelDQB) + the exactness comment |
| `c4b54159c9` | B, R: OWN_IDX_DTOPK / OWN_IDX_DTOPK_MIN, the arena candidate area, dtk_index, the mode-2 check, the exit report; dev_index's two selects moved into dev_sel_blocks / dev_sel_rows (same launches) |
| `52eb3db66a` | T: the one-card bench |
| `bcc7007857` | T: NaN edge patterns (0xFFFFFFFF, signalling NaNs) and header wording |

## 2. What changed (file:line)

**Kernels (K:7325-7651).**
- K:7325-7355: design and exactness comment.
- K:7356 `dkey_val`: the inverse of TopKSelP::okey. A candidate's value is sent as the float whose order key is the key,
  so stage 3 recovers the key bit for bit. -0 comes back as +0, which has the same key.
- K:7360 `TopKSelD1<C>` (stage 1, rows; the engine uses C = 16, so 16,384 rows per work-group). This is TopKSelM1 over
  a card's share: p.n is the share's rows below len, cand_n is taken relative to the share, and gbase is the share's
  first row. Each work-group writes its top k as (value, global index) pairs in ascending index. Unused slots get
  index -1 (K:7418).
- K:7431 `TopKSelDB1<C>` (stage 1, blocks of 8; C = 8, so 8,192 blocks per work-group). This is TopKSelMB1 with two
  changes:
  - The layer's newest block is passed in (`newest`, +inf only on the share that holds it, K:7456).
  - Every item first zeroes its stripe of the card's whole mask `cz[0, len)` (K:7440-7447). Stage 3 then sets the kept
    rows.
- K:7508 `dq_load`: loads candidates 8 at a time from card-chunk addresses (card q / nc, slot q % nc, chunks u floats
  apart). An empty slot (index < 0) is marked in a pad bitmask and kept out of the select.
- K:7545 `TopKSelDQ<MAXC>` (stage 3, rows). This is TopKSelQ2's walk over tp x nr candidates:
  - `all` is decided by the real candidate count (K:7563).
  - It writes `index + add` in ascending index, then -1 up to outn.
- K:7594 `TopKSelDQB<MAXC>` (stage 3, blocks). This is TopKSelQB2's logic, compared line by line:
  - Kept blocks above -inf have their rows set to 1 (vec8 stores, scalar at the tail).
  - out[0] = count, then the flagged blocks in ascending order.

**Backend (B).**
- Options:
  - B:578-586: `idx_dtopk` (0/1/2) and `idx_dtopk_min` (default 32,768 rows).
  - B:658-664: >2 is refused. Without OWN_IDX_DSPLIT bit 1 the switch is turned off with one line of output.
- B:861: the exit report (`dtk_report`).
- B:3464: dev_index's split branch: `if (dtk_on(L, len)) return dtk_index(...)`.
- B:3504-3535: `dev_sel_blocks` / `dev_sel_rows`. Today's block and row select dispatch, moved out of dev_index
  unchanged (same kernels, same arguments, same order) so the mode-2 check can run them into shadow buffers.
- B:3563/3586: `ixd_score(..., bool gather = true)`. With gather false it returns after this card's score launch,
  before the pull. The score lambda stays in the same function, so its kernel name is unchanged.
- B:3659-3687: the dtopk block comment (design, reuse rule, check), plus the DtkGeo struct.
- B:3689 `dtk_geo`:
  - shares from `ixd_bounds`;
  - gr = ceil(largest share / 16,384), nr = 512 gr;
  - with blocks: gb = ceil(ceil(share / 8) / 8,192), nb = 2,048 gb;
  - chunk u = 2 nr + 2 nb floats, laid out as [row values | row indices | block values | block indices].
- B:3705 `dtk_on`: on when idx_dtopk is set, the area exists, len >= idx_dtopk_min, and the layer is not 20 or has
  more than 2,048 blocks. It depends on L, len and the options only, so it is the same on all cards.
- B:3708-3745 `dtk_index`:
  - mask rule as dev_index;
  - score share;
  - TopKSelD1 (gr groups);
  - at layer 20, TopKSelDB1 (gb groups);
  - one `ixd_pull` of the chunks at xscK (B:3733);
  - at layer 20, the block merge into s.blist / s.cand, then dcand_n / dcand_ok;
  - the row merge into cidx_mirror;
  - tile_cidx_ver, counters, and the mode-2 check.
- B:3747 `dtk_merge_rows` and B:3762 `dtk_merge_blocks`: MAXC 16/32/64/96 by qsel_span of the candidate count.
- B:3778 `dtk_check` (mode 2): today's gather (a second pull at xscD), optional `ixd_check`, then dev_sel_blocks /
  dev_sel_rows into shadows (`dtk_bl2`, `dtk_cd2`, `dtk_l2`), then `dtk_cmp`.
- B:3798 `dtk_cmp`: one 1,024-item work-group compares the list (512), the block list (count, then that many blocks)
  and the marks (len bytes). Device atomics add to `dtk_cnt[c]`. No host wait.
- B:3829-3854 `dtk_report`:
  - per card: layers by candidates, and in mode 2 the compared/differing counts;
  - final line: `OWN_IDX_DTOPK=2 check: N lists compared, M differ -> ALL SAME | MISMATCH | NOTHING COMPARED`.
- B:4175-4182: members (xscK, dtk_umax, counters, shadow pointers).
- B:5067-5083 the arena:
  - Only with the switch on: the candidate area (tp x u floats at max_seq, 64-byte aligned) goes after idxsplit-2's
    xscD.
  - It refuses max_seq + 64 >= 2^24 (indices travel as floats) and merge spans > 96.
  - It prints one `OWN_IDX_DTOPK=...` line.
- B:5114-5119: mode 2 only, the counts and shadow buffers (576 + 2,112 ints + max_seq + 64 bytes per card).

**Runner (R:432-441).** `OWN_IDX_DTOPK` = 0/1/2 (else die) and `OWN_IDX_DTOPK_MIN`, next to OWN_IDX_DSPLIT.

**Bench (T).**
- T:57 `geo`: ixd_bounds + dtk_geo with tp = 6.
- T:85 / T:102: host references (partial_sort with TopKSelP's order, blocks with the same max fold).
- T:166 / T:174: today's dispatch, as dev_sel_rows / dev_sel_blocks with default options.
- T:182-235: stage 1 per share into one candidate area (the bytes the pull would put on every card), then the merges.
- T:278: lengths. T:388: `PASS (441 cases)` is expected (9 lengths x 7 score families x 7 checks).

## 3. Why the result is bit for bit the same

Order: (order key, row) under "key descending, then row ascending" is a strict total order. It is TopKSelP's: okey
maps -0 to +0, negatives to ~bits and positives to bits | 2^31, and ties go to the lower row. Every select in the
engine (P, R, Q, BQ, the topk-m forms) implements exactly this order. The output is the selected rows in ascending row
order + 128, then -1.

1. **Stage 1 keeps every global winner.** Let S be the global top k (k = 512 rows, 2,048 blocks). A member x of S has
   fewer than k elements ahead of it overall, so fewer than k ahead of it inside its own work-group. So x is in its
   group's top k. Each stage-1 group runs TopKSelP's select over its positions, with the same keys and local positions
   ascending with global ones. So the union C of all candidates contains S.
2. **Stage 3 picks S out of C.** Each member of S has fewer than k elements of C ahead of it, and |S| = k. So the top k
   of C is S, and stage 3's threshold T and taken-tie count rem equal TopKSelP's over all rows.
3. **Ties go to the same rows.** Candidates in position order (card 0 chunk, group 0 first, ...) are in ascending
   global row order: groups ascend inside a share, and shares ascend in card order (ixd_bounds). So "the first rem
   candidates equal to T" are the rem lowest rows equal to T, the same ones TopKSelP takes. The output is written in
   that same position order, so it is ascending.
4. **Fewer real candidates than k.** If k >= the rows, or one group held them all, stage 3 keeps every real candidate.
   That is TopKSelP's k >= n branch (or C = S). Empty slots (index -1) are excluded by the pad bitmask, not by key 0.
   So a real score with bits 0xFFFFFFFF (a negative NaN with order key 0) still competes exactly.
5. **Transport.** Value = dkey_val(key) and stage 3 recomputes okey(value): identity on all 2^32 keys (okey is a
   bijection from floats with -0 folded to +0, and dkey_val is its inverse). The index travels as an exact float
   (< 2^24, checked at load). XchgPull copies bytes.
6. **Rows at or past len.** No group sees them: stage 1's n is the share's rows below len, as TopKSelP's n = len. Masked
   layers past 20: key = -inf for rows j < cand_n with mask 0. That is the same per row, since the share's mask pointer
   and cand_n are both shifted by the share's start.
7. **Blocks (layer 20).**
   - A block's 8 rows lie in one share (shares are 32-row multiples), so its key is the same max fold over the same rows
     (`m = m < v ? v : m` from -inf, NaN never taken).
   - The newest block is +inf on the one share that holds it.
   - The marks: every card zeroes [0, len) in stage 1, then stage 3 sets 1 for rows below len of kept blocks whose key
     is above -inf. That is TopKSelP<true>'s cand.
   - The block list: the flagged blocks ascending, count first (TopKSelQB2's code).
   - Every card computes the same marks and list from the same candidates, as today every card runs the same select.

**Layer 20 is distributed, but only past 2,048 blocks (len > 16,384).** At or below that every block is kept, the
blocks need all rows anyway, and today's path is short. Past it, the block select by candidates is exact by the same
argument (point 7). It also removes layer 20's full pull, which is the largest one: 2x the rows of the ratio-2 layers.
Rows and blocks travel in one pull: one exchange per layer, the same count as idxsplit-2.

## 4. Build (CPU only; after `six.active` clears, one compile at a time)

```bash
W=/home/steve/dsv41-work; C=bcc7007857
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
F="-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1 -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations"
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
rm -rf $W/src121; mkdir -p $W/src121
git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src planning tools/bench | tar -x -C $W/src121
cd $W/src121
# runner
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src -fsyntax-only planning/dsv41-fixtures/own_run_v41.cpp
nice -n 5 icpx $F -I planning/dsv41-fixtures -I src $GPU "-options -ze-intel-enable-auto-large-GRF-mode" planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp121 -lze_loader
# bench
nice -n 5 icpx -fsycl $GPU "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_dtopk.cpp -o $W/test_dtopk
# private memory (privmem-1): TopKSelD1 / TopKSelDB1 / TopKSelDQ / TopKSelDQB and the dtk_cmp lambda should need none
python3 -I $W/privmem_check.py $W/test_dtopk
python3 -I $W/privmem_check.py $W/own_run_v41_tp121
```

## 5. Test order (first failure, fault line or difference = STOP)

1. **Bench, one card** (a few MB of card memory, < 0.3 GB host):
   `ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/test_dtopk` must end `PASS (441 cases)`. Every row reads `y` in all eight
   columns: rows / masked / part, layer 20 rows / block list / marks, and the reference against the host.
   - The timing columns (us, normal scores) give today's rows select and block select against the slowest card's
     stage 1 plus the merges, and so the break-even for `OWN_IDX_DTOPK_MIN`.
   - Use `ONLY=194000` for one length and `NOTIME=1` to skip timing.
   - privmem_check: none of the four kernels at ~1 KiB per lane.
2. **Six cards, `OWN_IDX_DTOPK=2`** (stable mode, c118p's `run` pattern, binary `own_run_v41_tp121`). Each case must
   print `OWN_IDX_DTOPK=2 check: N lists compared, 0 differ -> ALL SAME` and match its reference. c118p's `run` already
   stops on `MISMATCH`. Add `grep -h "OWN_IDX_DTOPK" $D/$name.log >> $sum` so the counts land in the summary.
   1. p3k:
      `run p3k_dt2 $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 OWN_IDX_DTOPK=2 OWN_IDX_DSPLIT_MIN=513 OWN_IDX_DTOPK_MIN=513`.
      - Without both MIN overrides nothing qualifies and the line reads `NOTHING COMPARED`.
      - At 3K only layers 2/8/14 are distributed, because layer 20 has <= 2,048 blocks.
   2. x95k: `run x95k_dt2 $x95 256 $(mx $x95 256) $W/runs/e82/x95k_plain-ids.txt 256 $PL $P5 OWN_IDX_DTOPK=2`.
      - Layer 20 is distributed here (11,937 blocks).
      - The per-card lines must show `(N with layer 20's blocks)` > 0.
      - Optional: once more with `OWN_IDX_CAND=0`. Layers 24-36 then take the masked dtopk path (B:3709-3712), which
        the default never reaches past 16,384 rows.
   3. x200k: `run x200k_dt2 $x200 1024 $(mx $x200 1024) $W/runs/lc1-20261115T1936/x200k_def-ids.txt 1024 $PL $P5 OWN_IDX_DTOPK=2`.
3. **`OWN_IDX_DTOPK=1`: identity and speed**, same references. Speed is compared to the same binary with
   `OWN_IDX_DTOPK=0`, back to back:
   - x200k (194,000 tokens): IDS1024_SAME. tp118p measured 87.60 tok/s.
   - x400k (388,251): IDS1024_SAME vs `$W/runs/lc2-20261115T1948/x400k_def-ids.txt`. 76.90 tok/s before.
   - x700k (704,773): IDS1024_SAME vs `$W/runs/c118p-20261116T1117/x700k_def-ids.txt`. 64.40 tok/s before.
   - Mode 1 speed only. Mode 2 adds the old gather and selects back, so its times mean nothing.
   - Also p3k with the switch off and on: IDS256_SAME. With the default MIN it should not change anything at 3K; the
     `OWN_IDX_DTOPK=1: card c: 0 ...` lines confirm that.

## 6. Expected savings per answer step

The model:
- **Today:** TopKSelQ<96> ~61 us at 95-97K rows. TopKSelR ~1.43 ns per row. TopKSelBQ<32> ~36 us at 139K rows.
  TopKSelP<true> ~0.96 ns per row past 32,768 blocks.
- **dtopk:** stage 1 ~23-35 us per launch (its groups run in parallel). Merges near the one-work-group floor, ~15-25 us.
- **Pulls:** the same count; inbound bytes from 5/6 x len x 4 down to 5 u x 4. At ~17.5 KB/us that is the low end. The
  194K profile's XchgPull share (+0.28 ms) suggests the high end.

| context | layers (rows) | selects today | selects dtopk | inbound pull bytes per card, today -> dtopk | saved per step |
|---|---|---|---|---|---|
| 194K | 2/8/14 (97K): Q<96>; 20 (194K): BQ<32> + R | ~0.5-0.6 ms | ~0.21 ms | 1.58 MB -> 0.18 MB | **~0.4-0.6 ms** (11.4 ms step -> ~10.9: +4-6 %) |
| 388K | 2/8/14 (194K): R; 20 (388K): P<true> + R | ~1.8 ms | ~0.22 ms | 3.16 MB -> 0.28 MB | ~1.7-2.0 ms (13.0 -> ~11.2: ~+16 %) |
| 705K | 2/8/14 (352K): R; 20 (705K): P<true> + R | ~3.2 ms | ~0.25 ms | 5.74 MB -> 0.56 MB | **~3.3-3.9 ms** (15.5 -> ~11.6-12.2: 64 -> ~82-86 tok/s) |

Cross-check: today's step grows 4.1 ms from 194K to 705K. The model attributes ~2.7 ms of that to the selects and
~0.3-0.7 ms to the pulls, so most of the growth past 194K is what this removes. At 95K the gain is small: ~0.1-0.15 ms
(this agrees with idxsplit README 8.4).

## 7. Doubts (numbered, file:line)

1. **Nothing is compiled.** All code is checked by reading only. Expect a typo-level compile round (syntax-only first).
   The bench's `local_g` lambda (T:153) captures a parameter pack by copy (C++20).
2. **Registers / private memory** (K:7545, K:7594). TopKSelDQ/DQB<MAXC> hold kr[MAXC] plus pm[MAXC/32]. Only constant
   indices are used after `#pragma unroll`, as in TopKSelQ2.
   - MAXC 64/96 are instantiated but only used past ~1.3M rows. 16 is used up to 194K, 32 at 705K.
   - privmem_check must show none. If DQ<96> spills, drop the 64/96 forms and refuse longer max_seq at load
     (B:5072).
3. **Layer 20 mask zeroing inside TopKSelDB1** (K:7440-7447). Every card zeroes s.cand[0, len) in its stage-1
   launch: 2,048 items at 705K, ~22 rounds of 16 bytes per item. That should be a few us, but it sits on layer 20's
   critical path.
   - The alternative is a `qs.fill` before the score, which costs one more launch.
   - It is correct either way: in-order queue, and the merge runs after the pull.
4. **Pull cost** (B:3733). The exchange count is unchanged, so only the bytes shrink. If the pull's fixed cost
   dominates at these sizes, the low end of section 6 applies. XchgPull's ~4 us fixed latency is per layer either way.
5. **More launches** (B:3708-3745). There is one more launch per ratio-2 layer (D1 + DQ instead of one select) and two
   more at layer 20 (D1, DB1, DQB, DQ instead of BQ/P + R). That is +5 per card per step, 30 submissions from the host
   thread. If the host is on the critical path in one-token steps (~10 us "copy + decode launch calls" today), this
   could eat ~0.05-0.1 ms at 194K.
6. **`OWN_IDX_DTOPK_MIN` = 32,768** (B:585, R:441) is an estimate. At 95K the ratio-2 layers (47.7K rows, Q<64> ~52 us)
   gain only ~10-20 us each. Set it from the bench's times (section 5.1).
7. **Mode 2 is not mode 1's exchange sequence** (B:3782): it adds a second pull per layer. It is the same on all cards,
   so it is safe, but it is a different numbering than mode 1.
   - In mode 1, `OWN_IDX_DSPLIT_CHECK` does not cover dtopk layers, because there is no gather (B:3586).
   - Neither does `OWN_DEV_INDEX_CHECK`: ixd_on already excludes it (B:3551).
8. **The dev_sel_* refactor** (B:3504-3535) should be launch-for-launch identical with the switch off. Verify with
   `git diff ee129d837e -- <B>` and a p3k traced run with the switch off (TRACE_IDENTICAL against tp120).
9. **Indices as floats** (written K:7418, K:7496; read back K:7583, K:7651). Exact below 2^24. The load refuses max_seq + 64 >= 2^24
   (B:5070), well above the ~3.1M-row merge limit (doubt 11).
10. **NaN payloads** (K:7356, K:7524). The value is sent as raw bits through a float store, a byte copy (XchgPull) and a
    vec load, with no arithmetic. This assumes no step canonicalizes NaNs.
    - The bench covers quiet and signalling NaNs of both signs and 0xFFFFFFFF, but on one card without the pull.
    - Scores are softmax-free index sums, so NaNs should not occur in practice anyway.
11. **max_seq reach** (B:5072). One merge work-group holds 96 x 1,024 candidates: nr <= 16,384, so a share of <= 524,288
    rows, so len <= ~3.1M. Past that the load refuses; nothing is silently wrong.
12. **The false-pass guard** (B:3845-3853). `MISMATCH` is also printed when a card's device count of comparisons is not
    the host's count of checks made (a comparison never ran), or when a count cannot be read. `NOTHING COMPARED` (no
    layer qualified) is not a pass.
13. **Same decisions on every card** (B:3705). dtk_on uses only L, len and options, inside ixd_on (B:3551), which also
    uses `!px_q[t]`. This is idxsplit-2's existing rule; dtopk adds nothing per card.
14. **Reuse of the candidate area** (B:3659-3680 comment). A card rewrites its chunk at the next dtopk layer. Every peer
    has copied it before raising its flag of an exchange in between, and the writer waits for that first. This is
    XchgPull's rule, as for idxsplit-2's score rows, and only the six-card mode-2 runs test it (the bench has no pull).
15. **Layer 20 at <= 2,048 blocks keeps the gather** (B:3706). So the p3k check covers rows only. The block merge is
    first checked at x95k (5.2.2).
16. **Possible follow-ups, not done:**
    - Fuse layer 20's two merges into one launch (one work-group per form, two groups).
    - Fuse D1 + DB1, which read the same share.
    - Each saves one launch at layer 20.
