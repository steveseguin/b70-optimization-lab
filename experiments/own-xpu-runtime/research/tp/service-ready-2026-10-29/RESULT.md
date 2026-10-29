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

## 2. 64K context under TP: the QSA raw ring on both cards (route a)

**Choice: (a), the existing raw ring under TP.** The 32.43 GB that refused TP rank 1 at 64K was the *one-card* plan
check without the ring. The engine admitted the plan before the TP transform. The ring was excluded under TP only by
a guard (QSA sites are replicated under TP, so each card holds the same ring and runs the same pool launches), so (a)
needed no kernel work. Stage 3 (b) needs new head geometry in the prepare, pool and p49 attention kernels (about 22
literals), and it would add little speed now: TP stage 1 (rank 1) and stage 0 (rank 0 + draft) are balanced at about
10.8 ms, so a faster rank 1 alone does not shorten the pipeline period. Stage 3 stays the capacity lever for longer
contexts.

**Changes** (engine source, opt-in paths only; one-card plans byte-identical to `16ed1ff1a203`'s `plan.json`):
- `rank.hpp`: `OWNRT_QSA_RAW_RING=1` is admitted with `--tp-replicate`. The adapter already selects ring indexing per
  card from the bound allocation's size.
- `main.cpp`: `write_tp_plan`, a per-card admission of the two-card plan after the TP transform. Every buffer is
  counted on both cards; each card's weights are counted as loaded, with a TP slice storing only its rows; the exchange
  control words are added. It prints `tp card <c> planned_bytes`, writes `tp-plan.json` and refuses a card above
  30 GiB. `OWNRT_PLAN_ONLY=1` under TP now stops after it. `write_plan`'s storage rule moved into
  `plan_stored_bytes` and `plan_extra_bytes`, shared by both.
- Binary `fc18c9b0fe6a…` (build r2; [receipt](../../../engine/receipts/fc18c9b0fe6a.json)). Lab tooling:
  [arm_env.py](arm_env.py) (B19 flags at 65536 with ring, packing, 256-row prefill, `OWNRT_NO_DRAFT_TIMING=1`),
  [plan_probe.py](plan_probe.py), [make_launch.py](make_launch.py), [run_phase.sh](run_phase.sh), and lab copies of
  the rank drivers.

**CPU plan check at 65536** ([evidence/probes/](evidence/probes/); cap 32,212,254,720 B; plans exclude prefill shadows
and rank 0's draft, as before):

| Rank | One card (ring) | TP, per card |
|---|---:|---:|
| rank 1 | 32,199,218,796 (13 MB headroom) | **31,717,388,580** (495 MB) |
| rank 0 | 26,401,823,300 | **25,929,055,244** (+ draft on card 0) |

- One card minus TP per card is 481,830,216 B on rank 1. That is the saving the e2e suite measured in the card-0 census
  at 32K, to the byte, so the per-card accounting matches the allocator.
- Measured card-0 census at 65536: rank 1 TP 31,641,956,644 B (570 MB headroom; one card 32,123,786,860 without
  prefill shadows); rank 0 TP 29,151,572,890 B including the draft (one card 29,622,812,842).
- The three service binaries (`16ed1ff1a203`, `57744505eabc`, `6280724f7c75`) plan one-card rank 1 at 64K identically
  (32,199,218,796).

**Device gates** (binary `fc18c9b0fe6a`, context 65536, cards 23:00.0 + 47:00.0, one card on 23:00.0; phases
`s2a-smoke`, `s2b-gate` in [logs/](logs/), compact evidence in [evidence/](evidence/)):

| Run | What | Result |
|---|---|---|
| `r1tp-smoke` | rank 1 TP, 4 halves (first run of the ring under TP) | rc 0; card 1 = card 0 on 785 buffers; 0 timeouts |
| `r1-one` / `r1-tp` | rank 1, 1,100 prompt rows token by token (the 512-row ring wraps twice), then 16 decode halves | **1079/1079 buffers bitwise** (all 7 rings), 16/16 tokens equal; card 1 = card 0 on 785; half 12.38 → 11.03 ms |
| `r0-one` / `r0-tp` | rank 0, 48 speculative halves (hit, miss, cancel at first launch, timed cancel) | **1029/1029 target, 71/71 draft, draft tokens equal**; card 1 = card 0 on 710; 37 redos each |

0 exchange timeouts or aborts (8,922 waits per card on rank 0). The kernel log was clean before each phase (24 h) and
after every arm. There were no incidents. Raw run directories (208 files, 9,829,218,266 B) and probes (89 files)
were sha256-verified and moved to `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/svc-ready-step2-{runs,probes}`.
