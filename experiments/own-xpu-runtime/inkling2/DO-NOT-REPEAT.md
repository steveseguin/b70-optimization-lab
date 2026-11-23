# Inkling-2 engine: tried and closed

Ideas measured and not kept, so nobody spends a run re-deriving them. Numbers are from the commits and README
paragraphs named in the Evidence column (card in brackets). Re-open only under the stated condition.

| Idea | Result | Evidence | Re-open when |
|---|---|---|---|
| Warm kernel on a second in-order queue (same context), started after the previous matrix kernel, to pull the next weights into L2 while the main queue runs small kernels | Slower in every setting: 80.5 -> 73.97-79.42 tok/s. Reading 2 MB of weights nobody needs costs ~4.4 µs per step-slot, i.e. its full time: the two queues do not run side by side on this card. Launch alone (32 bytes) ~free. | 2026-11-23, README "Warm weights" (card 2) | A driver or queue mode that demonstrably runs two queues' kernels at once on one B70 |
| Warm work-groups inside the 2-3 µs norms (control norm, input norms) after the mix | 11.84 -> 11.86-12.02 ms per step with 1-3 MB each | 2026-11-23 (card 3) | A longer latency-bound kernel sits before a big product |
| Attention kernels (scores, P.V of one token) as warm carriers | Not run: they already read ~2 MB of cache each at near the memory's pace | 2026-11-23 profile (scores 2.1 MB in ~4 µs) | |
| Split F32 product (gemv_split) for the router (128 x 2304) and the three loop down products in one launch | Identical values but slower: 4.77 -> 5.51 µs and 9.76 -> 10.80 µs (both already at the memory's pace). Kept only for the single loop down product (7.15 -> 5.72) | commit "403K needle test ..." (card 3) | |
| One-launch P.V (the last work-group adds the blocks) | Slower at every length: 31,000 keys 199 vs 157 µs; 3,134 with the window 10.2 vs 8.9 µs | README block-order paragraph | |
| Attention tiles of 16 queries | Register spills, ~8x slower than 8 queries | README attention tiles | Larger register file mode measured |
| Preload ("planar-pre") matrix kernels | Slower (register pressure): attn_output 15.1 -> 30.3 µs, gate|up routed 50.8 -> 99.7 µs | bench_gemv rows "planar-pre" | |
| Gate|up pair kernel with the gate and up rows adjacent (interleaved layout) | No gain: 49.0 vs 49.9 µs far vs adjacent | bench_gemv "pair" rows, 2026-11-23 (card 2) | |
| Four-wide state reads in the mix without removing the per-state branch | No gain (10.0 -> 10.4 µs). The branch around each read and its use was the cost; removing it gave 10.0 -> 9.0 | 2026-11-23 stage timing (card 2) | |
| Feed-forward tail (combine, convolution, residual) folded into the one-token down products: the last of each row block's 8 work-groups runs it (a counter per block) | Identical values but 31 -> 57 µs per launch (179 µs with a device-scope barrier in every work-group): the release fence in each of 4,608 work-groups costs far more than the 4.2 µs launch it removes | 2026-11-23 INK_PROF (card 3) | |
| Attention-input launch with other rows per sub-group (INK_AIN_R 1/2) or sub-groups per group (1/2/4) | Default (tune R capped at 2, 2 sub-groups) fastest: 2.08 ms per step vs 2.18-2.42 | 2026-11-23 INK_PROF (card 3) | |
| The mix kernel reading every state's first float4 together with the table entries | 9.0 -> 9.9 µs (register pressure) | 2026-11-23 INK_PROF (card 3) | |
| Gate\|up with gate and up rows in two sub-groups of one work-group (value handed over in local memory), lane-order input | 48.8 vs 47.7 µs for the two-row pair kernel with lane-order input | 2026-11-23 bench_gemv (card 3) | |
| Lane-order input for the Q8_0 attention products | 0.3-0.5 µs each (q 16.0 -> 15.4-15.6, output 15.1 -> 14.8, k 6.6 -> 6.2): about what the norms lose writing the copy (+0.8-1.1 µs) | 2026-11-23 bench_gemv (card 3) | Producers that write lane order for free |
| F32 weights stored in lane order (pl::F32L) for the router and loop down products | Router 4.31 -> 3.94 µs, loop down 5.9 -> 5.3 (bench): ~0.03 ms per step, for ~85 MB of extra copies (the prompt path needs the file layout) | 2026-11-23 bench_gemv (card 3) | The prompt kernels read F32L too (one copy) |
| Prefetching the mix's block states into L1 before the mix reads them | `INK_PROF` 0.5-0.65 µs less for the mix, the step unchanged | 2026-11-23 INK_PROF + INK_BENCH_STEP (card 3) | |
| Warming the gate\|up weights from extra work-groups of the expert-routing kernel | Routing +2.5 to +28 µs, gate\|up only -2.5 µs | 2026-11-23 INK_PROF (card 3) | |
| P.V edge blocks (the window's first and last 128-key blocks) through the whole-block path with zeroed weights outside the row | 11.38 -> 11.12 µs per windowed layer: too small for the extra code | 2026-11-23 INK_PROF (card 3) | |
| Softmax / block-sum reads 32 at a time on short rows (the windowed layers' 1,024 keys), or a predicated last round instead of the one-by-one tail | Softmax 2.46 -> 4.33 µs (32 at a time); predicated tail at 3K: softmax 2.57 -> 2.73, block sum 2.18 -> 2.63. Short rows keep 8 at a time + one-by-one tail; only rows past 16K keys take 64 | 2026-11-23 INK_PROF (card 3) | |
| Long rows (past 16K keys) with 32 or 128 reads per round instead of 64 | bench_attn `BENCH_SM` at 400K keys: softmax 247 (32) / 255 (128) vs 159 µs (64); block sum 222 (32) / 183 (128) vs 132 (64) | 2026-11-23 bench_attn (card 3) | |
| One query head per thread for the writing step's scores and P.V (the 3 heads of a KV head in 3 adjacent work-groups, keys from cache the 2nd and 3rd time) | Same values but slower at 3K: windowed P.V 11.25 -> 12.66-12.96 µs, scores 7.99 -> 8.58-8.88; on all layers the full scores 17.89 -> 20.95 | 2026-11-23 INK_PROF, builds m29/m30 (card 3) | |
| Speculative decoding with the DSpark drafter | Deferred 11-22: a step of 2 tokens cost 20.27 ms vs 12.38 for 1 (4: 28.53, 8: 45.15). **Re-opened 11-23**: 2 / 3 / 4 tokens now 15.65 / 18.26 / 21.42 ms vs 11.42 for 1 (card 2, real tokens) | 2026-11-22/23 step bench | (open: state rollback, drafter) |
| Global-pointer cast (`gptr`) in the mix and the three-input norm | Mix 9.69 -> 9.92 µs, three-input norm 2.86 -> 2.87, step 11.157 both (`INK_PROF`, sb4 vs sb5, card 3) | 2026-11-23 | |
| Multi-token job picked by reference with a run-time index (`m.j[k]`) instead of the fixed-index copy `pick_job` | One-token attention inputs 40.9 -> 44.0 µs: the global cast is lost | 2026-11-23 sb9 vs sb8 `INK_PROF` (card 2) | |
| Multi-vector kernel slowness chased with a larger register file, the job table in card memory, one row count per kernel, the job's fields broadcast from one lane | No change; the cause was generic pointers from the job table (`gptr`) | 2026-11-23 bench_gemv (card 2) | |
| Prompt-lookup guesses (the last 2-4 tokens seen before) on fresh text with 2 or 3 guesses per check | Code 256 tokens: plain 87.10-87.16 tok/s, 1 guess 88.42-88.51, 2 guesses 86.77-86.87, 3 guesses 83.48-83.59 (card 2) | 2026-11-23 `INK_SPEC` | Text that repeats its input (edits, quotes) |
| Checks of 5-8 tokens (more than 3 guesses) | Simulated on 7-guess logs vs the plain text: max 4 guesses code +4 %, haiku / 3K / 8K even; max 5 code +6 %, others -1 to -2 %; max 7 worse | 2026-11-23 `INK_DRAFT_LOG`, `tools/spec-sim.py`, logs in /home/steve/inkling-work/ev | a much better drafter would change it |
| Prompt expert products with one weight row per lane (tokens in a loop) | Same bits, gate|up 13.3-13.9 ms vs 6.3-6.7, down 4.4-7.1 vs 3.5 (512 tokens) | 2026-11-23 bench_moe (card 3) | |
| NVFP4 prompt tiles loading each virtual lane's weight bytes first | gate|up 6.9-8.3 ms vs 6.7, down 4.0 vs 3.5 | 2026-11-23 bench_moe (card 3) | |
| NVFP4 table decode in the down tiles | 3.52 -> 3.66-3.69 ms (gate|up keeps it: 6.71 -> 6.35-6.40) | 2026-11-23 bench_moe (card 3) | |
| Checks sharing key / value reads across tokens in windowed layers or short contexts | Windowed P.V 15.3 -> 28.6 µs at 31K; code (~400 keys) P.V full 7.7 -> 18.4, scores 4.8 -> 8.8; 3K and 8K even (too few work-groups) | 2026-11-23 `INK_PROF`, A/B `INK_ATT_SHARE` (card 2) | kept for full layers from 4,096 keys |
| DSpark drafter's 8-slot products through the token tile kernels (`dense_t`, 8 of 16 lanes) | ffn_gate 110-116 µs, ffn_down 202-212 vs lane-order blocks of 8 (`GemvMR` XL mr 8) 81 / 103 in the engine | 2026-11-23 `INK_PROF` (card 2) | |
| DSpark head with a full output-layer pass per guess (the reference's way), or its guess slots' output rows through the tile kernels | Per guess ~0.7 ms (380 MB) vs 189 µs with the folded (W_lm Wh)^T table; 3 slots through tiles 2,140 µs vs 793 with `gemv_multi_m` | 2026-11-23 `INK_PROF`, `INK_DSP_FOLD=0` (card 2) | |
| Small-step NVFP4 expert kernels with every weight load of a lane issued first (3 or 5 chunks per lane, clamped) | 2 tokens: gate\|up 77.9 -> 94.8 µs, down 46.6 -> 50.1 (4 down rows 57.3); 4 tokens 126.3 -> 150.1 and 79.0 -> 85.1 | 2026-11-23 `INK_SB_PRE` (card 2) | |
| Small-step experts with one code path for every token count; two gate\|up row pairs or four down rows per sub-group | 4 tokens: gate\|up 149.0 / down 92.1 µs vs 124.3 / 79.3 with per-count code; 2 tokens: two pairs 82.6 vs 76.1, four down rows 49.3 vs 46.7 | 2026-11-23 `INK_PROF` (card 2) | |

Measurement cautions (not ideas, but they decide results):
- A card under continuous big reads boosts to 2,800 MHz, then the short power limit (PL2) pulls it to ~2,333 MHz within
  1-2 s; a kernel timed late in a bench run looks ~9 % slower. Interleave variants. Writing itself runs at 2,667-2,800.
- `INK_PROF` (profiled queue) and unprofiled timings can disagree by ~1 %; decide with `INK_BENCH_STEP` alternations.
- `INK_SAVE_GEN` copies a 201,024-value row per step to the host: never time one arm with it and the other without.
- Cards differ by up to ~8 %: compare on one card.
