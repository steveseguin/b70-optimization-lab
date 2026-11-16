# c115: tp115 exact in the stable mode - 23 fresh starts, every output identical to its reference (2026-11-15 10:08-10:31)

Configuration: the stable mode (owner 2026-11-15): `OWN_PX_SERIAL=1` (now tp115's default, also in `stable.env`), the
six GPU root links at Gen4 x16 (`stable/gen4.sh`), BIOS 11.02, default power; `stable/preflight.sh` before the start
("ok (BIOS 11.02, Gen4 x16 x6, default power, clean kernel log)") and at every gap. tp115 = tp114 sources + three
defaults: `OWN_SKIP39=1` (layer 39 runs only its kept key rows in prompt blocks), `OWN_IDX_DSPLIT=3` (the block-index
scoring split), `OWN_PX_SERIAL=1`. Built in 1328 s (exit 0). Two arms: **def** (tp115 defaults) and **off**
(`OWN_SKIP39=0 OWN_IDX_DSPLIT=0`, = tp114 in the serial mode). Script: `../round18-scripts/strategy/c115.sh` (same
bytes as the script that ran). Speeds compare only within the stable mode.

| stage | starts | checked against | result |
|---|---|---|---|
| 1 traces: prompt 1 read in blocks of 1 / 5 / 16 / 64 / 256 tokens (h1..h256); 3K prompt def / off (t3k) | 7 | runs/ab1 trace + 40 ids; runs/gm64 t3k_ref | 7/7 TRACE_IDENTICAL + IDS40_SAME |
| 2 plain writing, prompt 1, 128 answers (warm, plain_1, plain_2) | 3 | runs/ab1 128 ids | 3/3 SPEED128_SAME |
| 3 3K def / off alternated x2 (256 answers); 10K def / off (64) | 6 | e52; tg107 | 6/6 SAME |
| 4 guessing, code + analysis prompts (512 answers) | 2 | tg105v guess log; e57 plain answers | 2/2 GLOG_SAME + "SAME AS the plain run" |
| 5 x34k / x95k def / off (256 answers); guessing after x95k (s95_def) | 5 | e82 | 5/5 ANSWER256_SAME |

Speeds (prompt reading = tokens read on the cards / seconds; writing = plain answers):

| case | prompt tokens | reading def | reading off | writing def | writing off |
|---|---|---|---|---|---|
| p3k (256 answers, x2) | 3,323 | 4.97 / 4.99 s (679.7 / 678.2 tok/s) | 5.11 / 5.10 s (663.0 / 663.8 tok/s) | 99.13 / 98.83 tok/s | 98.56 / 99.54 tok/s |
| p10k (64 answers) | 10,621 | 15.61 s (684.5 tok/s) | 16.03 s (666.9 tok/s) | 96.10 tok/s | 99.28 tok/s |
| x34k (256 answers) | 33,815 | **50.27 s (673.2 tok/s)** | 51.56 s (656.2 tok/s) | **97.30 tok/s** | 94.82 tok/s |
| x95k (256 answers) | 95,497 | **144.53 s (660.8 tok/s)** | 148.33 s (643.9 tok/s) | **91.69 tok/s** | 88.32 tok/s |

| guessing (def) | prompt | writing | tokens per cycle | guesses kept |
|---|---|---|---|---|
| code_def | 82 tokens | 148.19 tok/s | 2.27 | 78.4 % |
| analysis_def | 113 tokens | 166.41 tok/s | 2.84 | 75.3 % |
| s95_def | 95,497 tokens, read in 146.27 s (652.9 tok/s) | 123.39 tok/s (255 tokens) | 2.01 | 80.1 % |

- All 23 starts exited 0; no fault, warning or STOP line in `summary.txt`; ALLDONE with no SOME_DIFFER.
- tp115's defaults read prompts faster than the switches-off arm: +2.3 % at 3K, +2.6 % at 10K, 34K and 95K. Writing:
  the same at 3K (-0.1 %), -3.2 % at 10K (64 answers only), +2.6 % at 34K, +3.8 % at 95K.
- skip39 was on by default in every def prompt run: 6 prompt blocks at 3K (768 rows per card), 21 at 10K, 66 at 34K,
  187 at 95K. idx_dsplit split 0 index layers at 3K, 315 one-token layers at 10K, 1020 at 34K and 95K, 196 one-token
  + 312 block layers in s95_def. Its built-in compare was off here ("0 score rows compared"); exactness comes from
  the answer compares above.
- Reading stays high with length (def): 684.5 (10K) / 673.2 (34K) / 660.8 tok/s (95K). Plain writing on prompt 1:
  108.06 / 107.63 / 109.09 tok/s.
- tp115 became the base: the long-context runs lc1 and lc2 used this binary.
- The next start reset the host. sm1 (`sm1.sh`: stable-mode budget and card-balance A/Bs on tp115) was started by
  `chain_sm1.sh` once c115's unit ended; its first case `t3k_h1` (a 3K trace with prompt heads 4,2,2,4,2,2) had
  started when the host reset at 10:32. sm1's `summary.txt`, `marks.txt` and `t3k_h1.log` are 0 bytes. c115's own
  results were all on disk before (ALLDONE). Incident details: `CURRENT.md`, entry "November 15, 2026 13:56 EST".
- Records: the reset also emptied this page's first commit; the re-made commit 2ccbabe5d6 (16:50, message "tp115
  exact in the stable mode (23 starts); new base; stable-mode cost measured; the next start reset") again held two
  empty files. Rebuilt 2026-11-16 from `/home/steve/dsv41-work/runs/c115/` (`summary.txt` copied unchanged; marks and
  logs stay there). The run's files hold no overlap-mode numbers; for the stable mode's cost against the overlap mode
  see `../stable-mode/README.md`.
