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

## 3. Batched prompt reading under TP: TP-native (route 2), not the one-card copy (route 1)

**Why not route 1.** Route 1 reads the prompt on card 0 with the one-card prefill, which needs card 0 to hold the
one-card rank (full weights of every split site) *and* its TP slices. On rank 1 at 65536 with split 23 that is the
one-card plan 32,199,218,796 B plus card 0's slices 483,495,296 B plus 68 MB of packed prefill shadows: **538 MB over
the 30 GiB cap** (the plan check and the runtime arena admission both refuse it). The one-card rank alone has 20 MB
headroom (live B19 census 32,192,153,260 B). Stage 3 cannot help, because card 0 must still hold the whole KV cache for a
one-card prefill. Fitting route 1 would need extra decode changes (for example the head on card 1 only) or split 24
(about 3% slower decode). Route 2 keeps every card at the TP footprint and needs no state copy in either direction,
so a prompt after decode (a continuation) needs no reverse step.

**Change** (opt-in: only with `--tp-replicate` and `--prefill-rows`; one-card prefill unchanged and re-gated below):
- `prefill_engine.hpp` is per card. The sites are the TP plan's launches on both cards. Each runs on its own card with
  that card's shadows, row views, positions, tokens, banks and captured replays.
  - Head-split and compact-slot buffers use their compact extent per card (`head_split_layout`) as the shadow row, as
    their M-row writers and readers do.
  - Rank 0's lookup rows are computed once and uploaded to both cards. Rank 1's input rows go to both cards. The output
    rows come from card 0.
- Multi-row TP sites:
  - `tp_xgather` and `tp_xheads` become one strided direct exchange over the chunk's M rows. The per-row layouts are
    uniform strides: row halves, runs of 1024 every 2048, compact expert slots of 2560 every 5120.
  - Each exchange uses its own prefill flag slot (decode slot + 128). Before a pair, both cards are drained and the
    slot's counter and flag are zeroed on both cards. The epoch is then 1 whatever the row count, and the decode epochs
    are untouched. No peer store can reach a shadow the peer's earlier sites still use.
  - `tp_route_compact` runs RouteCompact over the M × 10 routes. The new `SlotRowsCompact` kernel selects the same
    slots' expert-input rows (a bitwise copy) for the compact gate/up launches, which read one input row per slot.
- `rank.hpp` admits the prefill command under TP. `OWNRT_PREFILL_ERROR_TRACE=1` (diagnostic, default off) names the
  first prefill site that sets a sticky error.
- Binary `0702b5a9cd78…` (build r5; [receipt](../../../engine/receipts/0702b5a9cd78.json)). The rank-0 driver gained
  `--token-prompt`, which makes the same draft calls as the batched path, in the same order.

**Incident on the way (host-side, no device fault).** The first gate run (r3, `2fe1b9a57ada`) read the 1,100 rows
token by token fine but stopped at the first 256-row chunk with "sticky rank error in batched prefill". The 16-row
smoke had passed. The trace run ([evidence/step3-r3/](evidence/step3-r3/)) showed card 0's first exchange timing out
at the 2^22-poll cap. A drain had run between card 0's and card 1's halves of an exchange pair: the chunk's periodic
drain every 6,000 submissions, which 256-row chunks cross often. The host then waited on card 0 while card 0 waited on
card 1's flag, and card 1's half was not yet issued. Fix (r5): no drain while a pair is open, and a check that card 1's
half is the very next site. Both cards tore down clean, and the kernel log stayed clean throughout.

**Gate** (binary r5, context 65536, cards 23:00.0 + 47:00.0, one card on 23:00.0; 1,100 prompt rows (256-row chunks:
4 full and one of 76; the 512-row raw ring wraps twice), then 16 decode halves; rank 0 with hit/miss/cancel
speculation `hmcn`; phase `s3d-gate`, [evidence/](evidence/), [results/step3-gate-timings.json](results/step3-gate-timings.json)):

| Comparison (full dump, bitwise) | Rank 1 | Rank 0 |
|---|---|---|
| TP batched vs one card batched | 1079/1079 | 1029/1029 target, 71/71 draft, draft tokens equal |
| TP batched vs TP token by token | 1079/1079 | 1029/1029, 71/71, equal |
| one card batched vs one card token by token | 1079/1079 | 1029/1029, 71/71, equal |
| TP token by token vs one card token by token | 1079/1079 | 1029/1029, 71/71, equal |

All 16 decode tokens are equal in the four rank-1 runs. Card 1 equals card 0 on every buffer both hold in full (785 /
710). 0 exchange timeouts or aborts. The kernel log was clean before the phase and after every arm.

**Prompt reading, rank harness (1,100 rows; ms):**

| | One card, token by token | One card, batched | TP, token by token | **TP, batched** |
|---|---:|---:|---:|---:|
| rank 1 | 13,630 | 4,281 | 12,177 | **3,627** (1.18× one card batched) |
| rank 0 (prefill only; + ~980 ms draft replay in each) | 11,661 | 2,813 | 10,333 | **2,326** (1.21×) |

- Card-0 census at 65536 with 256-row prefill: rank 1 TP 31,718,847,844 B (**493 MB headroom**; one card
  32,192,153,260); rank 0 TP 29,444,280,282 B (one card 29,911,490,794).
- Decode halves are unchanged by the prefill path: rank 1 10.88–10.91 ms on TP against 12.36–12.41 ms on one card;
  rank 0 9.33–9.36 against 10.59–10.63.
- End-to-end TTFT on a 3,490-token prompt against the two-card control is measured in section 4 (the same service
  launches).
- Raw runs (sha256-verified) are in `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/svc-ready-step3-{gate-r3,trace-r4,gate-r5}`.

## 4. The 12-prompt suite at 65536 with batched prompt reading: 73.18 vs 66.39 tok/s, outputs identical

Run exactly as the e2e suite ([run_arm.sh](run_arm.sh), from the e2e copy): the lab service on 127.0.0.1:18171, one
fresh transient unit per arm (`sc117-tp-svc-arm-{two,tp}-20261029`, `Restart=no`, `KillMode=process`, no SIGKILL,
`LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19), all four card locks held by `sc117-tp-svc-locks-20261029`, one cold
request per frozen prompt (512 cap, greedy), then one cold 3,490-token prompt ([ttft_probe.py](ttft_probe.py),
[ttft-doc.txt](ttft-doc.txt), 64-token cap). The same binary `0702b5a9cd78` in both arms; flags from
[arm_env.py](arm_env.py) (B19 set at 65536: ring, packing, `SC117_PREFILL_ROWS=256`, `OWNRT_NO_DRAFT_TIMING=1`,
`NEOReadDebugKeys=1 EnableDeferBacking=0`; no sessions, keeper or continuation). The lab service and adapter are
[lab/](lab/) (diffs to the e2e copies in `lab/*.vs-e2e.patch`). The `sc117-lan` unit was not touched.

| Arm | Cards (rank 0 / rank 1) | Median tok/s | Mean | Range | MTP acceptance | Median TTFT (suite) | TTFT, 3,490-token prompt | Outputs |
|---|---|---:|---:|---:|---:|---:|---:|---|
| two: control | 23 / 47 | **66.39** | 66.67 | 64.25–70.09 | 4533/5954 = 0.7613 | 793 ms | **12,497 ms** | = B19, all 12 |
| tp: exact TP2×PP2 | 23+27 / 43+47 | **73.18** | 73.48 | 70.40–77.16 | 0.7613 | 716 ms | **10,344 ms** | = B19, all 12 |

- **Decode 1.102×** (every prompt 1.089–1.108×), against 1.110× at 32K with token-by-token prompts in the e2e suite.
- **TTFT on the 3,490-token prompt: 1.21× faster** (10.34 against 12.50 s). Its 64 output ids and hash are equal in
  both arms; `cached_tokens=0`.
- The suite prompts are 60–90 tokens, below the bulk threshold (length − 2 ≥ 256 rows), so both arms read them token by
  token. Their TTFT is 0.903×.
- **Outputs:** all 5,965 token ids, hashes and per-prompt MTP guesses and hits are equal in both arms and equal the B19
  receipt at 65536 (`f32-suite-51f32b2655cc-ctx65536-split23.json`). `cached_tokens=0` everywhere.
- **Startup gates, each arm:**
  - F32 self-tests equal the B19 record.
  - The post-self-test state equals the pinned 4096 and 65536 oracles (the ring compared through its zero extension).
  - The service's one-time batched-prefill gate passed 13/13: two scalar suite checks, and 11 cases of up to 581
    tokens with 7-, 13- and 256-row chunks, comparing tokens, MTP guesses and every persistent state buffer, batched
    against token by token.
  - Warm batched reading, tp against two: 581 tokens in 1,853 against 2,324 ms; 514 tokens in 1,842 against 2,281 ms.
- **TP:**
  - Card 1 equals card 0 on 710 (rank 0) and 785 (rank 1) buffers at the last startup dump, with 0 exchange timeouts.
    A timeout sets the sticky error and fails the request; all 40 requests completed.
  - Card-0 census: 29,444,280,282 / 31,718,847,844 B (rank 1: 493 MB under the cap).
- **Teardown:** both arms wrote `terminal.json` with `passed: true`. The TP arm's two-record rank teardowns pass the
  step-1 check (the e2e arm C had written `incident.json` here).
- Kernel log: clean before, after ready, after the suite and after each arm. The only line in the window is an
  AppArmor audit of a snap.
- Files: [results/summary.json](results/summary.json) ([compare.py](compare.py)); per arm `results/arm-*/` (suite,
  TTFT probe, prefill gate, plan, monitor, requests, rank logs, journal, startup TP evidence). Raw run directories (449
  files, 168,285,862 B, sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/svc-ready-suite-20261029/`.

## Next

1. **Service switch (owner's call; the `sc117-lan` unit was not touched).** The lab service clears the three gaps at
   65536 with batched prompt reading. Two things remain before the live unit can move to four cards:
   - **Sessions, checkpoints and continuation are still refused under TP.** The B19 unit runs `SC117_SESSIONS=1` and
     the keeper; these arms ran without them.
   - The unit needs `EnableDeferBacking=0` and `LimitNOFILE=1048576`.
2. **Decode: rank 0 now sets the pace** (half 9.36 ms + draft 1.32 ms on card 0 alone, against rank 1's 10.9 ms).
   Splitting the draft head by vocabulary across rank 0's two cards (argmax per half, then one exchange of
   value and index, lowest index on ties) is worth about 0.4–0.6 ms per position, then moving the split point.
3. **Prompt reading:**
   - The first batched chunk after load pays its captures (the service gate's first 258-token case took 9.4 s), so a
     warm-up chunk belongs in startup.
   - TP prefill issues both cards from one host thread. Per-card submission threads, as in decode, are the next lever.
