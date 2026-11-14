# tlpx112: prompt budgets on tp112 at the 200 W cap, 3K (pieces 3-4) and late in the 95K document (pieces 183-184)

Profiled timelines (per-kernel times valid, overlap between queues not), production prompt mode px-512 + copy engine,
`tlpx112.sh`, 2026-11-13 23:24-23:31. Tool: `round19-tg109/tools/one_budget.py` (ms per 512-token piece, mean of the
two recorded pieces). Timelines (5.5 MB each) kept out of git: `dsv41-work/runs/tlpx112/`.

## In plain words

- **Late in a 95K document a piece costs ~10 % more than early on** (card 2: 806.6 -> 889.1 ms busy). The growth is
  the index scoring (IndexerScoreBM 2.0 -> 37.6 ms per piece, IndexerScoreBCM 0 -> 10.8, top-k ~+1.5; these are
  already split by tokens since idxsplit-1) and the exchanges / waits (+28 ms). Attention itself barely grows (OutM
  32.4 -> 34.4, ScoreM 19.6 -> 19.8).
- **Under the 200 W cap card 3 (0000:83) is the slow card:** the same work takes it ~12 % longer than cards 0-2
  (3K: experts 406.6 vs 362.4-371.7 ms, dense rows 287.1 vs 254.1-261.0) and it is the only card that does not wait
  (exchanges 9.6 ms; cards 0-2 wait 80-98 ms, the 8-head cards 4-5 147-171). Uncapped, card 3 was one of the two fast
  275 W cards. Software lever (same bits): give card 3 fewer attention heads in prompt blocks - `hl112.sh` tries
  OWN_TP_HEADS 3,3,2,2,3,3 and 3,3,3,2,3,2 (traces first, then the 3K read A/B).

| card (3K, per piece) | experts | dense rows | exchanges (waiting) | attention + index |
|---|---|---|---|---|
| 0 (03) | 362.36 | 254.14 | 98.08 | 21.89 |
| 1 (23) | 363.91 | 255.75 | 94.69 | 21.92 |
| 2 (43) | 371.72 | 260.99 | 80.35 | 22.39 |
| 3 (83) | 406.56 | 287.08 | 9.57 | 24.66 |
| 4 (a3) | 346.36 | 210.65 | 171.47 | 14.32 |
| 5 (e3) | 359.18 | 219.96 | 146.54 | 15.02 |

Files: `b3.txt`, `b95.txt` (all six cards, top 30 families for card 2), `summary.txt` (run lines; reads 5.55 s and
162.47 s under profiling, card memory free after load).
