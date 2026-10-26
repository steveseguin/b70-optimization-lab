# QSA decode attention: exact restructure (2026-10-26)

SC117 Qwen3.8 Flash-Next IQ3_S, own engine, GSQ path, F32 activations + F32 KV, rank 1 alone on card 27
(0000:27:00.0), split 24, context 65536. Lab only; the canonical tree and the live service were not touched.

## Verdict

**Win, bit-exact.** `OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1` (default off) cuts rank-1 decode QSA attention
from 1446 to 263 us of device time per token (6 QSA layers on rank 1 at this split), and the rank-1 half at a
4096-row prompt from 18.076 to 16.835 ms (mean of three interleaved run medians, -1.240 ms, -6.9%). Every state compare against the unmodified
build has `differ_count` 0 with identical tokens, at 4096 (full 2,051-slot budget) and 300 (below budget).

Patch: `attention.patch` (unified diff against canonical `engine/src`, two files:
`stage2/packet194-expert-diet-engine/p49_qsa_kernel.hpp`, `p49_qsa_submit.cpp`). Evidence: `results.json`.
Microbenchmark and every variant tried (including losers): `bench/`.

## Root cause the brief did not name

`blocked(a)` (`!a.i(18)[0] || atomic_ref(a.i(15)[0]).load()`) is evaluated by **every lane** of the incumbent
`tiles<true,true>` and `combine<true,true>`, before the `start >= n` exit. A relaxed device-scope atomic load by
every lane of one address serializes: a probe kernel with 130x384 lanes takes 37 us with the atomic and 1.0 us
without. `tiles<true,true>` launches 24x65 work-groups x 128 lanes = 200K such loads per layer: the incumbent pass
costs 157 us even at n = 33 (2 live tiles), against 178 us at n = 2051. `admit_fast`, round2 and the specialised
subgroup kernels already read the flag once per group; the attention passes did not.

Reading the guard once per group alone (`OWNRT_ATTN_GUARD=1`, incumbent arithmetic and layout otherwise) takes
the tiles pass from 178 to 78 us (bench, hot) and the rank-1 half by 0.70 ms (17.373 vs 18.076 ms, final series).

## Final kernels (behind switches, default off)

Both new kernels are F32-only (dispatch requires `a.f32`), support 1-4 rows with per-row slot counts, and use the
guard once per group.

### `tiles_heads` (`OWNRT_ATTN_HEADS=1`)

One 512-lane work-group (16 subgroups) per (row, KV head, tile): the 12 query heads sharing a KV head and tile are
in one group. Each K element is loaded by 4 subgroups of the group and reused in registers for 3 heads, each V
element by 2 subgroups and reused for 6 heads (the incumbent loads every K and V row once per query head, 12x, from
separate work-groups).

- Scores: subgroup (dq = sub&3, hg = sub>>2); lane = slot; 3 query heads; dims 64dq..64dq+63 in natural order
  through a streaming balanced 64-leaf tree (binary counter, left + right); q is held lane-distributed and
  broadcast with compile-time indices. score = ((Q0+Q1)+(Q2+Q3)) / sqrt(256).
  *Exactness:* `score<true>()` forms v[e] = k[e]*q[e] for the lane's 8 dims, an in-lane balanced 8-leaf tree and
  then `lane_tree` (lane l + lane l+z for l%2z == 0): together the balanced 256-leaf tree over the dims in natural
  order. The decomposition into four aligned 64-leaf subtrees and ((Q0+Q1)+(Q2+Q3)) is the same tree, same
  operands, same operation order inside every node (lower + upper); the division is the same expression.
- Softmax per head: subgroup = local head, lane = slot. Tile max by `first_max` (below), exp(x - m) by
  `detmath::exp`, denominator by the incumbent `lane_tree`. p[256] = m, p[257] = den.
- Values: lane = (dimension, head half); 6 heads per lane; leaves weight*V in slot order, balanced 32-leaf tree by a
  binary counter (left + right), identical to the incumbent `vals[j] = vals[j] + vals[j+z]` tree. Weights are read
  once into registers (lane = slot) and broadcast.
- Loads that do not depend on the slot count (the row's slot ids, q) are issued before the guard; full tiles
  (valid == 32) run a body without per-slot conditionals. Partial-slot layout (258 floats per (row, head, tile))
  unchanged, so `combine<>` and `combine_blocked` both consume it.

### `combine_blocked` (`OWNRT_ATTN_COMBINE2=1`)

One 128-lane work-group per (row, head, 32-dimension block): 192 groups instead of 24. Every global read (the
head's raw tile values for the block, tile maxima, tile denominators, the gate) is issued before the guard (all
in-bounds: tiles c < C of the head always exist in the scratch; values of tiles >= count are never used).
Phase A: tile max by `first_max`, factors exp(m_c - m), denominator leaves d_c*f_c and their level 1-5 nodes by
subgroup butterflies (lower + upper). Phase B: subgroup s owns tiles 16s..16s+15, lane = dimension, leaves
p_c[dim]*f_c, levels 1-4 in registers. Phase C: levels 5-7 from local memory, tile 64's subtree, v/den,
v*sigmoid(gate).

*Exactness of the per-dimension and denominator trees:* `p30::attention::tree(x, n)` runs ceil(log2 n) levels with
x[i] = x[i] + (i+step < n ? x[i+step] : 0.f). That is exactly the balanced tree over 2^L leaves with leaves >= n set
to +0.f: a missing right child is a zero-padded subtree (0+0 = +0, and x + 0.f is what the incumbent adds), and
nodes at index >= n are only ever right children. The kernel evaluates that padded tree and returns the node of
level L (count <= 16: subgroup 0's level-L node; 32: Q0+Q1; 64: (Q0+Q1)+(Q2+Q3); 65:
((Q0+Q1)+(Q2+Q3)) + (x64 + 0.f six times), the six +0.f being tile 64's padded right subtree). Products are the
incumbent's (p*f, pd*f, weight*V), the output expression is v/den then v*sigmoid(gate) with
sigmoid = `ng::sigmoid` (computed earlier, same value).

### `first_max` (parallel max, argued exact)

The incumbent scans `m = -INFINITY; m = std::max(m, x)`, i.e. m = (m < x) ? x : m. That keeps the **first** of equal
maxima (so +0 vs -0 is decided by position) and skips NaN (m < NaN is false). `first_max(l, r)` (l covers the
lower indices) = isnan(r) ? l : isnan(l) ? r : (l < r ? r : l) returns, for any concatenation of two ordered
sequences, exactly that element: it is a homomorphism over ordered sequences, so any order-preserving tree
(a subgroup xor-butterfly that always puts the lower lane block on the left) followed by first_max(-INFINITY, .)
returns the scan's bits, including signed zeros, all-NaN (-INFINITY) and all -INFINITY inputs. The proof does not
rely on max being order-independent. (In the combine the max only feeds exp(m_c - m), which would be equal for
+0/-0 anyway; in the tiles pass it is also stored to p[256], so bit equality matters there.)

## Numbers

### Microbenchmark (bench/bench.cpp, card 27, n = 2051 slots, T = 1, median device time)

| variant | tiles hot | tiles cold* | combine |
|---|---|---|---|
| incumbent `tiles<true,true>` + `combine<true,true>` | 177.6 | 184.4 | 42.6 |
| incumbent, guard once per group (OWNRT_ATTN_GUARD) | 78.4 | 94.8** | 40.7 |
| tiles_heads v1 (384 lanes, lane = 8 dims, 1 head/subgroup) + guard + L1 prefetch (build c1) | 30.8 | 52.2** | - |
| **tiles_heads final (v3)** | **20.0** | **30.7** | - |
| **combine_blocked final** | - | - | **6.7** (5.7 cold) |

\* cold = 256 MB read kernel before every iteration (clean L2); \*\* = 256 MB write flush (dirty L2), which is
harsher (v3: 43.4). The in-engine profile matches the clean-cold column.

Phase split of the final tiles kernel (hot, phases removed one at a time, additive): prologue (launch, guard,
id/q loads, stores) 3.9 us, scores 6.4, softmax 5.4 (one detmath::exp chain per lane between two barriers), values
5.0.

### Rank-1 device profile in the engine (OWNRT_DECODE_PROFILE=3, 4096-row prompt, same binary c2, 16 halves)

| pass (per QSA layer) | incumbent | final |
|---|---|---|
| qsa_attention#0 admit | 3.7 us | 3.6 us |
| qsa_attention#1 tiles | 192.8 us | 32.3 us |
| qsa_attention#2 combine | 44.5 us | 7.9 us |
| total per token (6 layers) | 1446 us | 263 us |

(The profile build carries the lab-only rank.hpp export deferral from /dev/shm/ownrt-lab-prof32k; it is not in
the patch. Profiled half spans: 17.42 vs 16.17 ms.)

### End-to-end rank-1 half (no profiling; 48 decode halves; median)

Final pair built from the same canonical tree (06:0x, incl. the 05:35 session_checkpoint.hpp update):
ref2 = canonical, binary `002a2785e4e88d5b5603b11be69207696697b42eea85a7ddf52a51ddd20da0ef`;
c4 = canonical + attention.patch, binary `19d60bef5dc95a709332b0098d74d4dedecb94ae0d06c910535615e3f581f6b3`.
Runs interleaved ref2/c4 x3 on card 27, then the controls.

| run | prompt | env | median half ms | compare vs fin-ref2-p4096-a (or -p300) |
|---|---|---|---|---|
| fin-ref2-p4096-a | 4096 | - | 18.079 | (reference) |
| fin-c4on-p4096-a | 4096 | HEADS=1 COMBINE2=1 | 16.905 | differ 0, tokens equal |
| fin-ref2-p4096-b | 4096 | - | 18.106 | differ 0 |
| fin-c4on-p4096-b | 4096 | HEADS=1 COMBINE2=1 | 16.789 | differ 0, tokens equal |
| fin-ref2-p4096-c | 4096 | - | 18.042 | differ 0 |
| fin-c4on-p4096-c | 4096 | HEADS=1 COMBINE2=1 | 16.812 | differ 0, tokens equal |
| fin-c4off-p4096 | 4096 | switches off | 18.001 | differ 0 (patch inert when off) |
| fin-c4guard-p4096 | 4096 | GUARD=1 | 17.373 | differ 0 |
| fin-ref2-p300 | 300 | - | 16.570 | (reference) |
| fin-c4on-p300 | 300 | HEADS=1 COMBINE2=1 | 16.343 | differ 0, tokens equal |

Mean of medians at 4096: ref2 18.076, c4 on 16.835 (-1.240 ms, -6.86%); guard only -0.70 ms. Run-to-run spread
of the three ref2 medians: 0.06 ms.

Earlier lab-copy builds (same exactness outcome): ref 17.866, c1 heads-v1+combine2 16.961, c1 guard-only
17.368, c1 switches off 18.008 (control: about 0.8% run-to-run drift), c2 final kernels 16.761 ms.

## Exactness evidence

- Engine: `tp_rank1_driver.py compare` of the full state dump (1032 buffers, including every layer's qsa.y
  output, KV, logits, next token) against the unmodified build: differ_count 0, no one-sided buffers, identical
  48 decode tokens, for: 4096-row prompt (c1 heads-v1+combine2, c1 guard, c1 off, c2 final, c4 final x3, c4 off,
  c4 guard, and ref2 b/c against ref2 a) and 300-row prompt (c1 heads-v1+combine2, c4 final). See `results.json`
  `compares`. No kernel fault lines after any run; every engine process held only renderD131.
- Below the budget the gain is small by construction: the launch extent is position-bucketed, so at a 300-row
  prompt the incumbent launches about 10 tiles per head, not 65 (p300 halves: 16.570 -> 16.343 ms).
- Bench: bitwise output and every valid partial (258 floats per tile) against the incumbent kernels over 23 cases:
  n in {1, 2, 31, 32, 33, 64, 65, 300, 513, 1025, 1056, 2047, 2048, 2049, 2050, 2051}, 1/2/4 rows with different
  per-row n, and inputs with exact +0/-0, scaled K and repeated slot ids (exact score ties). 0 failures for every
  variant adopted or listed as exact below.

## Tried and closed (numbers: bench, n = 2051, us)

- SLM staging of the K and V tile (v1 layout): 50.5 hot / 73.7 cold vs 28.0 / 74.7: loss (barrier + occupancy).
- SLM K + L1-prefetched V: 35.1 / 55.6: loss.
- L1 prefetch of the whole tile (v1): hot 30.8 (from 28.0), cold 52.2 (from 74.7): win for v1, loss for v3
  (L1 or L2 hint, K+V or V only: hot 21.4-22.6, clean-cold 33.5-35.0 vs 20.0 / 30.7).
- tiles_v2 (v3 without early loads, full-tile body and register weights): 28.5 / 49.4.
- Explicit K/V load batching on v3 (6 shapes): 19.7-20.8 / 30.6-31.4: neutral.
- 6 query heads per work-group (2 groups per tile): 22.2 / 33.3: loss.
- V loads issued before the softmax barrier: 22.2 hot / 28.2 clean-cold: +2.2 / -3.5, not adopted (below 0.1% of
  the half either way).
- Large GRF for all kernels (SYCL_PROGRAM_COMPILE_OPTIONS=-ze-opt-large-register-file): v1 63.6 -> 72.2: loss.
- combine without the local-memory factor exchange (3 exp per lane, one barrier): 10.1 vs 6.7, and inexact for
  count < 65 (not debugged): loss.
- Not attempted: fusing combine into tiles (the last group of a KV head would combine 12 heads x 256 dims x 65 tiles
  serially, a longer tail than the 7.9 us pass), fusing admit (3.6 us/layer).

## Reproduce

```
rsync -a --exclude __pycache__ --exclude receipts engine/ LAB/engine/ && (cd LAB/engine/src && patch -p1 < attention.patch)
cd LAB/engine && python3 -B build.py OUT --jobs 6 --name sc117-engine
# launch template with the binary replaced, environment + OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1
flock /dev/shm/card27.lock ... tp_rank1_driver.py run --launch X.json --out RUN --steps 48 --prompt 4096 --batched --rows 32
tp_rank1_driver.py compare REF_RUN RUN
```
Bench: `icpx` with the manifest's compile flags, `-I engine/src -I bench`, run on card 27 via `bench/run_dev.py`
(`BENCH_RFLUSH=1` clean flush, `BENCH_N=2051,300`, `BENCH_SKIP_EXACT=1`).

## Next steps (decode tok/s)

1. Promote `OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1` through the normal service gate (both ranks run p49
   attention; rank 0 should gain similarly, unmeasured here). If a smaller step is wanted first,
   `OWNRT_ATTN_GUARD=1` is the one-line change worth about 0.5 ms per rank-1 half.
2. QSA attention is now 263 us of a ~16.8 ms half; the larger QSA cost is `qsa_select` (76 us/layer at 4K,
   ~277 us/layer at 30K in the earlier profile). Its TOPK stage-0 kernel (`select_scores_item`,
   specialised_submit.cpp) also reads the atomic guard per work item, but the launch extent is position-bucketed
   (rank.hpp: min(context, ((position+32)/32)*32)), so that is only ~1K (4K) to ~7.5K (30K) atomics per layer,
   about 1-5 us at the measured rate: the select cost is its real work and needs its own study.
3. Remaining attention levers, each <= 0.3% of the half: tiles cold path (in-engine 32 us vs 20 us hot; DRAM
   floor for 8.4 MB is about 15-19 us), admit fusion (3.6 us/layer), combine (7.9 us/layer).
