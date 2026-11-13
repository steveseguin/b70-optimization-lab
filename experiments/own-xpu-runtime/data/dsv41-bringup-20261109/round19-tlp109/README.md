# Round 19, tlp109 / tlpx109: prompt budgets on tp109 (2026-11-13 ~04:00-04:25)

Timelines (profiling on: per-kernel times valid, overlap between queues not; speed numbers from these runs are not
used). Production prompt mode `OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1` (two halves of 256 in flight, copy-engine
exchanges), plus plain blocks of 256 for comparison. Parts per card from `round19-tg109/tools/one_budget.py`
(per recorded block, ms; "dense rows" includes their riders; RoutePMRows (router) counts under experts; OutM, the
attention output, under small/other).

## In plain words

- **A 3K prompt, per 512-token piece (~720 ms on card 2):** expert kernels 364 ms (51 %), dense rows 248 ms (34 %),
  attention + index ~60 ms (OutM 30, ScoreM 18, index 9), norms + mix 30, exchanges ~11 on card 2 (the critical card;
  card 0 waits 82). Against the strict FP32 floor (separate multiply and add at 5.73 T pairs/s per card): experts run
  at ~31 % of it (~112 ms per piece), dense rows at ~72 % (~179 ms, a third of it the replicated q_a + kv / router rows).
- **34K into a document (pieces 62-63, ~850 ms):** the same, plus the index scoring: IndexerScoreBM 70 ms +
  IndexerScoreBCM 58 ms + top-k ~4 ms per piece (9 ms at 3K). That is the whole growth with context. The engine
  computes it on all six cards for every token (each card scores every token of the piece against its own mirror of
  the index keys): helper **idxsplit** splits it by tokens and all-gathers the 512-entry lists (predicted ~-12 % per
  piece at 32K, ~-25 % near 95K).
- Blocks of 256 without PX (3K, ~400 ms per 256 block): experts 175, dense 114, exchanges 71 (exposed), so PX + the
  copy engine hide ~60 ms of exchanges per 256 tokens.

## Files

`summary.txt` (run lines: 3K px-512 5.13 s and 256 5.50 s under profiling; 34K 53.7 s), `px512-3k-blocks3-4.txt`,
`b256-3k-blocks3-4.txt`, `px512-34k-blocks62-63.txt`. Timelines (2.7-5.5 MB) kept out of git:
`dsv41-work/runs/tlp109/`, `runs/tlpx109/`. Scripts: `../round18-scripts/strategy/tlp109.sh`, `tlpx109.sh`.
