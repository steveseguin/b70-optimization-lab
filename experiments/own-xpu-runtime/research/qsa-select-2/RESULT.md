# QSA select (decode): exact restructure (2026-10-26)

SC117 Qwen3.8 Flash-Next IQ3_S, own engine, F32 activations + F32 KV, rank 1 alone on card 27 (0000:27:00.0),
split 24, context 65536, `OWNRT_SELECT_TOPK=1` (production), and `OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1` in every
run (as the service). Lab only; canonical tree and service untouched.

## Verdict

**Win, bit-exact.** `OWNRT_SELECT_FAST=1` (default off; requires `OWNRT_SELECT_TOPK=1`) cuts qsa_select device
time per QSA layer on rank 1:

| prompt | stage 0 (scores) | stage 1 (top-k + order) | total |
|---|---|---|---|
| 4096 | 15.8 -> 5.0 | 60.7 -> 14.2 | **76.4 -> 19.2** |
| 30000 | 20.0 -> 10.8 | 70.6 -> 16.6 | **90.7 -> 27.4** |

(before -> after, us, rank-1 device profile, OWNRT_DECODE_PROFILE=3, 6 QSA layers per token on rank 1). Rank-1 half: 4096-row prompt 16.748 -> 16.401 ms (mean of 3 interleaved
run medians, -0.348 ms, -2.1%); 30000-row prompt 16.839 -> 16.448 ms (-0.39 ms) in the pair run at equal host load
(see below). Every state compare against the unmodified build: differ_count 0, identical tokens (4096, 300 and
30000-row prompts).

Patch: `select.patch` (against canonical `engine/src`: `stage2/packet194-expert-diet-engine/specialised_submit.cpp`
dispatch + new `select_fast.hpp`). Evidence: `results.json`. Bench and every variant: `bench/`.

## Where the time went (reference)

- **Stage 1** (`select_topk_row`, one 1024-lane work-group per row, i.e. one Xe core): the phases up to the
  compaction cost 9 us (4K) / 17 us (30K); the rest (about 50 us of 60 at 4K) is the final rank count: lanes
  0..511 each loop over all 512 selected blocks with two local-memory loads per comparison, lanes 512..1023 idle.
- **Stage 0** (`select_scores_item`, one work item per block): every lane reads its own 512-byte key row in strided
  pieces (32 rows per load message), few threads (2051 items at 4K = 64 SIMD32 threads for 32 Xe cores), and every
  item first does the device-scope atomic guard load (the pattern found in the attention passes).

## Final kernels (`select_fast.hpp`)

### Stage 0: `select_scores_sg<BPS>`

One 32-lane subgroup per BPS consecutive blocks of a row (BPS 4 if the launch extent <= 8192 positions, else 8).
Lane l loads keys 4l..4l+3 of each block (the subgroup reads the 512-byte key row in one coalesced access) and q
4l..4l+3 of the four heads once.
- Per (block, head): the group sum ((p0+p1)+(p2+p3)) with p = q*key: `select_scores_item`'s leaves, same order.
- The 32 group sums go through the same balanced 32-leaf tree (strides 1..16, node = lower lane block + upper lane
  block). This uses a transposing butterfly: at the first log2(BPS) levels, lanes l and l^z exchange the half of
  their pending blocks that the other keeps; at the remaining levels both lanes hold the same block and add
  lower + upper.
- Lane l ends with block b0 + (l & (BPS-1)). score = (((0.f + max(0,d0)) + max(0,d1)) + max(0,d2)) + max(0,d3),
  divided by sqrt(128): the incumbent expression, with std::max(0.f, d) as written.
- The -1 fill of slots [0, S) is done by subgroup gi for slots 32gi..32gi+31.
- The guard is read once per subgroup. Invalid-position handling is unchanged (fail from global item 0).

### Stage 1: `select_topk_row2`

Same algorithm and the same intermediate values as `select_topk_row`. Only the data placement, the collectives
and the final count change.
- The row's scores are loaded once into registers. Lane l owns blocks [l*C, l*C+C) with C = ceil(n/1024) <= 16,
  the ownership the incumbent compaction already used. The finite check is over all n, with std::isfinite, before
  anything else, as before.
- Radix select of T (the count-th largest bit pattern) with the same three digits (30..20, 19..9, 8..0) and the
  same descending-scan digit search:
  - Each pass has its own histogram, cleared once up front, and its own `found` slot, so a pass needs 2 barriers
    instead of 4.
  - Pass 0 counts into 4 histogram copies chosen by subgroup, to spread same-address local atomics (scores share
    a few exponents); the search sums the copies per bin.
  - All of this is integer counting, so T and `need` are the same numbers.
- Compaction in index order with one packed scan instead of two.
  - Before lane l, the selected count is (gt before l) + min(ties before l, need). Inside a lane, ties are taken
    while the running tie count is below need.
  - That is exactly the incumbent's tie_before / at scans: ties are taken in index order until need is reached,
    so the selected set and the order of `sel_idx` / `sel_val` are identical (index order).
  - `taken` is read from the scan's last lane instead of a group reduce.
- Rank among the selected set is spread over all 1024 lanes. Lane L counts element i = L & 511 against half (L>>9)
  of the set, 32 keys per local-memory load, broadcast across the subgroup. The two halves are summed: integer sums
  of the same 0/1 terms, independent of order.
- **Tie handling (argued):** the incumbent counts `other > v || (other == v && sel_idx[j] < b)`.
  - Selected scores are finite and >= +0, and never -0: score starts at 0.f and adds `std::max(0.f, d)`, which is
    +0 for d = -0, negative or NaN; the sum of +0 and positives is never -0; dividing by sqrt(128) > 0 keeps the
    sign. Non-finite rows are refused by the finite check first.
  - For such floats, a > b <=> bits(a) > bits(b) and a == b <=> bits(a) == bits(b) (the same property the
    incumbent radix select already relies on).
  - Positions in the compacted set increase with block index, so `sel_idx[j] < b` <=> j < i.
  - Hence the term is `key_j >= key_i + (j >= i ? 1 : 0)` (j == i never counts). Equal bit patterns are resolved
    by index order, exactly as now. Each rank is the same integer, so the ids are written to the same
    `a.i(2)` slots.
- Writes of the 4 ids per selected block and the tail (pos+r+1 - 4n ids at slot 4*count) are unchanged. Failure
  paths are unchanged: the non-finite refusal; `taken != count` refused (unreachable).
- The compaction's local-memory writes are additionally bounded by `at < count` (never limits on the exact path).
- Host checks: `ceil(cap/1024) <= 16` and `budget/4 <= 512`, otherwise the incumbent kernel runs.

## Guard pattern (per-lane device-scope atomic read of the error flag) in the QSA passes

- select stage 0 (`select_scores_item`): **per work item** (n_items = max(extent/4, 2051) per row). Fixed in
  `select_scores_sg` (once per subgroup).
- select stage 1 (`select_topk_row`): once per work-group (lane 0 + group_broadcast). Already fine.
- admit (`admit_fast`, attention pass #0): once per work-group. Fine.
- qsa_prepare and qsa_append_pool: production dispatch class `packet18` = the ng group kernels (kernels.hpp), which
  read the flag once per group (`t.each(1, ...)` + barrier). Fine.
- Outside QSA: the generic `specialised` body (`body<Code,Stage>`, used by the production classes for the norms,
  combines, route, gather, argmax, streams and ple.add) reads the flag per work item. Example: the 2560-wide norm
  stage 1 has 2560 items per row, so about 2 us per call at the rate measured in the attention study (50K
  lanes = 36 us). The 4K profile shows 49 norm calls per token at 8.1 us. This is an estimate, not measured: the
  next cheap lever outside this brief.

## Numbers

### Microbenchmark (bench/bench_select.cpp, card 27, context 65536, T = 1, median device time, us)

| kernel | 4096 hot | 4096 cold | 30000 hot | 30000 cold |
|---|---|---|---|---|
| stage 0 incumbent `select_scores_item` | 16.3 | 17.8 | 19.1 | 21.4 |
| stage 0 `select_scores_sg<4>` | 3.3 | 5.9 | 8.0 | 12.4 |
| stage 0 `select_scores_sg<8>` | 4.1 | 7.6 | 6.7 | 12.3 |
| stage 1 incumbent `select_topk_row` | 60.2 | - | 68-89 | - |
| stage 1 original all-pairs `select_rows<1>` | 29.4 | - | 221.7 | - |
| stage 1 `select_topk_row2` final | 13.1 | - | 15.0 | - |

Stage-1 versions (4K / 30K, us):
- v1 (registers, rank split with float compares): 29.4 / 34.4.
- v2 (integer-threshold rank + packed compaction scan): 13.4 / 18.0.
- v3 (2 barriers per radix pass, taken from the scan): 13.0 / 17.7.
- v4 (pass-0 histogram copies; NH0 = 1 / 4 / 8): 13.0 / 17.9, **13.1 / 15.0**, 13.9 / 15.5.

Final phase split at 4K (cumulative): finite 1.9, radix pass 0 4.3, passes 1-2 7.7, compaction 9.8, rank 12.9.

Bench exactness: ids (all 2051 slots per row), every row score (bits) and the error flag against the incumbent
TOPK path over 25 cases:
- positions 0, 2, 3, 100, 1500, 2030, 2046-2051, 4000, 4095-4099, 9999, 29990, 30000, 65530;
- 1, 2 and 32 rows (prefill chunk shapes);
- normal keys; many exact score ties (repeating key patterns, every third block all-zero); almost all zero keys
  (T = +0, ~7400 tied blocks resolved by index).
The original all-pairs kernel serves as a third oracle. 0 failures for every variant.

### Rank-1 device profile in the engine (per QSA layer)

| pass, per QSA layer (us) | 4096 before | 4096 after | 30000 before | 30000 after |
|---|---|---|---|---|
| qsa_select#0 (scores) | 15.8 | 5.0 | 20.0 | 10.8 |
| qsa_select#1 (top-k, order) | 60.7 | 14.2 | 70.6 | 16.6 |
| qsa_select total | 76.4 | 19.2 | 90.7 | 27.4 |
| per token, 6 layers | 458 | 115 | 544 | 164 |
| profiled half span (us) | 16235 | 15851 | 16393 | 15988 |

Before at 4096 and both "after" columns: profile build c2P (canonical at 06:23 + select.patch + the lab-only
rank.hpp export deferral) with `OWNRT_SELECT_FAST` off / on, 16 halves (8 at 30000). Before at 30000: refP
(the same tree without the patch). qsa_prepare (7.7 us), qsa_append_pool (3.3 us) and qsa_attention
(44 us) are unchanged.

### End-to-end rank-1 half (48 decode halves, median)

Final pair from the same canonical tree (incl. the attention patch and the prefill agent's 06:xx changes):
ref2 = canonical, binary `84bf7fcb34da10b5cbcc80122eb64402a6269f321fd1fd879a94b8ae288fd909`;
fin = canonical + select.patch, binary `3783702a90ef32d47e54f76e78470ba439c577d118304c039519de86a18dc564`.
All runs with `OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1`; fin runs with `OWNRT_SELECT_FAST=1`.

| run | prompt | median half ms | engine wait / enqueue ms | host load 1m | compare |
|---|---|---|---|---|---|
| fin-ref2-p4096-a / b / c | 4096 | 16.729 / 16.769 / 16.747 | - | - | (reference a; b, c not compared) |
| fin-on-p4096-a / b / c | 4096 | 16.409 / 16.377 / 16.415 | - | - | differ 0, tokens equal (x3) |
| fin-off-p4096 (switch off) | 4096 | 16.744 | - | - | differ 0 (patch inert when off) |
| fin-ref2-p300 / fin-on-p300 | 300 | 16.333 / 16.271 | - | - | differ 0, tokens equal |
| fin-ref2-p30000 (pair a) | 30000 | 16.832 | 13.07 / 3.70 | 3.8 | (reference) |
| fin-on-p30000 (pair a) | 30000 | 16.802 | 12.51 / 4.16 | 6.5 | differ 0, tokens equal |
| fin-on-p30000-b (pair b, run first) | 30000 | 16.448 | 12.66 / 3.72 | 1.3 | differ 0 |
| fin-ref2-p30000-b (pair b) | 30000 | 16.839 | 13.23 / 3.52 | 1.3 | differ 0 vs pair-a reference |

At 30000 the device-side saving is consistent: engine-measured device wait per half -0.56 / -0.58 ms. Pair a's
candidate ran while the live service was busy (host load 6.5 vs 3.8), and its host enqueue loop grew by 0.46 ms
(p10 4.03 vs 3.42 ms), hiding the gain. Pair b ran at equal load: -0.39 ms. Mean over both pairs: -0.21 ms. Even
at equal load the candidate's enqueue loop was 0.2 ms longer at 30000 (not at 4096); not explained, to be watched
in the service gate. 300-row prompt: -0.06 ms (the launch extent and the select work are small there).

## Incident (my bug, caught, no device fault)

The first final candidate (binary f5e74f2d...) raised the pass-0 histogram to 4 copies (10752 ints) in the kernel
and the bench, but the engine's local accessor still allocated 4608. The overrun corrupted the histogram, the
kernel's own `taken != count` check set the error flag, and the rank stopped with "sticky rank error in batched
prefill". There was no kernel/GuC fault line and only renderD131 was held. Fix: one constant (`select_hist_ints`,
`select_found_ints`) used by the engine launch and the bench. The bench now also covers 32-row prefill shapes.
Evidence: lab `failed-hist-overrun/`.

## Tried and closed

- Stage 0 with 16 / 32 blocks per subgroup: slower at 4K (5.9 / 10.1 us hot), equal or slower at 30K.
- Rank count with float compares, one element per lane pair: 14.7 / 17.7 us for the rank phase. Replaced by the
  integer threshold form (3.1 us).
- Barrier trimming in the radix passes: about 0.4 us.
- 8 pass-0 histogram copies: worse than 4 at both sizes.
- Not attempted: replacing passes 1-2 by an exact rank among the boundary-bin candidates (about 3 us/layer at
  most), and fusing stage 0 into stage 1 (the score pass needs many work-groups, the top-k one).

## Reproduce

Apply `select.patch` to canonical `engine/src`, build with `build.py`, and run the launch template with the binary
replaced and environment + `OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1 OWNRT_SELECT_FAST=1`:
`tp_rank1_driver.py run --steps 48 --prompt 4096 --batched --rows 32`, then `compare` against the unpatched run.
Bench: `bench/build_bench.sh` (add `-DSELECT_NH0=n` to vary the copies), run via `bench/run_dev.py`.

## Next steps (decode tok/s)

1. Promote `OWNRT_SELECT_FAST=1` (with the existing `OWNRT_SELECT_TOPK=1`) through the service gate. Both ranks run
   6 QSA layers, so expect about 0.35 ms per card per decode half at 4K-30K contexts (device: -57 us/layer at 4K,
   -63 us/layer at 30K).
2. Read the guard once per subgroup in the generic `specialised` body (norms, combines, route, gather, argmax,
   streams, ple.add). Same exactness argument as here, and an estimated ~0.1 ms per rank-1 half (49 norm calls at
   8.1 us each, of which roughly 2 us is per-item atomics). Cheap to do; measure with the same harness.
3. Host enqueue loop: 3.4-4.2 ms per half for 880 launches. At long context with a busy host it became the bound
   (pair a above). Fewer launches or captured graphs are now worth more than further select kernel work.
4. Remaining select work, each <= 3 us/layer: exact rank among the pass-0 boundary-bin candidates instead of radix
   passes 1-2; stage 0 at 30K is DRAM-bound (10.8 us for 3.8 MB of keys).
