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
| Speculative decoding with the DSpark drafter | Deferred: a step of 2 tokens costs 20.27 ms vs 12.38 for 1 (4: 28.53, 8: 45.15), so even high acceptance gains <= ~1.2x | 2026-11-22/23 step bench | Multi-token steps get much cheaper (e.g. 2-token step < 15 ms) |

Measurement cautions (not ideas, but they decide results):
- A card under continuous big reads boosts to 2,800 MHz, then the short power limit (PL2) pulls it to ~2,333 MHz within
  1-2 s; a kernel timed late in a bench run looks ~9 % slower. Interleave variants. Writing itself runs at 2,667-2,800.
- `INK_PROF` (profiled queue) and unprofiled timings can disagree by ~1 %; decide with `INK_BENCH_STEP` alternations.
- `INK_SAVE_GEN` copies a 201,024-value row per step to the host: never time one arm with it and the other without.
- Cards differ by up to ~8 %: compare on one card.
