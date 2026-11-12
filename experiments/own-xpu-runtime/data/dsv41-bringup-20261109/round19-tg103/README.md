# Round 19, gate tg103 (build tp103, 2026-11-11/12)

tp103 = tp102 + px-1b (the overlap's halves read their own rows in the fused router; pb256 helper) +
`OWN_TIMELINE_PROMPT` (prompt-block timelines on both queues; analyzer `engine/tools/perf/dsv41_tl_prompt.py`) +
xperm-3 compiled in (IQ2_XXS / IQ3_XXS grid tables copied from a constant image) + pace-2 (`OWN_MT_PACE_ROLES` 8 / 16
/ 32 / 64: every card's q_a + kv, output-b, shared down, shared gate + up with the router in one-wave forms at 2-6
tokens; opt-in) + G128 and pace-1 on by default. Build 23:32-23:52 (1221 s); gate 23:53-00:34 (ALLDONE). A = tp102
with `OWN_PAIR_G128=1 OWN_MT_PACE=1` (= tp103's defaults), B = tp103, C = tp103 + pace-2 (`OWN_MT_PACE_ROLES=127`).

## In plain words

- **Every trace identical (28)**, the overlap included: prompt-1 at 1-6 / 64 / 128 / 256, everything off, G128 off,
  pace-2 at 2-6, the overlap at blocks of 36 (halves of 18) and its one-queue form; 3K traces at 64 / 256, pace-2 at
  256, the overlap at 256 three times, one-queue, 128, 250 and with 32 pull groups. `OWN_PX_CHECK`: 0 bad blocks. All
  21 guessing runs gave the same text as plain writing; all 13 guess logs equal.
- **Plain writing +0.3 %** (xperm-3): A 103.66 / 104.23 tok/s, B 104.11 / 104.42.
- **The overlap is exact now but saves nothing yet**: 3K read at 256 base 5.71 / 5.71 s, overlap 5.71 / 5.68, with 32
  pull groups 5.70 / 5.70, one-queue 6.10 / 6.10; blocks of 128 5.92. The prompt timelines (pb256 helper, blocks 3-4)
  show why: a pull overlaps only the one compute launch queued right after it; the launch after that waits for the
  whole pull (0 exceptions in 1,438 cases). Three pulls sit in front of tiny launches and hide almost nothing (~0.41 s
  per card over the read), and kernels beside a pull run 13-76 % slower (246 of 722 ms overlapped come back). Each
  card exposes one compute engine (Level Zero: ordinal 0 compute with 1 engine, ordinal 1 copy), so a second engine
  is not an option; the suspect is the barrier style the overlap uses (a barrier on the compute queue before each
  pull). Next: a one-card bench of fire / wait styles, the launch-order move (`OWN_PX_MOVE`), halves of 256 (blocks of
  512, `OWN_PX_BIG`).
- **pace-2 does not pay**: code 143.24 / 143.92 (C) against 143.83 / 143.68 (B), analysis 159.33 / 159.50 against
  160.05 / 159.90; checks of 2-6 tokens moved -0.3 to +0.2 ms. Stays off.
- **Guessing, B**: code 143.83 / 143.68, analysis 160.05 / 159.90, prose 120.35, after 3K (blocks of 256) 147.14;
  with the overlap 147.71 (guess log equal). With the draft vocabulary (and pace-2): code 143.84, analysis 157.47
  (that run read engram rows from disk: 586 us per step against ~125 normally; the page cache is tight beside the
  6.5 GB engine).
- **Threshold 0.40** (with vocabulary + pace-2): code 147.12 (+2.3 %), analysis 155.94 (-1.0 %): mixed again; TAU stays
  0.5.

## Check cost by guesses (median ms, round 2; `check-cost-by-guesses.txt`)

| run | 0 (1) | 1 (2) | 2 (3) | 3 (4) | 4 (5) | 5 (6) |
|---|---|---|---|---|---|---|
| code, A | 10.07 | 12.75 | 15.09 | 16.62 | 18.87 | 21.27 |
| code, B | 10.10 | 12.73 | 15.16 | 16.57 | 19.01 | 21.29 |
| code, C (pace-2) | 10.06 | 12.94 | 15.05 | 16.79 | 18.71 | 21.07 |
| analysis, B | 10.10 | 12.91 | 15.30 | 16.74 | 19.23 | 20.90 |
| analysis, C | 10.13 | 13.10 | 15.33 | 16.95 | 19.03 | 20.83 |

## Files

`tg103-summary.txt`, `spec/`, `check-cost-by-guesses.txt`. Timelines (2.7-5.6 MB each, kept out of git):
`dsv41-work/runs/tg103/{tl_one,tl_ck,tlp_base,tlp_px,tlp_pxs}.txt`. Scripts in `../round18-scripts/strategy/`
(build103.sh, build103-go.sh, tg103.sh).
