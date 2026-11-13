# Round 19, gate tg106 (build tp106, 2026-11-12 22:02-22:26) + ck2rep (22:47-22:50)

tp106 = tp105 + ck2-1 (`OWN_CK2`: the FFN pre-norm + mix dot rows + router of 2-3-token checks in fewer launches,
opt-in) + three defaults flipped: `OWN_FL=3`, `OWN_U3_NOPAIR=1`, `OWN_MT_EU_HEAVY=0`. Guessing runs use BEST + the
draft vocabulary. Speed only from unprofiled runs alternated. No sampler.

## In plain words

- **Every trace identical** (prompt 1 at blocks 1-6 / 64 / 256 with the new defaults and with every CK2 form; the old
  defaults `h1old`; 3K at 256 and px-512). All guessing runs SAME AS the plain run (18 of 18), all 3K answers the same.
- **Plain writing:** tp105 with the new defaults as switches 105.74 / 105.73 tok/s, tp106 105.79 / 105.09: the same.
- **Guessing (BEST + vocabulary), tp106 -> + CK2:** code 146.31 / 147.13 -> 148.15 / 147.79 (forms-only runs 147.37 /
  147.17); analysis 162.80 / 163.89 -> 164.90 / 164.45 (164.55 / 164.49); prose 122.99 -> 123.93; docs 151.90 ->
  153.08; ops 144.26 -> 145.11. **CK2: +0.6-1.1 %**, checks -0.1 to -0.2 ms per cycle, as ck2 predicted.
- **3K read:** 5.57 s at 256, **5.45 s with px-512** (613 tok/s).
- **One guess-log difference:** ops with CK2 (`ops_c1`, round 55): the draft's confidences 2-5 differed once (same
  text). `ck2rep`: six more ops runs (CK2 x3, each form alone, CK2 off): all 222 rounds identical to the reference.
  So it is a one-off, like tg100's code_w2_2 (round 66, before CK2 existed): 2 differences in 238 guess-log checks
  so far, both on the draft side (suspect: the draft reads its input features before they are final,
  `OWN_DR_NOWAIT`). It changes guesses only, never answers (every token is checked by the full model).

## Decision

CK2 becomes a default in tp107 (`OWN_CK2=0` turns it off). The draft-side race is noted as an open item (rate ~1 %
of runs, effect: one round's guesses).

## Files

`tg106-summary.txt`, `spec/` (guess logs; names: `_b` = tp106, `_c1` / `_c2` = CK2 rounds, later overwritten by the
forms-only arms of the same names in code / analysis), `ck2rep/`. Scripts: `../round18-scripts/strategy/tg106.sh`,
`ck2rep.sh`.
