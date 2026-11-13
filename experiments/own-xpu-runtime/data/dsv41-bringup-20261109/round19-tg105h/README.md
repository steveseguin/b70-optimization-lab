# Round 19, gate tg105h: plain expert-group order (2026-11-12 21:34-21:40, tp105 binary)

Helper rux3 (`dsv41-work/rux3/README.md`) measured on one card that prompt routed-expert kernels run 6.3 % faster
with the groups in plain order (ascending first slot) than heaviest first (`OWN_MT_EU_HEAVY=1`, the default since
groups could hold 16 slots; today's cap is 6). Same kernels and groups, only their order: same sums by construction.
Its main idea (bigger expert groups, rux3) lost 4-14 % per format and is not used.

## In plain words

- **Exact:** 3K traces identical to the tp84 reference at blocks of 256 and with px-512; all 256-token answers the same.
- **3K prompt read** (256 answers, alternated x2, all with `OWN_FL=3 OWN_U3_NOPAIR=1`): px-512 5.52 / 5.52 s ->
  **5.43 / 5.44 s (-1.5 %)**; blocks of 256: 5.69 / 5.70 s -> **5.56 / 5.56 s (-2.4 %)**. Predicted -2.9 % (card 2's
  kernels only); the gain is under it.

## Decision

`OWN_MT_EU_HEAVY=0` becomes the default in tp106 (`=1` brings the old order back).
