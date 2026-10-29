# Four-card TP toward the service configuration (2026-10-29)

**Question.** Exact TP2×PP2 decodes SC117 at 73.53 tok/s against 66.25 on two cards with identical outputs
([e2e suite](../e2e-suite-2026-10-29/RESULT.md)). Three gaps keep it out of the service: the teardown check flags TP
ranks, 64K context does not fit rank 1 under TP, and prompts are read token by token under TP. This file closes them in
order, then reruns the suite.

## 1. Teardown check accepts one record per card (CPU only)

**Cause.** The lab adapter's `Transport` inherits `close` from the sealed P195 pipeline (sha-pinned, not edited). Its
last statement requires `len(receipt["teardown"])==1` per rank. A TP rank writes one record per card (backend
`LevelZero:0:…` and `LevelZero:1:…`), so arm C stopped with "rank teardown failure" after both ranks had exited 0
with complete, safe teardowns.

**Change** ([lab/adapter6_tp.py](lab/adapter6_tp.py), diff against the e2e lab copy in
[lab/adapter6_tp.py.vs-e2e.patch](lab/adapter6_tp.py.vs-e2e.patch)):
- `rank_teardown_ok(receipt, rank, returncode, cards)`: the rank exited 0, its receipt passed and names this rank,
  and it holds **exactly `cards` records, one per card index 0..cards−1** (from the backend string). Every record must
  be `complete`, exit 0, safe to exit, 0 in flight, 0 live bytes, empty error. Anything missing, extra, duplicated or
  nonzero fails. `cards` is the rank's card count from `SC117_RANK_BDFS`.
- `Transport.close` calls the base close unchanged. The base reaches its receipt check only after FINISH, drain, the
  ownership receipt and closing. The override catches exactly that error in that state, then applies
  `rank_teardown_ok` to every rank. Every other error, and this one before closing, propagates.

**Gate** ([test_teardown.py](test_teardown.py), [output](test_teardown.out)): 8 tests pass. They use the real rank
receipts of the e2e suite.
- Arm C (two cards per rank): accepted with 2 cards, rejected with 1. The verbatim base expression rejects them,
  reproducing the incident.
- Arm A (one card per rank): accepted with 1 card, as the base does; rejected with 2 cards (a missing card record).
- Mutations, each card of each rank: every bad value or missing field in status, exit code, safe-to-exit, in flight,
  live bytes, error and backend fails. A missing, extra or duplicated record fails, as do a nonzero or absent return
  code, a failed receipt and a wrong rank. Record order does not matter.
- `close` with the base stubbed to end as the sealed one does: TP, one-card and mixed layouts close clean. The failure
  cases above raise "rank teardown failure", other base errors propagate unchanged, and a failure close checks no
  receipts.
