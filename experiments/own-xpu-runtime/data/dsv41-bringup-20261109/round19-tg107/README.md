# Round 19, gate tg107 (build tp107, 2026-11-12 23:57 - 2026-11-13 00:15)

tp107 = tp106 + `OWN_CK2` on by default (2-3-token check forms, ck2-1) + bcs-1 (`OWN_PX_BCS`, opt-in in tp107: in a
prompt block run as two halves (`OWN_PX=1`), every per-layer exchange and the engram rows travel as pushes on each
card's copy engine, posted writes instead of card-to-card reads; `dsv41-work/bcs/README.md`). Speed only from
unprofiled runs alternated. No GPU sampler, no b300.

## In plain words

- **Every trace identical, every answer the same, no fault.** Stage 1 (against runs/ab1): h1 / h5 / h64 / h256 / h4 /
  h2 / h3 / h6 defaults, h3 with CK2 off, h64 with the copy-engine pushes. 3K traces against the tp84 reference:
  blocks of 256, px-512, px-512 + copy engine, 256 + copy engine. 10K prompt (10,621 tokens): the copy-engine px-512
  trace equals the blocks-of-256 trace, and its first two answer ids equal the u84 run's. Guessing: 4 of 4 SAME AS the plain
  run, every guess log equal to tg105v's.
- **Prompt reads (answers the same):** 3K px-512 5.46 / 5.53 s -> with the copy engine **5.07 / 5.03 s (-8 %)**;
  copy engine at blocks of 256 5.28 s. 10K: px-512 17.78 s -> **16.45 s with the copy engine (-7.5 %; 647 tok/s)**.
- **Plain writing unchanged** (the new code does not touch one-token steps): tp106 100.86 (cold page cache) / 106.03,
  tp107 104.74 / 106.35 tok/s.
- **Guessing unchanged** (tp106 with CK2 = tp107's default path, the same code): code 147.06 / 143.81, analysis
  163.64 / 164.68. code_b's 143.81 is a host-side outlier: engram rows 561 us per step (vs 278 cold / ~115 warm
  elsewhere) with almost no disk read; check 14.02 ms vs 13.68.
- Side reading: runs that read engram rows from disk (the first run of a prompt after other prompts: 75-93 MiB) have
  checks ~0.08-0.15 ms slower than the warm rerun (tg104-tg107 summaries), under 1 %. The 34 MiB read in the
  answers after some 3K reads is page-cache churn, not the prompt mode (p3k_bcs_2 read it too).

## Decision

The copy-engine pushes become the default for prompt halves in tp108 (`OWN_PX_BCS` default 1; the backend forces 0
when `OWN_PX` is off, so non-overlap runs create nothing new). Recommended prompt mode: `OWN_PROMPT_BLOCK=512
OWN_PX=1 OWN_PX_BIG=1`. Posted writes also take most card-to-card READ traffic out of the prompt (only the pair
swaps stay pulls), which is the traffic the host resets pointed at.

## Files

`tg107-summary.txt`, `marks.txt`, `spec/` (guess logs). Scripts in `../round18-scripts/strategy/` (build107*.sh,
tg107.sh).
