# ckm: the cost of each extra token in a guessing check (helper, 2026-11-13 12:50-13:40)

Goal (brief): cut the cost per extra token of a check of M = 2-6 tokens (today code 158 / analysis 176 tok/s, tp110).
Stop line: < 0.3 ms per average check predicted (tl105 mix M = 1..6 at 32 / 30 / 20 / 6 / 8 / 4 per 100) = write up, stop.

## In plain words

Each extra guessed token in a check costs about 2 ms (2.08 code / 1.97 analysis; section 1). Of that, 43 % is the
routed experts reading new experts (already studied and closed by xperm), ~30 % is the cards exchanging data and
waiting for the slowest card, and the rest is dense rows close to their arithmetic floor. Everything that is left to
win adds up to about **0.2 ms per average check (realistic), 0.32 at best**, which is under the 0.3 ms stop line.
So: **written up, stopped** (step 2). Nothing was built, patched or run besides two timeline runs (plan1).
The cheap settings-only candidates are listed in section 3 for the main thread's next gate.

## State (resume here)

- 13:01-13:12 plan1 (unit ckm-plan1): tp110 check timelines, code and analysis, `runs/tl1/` (both SAME AS the plain
  run, guess logs equal to tg105v: `runs/tl1/summary.txt` lines 3, 6, 11, 14).
- 13:40 written up; stopped at the stop line. Nothing built, nothing patched. No GPU fault seen. No STOP file.
  No ckm units or locks left.

## Files

- `tools/forms_by_m.py` timeline + guess log -> per card and M, every kernel name: launches, us/launch, us/check
- `tools/roles.py` / `tools/roles_ck.py` kernel names -> roles (q_b, o_a, o_b, experts, xchg, ...); roles_ck sums per
  check first, then takes the median per M (the numbers below)
- `tools/xwait.py` exchange time per card split into WAIT (until the last card arrives) and MOVE (after), who is last,
  per exchange part (M = 1 checks are misaligned there: ignore them)
- `tools/xseg.py` per card compute (non-exchange busy) and the critical path = sum of per-segment max + exchange
- `tools/gaps.py` span vs busy, gaps > 0.5 us and the launch after each gap
- `tools/simheads.py` moves the attention segments of cards 2 / 5 to other cards (scaled by card speed), new path
- `envs.sh` the gate's env strings (tg110.sh); `six.sh` / `one.sh` / `drive.sh` copies of qkv's (unit prefix ckm-)
- Outputs: `ana/*_tl1c.txt` (code), `ana/*_tl1a.txt` (analysis), `ana/*_tg109.txt` (tp109, first look)

## 1. Ledger: what grows per extra token, and why

Unprofiled check ms by M (median per M, `runs/tg110/*-spec.txt`, column 9 by column 6 + 1):

| run | M=1 | 2 | 3 | 4 | 5 | 6 | ms per extra token (2 -> 6) | tl105-mix average |
|---|---|---|---|---|---|---|---|---|
| code_b1 | 9.37 | 11.40 | 13.46 | 15.26 | 17.21 | 19.75 | 2.09 | 12.19 |
| code_b2 | 9.33 | 11.34 | 13.32 | 15.13 | 17.09 | 19.67 | 2.08 | 12.11 |
| analysis_b1 | 9.46 | 11.48 | 13.69 | 15.25 | 17.55 | 19.46 | 1.99 | 12.31 |
| analysis_b2 | 9.43 | 11.47 | 13.59 | 15.13 | 17.43 | 19.32 | 1.96 | 12.25 |

Timeline runs (`runs/tl1/tlc-tl.txt`, `tla-tl.txt`, checks 20-119; per-kernel times valid, overlap not): card 2's busy
time per check by role (`ana/roles_ck_tl1c.txt`, us, median of per-check sums):

| role | M=2 | 3 | 4 | 5 | 6 | us per extra token | why it grows |
|---|---|---|---|---|---|---|---|
| routed experts | 2971 | 3743 | 4599 | 5242 | 6359 | 847 | new experts: 67-87 % of (token, expert) pairs bring an expert no other token of the check uses; each new expert costs its decode (~4.3 us, instruction-bound); an extra token on an expert already decoded 0.6-1.25 us, near the mul+add floor (`../xperm/README.md` outcome 3; `../ck2tok/README.md`: 1.75x the bytes for 1.48x the time at 2 tokens). Grows slower than its bytes. Closed by xperm. |
| exchanges (move + wait) | 2069 | 2502 | 3403 | 3653 | 4394 | 581 | see the exchange table below |
| attention core | 572 | 624 | 598 | 866 | 1100 | 132 | 16 heads on cards 2 / 5; card 0 (8 heads) 58 us per token |
| o_b rows | 698 | 829 | 860 | 1014 | 1008 | 77 | M = 5 runs T3 groups (TGM 5:3) = 6 tokens' work: 1014 at 5 vs 1008 at 6 |
| q_b (Pace) | 942 | 1011 | 1019 | 1083 | 1180 | 60 | at its ALU floor (1.5 us per launch per token vs floor 1.84; exact mul+add ~5.7 T pairs/s) |
| shared gate+up | 442 | 550 | 528 | 619 | 633 | 48 | as o_b: M = 5 ~ M = 6 |
| shared down | 271 | 318 | 420 | 453 | 457 | 47 | M = 4 jump: DSPLIT's finishes ride it from 4 tokens; M = 5 ~ M = 6 |
| norms + mix | 618 | 838 | 784 | 923 | 807 | 47 | M = 3: the dot rows ride (HcDotsRows) until DSPLIT / SKDOTS take them at 4 |
| q_a + kv share | 318 | 334 | 399 | 427 | 501 | 46 | G1 share 7.5 -> 11.6 us per Q8 launch, 8.9 -> 14.3 per Q6 launch |
| o_a rows | 710 | 734 | 781 | 812 | 865 | 39 | 16-head cards (PaceK) |
| head, engram, draft input, other | | | | | | ~45 | small per-token forms |
| **total busy** | 10804 | 12731 | 14446 | 16340 | 18597 | **1948** | |

Card 0 (275 W, 8 heads) and card 5 (230 W, 16 heads) in the same file: totals 1960 / 1953 us per token, card 0's
exchange share 718 (it waits more), card 5's 425 (it is usually last). Analysis: `ana/roles_ck_tl1a.txt`.

Critical path (sum over exchange stretches of the slowest card's compute + the fastest card's exchange,
`ana/xseg_tl1c.txt`): 10.59 / 12.52 / 14.12 / 16.06 / 18.19 ms at M = 2-6 (code). Card 2's span: 11.14 / 13.27 /
14.95 / 16.87 / 19.02 ms; span minus busy (gaps) 0.34-0.54 ms per check (`ana/gaps_tl1c.txt`).

### Exchanges: moving vs waiting (`ana/xwait_tl1c.txt`, us per check, card 2 unless noted)

Move (after the last card arrived) per exchange, by part (move per check / number of exchanges):

| part (form) | M=2 | 3 | 4 | 5 | 6 | grows faster than its bytes where |
|---|---|---|---|---|---|---|
| output-a, 40 per check | 6.7 (XchgQ) | 11.4 (pull) | 17.6 (pull2) | 18.2 (pull2) | 18.0 (pull2) | at 3: form change XchgQ -> pull (the mask's bit 5 is off: xchg2's bench saw no gain for the real heavy-card shape, -0.7..+0.2 us); at 4: +6 us from OWN_MT_DSPLIT's second region on XchgPull2; flat 4-6 = the region's fixed cost, not bytes |
| expert act, 40 | 12.3 (pull) | 13.3 (pull) | 19.0 (pull2) | 21.8 (pull2) | 25.1 (pull2) | at 4: +5-6 us, the same second region (the FFN mix's partials) |
| h rows, 81 | 6.5 (XchgQ) | 6.8 | 6.7 | 10.1 (XchgQ lockstep) | 9.9 | at 5: > 1024 vec4 per card switches to the lockstep (xchg2: the only robust form there) |
| q_a + kv, 40 | 5.7 (XchgP) | 7.5 (XchgP) | 9.3 (XchgP) | 6.9 (XchgQ) | 6.8 (XchgQ) | XchgP past ~3 tokens (OWN_QKV_XQ = 5) |
| engram, 3 | 17 | 24 | 29 | 36 | 41 | |

Totals (all parts): move 1.57 / 1.92 / 2.46 / 2.78 / 2.93 ms per check at M = 2-6 (code; analysis 1.57-2.96,
`ana/xwait_tl1a.txt`). Wait: card 2 0.49 / 0.61 / 0.94 / 0.94 / 1.49 ms; card 0 0.98 -> 2.57 ms; card 5 0.40 -> 0.67.

Who arrives last (instances per check at M = 2 / 6): card 5 57 / 81, card 4 37 / 62, card 1 49 / 51, card 2 36 / 6.
Card 5 leads the second-last by 116 us per check at M = 2, 368 us at M = 6. The longest launch before the exchange on
the last card: the routed experts (RoutedUQ IQ2_S / IQ2_XXS) and the Pace q_b / o_a launches.

Card speed in the non-attention stretches, relative to card 0 (`ana/simheads_tl1c.txt`; analysis in
`ana/simheads_tl1a.txt`): M = 2: c1 1.021, c2 1.000, c3 0.995, c4 1.004, c5 1.023; M = 6: c1 1.062, c2 1.015,
c3 0.998, c4 1.065, c5 1.071 (analysis M = 6: 1.078 / 1.026 / 1.002 / 1.061 / 1.073). The 230 W cards 1, 4, 5 slow
down as the check gets heavier (card 2, also 230 W, much less); cards 0 and 3 (275 W) do not.

### Gaps (`ana/gaps_tl1c.txt`, `ana/gaps_tl1a.txt`)

- Check start, host-fed: the engram rows of the guessed tokens (EngRowsA, layers 1 / 14) wait for the host: 103 / 207 /
  165 / 248 / 105 us per check at M = 2-6 (code), 98 / 143 / 134 / 160 / 63 (analysis); ~0-7 us at M = 1 (no
  guesses; the anchor's rows are asked during the draft, OWN_ENG_EARLY). The runs read 90.9 / 76.9 MiB from disk
  during decode, engram rows 272 / 322 us per step on the host (`runs/tl1/summary.txt` lines 7, 15).
  Over the tl105 mix: ~0.11 (code) / 0.08 (analysis) ms per average check.
- Register-mode changes around 256-register launches (PaceK, WsQ6<32>/<16>, XchgPull): gaps > 0.5 us sum 225 / 355 /
  293 / 591 / 404 us per check at M = 2-6 (incl. the engram wait above).

## 2. Predictions (per average check, tl105 mix; before any code)

| lever | kind | predicted | basis |
|---|---|---|---|
| B: the 16-head groups on the 275 W cards 0 / 3 (`OWN_TP_HEADS=4,2,2,4,2,2`) | setting; keeping the prompt split (3,3,3,3,2,2 for >= 16 tokens) needs a small code change, because setting OWN_TP_HEADS replaces that default (own_run_v41.cpp 475-480) | 0.054 code / 0.086 analysis | simheads: moves the attention stretches to cards 0 / 3 at their speed; [3, 0] gives the same, [0, 1] 0.010, [1, 4] -0.007 |
| C: rows weighted by card speed (`OWN_TP_WEIGHTS`, ~960 on cards 1 / 4 / 5) | setting | 0-0.085 | the 2-7 % speed gap above on ~5 ms of row-split work; e66 lost with weights used for head balance (different stretch); speeds vary run to run |
| E: XchgPull2's second region (OWN_MT_DSPLIT partials) costs ~5-6 us per output-a / act exchange at M = 4-6 | code (exchange kernel) | <= 0.065 | 80 exchanges x ~4.5 us saved x 18 % of checks |
| F: the guessed tokens' engram rows (host disk reads after the draft) | host code | 0.03-0.05 | the measured wait is 0.08-0.11 in full; the guesses exist only at the draft's end, so at best part of it |
| D: M = 5 forms (T3 groups compute 6 tokens) for o_b / shared gate+up / shared down | code (WsTab / TGM) | ~0.011 | ~0.13 ms per M = 5 check x 8 % |
| A1: `OWN_QKV_XQ=4` (and 3) | setting | ~0.014 | q_a + kv move 373 -> ~274 us at M = 4; ~30 us at M = 3 |
| A2: `OWN_XPUSH2_MASK=0x3F` (output-a 3-6 / act 2-3 as XchgQ) | setting | ~0.01 | xchg2's bench, heavy-card shape: -0.7..+0.6 us per exchange (`../xchg2/data/README.md`) |
| A3: `OWN_MT_DSPLIT_MIN=7` (frees output-a for bit 5) | setting | negative | tune92: DSPLIT saves 0.25-1.5 ms at 4-6 tokens; bit 5 gains ~0 |
| dense forms otherwise | - | ~0 | the per-token dense slope (~0.35 ms) is within ~0.06 of the mul+add floor (0.28) |
| routed experts | - | ~0 | closed by xperm (new-expert decode, instruction-bound) |

Sum: realistic ~0.19-0.23 ms per average check (~1.3-1.6 % of a 14.3 ms cycle), optimistic ~0.32 (B at 0.086, C at
0.085, E, F, D, A1, A2 all at their best). **Under the stop line: written up and stopped at step 2.**

## 3. For the main thread (untested here)

Settings-only arms, cheapest first, each a six-card guessing A/B (off/on/on/off) + prompt-1 traces at blocks 2-6:
1. `OWN_TP_HEADS=4,2,2,4,2,2` (B). Traces must be identical (whole groups, no pair exchange; a layout change only);
   it also moves the prompt blocks to whole groups (the 3,3,3,3,2,2 prompt split is lost unless a base-layout switch
   is added), so check the 3K read too.
2. `OWN_QKV_XQ=4` (A1) and `OWN_XPUSH2_MASK=0x3F` (A2): small, both inside a single run's noise (e66: up to 2.7 %
   between repeats), so only worth adding to a gate that runs anyway.

Code candidates, if a later round wants them: E (cheaper second region in XchgPull2), F (start the guessed tokens'
engram reads sooner), D (a 5-token group form).

## 4. Earlier look (tp109, `runs/tg109/tl_ck.txt`)

`ana/forms_tg109_card2.txt`, `ana/forms_tg109_c0125.txt`, `ana/xwait_tg109.txt`, `ana/xseg_tg109.txt`,
`ana/gaps_tg109.txt`: the same picture before the q_a + kv split (tp110 = tp109 + qkv-1).
