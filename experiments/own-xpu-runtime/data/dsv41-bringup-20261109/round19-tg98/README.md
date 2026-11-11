# Round 19, gates tg98 + tg98b (build tp98, 2026-11-11)

tp98 = tp97 + dride-1 (`OWN_MT_DRIDE=1`: the split mix finishes ride output-b's and shared down's launches in checks
of 4-6 tokens) + qb-off-3 (`OWN_QB_OFF_M`: the light neighbours compute some of the 16-head cards' q_b heads in
checks), both opt-in. Build 15:58-16:15 (1040 s, restarted after the 15:17 host reset). tg98 16:15:40-16:25:23
(stopped at the qb-off-3 hang); tg98b 16:27:00-16:42:45 (ALLDONE), the rest of the gate without the qb arms.

## In plain words

- **dride works and is now the default (tp99).** Same answers and the same guesses everywhere, and checks of 4-6
  tokens are 0.7-0.8 ms cheaper. Code 138.74 / 139.41 -> 140.65 / 140.76 tok/s (+1.2 %), analysis 152.71 / 153.83
  -> 156.04 / 155.86 (+1.8 %), prose 117.00 -> 118.49, guessing after a 3K prompt 136.71 -> 143.36 (+4.9 %).
- **qb-off-3 hung the two 16-head cards again** (cards 2 and 5, 16:25, its first run, blocks of 2). The driver reset
  the stuck jobs, the health probe passed at 16:26. Its own 1 s in-kernel timeout never reported, so the cause is
  not the polling form that qb-off-3 fixed. Parked: worth ~1-2 % on guessing, and each try costs a driver reset on two
  cards. A retry needs a short six-card bench of the hand-over first (as xll-1 did), not an engine gate.
- **Plain writing unchanged:** tp98 101.36 / 101.43 tok/s, tp97 100.21 / 101.49 (same settings).
- **3K read (whole time):** blocks of 64 6.78 / 6.79 s, blocks of 256 6.71 / 6.72 s (its first step 0.54 s includes
  kernel builds). `OWN_MT_DSPLIT_WA=0,0,0,0,1,1` (the prompt study's free head-balance test) 6.77 / 6.85 s: neutral,
  closed.

## Correctness

tg98: h1, h5, h64 (defaults) and h4dr, h5dr, h6dr, h5drf (with `OWN_MT_DSPLIT_FIN=1`), h64dr TRACE_IDENTICAL +
IDS40_SAME; h2qb3 exit 1 (DEVICE_LOST after the driver's job timeouts on 0000:e3 and 0000:43), STOP_FAULT.
tg98b: t3k_b64 identical, 5 SPEED128_SAME, 6 ANSWER256_SAME (blocks 64, 256, head-balance), 12 / 12 guessing runs
SAME AS the plain run, every guess log equal (d98 = tg97b's d97; dr = d98).

## Check cost by guesses (median ms; `check-cost-by-guesses.txt`)

| guesses (tokens checked) | 0 (1) | 1 (2) | 2 (3) | 3 (4) | 4 (5) | 5 (6) |
|---|---|---|---|---|---|---|
| code, d98 | 10.33 | 13.05 | 15.47 | 17.88 | 20.47 | 22.71 |
| code, dride | 10.35 | 13.05 | 15.45 | 17.17 | 19.63 | 21.97 |
| analysis, d98 | 10.32 | 13.14 | 15.69 | 17.84 | 20.80 | 22.23 |
| analysis, dride | 10.35 | 13.18 | 15.60 | 17.18 | 20.02 | 21.68 |

Draft 1.92-1.95 ms per round in every run.

## Files

`tg98-summary.txt`, `tg98b-summary.txt`, `spec/` (tg98b spec logs), `check-cost-by-guesses.txt`,
`fault-20261111T1625/` (journal, h2qb3 log, probe). The driver coredumps of both cards stay in
`/home/steve/dsv41-work/faults/fault-20261111T1625/`. Scripts in `../round18-scripts/strategy/` (build98.sh, tg98.sh,
tg98b.sh).
