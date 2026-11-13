# Round 19, gate tg105 (build tp105, 2026-11-12 19:40-20:22, ALLDONE)

tp105 = tp104 + xorP compiled in (`-DOWN_R2_XORP=1`, the routed kernels' butterfly as xor-permutes: default path) +
fl-1 (`OWN_FL=1..3`, fold launches, opt-in) + xperm-4 A (`OWN_U3_NOPAIR=1`, no pair code below 16 tokens, opt-in) +
sw (`OWN_MT_SW`: 1 re-picked check forms, 2 one-token 128-register forms, 3 both; opt-in). Readiness survey:
`tp105-readiness.md`; static b300 hunt: `b300-static-hunt.md`. Build 1222 s. No GPU sampler (removed from gates).

## In plain words

- **Every trace identical (28 prompt-1 + 3 3K traces), every answer the same, all 18 guessing runs SAME AS the plain
  run, every guess log equal to tg100's.** xorP is exact on the default path; FL 1 / 2 / 3, K7 + FL, NOPAIR, SW 1 / 2
  / 3 and everything together are exact.
- **Plain writing (alternated x2):** tp104 103.33 / 103.94; tp105 104.02 / 104.28 (+0.5 %, xorP); **`OWN_FL=3`
  106.14 / 106.12 (+2.0 % over tp105, +2.5 % over tp104)**; `OWN_MT_SW=2` 105.36 / 104.56 (+0.8 %); FL + SW2 105.70 /
  106.59 (= FL alone).
- **Guessing (BEST, no vocabulary; alternated x2):** code tp104 143.61 / 144.26, tp105 144.86 / 144.99 (+0.7 %),
  everything (FL 3 + NOPAIR + SW 3) 145.63 / 145.38; analysis 159.19 / 159.84 -> 161.71 / 161.41 (+1.3 %) -> 161.24 /
  161.36. Single arms: NOPAIR code 145.40 / analysis 161.82, FL 145.60 / 161.34, **SW1 143.98 / 160.59 (slower)**.
- **3K read at 256:** tp104 5.71 s, tp105 5.70; px-512 5.59.

## Decision

FL=3 and NOPAIR become defaults (next tree; until then in the gates' PL / BEST env). SW bit 1 (re-picked check forms)
lost: off. SW bit 2 adds nothing on top of FL: off. Expected with the draft vocabulary (tg105v): code ~147, analysis
~163 tok/s; plain ~106.
