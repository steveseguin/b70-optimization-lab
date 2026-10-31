# The four-card stack's non-TP flags on the two-card layout (2026-10-31)

**Question.** How much of the four-card speed work of 2026-10-29/30 carries over to the two-card layout of the SC117
engine (pipeline rank 0 = layers 0–22 + MTP draft on one card, rank 1 = layers 23–47 + head on another, no TP)? This is
the layout most readers have, and the one the LAN chat service runs. Outputs must stay bit-identical.

**Answer.** **Most of it carries over: +9.6% decode tok/s on two cards.** On four cards the same decode levers gave +3.7% (HC kernels) and +5.6% (fixed-cost-2). Fresh two-card lab
servers at 65536 (rank 0 on 23:00.0, rank 1 on 47:00.0), A/B/A/B on one binary (r1 `40388fc92c43`):
**66.07 / 66.11 → 72.46 / 72.44 tok/s (mean of medians 66.09 → 72.45, +9.6%)**, every output equal to B19.
- B is faster on 12/12 prompts in all four cross-pairs, by 1.094–1.098 (per-pair medians 1.096–1.097).
- The 3,490-token prompt reads in **9.95 s instead of 12.51 s (−20.5%)**.
- The hit cycle drops from 12.58 to 11.55 ms (−1.03 ms, −8.2%) and a miss from 23.7 to 21.5 ms.
- B = A + 16 default-off non-TP flags: the 10-30 decode levers, the 10-29 rank-0 trims, and the prompt-reading flags
  ([flags.py](flags.py)).
- The one-card rank-harness gate on the same binary found every flag bitwise exact in this configuration (step 1).
- No engine change. The one fix was in the lab adapter: it passed these keys to TP ranks only, so a two-card server would
  have run without them, silently.
- The certified service build B19 decodes 66.21 tok/s, and the reference two-card arm decoded 66.42. A here (66.09) is
  that baseline on the newer binary.

## In plain words

- **The decode levers were measured on one card, and a two-card rank is one card.** Each rank of the two-card layout
  is a single-card process, so the one-card savings apply in full: per half, about −1.0 ms on rank 1 and −1.14 ms on
  rank 0, and −0.11 ms on the draft. The stages stay close together, so the cycle shrinks by about the same amount:
  12.58 → 11.55 ms per hit.
- **Rank 1 now sets the pace on every hit.** In the 3,490-token request's 40 hits, rank 0 finishes 0.53–0.58 ms before
  rank 1 (rank 0 path 11.07 ms against rank 1's 11.61–11.65 ms). With A it was 0.27–0.30 ms. Any further two-card gain
  must come off rank 1, or move work from rank 1 to rank 0.
- **Prompt reading gains more than the harness suggested.** On one card, rank 0's 600-row prompt got 29% faster (its
  per-row draft replay drops from 537 to 32 ms) and rank 1's only 2.7%. Yet the 3,490-token TTFT drops by 2.57 s
  (20.5%), so rank 0 also held back the two-card pipeline during prompt reading. That is a measurement, not a
  decomposition. The retained controller traces of the request (archived) were analyzed only for the decode hits.
- **The flags reach the ranks only if the adapter forwards them.** The lab adapter passed them to TP ranks only, and
  the committed LAN adapter (`serving/lan/adapter6.py`) passes none of them. The B servers' rank processes carried all
  16 keys (`/proc/<pid>/environ`), and the A servers' carried none.

## The flag set (B) and the binary

- **Binary:** lab build r1 `40388fc92c43` (`engine/src` at `979462f7c` + [fixed-cost-2](../tp/fixed-cost-2-2026-10-30/engine-fixed-cost-2.patch)
  + [hc-split](../tp/hc-split-2026-10-30/engine-hc-split.patch); tree and build pinned at `/dev/shm/hcsplit-2026-10-30/{tree,build-r1}`,
  [receipt](../tp/hc-split-2026-10-30/results/engine-receipt-40388fc92c43.json), all 269 source hashes and the binary
  re-checked before the servers). Both arms run it, so the A/B isolates the flags. The fixed-cost-2 engine change
  (`OWNRT_DRAFT_FAST`, `OWNRT_TARGET_FAST`) is not in the shared `engine/src`.
- **A** = the two-card control arm `two` of [target-head-split-2026-10-29](../tp/target-head-split-2026-10-29/RESULT.md)
  (66.42 tok/s there): the B19 service flags (F32, split 23, 65536, QSA raw ring, shadow packing, 256-row batched prefill)
  without sessions/keeper/continuation, `OWNRT_NO_DRAFT_TIMING=1`, `NEOReadDebugKeys=1 EnableDeferBacking=0`. Its
  flags equal that arm's unit environment line for line ([suite/arm_env.py](suite/arm_env.py) `twoA`).
- **B** = A + every key of [flags.py](flags.py), on both ranks (as the four-card servers pass them):

  | Flag | From | On a one-card rank |
  | --- | --- | --- |
  | `OWNRT_RETIRE_DEFERRED=1` | fixed-cost-2026-10-30 (F2) | host only: the next half retires the finished events |
  | `OWNRT_HC_KERNELS=1` | hc-kernels-2026-10-30 | `norm1,lowsel,cnorm` (rank 0: 46/46 norms, 44 pairs; rank 1: 51/51, 49 pairs) |
  | `OWNRT_DRAFT_FAST=1` | fixed-cost-2-2026-10-30 | rank 0's draft step (`inj,norm,merge,cnorm,gath`) |
  | `OWNRT_TARGET_FAST=1` | fixed-cost-2-2026-10-30 | `ssel,hcg,kptr,bptr,gdnr,ngop,moec`, both ranks |
  | `OWNRT_SNAPSHOT_NOWAIT=1`, `OWNRT_ROLLBACK_NOWAIT=1` | rank0-trims-2026-10-29 | rank 0's speculative snapshot and miss rollback |
  | `OWNRT_PREFILL_LOOKUP_BATCH=1`, `OWNRT_PREFILL_MOE_NATIVE=1`, `OWNRT_DRAFT_CHUNK_REPLAY=1`, `OWNRT_DRAFT_CHUNK_KV_ONLY=1` | prefill-speed-2026-10-29 | batched prompt reading (lookups, moe_combine rows, one draft command per chunk, KV-only draft rows) |
  | `OWNRT_PREFILL_SPECIAL_ROWS=1`, `OWNRT_PREFILL_LOOKUP_THREADS=4`, `OWNRT_DRAFT_CHUNK_STAGE_THREAD=1`, `OWNRT_DRAFT_CHUNK_GUARD_ROW=1`, `OWNRT_DRAFT_CHUNK_ROW_COPY=1` | prefill-host-2026-10-30 | the same |
  | `OWNRT_DRAFT_CHUNK_BATCH=1` | prefill-draft-batch-2026-10-30 | the draft's prompt rows as 15 launches per chunk |

  Left out as TP-only: `OWNRT_PREFILL_XZERO_ONCE` (zeroes TP prefill exchange slots; `prefill_engine.hpp` runs it only
  under `--tp-replicate`), every `OWNRT_TP_*` (exchange, experts, GDN, QSA split, HC split, expert pair, threads, card
  context), both head splits and `OWNRT_DRAFT_GEMV_SPLIT`.
- **The two-card admission fix (lab adapter only).** The lab adapter forwarded these keys to TP ranks only
  (`TP_KEYS` inside `if tp_rank(rank)`), so a two-card server with them in its unit environment would have run without
  them, silently. [suite/lab/adapter6_tp.py](suite/lab/adapter6_tp.py) adds `ONE_CARD_KEYS` (= flags.py B) for one-card
  ranks; TP ranks are unchanged. No engine change. The committed LAN adapter (`serving/lan/adapter6.py`) forwards none of
  these keys either.

## Step 1: rank-harness gate on one card (the two-card rank configuration)

The harness's one-card launch environment is the `two` arm's (`--cards 1`, split 23, F32, 65536, the B19 flags,
dispatch file), so a one-card rank arm is exactly one rank of the two-card server. Phase g1: card 0000:47:00.0
(lock card47), binary r1, 128 prompt rows then 64 decode halves (rank 0: 64 speculative steps with drafts), and
600-row prompts in 256-row chunks with a RESET and a second 600-row request (`sp=600`). A = no extra keys; B = flags.py B
(extra `B`; rank 0's batched B arm also issues one DRAFT_CHUNK command per chunk, `dc`, as the native controller does
when `OWNRT_DRAFT_CHUNK_REPLAY=1`). [run_phase.sh](run_phase.sh), [compare.sh](compare.sh) (the drivers' own compare,
with the exact-pattern ones checker of prefill-draft-batch-2026-10-30 via [compare_driver.py](compare_driver.py)),
[logs/g1.log](logs/g1.log), [logs/g1-compare.txt](logs/g1-compare.txt). 17 arms rc 0; kernel log clean before the phase
(24 h) and after every arm.

| Compare (A vs B unless noted) | Result |
| --- | --- |
| rank 1, token by token, two pairs + A vs A2 + A vs B2 | 1079/1079 buffers, 64 tokens, 192/192 exported draft-input rows equal |
| rank 1, batched 600 + RESET + 600 | both requests 1079/1079 and tokens; exports 664 + 664 equal; reset inventories 28/28 equal, B has 2 more (`prefill:moe-mixture`, `prefill:moe-ones`: `OWNRT_PREFILL_MOE_NATIVE`'s scratch); ones OK |
| rank 0 `h`, two pairs + A vs A2 | 1029/1029 target, 71/71 draft buffers, 64 draft tokens equal |
| rank 0 `h`, A vs B without the two trims (`Bnonw`) | equal |
| rank 0 `hmcn`, `m` | 1029/1029, 71/71, draft tokens equal |
| rank 0, batched 600 + RESET + 600, B with chunk replay + batch (`dc`) | both requests 1029/1029 + 71/71 + draft tokens; reset inventories 116/116 equal, B has the same 2 more; ones OK |

The B arms' records show the flags reached the rank: `hc-kernels.json` (admissions above), `draft-fast.json` (all five
draft tokens admitted), `draft-chunk-batch.json` (256 rows, 21 row buffers), and the rank-0 driver's `env_flags` list
every B key.

**What was reused, not repeated** (one card, each on its own binary): hc-kernels G1 and the export check x1
(`OWNRT_HC_KERNELS` on vs off, 59d29a4a362e / 17f5f49ff010); fixed-cost-2 G1/G3 (`DRAFT_FAST`/`TARGET_FAST` on vs off
with `rd,hk` in both arms, m2 `dddf5cf0e067`); rank0-trims (one card + nowait vs one card); prefill-host and
prefill-draft-batch (TP flags-on = one card, two-request cases). None of those compared the whole set against the
two-card baseline on the served binary; g1 does that, once.

**Half medians (halves 3..64, one card; [results/g1-halves.json](results/g1-halves.json))**

| Rank | A | B | Change |
| --- | ---: | ---: | ---: |
| rank 1 half | 12.427 / 12.371 ms | 11.405 / 11.376 ms | **−1.01 ms (−8.2%)** |
| rank 0 speculative half (`h`) | 10.952 / 10.944 ms | 9.809 / 9.808 ms | **−1.14 ms (−10.4%)** |
| rank 0 draft step | 1.331 / 1.334 ms | 1.222 / 1.230 ms | −0.11 ms |
| rank 0 half, B without the trims | | 9.905 ms | the trims: −0.10 ms |
| rank 0 `hmcn` / `m` half | 10.895 / 10.900 ms | 9.780 / 9.801 ms | −1.11 / −1.10 ms |

Today's one-card measurements added up to about −0.13 (retire) −0.34 (HC) −0.54 (fast) ≈ −1.0 ms per half; the
two-card ranks get −1.0 (rank 1) and −1.14 ms (rank 0, with the trims).

**Prompt reading** (600 rows, the warm second request; [results/g1-prompt-times.json](results/g1-prompt-times.json)):
rank 0 2045 → 1443 ms (prefill 1508 → 1411, draft replay 537 → 32 ms); rank 1 2314 → 2252 ms (−2.7%). On two cards
the ranks run one chunk apart and rank 1 already bounds the A arm, so most of rank 0's gain cannot reach the first
token.

## Step 2: fresh two-card lab servers at 65536, A/B/A/B

Tooling: [suite/](suite/) (copies of the hc-split-2026-10-30 suite; port 18179; units `sc117-tp-svc-tc-*-20261031`).
- The chain [suite/suite.sh](suite/suite.sh) ran in unit `sc117-tp-svc-tc-chain-20261031`.
- The holder `sc117-tp-svc-tc-locks-20261031` took `/dev/shm/card23.lock` and `card47.lock` with bounded waits (1 h
  per lock). It waited 14 min for another agent's four-card phase q1.
- Each server ran once, in a fresh transient unit: Restart=no, KillMode=process, no SIGKILL, LimitNOFILE=1048576, nice 19,
  CPUs 0-3,16-19, NEOReadDebugKeys=1, EnableDeferBacking=0, and `--wait-seconds 300` on both ranks.
- Each server: preconditions (fresh paths, free port, MemAvailable ≥ 98.8 GB, root ≥ 27.13 GB, kernel log clean), load,
  the F32 self-tests (equal to the B19 record), and the pinned 4096 and 65536 state oracles (split 23, 0 differences).
- Then the 13-case startup batched-prefill gate (13/13 on all four), the 12-prompt suite (one cold request each, 512
  cap, greedy), the 3,490-token TTFT request, a graceful stop (`terminal.json` passed), and a kernel-log check (sudo)
  before, after ready, after the suite and after the stop.
- Unit environments: `suite/logs/arm-*-unit-env.txt`. Rank environments (`/proc/<pid>/environ`, both ranks, every
  server): `suite/logs/rank-env-*.txt`.
  - twoB-r1 and twoB-r2: all 16 B keys on rank 0 (0000:23:00.0) and rank 1 (0000:47:00.0).
  - twoA-r1 and twoA-r2: none.

| Server | Median tok/s | Mean | Range | Outputs | TTFT 3,490 | Its decode tok/s | Hit cycle | Miss interval | Rank 0 path | Rank 1 path |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| twoA-r1 | 66.07 | 66.31 | 63.89–69.71 | = B19 | 12.51 s | 59.89 | 12.583 ms | 23.71 ms | 12.350 | 12.618 |
| **twoB-r1** | **72.46** | 72.75 | 70.18–76.37 | = B19 | **9.95 s** | 65.85 | **11.547 ms** | 21.47 ms | 11.073 | 11.605 |
| twoA-r2 | 66.11 | 66.37 | 63.92–69.78 | = B19 | 12.51 s | 59.88 | 12.584 ms | 23.73 ms | 12.333 | 12.628 |
| **twoB-r2** | **72.44** | 72.74 | 70.14–76.38 | = B19 | **9.95 s** | 65.77 | **11.552 ms** | 21.52 ms | 11.067 | 11.649 |

- Mean of medians 66.090 → 72.449 tok/s (**+9.62%**).
  - Per prompt, B/A in the four cross-pairs: medians 1.0961–1.0973, ranges 1.0939–1.0984, 12/12 faster in each
    ([suite/results/suite/summary.json](suite/results/suite/summary.json)).
  - The 12-request wall sum is 100.6 s → 91.7 s.
- Outputs: on all four servers, all 5,965 ids, the sha256s, and the MTP guesses and hits (5,954 / 4,533 = 0.7613) equal
  B19 (`f32-suite-51f32b2655cc-ctx65536-split23.json`), with 0 cached tokens. The 3,490-token request's 64 ids are the
  same in all four (`29426ae7…`).
- Hit cycle ([suite/results/hitcycle-endgate.json](suite/results/hitcycle-endgate.json); the 3,490-token request, 40
  hits and 23 misses per server, through miss-stall-2026-10-29's analysis):
  - rank 1's half: 12.574 → 11.536 ms;
  - rank 0's speculative half: 11.03 → 9.85 ms;
  - the speculative snapshot: 0.244 → 0.018 ms (`OWNRT_SNAPSHOT_NOWAIT`);
  - rank 0 is never the later stage (0/40 hits in every server).
- Kernel log: 0 xe/fault lines in every check and over the whole chain
  ([suite/logs/kernel-log-post-endgate.txt](suite/logs/kernel-log-post-endgate.txt), from the chain start).

## Step 3: what a two-card service would need (not applied; `sc117-lan` untouched)

B wins, so here is the exact change. The LAN unit, its adapter and `engine/src` were not edited.
1. **Binary:** an engine with the fixed-cost-2 change. `OWNRT_DRAFT_FAST` and `OWNRT_TARGET_FAST` do not exist in the
   shared `engine/src`; that write is waiting on the owner.
   - Measured here: lab build r1 `40388fc92c43`. Its receipt is
     `research/tp/hc-split-2026-10-30/results/engine-receipt-40388fc92c43.json`, and its tree and build are pinned under
     `/dev/shm/hcsplit-2026-10-30` (archived at `.../2026-10-30/engine-builds/hc-split-r1`).
   - m2 `dddf5cf0e067` differs from r1 only by the default-off, TP-only HC split, but it was not served on two cards.
   - Set `SC117_ENGINE_RECEIPT` to that build's receipt.
2. **Unit environment:** add these 16 lines to the service unit's environment, unchanged otherwise (F32, split 23, 65536,
   256-row prefill, the dispatch file):

   ```
   OWNRT_RETIRE_DEFERRED=1
   OWNRT_HC_KERNELS=1
   OWNRT_DRAFT_FAST=1
   OWNRT_TARGET_FAST=1
   OWNRT_SNAPSHOT_NOWAIT=1
   OWNRT_ROLLBACK_NOWAIT=1
   OWNRT_PREFILL_LOOKUP_BATCH=1
   OWNRT_PREFILL_MOE_NATIVE=1
   OWNRT_DRAFT_CHUNK_REPLAY=1
   OWNRT_DRAFT_CHUNK_KV_ONLY=1
   OWNRT_PREFILL_SPECIAL_ROWS=1
   OWNRT_PREFILL_LOOKUP_THREADS=4
   OWNRT_DRAFT_CHUNK_STAGE_THREAD=1
   OWNRT_DRAFT_CHUNK_GUARD_ROW=1
   OWNRT_DRAFT_CHUNK_ROW_COPY=1
   OWNRT_DRAFT_CHUNK_BATCH=1
   ```
3. **Adapter:** `serving/lan/adapter6.py` must pass the same 16 keys to both rank processes. Its forwarded-key tuple has
   none of them today, so without this the unit lines do nothing, silently. The lab change is `ONE_CARD_KEYS` in
   [suite/lab/adapter6_tp.py](suite/lab/adapter6_tp.py). Verify after start that both ranks carry them
   ([suite/rank_env.sh](suite/rank_env.sh) does that for the lab units).
4. **Rank wait deadline:** these servers passed `--wait-seconds 300` (a deadline only). The 60 s default was shown to bite
   only TP rank 0's card-1 worker during the cold first half. Two cards were not run without it, so either pass 300 or
   watch the first start.
5. **Not covered here:** sessions, keeper and continuation (`SC117_SESSIONS=1`, `SC117_KEEPER=1` in the LAN unit) were
   off in every lab server, as in all earlier lab arms. A different binary also needs the service's own session
   cross-build compat gate and its startup gates, which the service runs by itself on first start.
6. KV cache and activations are unchanged (F32 activations, the B19 KV layout). Nothing here is lossy.

## Incidents

- No device incident: kernel log clean before phase g1 (24 h), after every harness arm, before / after ready / after the
  suite / after every server, and over the whole chain.
- Host-side: the g1 archive (2.5 GB from `/dev/shm` to the RAID, 19 s, not CPU-pinned) ran during the first,
  smoke-sized arm of another agent's rank-harness phase q1, which had just taken all four locks. Its timing arms
  started later. The end-gate archive ran pinned to CPUs 8-15,24-31 with idle I/O.
- Nothing was retried; no server or arm failed.

## Next levers (two cards, decode tok/s; ranked)

1. **Rebalance the split now that rank 1 paces.** Rank 0 has 0.53–0.58 ms of slack per hit. `SC117_TARGET_SPLIT=24`
   moves layer 23 (about 0.42 ms per half: rank 1's 11.4 ms for 25 layers + head) to rank 0. Both paths would then be
   near 11.2–11.5 ms, for a hit cycle about 0.05–0.1 ms shorter (≤ 1%). It is an existing setting, and split 24 is the
   pinned oracles' native split, so the server gates apply directly. One fresh A/B.
2. **Rank 1's own half on one card** (11.4 ms) is now the whole two-card budget. Its largest single site is the target
   head; on four cards it was split across rank 1's two cards. A pipeline-side equivalent (rank 0 computing part of the
   head rows during its slack, exchanging logits) is new engine work. Size it from a one-card site trace of rank 1
   first (`OWNRT_SITE_TRACE=1`, harness only).
3. The HC low/gate production-vs-bench gap (about 1 µs per launch, 100 launches per half on rank 1) is still
   unexplained (fixed-cost-2). Worth about 0.1 ms per half if found.

## Files

- [flags.py](flags.py): the B set (one place for the harness and the servers).
- Harness (copies of hc-split-2026-10-30's): [run_phase.sh](run_phase.sh) (one-card arms on `TC_BDF`, extras `B` /
  `Bnonw`), [launch_phase.sh](launch_phase.sh), [compare.sh](compare.sh), [compare_driver.py](compare_driver.py),
  [halves.py](halves.py), [klog.py](klog.py), [archive_runs.sh](archive_runs.sh), [drivers/](drivers/); `launch/` holds the
  generated launch JSONs.
- Suite (copies of hc-split-2026-10-30/suite): [suite/arm_env.py](suite/arm_env.py) (`twoA`, `twoB`),
  [suite/lab/adapter6_tp.py](suite/lab/adapter6_tp.py) (`ONE_CARD_KEYS`), [suite/run_arm_suite.sh](suite/run_arm_suite.sh)
  (two locks, port 18179, `--wait-seconds 300` on every server), [suite/suite.sh](suite/suite.sh),
  [suite/klog_check.py](suite/klog_check.py) (the sudo form), [suite/suite_compare.py](suite/suite_compare.py),
  [suite/hitcycle.py](suite/hitcycle.py), [suite/archive_endgate.sh](suite/archive_endgate.sh).
- Raw runs (sha256 lists beside them): `/mnt/raid-models/ownrt-experiment-archives/2026-10-31/two-card-flags-gates-runs`
  (phase g1, 859 files), `.../2026-10-31/two-card-flags-endgate` (all four server work directories, 1,194 files). Build r1 and its tree:
  `.../2026-10-30/engine-builds/hc-split-r1`. The `/dev/shm` copies were removed after verification.
- Results: [suite/results/suite/](suite/results/suite/) (per-server suite, TTFT, gate evidence, rank logs),
  [suite/results/hitcycle-endgate.json](suite/results/hitcycle-endgate.json), [results/](results/) (harness halves, prompt times).
