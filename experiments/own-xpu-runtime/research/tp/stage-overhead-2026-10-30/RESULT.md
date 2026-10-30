# Where the four-card stage overhead goes (2026-10-30)

**Question.** On four cards (two pipeline ranks, each split exactly across two cards, flag set `tptsxqc`), each stage
is about 1.6–2 ms slower than "half the split work plus the replicated work" predicts
([decode-site census](../../decode-site-census-2026-10-30/RESULT.md) calibrated about 1.96 ms). Where does it go, which
exchange sites make one card wait, and which exact levers can take it back?

## In plain words

- **Measured directly, the overhead is 1.58 ms per half on rank 0 and 1.68 ms on rank 1.** The census's 1.96 ms was
  calibrated against an older cycle (10.82 ms, before the snapshot/rollback trims and per-card contexts) and the
  one-card draft time. The current service's hit cycle is 10.41–10.45 ms, with both ranks' paths within 0.1 ms of each
  other.
- **About two thirds of it (1.01 / 1.16 ms) is the split kernels themselves.** When a kernel's work is halved for the
  two cards, its time does not halve: every split launch keeps a fixed part of 2–24 µs. The routed experts on 5 slots
  take 59–70% of their 10-slot time, the GDN recurrence on 24 heads 79–81%, and the small split kernels (QSA attention,
  GDN conv/gated/a, expert activation and check, QSA k/v/prepare/pool) barely shrink at all. QSA attention takes
  exactly as long on 12 heads as on 24.
- **The exchanges themselves are small.** Each of the 69 / 76 exchange kernels per half costs about 2.9 µs of its own
  time plus flag latency (0.20 / 0.22 ms per half), plus about 1 µs of launch and teardown (the 0.06–0.08 ms residual).
- **The two cards are balanced.** Measured on one card, card 0's and card 1's split work differ by 2–4 µs per half in
  total, and by under 1 µs at any single site. Waiting caused by one card arriving later costs only 0.04 / 0.06 ms per
  half. Rebalancing expert slots, GDN heads or vocabulary rows has nothing to win.
- **The host costs 0.24 / 0.17 ms per half extra on two cards, and it is event retirement.** After each drain the
  engine retires every finished event of both cards before it replies: 0.29–0.32 ms per half on two cards against
  0.13–0.15 ms on one card. That growth (0.16–0.18 ms) matches the extra host tail exactly. A persistent card-1
  submission thread (an existing flag) moves card 1's start from 25 to 7 µs but saves nothing measurable (A/B/A/B,
  both ranks).
- **Snapshot, rollback and handoff add nothing TP-specific on hit cycles any more:** the snapshot is 0.03 ms after
  `OWNRT_SNAPSHOT_NOWAIT`; token preparation (0.12 ms) and the handoff export (0.15 ms) are the same on one card.
- **What would pay (each exact):** fewer, fatter split launches. The single largest item is the routed experts on 5
  slots (0.46 / 0.54 ms per half of "not halving"); then event retirement on the critical path (0.16–0.32 ms), the GDN
  small kernels on 24 heads (0.28–0.29 ms) and the separate exchange kernels (0.2–0.3 ms). No single lever reliably
  reaches 5% of the four-card decode on its own; the expert one comes closest (upper bound 0.46–0.54 ms, 4.4–5.2% of
  the cycle). Together the first four project to about 0.75–1.05 ms per stage, 7–10%.
- **Recommended next build:** a paired compact expert launch for the four-card decode: on each card, gate and up of
  its 5 slots in one launch (each row's arithmetic unchanged), with the SiLU product in the same launch. On one card
  at 10 slots the existing gate+up pairing measured exactly 2× one launch (throughput-bound,
  [service-speed DO-NOT-REPEAT](../../../gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md)); at 5 slots each launch sits
  on its floor instead, so the pairing should recover about one floor per layer: estimated 0.35–0.4 ms per stage,
  about 3.5–4%. It can be measured on one card first with the probe built here (minutes, no TP run).

## What was measured, and how

- **Binary.** Engine sources at `0b9ee3468` plus two diagnostics, both default off (build r1 `967eca960b91…`; r2
  `932e4b5e2b3a…` adds the probe fix below; both archived in
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/engine-builds/stage-overhead-20261030-r{1,2}/`). The default
  paths are unchanged: every arm's state equals one card bitwise (below).
- **Rank harness.** The prefill-speed rank drivers unchanged ([run_phase.sh](run_phase.sh)); context 65536, F32, the
  census launch environment (r7) with this binary. Prompt rows are read token by token (128 rows), then 64 decode
  halves on fixture inputs (positions 128–191); rank 0 runs pattern `h` (64 speculative hits, each with its draft).
  Medians over halves 3..64. Rank 1 on 23:00.0 + 47:00.0, rank 0 on 23:00.0 + 27:00.0, one card on 23:00.0. Arms in
  one phase per rank, A/B order: one, full, full + stats, replicated, exchange-only, full, one.
- **(a, b) Per-site exchange statistics, under TP, no profiler: `OWNRT_TP_EXCHANGE_STATS=N`**
  (`single_device.cpp` `submit_exchange_stats`, `rank.hpp` `tp_compare`). The waiting work-item of each exchange
  kernel reads the EU thread's sub-group clock at kernel entry, at the start of its wait and at its end (the B70 offers
  no device-scope clock: [clocktest](clocktest/clocktest.cpp), [results](results/clocktest-c23b.json)). It adds the
  intervals to unused words of its own card's site record (never touched by the peer). Clock rate 2.80 cycles/ns,
  from a 200,000-poll spin timed by the host. One poll costs 255–270 cycles (91–96 ns) on an idle card and 470–530
  cycles (170–190 ns) under TP. Statistics skip each site's first execution and cover 191 halves (127 prompt rows
  read as halves and 64 decode halves; argmax only in decode halves). The slot labels come from
  `tp-exchange-slots.json`.
- **(c) Split shapes on ONE card, with the profiler: `OWNRT_TP_SHAPE_PROBE=0|1`** (`rank.hpp`). A one-card process
  (never `--tp-replicate`) builds the four-card plan with the unchanged transform. It keeps only card c's launches and
  drops the exchanges and the head merge, so every split site runs exactly card c's kernel, rows, heads and slots.
  `OWNRT_SITE_TRACE` then times every kernel. Outputs are not exact (the peer's rows are never written); timing only.
  The one-card reference is the same harness with the same trace. Rank 1: prompt 16, 48 halves; rank 0: prompt 0, 48
  speculative halves; medians over decode halves 9..48.
- **(d) Host.** The engine's own per-half host timings (`timings.jsonl`): preparation, enqueue loop, device wait,
  retirement, and the tail after the wait. Cross-checks: `--tp-replicate` with nothing split and no exchange, against
  one card, and an A/B/A/B of the existing `OWNRT_TP_PERSISTENT_THREAD=1`.
- **(e) Hit cycles in service.** The retained controller traces of the four fault-ladder suite servers (binary
  `5921bb96f630`, the 3,490-token request, 40 hit cycles each), re-analysed with the miss-stall analyzer
  ([hitcycle.py](hitcycle.py)).

**Exactness of the diagnostics** ([logs/a1-compare.txt](logs/a1-compare.txt), [logs/b1-compare.txt](logs/b1-compare.txt)):
- Rank 1: full state 1079/1079 equal for stats on vs stats off, stats on vs one card, full vs one card, replicated and
  exchange-only vs one card, and one card vs one card. All 64 tokens are equal in all 7 arms.
- Rank 0: 1029/1029 target buffers and 71/71 draft buffers equal, with equal draft tokens, in the same comparisons.
- Card 1 equals card 0 on every buffer both hold in every TP arm (728 / 670). There were 0 exchange timeouts.
- With statistics on, a half is 0.03 ms slower (10.170 vs 10.137 ms; 9.227 vs 9.198 ms).

## Breakdown per stage (ms per decode half)

| Component | Rank 0 | Rank 1 | Kind | Source |
| --- | ---: | ---: | --- | --- |
| one card (harness) | 10.662 | 12.289 | measured | `c2-r0-one-nw*` (snapshot/rollback nowait, as TP), `a1-r1-one*` |
| split roles on one card, S | 6.084 | 7.656 | measured | probe trace, one-card reference |
| ideal TP half = one − S/2 | 7.620 | 8.461 | derived | |
| **TP half, `tptsxqc`** | **9.198** | **10.137** | measured | `b1-r0-full*`, `a1-r1-full*` |
| **overhead** | **1.578** | **1.676** | derived | |
| (c) split kernels that do not halve | 1.013 | 1.162 | measured (one card) | [probe](results/c2-rank0-probe.json), [probe](results/c1-rank1-probe.json) |
| &nbsp;&nbsp;routed experts (gate, up, down, act, check, route compaction) | 0.463 | 0.543 | measured | |
| &nbsp;&nbsp;GDN small kernels (recurrence ×2, gated, conv, a) | 0.285 | 0.281 | measured | |
| &nbsp;&nbsp;QSA (attention, k, v, prepare, pool, q/gate) | 0.117 | 0.178 | measured | |
| &nbsp;&nbsp;GDN projections (qkv, z) | 0.114 | 0.095 | measured | |
| &nbsp;&nbsp;attention output (Q8_0 rows) | 0.051 | 0.067 | measured | |
| &nbsp;&nbsp;head (logits, argmax) | — | 0.005 | measured | |
| (a) exchange kernels: own time (stores, fences, counter, flag) | 0.146 | 0.158 | measured (TP, device clock) | [sites](results/b1-rank0-sites.json), [sites](results/a1-rank1-sites.json) |
| (a) flag latency (wait even when both arrive together) | 0.052 | 0.064 | measured (TP) | Σ min(wait card 0, wait card 1) |
| (b) imbalance (later card on the critical path) | 0.041 | 0.059 | measured (TP) | Σ \|wait0 − wait1\| / 2 |
| (d) host, two cards (preparation + tail after the device wait) | 0.244 | 0.173 | measured (host clock) | timings: tail +0.190 / +0.178; event retirement 0.29 vs 0.13 / 0.32 vs 0.145 ms |
| (e) snapshot, rollback, handoff on hit cycles | ≈ 0 | ≈ 0 | measured (service) | snapshot 0.028 ms; token prep 0.12 and export 0.15 ms are one-card costs too |
| residual: exchange-kernel launch/teardown, gaps | 0.081 | 0.059 | derived | ≈ 1 µs per exchange |

Cross-checks:
- Exchange-only minus replicated: 0.205 ms for the 33 / 37 row-split exchanges, which is 6.2 / 5.5 µs each. It
  includes the extra launch and card 1's systematic lag in that layout. Per-site own time + flag latency + imbalance +
  residual comes to 3.7–3.9 µs per exchange in the real layout.
- The replicated layout costs +0.21 ms (rank 1) and +0.50 ms (rank 0) against one card. On rank 0 that also includes
  the full-size card-1 state and snapshot of the replicated layout, so the host timings are used for (d).
- Card busy time in the probe: rank 1 9122.5 / 9124.7 µs (card 0 / card 1), rank 0 7969.7 / 7973.7 µs.

**Why the split kernels do not halve** ([split_fit.py](split_fit.py), [results/split-fit.json](results/split-fit.json)):
per launch, the part that does not shrink when the work halves (f = 2·t_card − t_one), mean (range):

| Role (launches per half r0 / r1) | one card µs | per card µs | ratio | fixed part f µs |
| --- | ---: | ---: | ---: | ---: |
| expsgate (23 / 25), 5 of 10 slots | 35.3 / 37.4 | 24.4 / 25.7 | 0.69 | 13.6 / 14.0 (9–22) |
| expsup (23 / 25) | 33.4 / 35.4 | 23.5 / 24.8 | 0.70 | 13.6 / 14.2 (8–22) |
| expsdown (23 / 25) | 34.7 / 36.5 | 20.4 / 22.3 | 0.59–0.61 | 6.1 / 8.1 (0–9; layers 30 and 36 halve exactly) |
| gdn.recurrence (2 per layer, 18 layers) | 31.6 / 28.9 per layer | 24.8 / 23.4 | 0.79–0.81 | 18 per layer |
| qsa.attention (5 / 7 layers) | 22.7 / 24.1 | 23.1 / 24.2 | 1.00–1.02 | all of it |
| gdn.gated, gdn.conv, gdn.a, expsact, expsdown.check, qsa.k/v/prepare/pool | 2–10 | 2–9 | 0.79–0.99 | 2–8 |
| attention output (Q8_0), gdn.qkv, gdn.z, qsa.qgate | 27–59 | 17–30 | 0.51–0.64 | 1–8 |
| logits (521 MB Q6_K), argmax | 882 / 102 | 449 / 48 | 0.47–0.51 | ≈ 0 |

The census measured 10 → 20 slots (two rows) at exactly 2× for the per-slot expert kernels. So below 10 slots the
expert launches sit on a floor rather than paying a constant per-launch cost: a 5-slot launch is not
throughput-bound.

## Imbalance per exchange site

Waits are per half and per site, means over 191 executions ([results/a1-rank1-sites.json](results/a1-rank1-sites.json),
[results/b1-rank0-sites.json](results/b1-rank0-sites.json), all 76 / 69 sites listed there). Total waits per half:
- rank 1: card 0 0.151 ms, card 1 0.096 ms;
- rank 0: card 0 0.092 ms, card 1 0.094 ms.

| Rank | Site | Card 0 waits µs | Card 1 waits µs | What it is |
| --- | --- | ---: | ---: | --- |
| 1 | first exchange `blk.23.qsa.attention` | 21.0 | 0.4 | card 1's submission thread starts 25 µs after card 0's (every half) |
| 0 | first exchange `blk.0.gdn.gated` | 16.3 | 0.4 | the same start lag |
| 1 | `argmax` (head shards) | 11.2 | 0.4 | card 1 arrives later at the end of the half; the two head shards take 47.7 µs each on one card |
| 1 | `blk.25` / `blk.31` / `blk.27.expsdown`, `blk.27.attention`, `blk.24.gdn.gated` | 3.5–10.9 | 0.7–2.2 | means carried by one 0.3–1.6 ms stall each in 191 halves (card 1 late; host-side) |
| 0 | `blk.7.qsa.attention`, `blk.6` / `blk.4.gdn.gated` | 2.5–5.1 | 0.8–1.7 | one 0.16–0.76 ms stall each |
| 0 | `blk.12–22` `gdn.gated` and `expsdown` | 0.3–0.6 | 1.7–3.5 | card 0 steadily ~1.5–3 µs later on the last layers |
| 1 | `attention` exchanges (19 of 25 sites), `expsdown` (16 of 25) | 0.6–2.3 | 0.5–1.8 | card 1 later by ~0.5–1.3 µs |
| 1 | `gdn.gated` (13 of 18), late QSA layers | 0.4–0.7 | 1.7–2.7 | card 0 later by ~1–2 µs |

- The probe shows the device work of the two cards equal at every site, to within 0.8 µs.
- So the steady 1–3 µs differences come from host submission timing and flag propagation, not from the slot, head or
  vocabulary assignment.
- The rare stalls (7 sites on rank 1, 4 on rank 0 had a wait over 32 µs) are card-1 host-side delays. They show in the
  tails, not the medians.

## Ranked exact levers (per-stage estimates; the cycle is 10.43 ms and both stages must drop)

| # | Lever | Estimated saving per half | Share of the four-card decode | Basis |
| --- | --- | --- | --- | --- |
| 1 | **Paired compact expert launch**: gate + up of the card's 5 slots in one launch, SiLU product fused; route compaction folded into the gather. Per-row arithmetic unchanged | 0.35–0.4 ms (upper bound 0.46 / 0.54) | 3.5–4% (≤ 5%) | (c) experts; one-card pairing was exactly 2× at 10 slots, so at 5 slots it should cost about one 10-slot launch |
| 2 | **Event retirement off the critical path** (retire after the reply, or in the next half's enqueue loop while the cards run). Host only | 0.16–0.19 ms (TP increase), up to 0.29–0.32 | 1.5–3% (one card would gain 0.13–0.15 too) | (d): retirement 0.29–0.32 vs 0.13–0.15 ms; the host tail grows by the same amount |
| 3 | **Fused GDN block per card** (conv + both recurrence launches + gated norm, + a) on 24 heads | 0.15–0.22 ms | 1.5–2% | (c) GDN small kernels 0.28–0.29 ms |
| 4 | **Exchange stores and flag in the producer's tail** (gated norm, attention-output GEMV, expert down, QSA attention, head shard): no separate kernel | 0.15–0.2 ms | 1.5–2% | (a) own 0.15–0.16 + residual 0.06–0.08; the flag wait stays |
| 5 | QSA attention with more work-groups per head on 12 heads (KV tiles spread, same combine order); the small QSA kernels fused | 0.05–0.1 ms | 0.5–1% | (c) QSA 0.12–0.18 ms; attention takes the same time on 12 heads as on 24 |
| 6 | Split the replicated HC low/gate GEMVs (1.51 / 1.65 ms per card) by rows | net 0.25–0.3 ms with today's exchanges (4 more per layer at ~3.9 µs); 0.45–0.55 ms with lever 4 | 2.5–3%; with lever 4 ≈ 4.5–5% | split GEMV ratios 0.51–0.64 measured here; exchange cost from (a); rough (narrow low outputs untested) |
| — | Rebalance expert slots / GDN heads / vocabulary rows | ≈ 0 (≤ 0.04–0.06 ms) | 0 | the two cards' work is equal; closed |
| — | Merge adjacent exchanges | 0 without changing the split plan | 0 | each of the 3 exchanges per layer feeds a different consumer of the full vector |
| — | Persistent card-1 submission thread (`OWNRT_TP_PERSISTENT_THREAD=1`, existing) | 0.00–0.01 ms (A/B/A/B: r1 10.124 / 10.196 vs 10.113 / 10.116; r0 9.199 / 9.209 vs 9.207 / 9.195) | 0 | closed |

**Which could move the four-card decode by ≥ 5%:** none alone with confidence. Lever 1 has a 4.4–5.2% ceiling, and
lever 6 together with lever 4 reaches about 5%. Levers 1 + 2 + 3 + 4 together project to 0.75–1.05 ms per stage
(7–10%, about 78.5 → 84–87 tok/s). They would also make every rank-0 redo on a miss faster.

**Single recommended next build: lever 1, the paired compact expert launch.** It is exact by construction and the
largest measured item on both stages. It can be checked on one card in minutes with `OWNRT_TP_SHAPE_PROBE` before any
four-card run. Lever 2 is a host-only change that can go alongside it.

## The census's 1.96 ms, reconciled

The census formula subtracts the one-card draft (1.32 ms) and uses a 10.82 ms hit cycle measured on binary
`b7786ad42675`. With today's service (hit cycle 10.41–10.45 ms; four-card draft 1.07 ms after the head and GEMV
splits) the same formula gives about 1.83 ms. That still includes rank 0's hit-cycle extras at 3,490 tokens. Measured
directly per half, at equal positions on one card and four cards, the overhead is 1.58 / 1.68 ms, broken down above.
Use 1.6–1.7 ms per stage in projections, and split it as above when a lever changes one part.

## Incidents

- No device incident. The kernel log was clean before every phase (24 h) and after every arm, and over the 2 hours
  at the end ([logs/](logs/)). All four cards were left free and no engine process remained.
- One host-side stop, in my own diagnostic. The first rank-0 probe (`c1-r0-p0`, build r1) refused to load: "third bank
  requires proved full destination overwrite". Rank 0's miss banks size compact buffers from the head layout, which
  the probe had cleared. Fix (build r2): the probe keeps card c's compact extents as the one card's, and the dump
  never reassembles a one-card run. The failed run is kept in the archive (`c1-r0-p0-failed-r1`). The same-binary
  r2 smoke then passed and the probe arms ran. r1 and r2 differ only in probe-mode code and a dump guard that applies
  to one-card runs with a head layout (the probe only).
- Archive copies first failed silently: `cp -a` exits 1 on the NTFS RAID (POSIX ACLs refused). Switched to
  `cp -r --preserve=timestamps`. Every archived run was verified by sha256 before its `/dev/shm` copy was removed.

## Files

- Engine (default off): `stage2/packet194-expert-diet-engine/single_device.cpp` (`OWNRT_TP_EXCHANGE_STATS`),
  `gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp` (`OWNRT_TP_SHAPE_PROBE`, the slot-label file, per-site dump).
- Scripts:
  - [run_phase.sh](run_phase.sh): device phases;
  - [cpu_plan_check.py](cpu_plan_check.py): plan-only check of both diagnostics, no device
    ([r1](results/cpu-plan-check.json), [r2](results/cpu-plan-check-r2.json));
  - [analyze.py](analyze.py): timing, sites and probe;
  - [breakdown.py](breakdown.py): [results/breakdown.json](results/breakdown.json), every number in the tables;
  - [split_fit.py](split_fit.py), [hitcycle.py](hitcycle.py), [klog.py](klog.py), [archive_runs.sh](archive_runs.sh);
  - [clocktest/](clocktest/): device-clock probe.
- Results: [results/](results/) (timing per phase, per-site statistics, probes, split fit, hit cycle, breakdown).
  Small per-run evidence: [evidence/](evidence/) (summaries, decode-row host timings, exchange statistics and slot
  labels).
- Raw runs (sha256 lists beside each): `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/stage-overhead-runs-{a0-a1,b0-b1,c0-c2,d1-d2}/`.
