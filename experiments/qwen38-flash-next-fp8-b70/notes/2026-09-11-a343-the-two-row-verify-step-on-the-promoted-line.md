# A343: the two-row verify step on the promoted MTP1 line

Preregistration: `2026-09-11-a343-mtp1-two-row-step-on-the-promoted-line-prereg.md`. A343 = the
promoted MTP1 packet A338 (fused QSA `6d872457`, Triton HC, placement, three exact-verify
selectors) with `Q38_STEP_TIMING_LOG=10` on the diagnostic head `a402f97d3`. Three exact-2K rows.

| | M=1 (A340, MTP0) | M=2 (A343, MTP1 verify) |
| --- | ---: | ---: |
| target forward, graph, exact-2K | 27.2 ms | **42.7 ms** (40.9-43.9, n=84) |
| sampler | 0.85 ms | 0.91 ms |
| drafter (MTP head) | - | 2.24 ms |
| timed step | 28.1 ms | 45.8 ms |
| acceptance (mean length) | 1 | 1.82-1.84 |
| row rate, conventional 99-interval | 33.3 tok/s | 24.8 (cold first row), **37.38, 37.27 tok/s** |
| exact-2K output | `afffd211…` x3 | `afffd211…` x3 |

Implied step from the warm rows: 1.83 / 37.3 = 49 ms, so ~3 ms sits outside the timed marks
(scheduler, D2H, API) - the same small residual as MTP0 (30 vs 28 ms). The MTP1 line's step is
the target forward: **the second verify row costs +15.5 ms (+57%) on top of the single-row
forward**, not the 2.6x of the 09-03 line (A124/A125: 181 vs 71 ms graph replay). That cost
is what speculation pays for its 1.83 tokens per step, and it is the last single-user term worth
attacking on this lane: at M=2 == M=1 cost the same acceptance would give ~60 tok/s at 2K.

The first row of a fresh server reads 24.8 (cold graphs / warm-up); quote warm rows. The
diagnostic head did not change outputs.

## Next

Decompose the +15.5 ms by block on this head (skip switches or the sub-op timing hooks): the
old line's excess was MoE at M=2 (2.6x) and the serial verifier-row GDN path (2.5x); the HC and
QSA rows were 1.25x. Whichever block still scales super-linearly at M=2 is the kernel target.

## Evidence

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/...-mtp1-4352-ple-only-r1-attempt343/`
(`server.log`, `exact-depth-2k-r{1,2,3}.json`, `step-timing-2k.json`); packet
`tools/rewrite-q38-a338-to-diag-mtp1-step-timing.py`, `tools/*a343*`.
