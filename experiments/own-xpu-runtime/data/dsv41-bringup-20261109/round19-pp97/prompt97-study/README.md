# prompt97: time budget for reading a 3K prompt on six B70 (DeepSeek V4.1 Flash, own SYCL engine, tp97)

2026-11-11. This is a CPU-only analysis: nothing ran on the GPUs, nothing was built, and no repo file was edited.
Inputs:

- the OWN_GPROF=2 prompt profiles in `runs/pp97`. They are byte-identical to
  `experiments/own-xpu-runtime/data/dsv41-bringup-20261109/round19-pp97`.
- the tp92 profiles in `runs/pp92`, to compare against.
- the unprofiled 3K reads in `runs/tg96b`, `tg97b` and `tg97c`.
- the six-card overlap pre-check in `runs/xov1`.
- the item E design in `xov/design.md`.
- the register-mode census in `pa/grf_pr.txt`.
- the engine source.

Every number below comes from `tools/*.py` and the tables in `tables/`. The ranked list for the coordinator is in
`README-prompt97.txt`.

## In plain words

- **Today.** Reading the 3,323-token test prompt takes 6.80 s, about 489 tokens a second.
- **The hard limit.** The arithmetic alone needs about 2.0 s. That is the arithmetic done the one way that keeps every answer bit-identical: a separate multiply and add, at the cards' full rate. Moving the data the cards must swap needs about 0.7 s more. So today is about 2.5x the hard limit, not 5x. A "5x" figure counts each multiply-add as one fused instruction, and the fused instruction rounds differently, so we cannot use it.
- **Where the 6.8 s goes.**
  - expert matrices: 2.7 s
  - the other matrices: 2.0 s
  - waiting on card-to-card exchanges: 1.0 s
  - everything else (attention, indexer, norms, gaps): 1.0 s
- **The biggest win.** Let each card send its data while it keeps computing. Today every card stops at each of its 243 exchanges per 64-token piece. This saves about 0.6 s. It is a big rewrite of the block schedule. The six-card pre-test has already passed.
- **The next four:**
  1. Read the prompt in 256-token pieces, with the kernel choices that are best per token. About 0.45 s. This is mostly a table change plus two small kernels.
  2. Faster expert kernels. About 0.4 s, but uncertain.
  3. Fix three matrix kernels that lag. The router-type rows re-read their inputs for every row, the 6-bit and 5-bit layers are slow, and the 6-bit kernels got slower in tp97. About 0.3 s, and these are small jobs.
  4. Stop all six cards from repeating the same q_a and kv rows. About 0.25 s.
- **All together.** About 2.2 s off, so roughly 4.6 s for the 3K prompt (about 720 tok/s). The range is 630 to 870 tok/s. Every lever keeps the answers bit-identical.
- **Ruled out or small:**
  - Two groups of cards working on different layers would need a second copy of the weights, and it does not fit.
  - The "16-head card" imbalance does not happen while reading a prompt. There the cards hold 12 or 8 heads, and what is left of the imbalance is worth about 0.06 s.

## Rates and floors (what "floor" means here)

| rate | value | why |
|---|---|---|
| FP32 issue | 11.47 T ops/s per card | 32 Xe-cores x 8 XVEs x 16 lanes x 2.8 GHz |
| multiply-add | **5.73 T/s** | The reference multiplies and then adds, two instructions. The build uses `-ffp-contract=off`, and the fused FMA rounds once, so it is not allowed. No DPAS / XMX, bf16, tf32 or int8 dot products. The 230 W cards run about 2.6 GHz under ALU load (e68), about 7 % below this rate. |
| card memory | 550 GB/s | 608 GB/s peak; the output head reaches 572 GB/s |
| peer link | 25 GB/s per card, + 2.5 us per exchange | `xchg_bw_bench` with all six cards pulling at once |
| L1 / data port | 8.28 TB/s per card (92.4 B/clock/Xe-core) | predict.py fit; this is where activations ("x") are read |
| expert decode | 7 instructions per weight per expert group | prefill plan calibration |

Floors of the whole read on card 2 (`tables/lever_estimates.txt`, top):

| floor | s | today / floor |
|---|---|---|
| strict FP32: every multiply-add at 5.73 T/s, nothing else | 1.97 | 3.4x |
| + exchange bytes at 25 GB/s, not overlapped | 2.69 | 2.5x |
| today's tile shapes (x read once per 2 dense rows through the port, expert weights decoded once per group), exchanges hidden | 3.35 at 64, 2.79 at 256 | 2.0x / 2.4x |

## 1. One 64-token block on the pace card

**Which card sets the pace.** Prompt blocks of 16 tokens or more use the head layout 12,12,12,12,8,8
(`OWN_TP_HEADS` 3,3,3,3,2,2). The 8,8,16,8,8,16 layout belongs to one-token steps. So card 2 and card 0 both hold
12 heads here; no card holds 16 heads in a prompt.

Card 0 (0000:03, a 275 W card) runs every compute family 5-7 % faster than card 2 (0000:43, a 230 W card). It
spends what it saves waiting in the exchanges: 1.377 s against 1.027 s, which matches its compute saving within
8 ms (`card0_vs_card2.txt`). So the pace is set by the 12-head 230 W cards, and card 2 is a fair proxy for them.

Per 64-token block on card 2: kernel totals over the read divided by 52 blocks (`ledger_b64.txt`):

| family | ms / block | floor ms | x floor | what bounds it |
|---|---|---|---|---|
| dense rows (q_a, kv, q_b, o_a, o_b, router, shared, engram) | 39.0 | 17.7 (FP32) | 2.2x | FP32 in name; in practice the x port: 2-row tiles read 2 B of x per multiply-add, 25.2 ms / block at 8.28 TB/s |
| experts gate + up | 32.3 | 10.5 (FP32) | 3.1x | issue: products + weight decode (23.1 ms with decode) |
| experts down | 19.9 | 5.3 (FP32) | 3.7x | issue (11.7 ms with decode) |
| experts other (grouping, SwiGLU, combine) | 2.3 | 0.1 | 30x | grouping is a 47 us serial kernel |
| attention | 5.9 | 3.2 | 1.9x | FP32 |
| compressor + indexer | 4.1 | 1.1 | 3.8x | H16 rows without weight reuse |
| norms + mix dot rows | 4.0 | 0.45 | 9x | launches (7-14 us small kernels) |
| **exchanges** | **19.75** | 13.9 (link) | 1.4x | link + waiting, fully exposed |
| small ops | 0.3 | 0.1 | | |
| **all kernels** | **127.6** | 52.2 | 2.4x | |
| gaps (6.80 s - kernels) / 52 | 3.2 | 0 | | |

Weight bytes are never the bound. The dense byte floor is 0.16 s per read and the experts' is 0.70 s, while their
FP32 floors are 0.92 s and 0.82 s.

**Exchanges per block.**

- The 12-head cards launch **243 per block**:
  - 80 `XchgPull2`: output-a plus the attention-mix partials, and expert act plus the FFN-mix partials;
  - 83 `XchgPull`: output-b, ffn rows, and 3 engram launches;
  - 80 `XchgPair`: the half-group head swap, two per layer.
- The 8-head cards launch **163**, with no pair swaps.
- Card 2 pulls 332 MB per block, about 5.2 MB per token and 17.3 GB per read.

| kind (card 2, 64) | ms / block | floor ms | x floor | effective GB/s |
|---|---|---|---|---|
| XchgPull2 | 10.87 | 8.71 | 1.25x | 19.6 |
| XchgPull | 8.12 | 4.12 | 1.97x | 12.1 |
| XchgPair (two-card link, faster than 25 GB/s) | 0.76 | 1.04 | 0.73x | 27.6 |

**Exposed waiting.**

- Nothing overlaps today, so all 19.75 ms per block are on the critical path.
- 5.9 ms of that is above the byte + sync floor: round trips plus waiting for a slower peer. That is 0.31 s per read on card 2 and 0.66 s on card 0.
- The profile times each exchange from start to end, so it cannot split the copy from the wait.
- No prompt-block timeline exists. `OWN_TIMELINE` records only answer steps and guess checks, and the tl85 analysis has a broken clock mapping. A prompt-block timeline is the one missing measurement for lever 1.

## 2. Blocks of 128 and 256

Per read on card 2 (`families_by_block.txt`):

| family | 64 | 128 | 256 | kind |
|---|---|---|---|---|
| dense rows | 2.028 | 2.284 | 2.285 | per token in principle; **grows** today (form choices) |
| experts gate+up | 1.680 | 1.557 | 1.492 | falls: fewer distinct experts per token (105.7 / 143.5 / 184.6 per block and layer) |
| experts down | 1.036 | 1.016 | 0.997 | falls slightly |
| experts other | 0.120 | 0.121 | 0.191 | grows: ExpertGroupM 47 -> 336 us per launch |
| attention | 0.307 | 0.297 | 0.295 | per token |
| compressor + indexer | 0.212 | 0.226 | 0.223 | per token / grows (compressor rows) |
| norms + dot rows | 0.208 | 0.190 | 0.190 | falls (per-block launches) |
| exchanges | 1.027 | 0.969 | 0.978 | per token (bytes); round trips fall |
| all kernels | 6.633 | 6.674 | 6.667 | flat |
| profiled wall | 7.21 | 7.03 | 6.89 | |
| unprofiled wall (tg96b / tg97b) | 6.80-6.87 | ~6.77 | ~6.69-6.77 | |

**What scales with tokens:**

- the dense and expert products;
- attention;
- the exchange bytes.

**What scales with blocks** (falls as blocks grow):

- expert weight decodes (per group);
- exchange round trips;
- the small per-block launches: finish, norms, softmax, window, rope.

**What grows at 256 today.** These are penalties, not physics:

- router rows +84 ms: `DenseRowsG` reads the weights once per 4 tokens with no x reuse, so 420 us per launch at 256 against 67 us at 64;
- expert grouping +77 ms;
- engram +44 ms: a non-weight-stationary form at 256;
- q_a / q_b / o_a / route pick +141 ms together: the form table picks T = 4, R = 4 forms at 256, which run 0.35 ps per multiply-add against 0.30 for the 64-token T = 8, R = 2 forms;
- compressor +20 ms;
- stream post+pre +18 ms.

The cheaper of 64 and 256 for every role sums to 6.273 s, 0.36 s below 64 today. That is lever 2.

## 3. Furthest from the floor, and the ranked levers

**Gaps above the FP32 floor, per read on card 2:**

| family | gap |
|---|---|
| experts gate+up | 1.13 s |
| dense rows | 1.11 s |
| exchanges | 1.03 s (every second of it exposed) |
| experts down | 0.76 s |
| norms + dots | 0.18 s |
| compressor + indexer | 0.16 s |
| attention | 0.14 s |
| experts other | 0.12 s |

By ratio the worst are the small launch-bound kernels (grouping 72x; norms and post+pre 10-20x) and the H16 rows
(router 3.1x, indexer q_b 5.2x).

**Ranked levers** (`tools/levers97.py` -> `tables/lever_estimates.txt`, which prints each derivation; seconds
off today's 6.80 s; every one keeps the output bit-identical):

| # | lever | change | saving s (low / central / high) | effort | confidence |
|---|---|---|---|---|---|
| 1 | **E: exchanges overlapped**: two 64-token halves of a 128 block in flight; pulls on a second queue built in the register mode of the kernels beside them, or riding inside them | scheduling | 0.43 / **0.62** / 0.84 | L | medium-low |
| 2 | **Blocks of 256 done right**: 64-token dense forms looped over 256, weight-reusing engram / router forms, parallel grouping | form table + 2 kernels | 0.30 / **0.44** / 0.50 | M | medium |
| 3 | **Expert kernels (rux-2)**: spill-free two-row forms, four-row tiles at 128 registers, decode shared by more slots | kernel | 0.31 / **0.40** / 0.64 | M-L | low |
| 4 | **Dense forms that lag**: weight-reusing H16 form (router, compressor, indexer rows) 0.14; Q6_K / Q5_K forms 0.09-0.13; tp97 Q6 slowdown 0.06 | kernel | 0.23 / **0.30** / 0.35 | S-M | medium |
| 5 | **D: replicated q_a + kv split by 6** (+ indexer q_b) | kernel table + 1 pull per layer | 0.16 / **0.23** / 0.31 | M-L | medium-low |
| 6 | Dense Q8_0 past the x-port cap (R = 4 x T = 8) | kernel | 0.03 / 0.08 / 0.15 | M | low |
| 7 | Parallel ExpertGroupM | kernel | 0.05 / 0.08 / 0.09 | S | medium-high |
| 8 | 12 / 8 head imbalance | runtime weights / layout | 0.02 / 0.06 / 0.12 | S / M | low |

All eight, treated as additive (they touch different time): 1.5 / **2.2** / 3.0 s off, so 5.3 / **4.6** / 3.8 s
for the read, 630 / **720** / 870 tok/s.

### How each saving is derived

**1. E (exchanges overlapped).**

- Card 2's exchange kernels take 1.027 s, and all of it is exposed.
- The xov1 six-card pre-check measured how much a pull on a second queue hides beside compute:
  - 74-95 % with 16 work-groups when both kernels use the same register mode;
  - 50-78 % with 64 work-groups;
  - about 0 % across modes;
  - 0 wrong values in 400 iterations of every shape.
- Here the pulls are 40-150 us long, beside 0.2-1 ms phases of the other half.
- Assumed hidden: 50-85 %, minus 0.03-0.08 s of cost (shared threads, about 12.6K cross-queue barriers, two expert-group copies).
- The halves are 64 tokens each, so every kernel keeps today's 64-token cost.
- Register-mode catch (`pa/grf_pr.txt`): the pulls are pinned to 128 registers, but most dense prompt forms build at 256. Each overlapped pull needs the mode of its neighbours, or must ride inside them. A mode switch ends the overlap.
- Bit-exact: the halves are two consecutive 64-token blocks, and traces are byte-identical across block sizes. The risk is ordering (races or hangs), which the gate catches.
- The lever grows as the other levers shrink compute.

**2. Blocks of 256 done right.**

- 0.360 s comes from the per-role minima (section 2).
- About 0.075 s comes from fewer gaps: unprofiled 256-token reads are about 0.04 s faster than 64-token reads despite 0.034 s more kernel time.
- Bit-exact: no risk. Block size never changes per-token arithmetic, and the gate already runs 256 / 129 / 255.

**3. Expert kernels.**

- Today: 2.716 s, against an issue floor of 1.807 s (products 0.824 + decode 0.984), so 67 % efficiency.
- At 75 / 80 / 85 % efficiency this saves 0.31 / 0.46 / 0.59 s.
- Cap 16 at 64 tokens would cut decode to 0.826 s, but only if the forms stay at 128 registers.
- At 256 the floor is 1.50 s (cap 6) or 1.25 s (cap 16), and today's kernels reach only 60 % of it, so this lever stacks on lever 2.
- Low confidence: the packed-lane K2 forms were all slower.
- Bit-exact: the same decoded weights, x addresses, per-output multiply-then-add order and butterfly; `bench_rux` checks every output.

**4. Dense forms that lag.**

- **H16 rows.**
  - The router, compressor and indexer-proj rows share one kernel type, and the indexer q_b has its own.
  - Today they take 0.287 s, against an FP32 floor of 0.082 s.
  - `DenseRowsG` loads x once per row, which is 4 B per multiply-add through the port.
  - A weight-reusing form at the Q8 forms' 1.75x floor saves 0.144 s at 64, more at 256.
  - WsH16 forms already exist for 2-3 token checks.
- **Q6_K / Q5_K layers** (13 of 40): they are 0.220 s above the same shapes at the Q8 per-launch time. Count 40-60 % of that as reachable, because their decode is heavier. The o_b Q6 form runs T = 4 at 64 tokens (4.0x its floor).
- **The tp92 -> tp97 slowdown** of unchanged Q6 forms:
  - o_b `WsQ6<32u>`: 244 -> 317 us;
  - engram `WsQ6<24u>`: 575 -> 670 us;
  - together 0.059 s;
  - check the register mode and spills in the IGC dump.

**5. D (replicated rows split).**

- q_a + kv run whole on every card: 0.439 s.
- A sixth share costs 0.10-0.15 s, because the 213 / 85-row slices are 1.4-2.0x less efficient per row.
- One new pull per layer adds 0.05-0.14 s: 382 KB per block and layer, plus 2.5 us of sync and 20-48 us of waiting.
- Net 0.16-0.26 s, plus 0.05 s from the indexer q_b, though that drops to about 0 once lever 4's H16 form exists.
- The router and compressor rows net about 0, because each needs its own pull.
- Bit-exact: no change, since every row is still computed whole on one card.

**6. Dense Q8_0 past the port cap.**

- The 64-token Q8 forms run 0.30-0.35 ps per multiply-add.
- The FP32 floor is 0.174 ps. The x-port bound at R = 2 is 0.242 ps.
- So they sit at about 1.25x the port bound, and the FP32 floor cannot be reached with 2-row tiles.
- R = 4 x T = 8 tiles would move the bound to 0.218 ps (ALU), but they need about 80 registers per lane.

**7. Parallel ExpertGroupM.** 98 ms at 64 tokens (47 us x 40 per block). About 10 us per launch looks reachable,
saving 0.077 s.

**8. The 12 / 8 head imbalance.**

- 12-head cards carry about 133 us per layer more q_b, attention, o_a and pair-swap work.
- The 8-head cards already take more mix dots (DSPLIT weights 1,1,1,1,4,4, about 32 us).
- That leaves about 0.21 s of slack per read on cards 4 / 5. Moving about a third of it off the four heavy cards saves 0.05-0.1 s.
- Free first test: `OWN_MT_DSPLIT_WA=0,0,0,0,1,1`.

### Considered and closed

- **Two blocks pipelined across card groups** (cards 0-2 on layers 0-19, cards 3-5 on 20-39).
  - Per card it holds the same bytes, but in a different layout from decode, which needs all six cards on every layer.
  - It would need a second weight copy: there are 28 GB of weights per card and only 3.45-3.98 GiB free.
  - The alternative is a 28.7 s re-upload between prompt and answer.
  - Its only gain, exchanges hidden behind another block's compute, is what E gets in place.
- **Fewer exchange bytes.** The bytes are fixed by the bit-exact layout. Every alternative (column-split down with a reduce, expert parallel) either sums partials across cards in a new order or moves more data: 7 x 5,120 instead of 7 x 2,304 per token.
- **The "16-head imbalance".** It does not occur in prompt blocks (section 1).
- **Clock-aware row weights** (`OWN_TP_WEIGHTS`): at most about 0.08 s, and the 16-row granularity loses the gate/up part.
- **Power caps.** If the four 230 W cards ran like the 275 W ones, about 0.33 s would come off. That is the owner's hardware call, not a software lever.
- **FMA, DPAS, bf16, tf32, int8.** These round differently.

## 4. tp92 -> tp97 (card 2, blocks of 64; `tp92_vs_tp97.txt`)

**Totals.** Kernels 6.957 -> 6.633 s and profiled wall 7.55 -> 7.21 s. The changes by family:

- experts: -0.363 s (rux-1);
- norms + dots: -0.037 s (the fused pre-norm + dot rows);
- exchanges: +0.025 s;
- dense rows: +0.057 s.

The dense rise comes entirely from Q6_K forms whose code is the same in both builds (same template, PF = 0):

| form | change | per read |
|---|---|---|
| o_b `WsQ6<32u>` | +30 % at 64 / 128 / 256 tokens | +49 ms |
| engram `WsQ6<24u>` | +17 % | +10 ms |
| `DenseRowsGR<GemvQ6KP<24u>>` at 256 | +22 % | |
| `RoutedQ2KF` at 256 | +21 % | |

Card 0 shows the same pattern. The cause is unknown; a register-mode or spill change in the new build is the
first thing to check.

At 128 / 256 tokens, rux-1 took -0.81 / -0.78 s off the experts, but dense rows rose by 0.09 s and 0.07 s. rux
had predicted 128 / 256 would beat 64 by 0.3-0.4 s; measured unprofiled, they are within 0.05 s of 64. Lever 2 is
the missing part.

## Files

| file | what |
|---|---|
| `README-prompt97.txt` | the ranked levers for the coordinator: time now, floor, saving, effort, bit-exact risk |
| `tools/prof97.py` | parses the OWN_GPROF=2 logs, maps every kernel to a role and family, removes the answer step |
| `tools/model97.py` | shapes, bytes, multiply-adds, expert picks (u84 dump), exchanges per card and block |
| `tools/budget97.py` | writes every table below (`python3 -I budget97.py`) |
| `tools/levers97.py` | lever arithmetic -> `tables/lever_estimates.txt` |
| `tables/ledger_b64.txt` | per 64-token block, every role and family against its floor, cards 2 and 0 |
| `tables/families_by_block.txt` | per read at 64 / 128 / 256, what scales with tokens or blocks, per-role minima |
| `tables/exchanges_b64.txt` | exchange launches, bytes, floors, measured, effective GB/s |
| `tables/experts_floor.txt` | distinct experts, groups, the FP32 / byte / decode / port floors by block size |
| `tables/dense_forms_b64.txt` | dense kernels per launch against their floor; Q6 / Q5 against Q8 |
| `tables/tp92_vs_tp97.txt` | family changes and same-code regressions |
| `tables/card0_vs_card2.txt` | the clock signature |
| `tables/kernels_<run>.txt` | every kernel type of each profile with its role |
| `tables/lever_estimates.txt` | floors of the whole read, ranked levers, each derivation |

Measurements this analysis could not make, in order of use:

1. A prompt-block timeline: copy against wait in the exchanges, which decides E's ceiling.
2. A card 4 prompt profile on tp97, for the 8-head cards' real slack.
3. The IGC dump of the tp97 Q6 forms.
