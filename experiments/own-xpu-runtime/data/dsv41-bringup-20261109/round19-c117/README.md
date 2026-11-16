# c117: tp117 identical through 194K; guessing at 194K stopped on an intermittent exchange time-out that predates tp117 (2026-11-15 21:08 - 2026-11-16 09:55)

Configuration: the diagnostic setup (SMT off, Gen4 x16, `OWN_PX_SERIAL=1`, default power, BIOS 11.02; preflight
before every start; boot 7e1ee92b). Binary tp117 (sha256 5137c6e294a6bb24) = tp115 + **idxrows-1** (`OWN_IDX_ROWS=1`
default: the block-index scores and candidate marks hold each card's token share per half instead of 512 rows, ~2.1 KB
less card memory per context token) + **ropewin-1** (`OWN_ROPE_WIN=1` default: a 16,384-position rope table window
per card, 512 B less per position). Both change only the memory layout, so every output had to be bit-identical to
its reference. Script `c117.sh`; first fault / non-zero exit / mismatch = STOP. The planned capacity test (704,773
tokens, two modes) never started.

| case | prompt tokens | prompt reading | writing | free after load, card 2 | result |
|---|---|---|---|---|---|
| p3k (256 answers) | 3,323 | 4.93 s (680.0 tok/s) | 98.37 tok/s | 3.13 GiB | IDS256_SAME |
| p10k (64) | 10,621 | 15.59 s (685.6 tok/s) | 96.01 tok/s | 3.08 GiB | IDS64_SAME |
| plain, prompt 1 (128) | 36 | 0.16 s | 107.63 tok/s | 3.45 GiB | IDS128_SAME |
| code, guessing (511) | 82 | 0.24 s (355.5 tok/s) | 148.24 tok/s (2.27 per cycle, 78.4 % kept) | 2.07 GiB | IDS511_SAME, GLOG_SAME |
| analysis, guessing (511) | 113 | 0.29 s (477.1 tok/s) | 166.45 tok/s (2.84 per cycle, 75.3 % kept) | 2.07 GiB | IDS511_SAME, GLOG_SAME |
| x95k (256) | 95,497 | **144.47 s (661.4 tok/s)** | **91.49 tok/s** | **2.81 GiB** | IDS256_SAME |
| x200k (1024) | 194,000 | **301.18 s (644.1 tok/s)** | **87.66 tok/s** | **2.47 GiB** | IDS1024_SAME |
| s200k, guessing (1024) | 194,000 | - | - | **1.07 GiB** | **exit 1**: "card 0000:03:00.0: card-to-card exchange timed out waiting for card 1" |

- Seven of eight starts identical to their references; tp117's layout is exact. Speeds equal tp115's in c115 (same
  mode): reading +0.1 to +0.2 % (3K, 10K, 95K), writing -0.6 to +0.0 % (3K, 10K, 95K, code, analysis).
- Memory (card 2, the fullest): the new layout frees 0.39 GiB (index rows) + 0.08 GiB (rope window) per card at 194K,
  0.19 + 0.03 GiB at 95K (the log lines). Free after load: 2.81 GiB (x95k), 2.47 GiB (x200k), **1.07 GiB (s200k)**:
  guessing at 194K takes **1.40 GiB** more than plain answers at the same length. pr2 shows where: the draft alone
  (g_draft) 1.07 GiB, the guessing kernel shapes alone (g_tg) 2.47 GiB, and a 95K prompt with room for 195,584
  positions (g_s95big) 1.07 GiB, so the draft's share follows the maximum context, not the prompt. The tp115 binary on
  the s200k case (pr1) had 0.60 GiB free on card 2: 0.47 GiB less, = 0.39 + 0.08.
- s200k failed 145 s after its start (`marks.txt`), before any prompt line (the plain x200k read took 301 s): exit 1
  with "card 0000:03:00.0: card-to-card exchange timed out waiting for card 1" (`s200k.log`). No kernel log line
  during the case ("-- No entries --"); host memory never under 3,706 MiB (`mem.txt` in the run folder; floor 2,560).

Follow-up probes (all tp117 unless named; each a fresh start, 64 answers checked against the same references):

| probe | what it changes | prompt reading | writing | card 2 free | result |
|---|---|---|---|---|---|
| pr1 c_tp115 (2026-11-15 21:24) | the **old tp115 binary**, s200k's case | - | - | 0.60 GiB | **hung**: no prompt line, no exit; 12 h later still in its teardown |
| pr2 g_s95big | guessing, 95,497-token prompt, room for 195,584 positions | 146.03 s (654.4 tok/s) | 144.08 tok/s (guessing) | 1.07 GiB | passed, IDS64_SAME |
| pr2 g_draft | the draft alone at 194K (no guessing kernel shapes, no draft vocabulary) | 304.77 s (636.6 tok/s) | 125.75 tok/s (guessing) | 1.07 GiB | passed, IDS64_SAME |
| pr2 g_tg | the guessing kernel shapes alone at 194K (plain answers) | 301.16 s (644.2 tok/s) | 86.02 tok/s | 2.47 GiB | passed, IDS64_SAME |
| pr3 r_full | s200k's exact settings, 64 answers | 305.02 s (636.0 tok/s) | 131.49 tok/s (guessing) | 1.07 GiB | passed, IDS64_SAME |
| pr3 r_novoc | the same without the draft vocabulary | - | - | 1.07 GiB | **exit 1**: "card 0000:23:00.0: card-to-card exchange timed out waiting for card 5" |
| pr3 r_full2 | r_full again | 304.76 s (636.6 tok/s) | 147.00 tok/s (guessing) | 1.07 GiB | passed, IDS64_SAME |

- pr1 (`pr1-summary.txt`, `pr1-c_tp115.log`, `pr1-c_tp115-gdb-bt.txt`): tp115 started 21:24:04 and never wrote a
  prompt line or an exit. The backtrace shows `main` -> `own41::Backend41::~Backend41()` -> `queue_impl::wait` ->
  `urQueueFinish` -> Level Zero: the engine was in its teardown waiting on a card queue that never finished, with the
  cards idle (pr2.sh header). It sat there about 12 hours and was stopped on 2026-11-16 about 09:22 (the last writes
  in its folder); its two other planned probes never ran. **So the failure predates tp116 / tp117.**
- No kernel fault line in any of these runs' kernel logs (the scripts' fault patterns). The failures were the engine's
  own exchange time-out (tp115: a hang), and the two time-outs named different cards (card 0 waiting for card 1,
  card 1 waiting for card 5).
- Tally at 194K with the draft loaded: 6 starts, 3 did not finish (s200k, pr1 tp115, r_novoc), 3 passed (g_draft,
  r_full, r_full2). s200k's exact settings failed once and passed twice (r_full, r_full2). Without the draft at 194K
  (x200k, g_tg) and with the draft at 95K (g_s95big, same 1.07 GiB free) every start passed. All passing outputs were
  identical to their references.
- **Conclusion: the failure is intermittent and older than tp117** (the tp115 binary also failed the case); tp117's
  layout change is not its cause. Not yet located. A diagnostics build is queued: tp118 = tp117 + turns-1 + topk-m
  (opt-in) + **tpd-1** (per-card host timing per step: "tpd:" lines for slow blocks, timings in the exchange time-out
  error), gated by c118, which runs guessing at 194K twice so that tpd-1 can show where the wait starts if the failure
  recurs (`build118.sh`, `c118.sh`, `chainq118.sh` in dsv41-work; the queue started the tp118 build when pr3 ended at
  09:55:35).
- Files: `summary.txt`, `marks.txt`, `s200k.log` (c117); `pr1-summary.txt`, `pr1-c_tp115.log`,
  `pr1-c_tp115-gdb-bt.txt`; `pr2-summary.txt`; `pr3-summary.txt`; scripts `c117.sh`, `pr2.sh`. Run folders under
  `/home/steve/dsv41-work/runs/`: `c117-20261115T2108/`, `pr1-20261115T2124/`, `pr2-20261116T0925/`,
  `pr3-20261116T0940/`.
