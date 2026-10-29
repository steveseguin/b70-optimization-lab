# Rank 0's MTP draft head split across its two cards (2026-10-29)

**Question.** In the four-card TP2×PP2 layout, rank 0 runs its half (9.36 ms on two cards) and then the MTP draft
(1.32 ms) on card 0 alone, while card 1 waits. Rank 1's half takes about 10.9 ms. Can the draft use rank 0's second
card, exactly, so that stage 0 gets shorter?

**Answer.** The split works and is exact, but it does not make the service faster.
- Splitting the draft head's vocabulary rows across the two cards cuts the draft from 1.32 to 1.16 ms (−0.16 ms,
  −12%) and rank 0's half plus draft from 10.62 to 10.45 ms. Every gate is bitwise equal to one card.
- Moving the layer split to 24 only mirrors the imbalance (10.92 / 10.48 ms instead of 10.45 / 10.92 ms), so the split
  stays at 23.
- **Suite at 65536, same binary:** 73.26 tok/s with the split against 73.39 without (two cards: 66.37). Per prompt the
  split arm is 0.996–1.009× the TP arm (median 1.002×), so there is no gain. All 5,965 output ids equal B19 in all three
  arms.
- **The premise was wrong.** In the service, rank 0 was *not* setting the pace in hit cycles. On the traced
  3,490-token request, rank 0's draft plus speculative half ends about 0.09 ms before rank 1's 11.1 ms half, in both TP
  instances. A shorter draft therefore cannot help.
- On the one 3,490-token request whose per-step trace the service keeps, the split arm decoded 2.9% slower (65.20
  against 67.15 tok/s): rank 0's speculative halves took 10.12 ms instead of 9.39 ms. The cause is not established.
  The rank harness shows no such slowdown. `OWNRT_DRAFT_HEAD_SPLIT` stays opt-in and off.

Binary `46891d491b08…` (build r1, [receipt](../../../engine/receipts/46891d491b08.json)), built from `engine/src` into
`/dev/shm/engine-build-draft-split-20261029-r1`. Rank 0 on cards 23:00.0 + 27:00.0 (rank 0's service cards), context
65536, B19 flags ([arm_env.py](arm_env.py)), F32 target, BF16 draft with the 91,392-row raw Q6_K head prefix.

**Update, later on 10-29** ([target-head-split-2026-10-29](../target-head-split-2026-10-29/RESULT.md)): once rank 1's
target head is split too, rank 1's in-service half drops from 11.1 to 10.6 ms and rank 0 sets the pace. The draft head
split then pays off: 1.007–1.027× per prompt over the target split alone (suite medians 74.66 against 73.73 tok/s,
outputs equal B19). The slow speculative halves of section 5 did not recur in that suite, and its plain TP arm showed
some too. So they were most likely server-instance variance.

## 1. Where the draft spends its time

There is no profiling under TP (the shared-context queues cannot time events), so the per-site times come from the
existing one-card B19 profile of 2026-10-26 (engine event times with profiling queues, positions 4095–4142, 48 draft
steps with the head on; archived at
`/mnt/raid-models/ownrt-experiment-archives/2026-10-26-lab-shm/ownrt-lab-r0-c27prefill/runs/prof-b19/rank0/draft-device-profile.jsonl`).
Profiling queues make the whole draft about 0.4 ms slower (1.73 against 1.34 ms), so read these as shares.

| Draft site | µs | Share | Row-separable? |
|---|---:|---:|---|
| **logits** (91,392 × 2,560 raw Q6_K, BF16 out) | **327.7** | 27.0% | yes: vocabulary rows |
| **argmax** | **36.7** | 3.0% | yes: per-card argmax + merge |
| qsa.qgate (12,288 rows) | 121.7 | 10.0% | rows, but needs an input and an output exchange |
| attention output projection | 82.8 | 6.8% | rows, two exchanges |
| routed experts gate+up / down | 71.8 / 50.5 | 5.9 / 4.2% | slots, two exchanges |
| merge.projected / merge.embedding_projected | 52.3 / 36.5 | 4.3 / 3.0% | rows, two exchanges |
| qsa.attention | 40.0 | 3.3% | heads |
| final.gate + final.low + final.norm (head input) | 56.0 | 4.6% | no (small) |
| everything else (34 sites) | ~390 | 32% | — |
| **sum of sites / device span** | **1,212.7 / 1,218.8** | | |

- The head (logits + argmax) is 364 µs, 30% of the draft. It needs only one input row (final.mix, 5 KB) on card 1
  and returns one 16-byte record, so it is the cheap exact split.
- Every other GEMV of the draft is 20–120 µs. Each would need the input row moved to card 1 *and* the output rows
  moved back (two exchanges, about 6 µs each in the engine). The largest, qsa.qgate, would save about 50 µs; the six
  largest together roughly 0.15 ms, for a much larger change (draft weights sliced per card, per-site exchanges in the
  draft's own command lists). Not built; listed under Next.

## 2. What was built: `OWNRT_DRAFT_HEAD_SPLIT=1` (opt-in)

Source: [draft_head_split.hpp](../../../engine/src/stage2/packet194-expert-diet-engine/draft_head_split.hpp) (kernels
and host twins), `mtp_kernels.{hpp,cpp}` (`head_shard`, `head_merge`), `mtp.hpp` (`DraftRuntime`, all new code behind
`split`). Admitted only for a `--tp-replicate` rank 0 with the raw Q6_K draft head (`OWNRT_DRAFT_HEAD_RAW=1`) and
prepared commands; refused with pipeline, probe and Q4-head modes. Unset, no code path changes.

- **Rows.** Card 0 keeps rows [0, 45,824) of its head; card 1 gets a byte copy of rows [45,824, 91,392) read back from
  card 0 (95.7 MB). `OWNRT_DRAFT_HEAD_SPLIT_ROWS` moves the boundary (a multiple of 128).
- **Per head-on draft step** (head-off prompt replay rows are unchanged and never touch card 1):
  1. Card 1's four prepared commands are issued just before card 0's first head site: exchange X1, its rows, its shard
     argmax, exchange X2.
  2. Card 0 runs final.norm/low/gate as before, then X1 sends final.mix (2,560 BF16 values) into card 1's copy. Card 1's
     X1 kernel sends a ping word and waits, bounded, for the row.
  3. Each card runs the **unchanged raw row kernel** (`p33` `DenseRawBF16`) on its rows. A row's arithmetic does not
     depend on the row count, so every logit is bitwise the one-card logit.
  4. Each card runs the **shard argmax**: ArgmaxFast's scan verbatim (one 1,024-lane work-group, first maximum per lane,
     then the largest value and the lowest index holding it, ±0 equal). It writes a Best record {value, global index,
     error, 0}. A non-finite logit sets the record's error and the card's sticky error. A card whose error is already
     set writes an error record, never a stale one.
  5. X2 swaps the two records. Card 0's merge reads them in a later kernel: card 1's index wins only if its value is
     strictly greater (card 0's rows are all lower), so ties go to the lowest global index. Either record's error fails
     the draft as ArgmaxFast does: sticky error, the guess is dropped, the draft disables itself. In that case the
     `next_token` word keeps its old value, where ArgmaxFast writes a fallback index; nothing reads it on that path.
- **Exchanges.** The kernel-direct exchange of the TP layers (`Device::exchange`), with the draft's own control words
  (slots 0 and 1, never reset; both cards run both exchanges once per head-on step) and the same 2^22-poll cap. A
  timeout sets the draft's sticky error (the draft stops guessing; the target is not affected). Statistics:
  `draft-final-state/draft-head-split-exchange.json`.
- **State.** No new allocation joins the draft's 71 mutable allocations. The dump reassembles the one-card logits
  layout from both cards, so the driver's bitwise draft-state compare is unchanged. Request reset zeroes the split's
  buffers (not the control words). Memory: card 0 +32,960 B (census 29,444,313,242 B); card 1 +95.7 MB weights +1.6 MB.

## 3. Gates

**CPU unit test** ([merge_unit_test.cpp](merge_unit_test.cpp), [output](merge_unit_test.out)): the engine's own device
kernels (shard and merge, run on the OpenCL CPU device; no GPU opened) and their host twins, against a plain sequential
argmax and a verbatim copy of ArgmaxFast's kernel, at six split points (128 … 91,264 rows) and small prefixes.
- **283 cases, 0 failures.** They include 144 random BF16 rows, equal maxima across the split, at the boundary, in two
  lanes and inside card 1, the maximum only on card 1, all-equal rows, +0/−0 in all four orders across and within the
  cards, NaN/+inf/−inf on either or both cards, and a sticky error already set on either card.
- 36 cases have the maximum on both cards. A negative control (card 1 wins ties) differs from ArgmaxFast in all 36.
- The device records equal the host twins bit for bit.

**Device gates** (rank-0 harness [tp_rank0_driver.py](../service-ready-2026-10-29/tp_rank0_driver.py) unchanged,
context 65536, 1,100 prompt rows in 256-row chunks, then 16 decode steps; [run_phase.sh](run_phase.sh); phases
`p1-smoke`, `p2-gate`, logs in [logs/](logs/), compare output [logs/p2-gate-compare.txt](logs/p2-gate-compare.txt)):

| Comparison (bitwise, full dump) | Target buffers | Draft allocations | Draft tokens |
|---|---|---|---|
| one card, **new binary vs previous binary** `0702b5a9cd78` (r0-one-b) | **1029/1029** | **71/71** | equal |
| TP + head split vs one card, `hmcn` (4 hits, 4 misses, 4 cancelled at first launch, 8 redos) | **1029/1029** | **71/71** | equal |
| TP + head split vs one card, `x` (3 completed misses, 13 cancelled mid-half, 16 redos) | **1029/1029** | **71/71** | equal |
| TP without split, new binary vs one card / vs previous binary's TP (r0-tp-b) | 1029/1029 | 71/71 | equal |
| six 64-step timing runs, each pair below | 1029/1029 | 71/71 | equal |

- The smallest smoke came first (`s-tps`: 16 prompt rows, 4 decode steps): rc 0, 0 timeouts.
- The 71 draft allocations include the reassembled logits of the last head-on step, all 91,392 rows. Of the 16 draft
  guesses, 2 came from card 1's rows (57,208 and 72,235).
- Exchanges: 0 timeouts and 0 aborts, for the split's own exchanges (2 waits per card per head-on step) and for the
  target's. Card 1 equals card 0 on all 710 target buffers both hold. The kernel log was clean before every phase
  (24 h) and after every arm.

## 4. Speed: rank 0, and the layer split point

Rank-0 harness, 1,100 prompt rows, then 64 non-speculative decode steps with the draft head on; medians of steps 3–64;
A/B/A/B order in one phase ([results-timing.json](results-timing.json)):

| Rank 0, cards 23 + 27 | Half ms | Draft ms | **Half + draft** |
|---|---:|---:|---:|
| TP (current), run 1 / 2 | 9.302 / 9.289 | 1.325 / 1.317 | **10.627 / 10.605** |
| TP + draft head split, run 1 / 2 | 9.297 / 9.297 | 1.165 / 1.158 | **10.461 / 10.455** |
| TP + split, card 0 47,104 rows, run 1 / 2 | 9.302 / 9.287 | 1.163 / 1.155 | 10.465 / 10.442 |

- The draft is 0.16 ms shorter (−12%); the half is unchanged. One card without profiling queues: half 10.64, draft
  1.34 ms (gate run).
- With the even split, card 0 waits about 9 µs at X2 for card 1 (card 1 starts after X1). Giving card 0 1,280 more rows
  removes that wait but gains only 0–3 µs, inside the noise. The default stays at 45,824 rows.

**Split point 23 → 24** (CPU plan check at 65536 per card, cap 32,212,254,720 B,
[evidence/probes/](evidence/probes/); harness timing in one phase, [results-split24.json](results-split24.json)):

| Split | Rank 0 TP plan per card | Rank 1 TP plan per card | Rank 0 half + draft | Rank 1 half |
|---|---:|---:|---:|---:|
| 23 (now) | 25,929,055,244 | 31,717,388,580 | 9.292 + 1.156 = **10.448** | **10.920** |
| 24 | 27,317,891,692 | 30,361,844,420 | 9.755 + 1.163 = **10.918** | **10.477** |

- Both fit (rank 0's card 0 also holds the 3.1 GB draft: about 30.8 GB at split 24).
- Moving one layer moves about 0.46 ms between the stages, about the whole gap, so the slower stage stays at 10.92 ms
  either way. Split 24 would also make every speculation miss's redo 0.46 ms longer on rank 0, and the service's F32
  state oracles are pinned at split 23. **The split stays at 23.**
- Rank 1 harness: cards 23 + 47, 1,100 prompt rows batched, 16 decode halves.

Raw runs (sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/draft-split-runs-p1-p3` (638 files,
20,713,722,867 B) and `draft-split-runs-p4` (with the plan probes).

## 5. Suite at 65536: no gain (73.26 against 73.39 tok/s), outputs identical

Run as service-ready-2026-10-29 step 4 ([run_arm.sh](run_arm.sh), copied with fresh names): the lab service on
127.0.0.1:18171, one fresh transient unit per arm (`sc117-tp-svc-ds-arm-{two,tp,tps}-20261029`, `Restart=no`,
`KillMode=process`, no SIGKILL, `LimitNOFILE=1048576`, nice 19, CPUs 0-3,16-19), all four card locks held by
`sc117-tp-svc-ds-locks-20261029`, arms in the fixed order two, tp, tps ([suite_chain.sh](suite_chain.sh)).
- Each arm: one cold request per frozen prompt (512 cap, greedy), then one cold 3,490-token prompt (64-token cap).
- Same binary `46891d491b08` everywhere, B19 flags at 65536 ([arm_env.py](arm_env.py)). The only difference between
  tp and tps is `OWNRT_DRAFT_HEAD_SPLIT=1` (launch diff checked).
- The lab service is service-ready's, with the adapter passing the two split keys to TP ranks. `sc117-lan` was not
  touched.

| Arm | Cards (rank 0 / rank 1) | Median tok/s | Mean | Range | MTP acceptance | TTFT, 3,490-token prompt | Its decode tok/s | Outputs |
|---|---|---:|---:|---:|---:|---:|---:|---|
| two: control | 23 / 47 | **66.37** | 66.65 | 64.22–70.05 | 4533/5954 = 0.7613 | 12,506 ms | 60.16 | = B19, all 12 |
| tp | 23+27 / 43+47 | **73.39** | 73.56 | 70.55–77.80 | 0.7613 | 10,371 ms | 67.15 | = B19, all 12 |
| **tps: tp + draft head split** | 23+27 / 43+47 | **73.26** | 73.71 | 70.79–77.66 | 0.7613 | 10,370 ms | **65.20** | = B19, all 12 |

- **tps against tp, per prompt:** 0.996–1.009× (median 1.002×). tp against two: 1.095–1.111× (1.106× on the medians;
  service-ready measured 73.18 against 66.39).
- **Outputs:** all 5,965 ids, hashes and per-prompt MTP guesses and hits equal B19 in all three arms. The 64 long-prompt
  ids are equal across the arms. `cached_tokens=0` everywhere.
- **Gates:** the startup gates (F32 self-tests, the pinned 4096 and 65536 state oracles, 13/13 batched-prefill cases)
  passed in every arm. The split arm's rank 0 wrote `draft-head-split.json` (45,824 / 45,568 rows), so the split ran
  for every request.
- **Teardown:** both ranks closed clean (`terminal.json` passed). The kernel log was clean before, after ready, after
  the suite and after each arm.
- Files: [results/summary.json](results/summary.json) ([compare.py](compare.py)), per arm `results/arm-*/`. Raw run
  directories (679 files, 253,474,572 B, sha256-verified):
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-29/draft-split-suite-20261029/`.

**Who sets the pace in the service.** The service keeps the controller's per-step trace for the last request only, the
3,490-token prompt (positions 3,490–3,553; [trace_summary.py](trace_summary.py),
[results/long-prompt-trace.json](results/long-prompt-trace.json)). Medians, ms:

| TP instance | Rank 0 speculative half (p10–p90) | Rank 0 redo half | Rank 1 half | Draft | Rank 0's half ends after rank 1's by | Decode wall |
|---|---:|---:|---:|---:|---:|---:|
| service-ready tp (binary 0702b5a9cd78) | 9.385 (9.36–9.41) | 9.37 | 11.10 | 1.282 | **−0.09** | 937 ms |
| tp (this suite) | 9.395 (9.38–9.46) | 9.38 | 11.11 | 1.284 | **−0.09** | 938 ms |
| tps (this suite) | **10.116 (9.42–10.68)** | 9.44 | 11.15 | **1.121** | **+0.44** | 966 ms |

- **Without the split, rank 1 sets the pace in hit cycles:** rank 0's draft plus speculative half finishes about
  0.09 ms before rank 1's half. On a miss, rank 1 waits for rank 0's 9.4 ms redo. Neither depends on the draft's length.
  So the earlier estimate "rank 0 sets the pace" (half 9.36 + draft 1.32 against rank 1's 10.9) was wrong; it left out
  rank 1's in-service half, which is 11.1 ms here.
- **With the split**, the draft is 0.16 ms shorter in the service too, but rank 0's speculative halves are 0.73 ms
  longer. Rank 0 then finishes 0.44 ms after rank 1, which costs this request 2.9%.
- The 31 speculative halves of the startup gates (positions about 100) show no such slowdown: 9.240 ms with the split
  against 9.221 ms without. Neither do the harness's speculative hit halves at 1,100 positions (9.61–9.62 against
  9.64 ms). The 12 short suite prompts show no loss either.
- The slowdown is therefore seen only on the long request, in one server instance. **Its cause is not established.**
  The trace shows when the half is slow, not why. This is one request on one server; a repeat with the service's
  per-phase host timing (p150) would separate a real effect from instance variance.

## Next

1. **Rank 1 is the pace in hit cycles: split the target head on rank 1** by the same vocabulary rows. The 248,320-row
   head took about 1 ms of rank 1's half in the last one-card profile (logits 885 µs, argmax 102 µs; decode-next2). The hidden row is already on both of rank 1's cards (replicated under TP),
   so it needs no X1, only the shard argmax on F32 logits, the record exchange and the merge on both cards. Expected
   about −0.45 ms on rank 1. It also frees about 260 MB per rank-1 card at 64K. The tie and non-finite rules, the merge
   and the CPU test carry over unchanged.
2. **Misses:** rank 1 waits the whole 9.4 ms rank-0 redo on every miss (24% of positions). That is now the largest
   structural cost.
3. **Draft head split:** keep it opt-in. Before it can help, rank 0 must be the pace again (after item 1). Explain the
   slower speculative halves on the long request first, with one diagnostic service run (p150 phase timing, tp
   against tps, the same long prompt).
4. Draft GEMV row splits (qgate, attention output, experts, merges): about 0.15 ms more on stage 0 for a large change.
   Only worth it once stage 0 is the pace.

## Files

- Engine: [draft_head_split.hpp](../../../engine/src/stage2/packet194-expert-diet-engine/draft_head_split.hpp),
  `mtp_kernels.hpp`, `mtp_kernels.cpp`, `gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp`.
- Lab: [run_phase.sh](run_phase.sh) (rank harness phases), [analyze.py](analyze.py), [collect_evidence.py](collect_evidence.py),
  [archive_runs.sh](archive_runs.sh), [arm_env.py](arm_env.py) (adds the `tps` arm and `ARM_SPLIT`),
  [make_launch.py](make_launch.py), [plan_probe.py](plan_probe.py), [lab/](lab/) (the service-ready lab service; the
  adapter passes the two split keys to TP ranks, [diff](lab/adapter6_tp.py.vs-service-ready.patch)), launch JSONs
  `rank{0,1}-launch-c65536-46891d491b08{,s24}.json`.
- Evidence: [evidence/](evidence/) (per run: summary, draft-state hashes, split and exchange statistics, target state
  hashes for the gate runs), [results-gate.json](results-gate.json), [results-timing.json](results-timing.json),
  [results-split24.json](results-split24.json), [results/](results/) (suite), [logs/](logs/) (phase logs, kernel-log
  checks, archive receipts).
