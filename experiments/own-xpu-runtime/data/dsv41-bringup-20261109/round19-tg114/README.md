# tg114: tp114 (skip39-1 + idxsplit-3, opt-in) gated exact; prompt -2.5 %, writing at 95K +2.5 %, guessing at 95K +4 %

tp114 = tp113 + idxsplit-3 (`OWN_IDX_DSPLIT`: the one-token and check steps' index scores split across the cards by
rows from 8,192 rows, gathered, the unchanged selects; dsv41-work/idxsplit) + skip39-1 (`OWN_SKIP39`: prompt blocks
without the prompt's last token run layer 39's kept rows only; dsv41-work/skip39). Both opt-in. Patch
`dsv41-work/tp114-vs-543b796ca.patch`, binary `own_run_v41_tp114` (SHA-256 c10151d3...).

tg114 (2026-11-14 11:5x-12:36, default power, all Gen5): switches off = tp113 (prompt-1 traces + 3K trace identical);
on-card checks all same (skip39: the full layer + the kept rows again, compared bitwise; index split: the full score
compared; prompt 1 at 5 / 16, 3K, a 3,080-token cut, 10K); skip-on traces identical (prompt 1 at 5 / 16 / 64 / 256,
3K at px-512 / 256, both on at 3K, the 3,080 cut off vs on); every answer the same:

| run | off | skip39 | both (skip39 + `OWN_IDX_DSPLIT=3`) |
|---|---|---|---|
| 3K read | 4.27 / 4.31 s | 4.18 / 4.20 | 4.19 / 4.19 |
| 10K read | 13.63 s | | 13.27 |
| guessing code / analysis (both) | | | 157.62 / 174.98 tok/s, GLOG same |

The long-document stage was cut by a host reset; its resume (`notes/2026-11-14-dsv41-tp114-resumed.md`, one root link
at Gen4) ran it once, all 256 answers the same as e82: x34k 44.16 -> 43.30 s (answers 97.42 -> 98.24 tok/s), x95k
128.13 -> 124.87 s (91.41 -> 93.66 tok/s), guessing after x95k 124.63 -> 129.79 tok/s.

In plain words: both changes keep every bit and help a little (prompt ~2.5 % faster, long-document writing 2.5-4 %
faster); both become defaults in tp115 together with the stable mode (`OWN_PX_SERIAL=1`).

Files: `summary-tg114.txt`. Script: `../round18-scripts/strategy/tg114.sh`.
