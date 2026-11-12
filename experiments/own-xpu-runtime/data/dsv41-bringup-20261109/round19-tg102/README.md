# Round 19, gate tg102 + tg102b (build tp102, 2026-11-11)

tp102 = tp101 + pace-1 (`OWN_MT_PACE=1`: one-wave launches for the 16-head cards' q_b / output-a rows in checks,
the next weight segment loaded while the current one multiplies; new `kernels/sycl_v41_pace.hpp`) + px-1 (`OWN_PX=1`:
prompt blocks as two halves with the four per-layer pulls on a second queue beside the other half's work) + the
draft head's exchange slots padded to 128 bytes (the rare stale confidence read) + pb-1 and wa-2 on by default. Build
1144 s. A = tp101 (`OWN_ATT_WA=2 OWN_PAIR_G128=1`), B = tp102 (`OWN_PAIR_G128=1 OWN_MT_PACE=1`), alternated.

tg102 (22:08-22:36) stopped after its first stage: 5 trace runs aborted on the engine's host-memory floor during
weight upload ("host MemAvailable fell below the floor"), caused by a helper's compiler builds beside the gate (rule
now explicit: no builds while `six.active` exists). Its 14 identical traces carry over. tg102b (22:39-23:05, ALLDONE)
ran the 5 again and everything after them; it waits for 7 GiB of free host memory before each run.

## In plain words

- **Every trace identical without the overlap**: 19 prompt-1 traces (defaults at 1 / 4 / 5 / 6 / 64 / 128 / 256,
  pb-1 and wa-2 off at 5 and 256, pace-1 at 2-6 tokens and at 5 with every pace role alone, everything at 4 / 5),
  three 3K traces (64, 256, everything at 256). All 17 guessing runs gave the same text as plain writing; every code /
  analysis guess log equal to tg100's (the padded draft slots changed nothing visible).
- **The overlap (px-1) is not exact yet**: every 3K trace with `OWN_PX=1` differs (256, 128, 250 tokens per block,
  the one-queue diagnostic too, so it is a plain logic error, not a race). The pb256 helper found it: the fused router
  (`OWN_MT_RFUSE=1`) read the whole block's first row instead of the half's, so the second half of every block kept
  unwritten expert choices. First differing trace record (runs/pxdbg): answer step 1, layer 2, the indexer's picks
  (`cidx`), then everything after. Confirmed without a rebuild: with the fused router off (`OWN_MT_RFUSE=0`) the
  overlap's 3K trace is identical, twice. Fix `px-1b.patch` (four sites) goes into tp103. The 3K read times with the
  overlap in tg102b (5.28 s against 5.71) are not valid: half of each block skipped its expert work. The exact
  comparison (router not fused, alternated): overlap 5.81 / 5.84 s against 5.87 / 5.88, only -1 %, far under the
  ~0.6 s predicted; likely the halves' 128-token forms cost what the hidden exchanges save (next: halves of 256).
- **pace-1 pays in checks**: checks of 4 / 5 / 6 tokens -0.27 / -0.58 / -0.48 ms (code), -0.26 / -0.53 / -0.45
  (analysis). Code 141.89 / 142.82 (A) -> 143.98 / 144.31 (B) tok/s, analysis 157.37 / 158.15 -> 159.93 / 159.83,
  prose 119.90 -> 121.15, after a 3K prompt 140.89 -> 147.48 (blocks of 64 for the prompt; 148.68 at 256). B
  without pace: code 143.05, analysis 158.03.
- **With the draft's candidate vocabulary** (draft-only): code **144.72**, analysis **162.43** tok/s.
- **Plain writing unchanged**: tp102 103.89 / 103.24, with G128 103.13 / 104.20 tok/s (G128 neutral here).
- **3K read at 256** (pb-1 now default): tp101 5.67 / 5.68 s, tp102 5.71 / 5.71.

## Check cost by guesses (median ms, round 2; `check-cost-by-guesses.txt`)

| run | 0 (1) | 1 (2) | 2 (3) | 3 (4) | 4 (5) | 5 (6) |
|---|---|---|---|---|---|---|
| code, tp101 | 10.05 | 12.78 | 15.15 | 16.83 | 19.49 | 21.64 |
| code, tp102 + pace | 10.06 | 12.72 | 15.06 | 16.56 | 18.91 | 21.16 |
| code, tp102 no pace | 10.10 | 12.80 | 15.16 | 16.85 | 19.36 | 21.60 |
| analysis, tp101 | 10.20 | 12.87 | 15.35 | 17.01 | 19.73 | 21.29 |
| analysis, tp102 + pace | 10.19 | 12.90 | 15.30 | 16.75 | 19.20 | 20.84 |

## Files

`tg102-summary.txt`, `tg102b-summary.txt`, `spec/` (every guessing log), `check-cost-by-guesses.txt`,
`pxdbg-summary.txt` (the overlap's first differing trace records and the no-rebuild check). Scripts in
`../round18-scripts/strategy/` (build102.sh, build102-go.sh, tg102.sh, tg102b.sh, pxdbg.sh).
