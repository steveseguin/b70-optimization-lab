# Round 19, gate tg108 (build tp108, 2026-11-13 02:06-02:26)

tp108 = tp107 + `OWN_PX_BCS` default 1 (copy-engine pushes for the prompt halves; acts only with `OWN_PX`) + rux4-1
(`OWN_RUX4`, opt-in: prompt routed experts with a sub-block's grid gathers issued back to back; helper
`round19-rux4/`) + xchg2-1 (`OWN_XPUSH2`, opt-in: the one-token and check exchanges as peer-ordered pushes, each card
writing to one peer at a time; helper `round19-xchg2/`). Speed only from unprofiled runs alternated, no sampler.

## In plain words

- **Every trace identical, every answer the same, no fault.** 18 traces: stage 1 defaults (blocks 1-256, checks 2-6),
  RUX4 at blocks 16 / 64 / 256, XPUSH2 at 1 / 3 / 5 / 64; 3K traces px-512 (copy engine by default), px-512 + RUX4,
  256 + RUX4. 8 of 8 guessing runs SAME AS the plain run, every guess log equal to tg105v's.
- **XPUSH2: +3 % writing everywhere.** Plain tp107 105.91 / 106.06, tp108 105.89 / 106.22, **tp108 + XPUSH2 109.05 /
  109.25 tok/s**. Guessing code 147.48 / 148.16 -> **152.45 / 152.36**; analysis 163.74 / 164.81 -> **169.14 /
  169.29** (check 13.6 -> 13.2 ms, 15.5 -> 15.0 ms per cycle).
- **RUX4: prompt reads -5 %.** 3K px-512 5.12 / 5.01 s -> **4.81 / 4.83 s** (692 tok/s); 10K 16.37 -> **15.65 s**
  (678 tok/s). Bench prediction was ~4.8 s.

## Decision

Both become defaults in the tp109 sources (`OWN_XPUSH2` default classes 0x0F, `OWN_XPUSH2=0` restores the tp108
exchanges; `OWN_RUX4` default on, `OWN_RUX4=0` restores the tp108 forms). Until tp109 is built, the best settings on
tp108 are `OWN_XPUSH2=1 OWN_RUX4=1` with the prompt mode `OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1`.

## Files

`tg108-summary.txt`, `marks.txt`, `spec/` (guess logs). Scripts in `../round18-scripts/strategy/` (build108*.sh,
tg108.sh).
