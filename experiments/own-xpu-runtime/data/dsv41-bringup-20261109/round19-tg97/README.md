# Round 19, gates tg97 + tg97b (build tp97, 2026-11-11)

tp97 = tp96 with the tg96b winners as defaults (`OWN_ATT_T=1`, `OWN_MT_CK=1`, `OWN_MT_RUX=1 OWN_MT_RUX_CAP=6`)
+ qb-off-2 (`OWN_QB_OFF_M`, opt-in) + k7-2 (`OWN_K7`, opt-in). Build 13:39-13:56 (1006 s). tg97 13:56-14:07;
tg97b 14:09-14:33 (ALLDONE).

## In plain words

- **The new defaults hold.** Every trace identical at blocks of 1, 2, 3, 4, 5, 6, 16, 64 and 256 tokens, and with the
  old defaults switched back on (5 and 64). Normal writing 100.4 / 100.6 tok/s (tp96 with the same settings by hand:
  99.9 / 100.9). Guessing code 138.4 / 139.2, analysis 153.0 / 150.5, prose 117.2, after a 3K prompt 141.3. All 16
  guessing runs gave the same answers as without guessing, and their guess logs equal tg96b's ATT + CK runs.
- **qb-off-2 hung both 16-head cards** at its first run (h2qbm, prompt blocks of 2): the driver reset the stuck
  compute jobs on card 2 (14:02:21) and card 5 (14:02:22). The health probe passed at 14:08. Back to its helper.
- **k7-2 is correct but does not pay.** Every K7 trace identical (blocks 1, 5, 16, 64, 256; sites 1, 2 and both),
  but normal writing is 1.5 % slower (98.3 / 99.2 against 100.4 / 100.6) and guessing is neutral (code 138.9 /
  136.4, analysis 153.5 / 150.1). The sender's extra 2.7 us per exchange lands on the critical path. Stays off.
- **A looser guess threshold is neutral overall.** TAU 0.45: code 141.7, analysis 149.4; TAU 0.40: 140.5 / 150.0,
  against 138.4-139.2 / 150.5-153.0 at 0.5. Code gains about 2 %, analysis loses about as much. TAU stays 0.5.
- **The 3K read was 0.9 % slower on tp97** (493.2 / 492.7 against tp96 with the same settings 497.7 / 497.3, tp96
  always first in its round). No setup line differs. tg97c repeats it with tp97 first.

## Correctness

tg97: h1-h6, h16, h64, h256, h5old, h64old TRACE_IDENTICAL + IDS40_SAME; h2qbm exit 1 (DEVICE_LOST after the
driver's job timeouts), STOP_FAULT. tg97b: the defaults' lines carried over, 8 K7 traces identical (h1k7 twice),
3K traces b64 / b256 / b64k7 identical, 7 SPEED128_SAME, 4 ANSWER256_SAME, 16 / 16 guessing SAME, 8 GLOG_SAME.

## Fault (`fault-20261111T1407/`)

`kernel.txt` (journal), `h2qbm.log`, `probe1.txt` (six-card barrier + all-reduce passed). The heavy cards' q_b pull
waited for the helpers' flags; no in-kernel timeout fired before the driver's job timeout.

## Files

`tg97-summary.txt`, `tg97b-summary.txt`, `spec/` (tg97b spec logs), `check-cost-by-guesses.txt`. Scripts in
`../round18-scripts/strategy/` (build97.sh, tg97.sh, tg97b.sh, tg97c.sh).
