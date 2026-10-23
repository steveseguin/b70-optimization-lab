# Packet185: two-card un-split target head, the measured attribution for packet177(b) and V3's kill thresholds

This is CPU preparation only. Nothing was touched: no GPU, `/dev/dri`, device binary run, service, setting, PAUSE/STOP
file, queue file or sudo. Nothing was queued or committed.

The line is the Unsloth UD-IQ3_XXS of Qwen3.8 Flash-Next (the quantized compressed version):

* two B70 cards, single user, greedy;
* 128-token capped suite, exact against `iq3-p49-split32-v1`;
* full BF16 KV and state.

Record: two-card **58.798109 tok/s** (packet136 bundle 8). This packet is a measurement: it never runs a record, chain
or waiter.

## Why

The 2026-10-22 lever synthesis (`analysis/lever-synthesis-20261022.md`) found that bundle 8's split target head ties
rank 0's speculative half A into every emission. The emission is `max(rank1_own, A + σ)`, where σ is the rank-0 suffix
service (σ ≈ 0.478 ms in six coupled split-head arms).

The only lever that priced at ≥ +2% was V3: un-split the head, then run layers 24-25 on rank 0 for the verified token.
It sits in packet177's closed placement family.

**Coordinator ruling (2026-10-22):** packet177(b) stays closed by its letter until the attribution is MEASURED.
Packet185 supplies that attribution and V3's two kill thresholds. V3 is built afterwards on these measured numbers, or
closed cheaply.

## What is measured

Bundle 8 as recorded (`production`, target head split 202,240 / 46,080 rows) is compared with bundle 8 with the full
248,320-row target head on rank 1 (`unsplit`, `target_head=production`). In the unsplit selection rank 1 does no merge
and rank 0 does no suffix service.

**The design uses fresh loads; a one-load switch is impossible without a new binary.**

* The head split is a storage choice. Rank 1 loads 202,240 or 248,320 head rows; rank 0 loads the 46,080-row suffix
  plus the p105 auxiliary buffers, or nothing.
* The native bracket's `bracket_select` refuses a `head` change in both directions. The production-shape gate proves
  this with 15 refusals per run, including the head switch.
* The v5 harness also requires identical arena descriptors and zero weight uploads across views.

Each queue row is therefore one load with one view. There are five rows, C/U/C/U/C, and each depends on the previous one.

Per view, the vendored packet85 interval model (`v5/interval_model.py`) reproduces the 58.798109 record from its own
receipts. It splits the first 99 intervals of each of 12 prompts into:

* D: rank-1 draft;
* A: rank-0 speculative half;
* B: rank-1 half, including the head and, on split views, the merge wait;
* R, C: miss restore and correction;
* offset and G.

Rank 0's packet150 host scopes give the split views' suffix service σ. They must be absent on the unsplit views.

## Decision (`s185_decision` in view row 4's summary, or `v5/s185_decision.py` over the five outputs)

**V3 GO** only if all of the following hold:

* **u** = mean(unsplit hit-B) − mean(production hit-B) **≤ 0.39 ms**. This is the point where V3's central case falls to
  +2% (`analysis/v3_corners.py`).
* **Decoupled B − A** (mean hit B − A over the two unsplit views) **≥ 0.60 ms**.
* Every view is 13/13 exact, with identical draft proposals and per-prompt acceptance.
* Control drift is ≤ 3%.

Otherwise V3 is **closed**, and packet177's placement row keeps its closure with the measured `attribution` appended.

**Resolution.**

* Fresh loads drift. v4 controls drifted up to 1% on this line, which is about 0.13 ms on B.
* u is a cross-load difference. It is reported as resolved only when |u − 0.39| exceeds the spread of the three control
  hit-B means, and the draft-corrected u agrees on the side. The draft-corrected u scales control B by rank 1's own draft
  ratio; D is identical work in both selections (full-shape: draft commands identical).
* The expected u is 0.15–0.25 ms. That is the 46,080 rows at the head's roofline minus the merge round trips; the
  bundle-6-era lower bound from packet106b's real fresh-load grid is 0.049 ms. So the margin to 0.39 (≥ 0.14 ms) exceeds
  the drift band, except near the threshold.
* B − A is within one load and needs no cross-load correction. Packet183's one-load controls today were
  0.652 / 0.668 / 0.652 ms on the split head; bundle 8's predicted un-split value is 0.66–0.81 ms.

## Binary, selections, memory

**Binary: no rebuild.**

* `v5/build/device/own-rt-iq3` is packet183's engine byte for byte: sha256
  `36e476d198fb302124fb687c8405cfdcd873d14dff89d94049581ef7c86fc631`.
* It is verified against packet183's committed build receipt (`lineage-inputs/packet183-own/v5/evidence/build.json`).
* The 78 packet103/136 parent objects are linked through pinned `inherited/` links, and `compiler_runs` is 0.
* With `dense_scales: expanded`, every S1 site issues the production kernels, so its `production` selection is bundle 8
  (packet183's device controls 58.617 / 58.587 / 58.630 tok/s).

**Selections.**

* `v5/lineage/production/selection.json` is packet183's, unchanged.
* `v5/lineage/unsplit/selection.json` is identical except `"head": "production"`.
* The dispatch is identical.
* `packet153` static snapshot is **not selectable without a new build**, so it is left out.
  * The reused engine's bracket domain admits only `snapshot_host: production`
    (`v5/native/engine_bracket.hpp`, the `packet183-s1` line), and every view row's reset passes through
    `bracket_select`.
  * Packet153's own engine is no longer on this host.
  * V3's build carries static snapshot.

**Memory (production-shape census, actual allocation calls, `v5/evidence/full-shape.json`).**

| Rank | production | unsplit | delta |
|---|---:|---:|---:|
| 0 | 28,144,229,620 B | 27,986,907,348 B | **−157,322,272 B** (46,080 suffix rows × 3,380 B + 1,571,872 B p105 buffers) |
| 1 | 31,425,985,242 B | 31,581,735,626 B | **+155,750,384 B** (46,080 rows × 3,380 B − 16 B best16) |

* On rank 1 unsplit, arena headroom is 630,519,094 B and physical free is 2.66 GB.
* The derived ledger `v5/lineage/unsplit/memory-plan.json` keeps the inherited, unused 629 MB class-layout reserve.
  This leaves 1,373,494 B of plan headroom under 30 GiB; it passes the memory gate.
* Host admission is unchanged: 105,411,248,128 B MemAvailable plus the queue's 1 GiB at START. The host shadow nets
  −1.57 MB.

## Rows (`ops/lane-queue/proposed-p185-two-card-B.txt`, sha256 `0c8b23fe...`, PROPOSAL ONLY)

Expected times derive from packet183's recorded rows today:

* The smoke ran 11:56:31–12:01:34 UTC: 299.2 s, of which the load was 188.2 s (cold page cache).
* The bracket ran 12:03:09–12:11:14 UTC: 479.7 s = a 94.2 s load plus views of 122.6 (first, cold first request),
  67.4, 64.3, 66.7 and 64.5 s.

A packet185 row is therefore ≈ 94 + 123 ≈ 217 s, or ≈ 311 s for the first row of a window.

| Row | View | Expected | Plan | Watchdog | Writes |
|---|---|---|---|---|---|
| `packet185-view0-production-B` | split (bundle 8) | ~311 s | 300–420 s | 3600 s | 240 MB |
| `packet185-view1-unsplit-B` (after view0) | full head | ~217 s | 200–330 s | 3600 s | 240 MB |
| `packet185-view2-production-B` (after view1) | split | ~217 s | 200–330 s | 3600 s | 240 MB |
| `packet185-view3-unsplit-B` (after view2) | full head | ~217 s | 200–330 s | 3600 s | 240 MB |
| `packet185-view4-production-B` (after view3; decides) | split | ~217 s | 200–330 s | 3600 s | 240 MB |

Five rows plus four 61 s queue drain spacings come to ≈ 1,423 s, **about 24 minutes of lane B**. There is no separate
smoke. Every row's first request carries the in-run data proof, every-token exactness stops a row at its first mismatch,
and row N > 0 refuses unless row N − 1 passed exact on the same lane.

The rows need:

* lane B, cards 2+3;
* PAUSE-A held for the whole window;
* the owner's three endpoints stopped only after `lanequeue.py plan --lane B` passes on the live queue.

Card 2 has a GuC lockup history, so the rows may run on lane A instead (the entry gate covers both lanes). Five loads
mean five teardowns: count faults after each row.

## Gates (all CPU; receipts in `v5/evidence/`)

| Gate | Result |
|---|---|
| Reuse (`p185_v5_build_engine.py`, `build.json`) | no compiler; device `36e476d1...`, gnu-host `1164a9eb...` equal packet183's receipt; 78 parent objects pinned |
| Production shape (`p185_v5_full_shape.py`, `full-shape.json`, 8 `shape-*.tar.gz`) | both selections × both ranks: fresh startup, 5 re-select resets, reset extents, arena and capture identity, 15 native refusals (incl. in-load head switch); rank 0 533/533 commands identical; rank 1 523/526 identical, the 3 differing are the head GEMV (683,571,200 vs 839,321,600 B binding, same `p33::Kernel<0,Q6_K,2560,1>`) and two argmax phases; draft commands identical; real-parser startup census equals the bracket fixture's |
| Controller (`controller.json`) | GNU/Intel, two repeats each, 12 hit/miss/mixed/native-draft cases |
| Admission (`admission.json`) | both plans pass the 30 GiB / 1.5 GB gate; census ≤ plan; deltas match the allocation formulas exactly |
| Analysis (`analysis.json`) | 22 tests: `test_analyze` (10, incl. unsplit scope absence), `test_timing_report` (3), `test_s185_decision` (9) on REAL data: packet183's 60 bracket streams (controls D 1.597, A 12.49, B 13.147, B−A 0.66, σ 0.403 ms; rule CLOSES on its S1 rows; every GO/CLOSE/INCOMPLETE branch), packet153's real summary refused (INCOMPLETE), packet106b's real fresh-load grid (u 0.049, un-split B−A 0.524 ms) |
| Safety, exec limits, loader | drain/refusal tests; no forbidden math, no external includes; pre-exec getrlimit guard; `ldd` on both engines (no program code runs) |
| Seal (`cpu_seal.py`), `package_rows.py` | `v5/cpu-seal.json`; proposal written (`package-rows.json`) |
| `check_queue_rows.py` | entry (5 rows × 2 lanes × positive/unit/environment), launch limits (20), worker (65 requests + corrupted-output abort), report (5 rows × 2 lanes), private-copy `lanequeue.py plan --lane B` (5/5 passed), `rehearse_entry.py` (5/5, 0 identity refusals), live pin guard (5/5) |
| `final_checks.py` (+ `--ready`) | drain scan: packet code FIXED, only two vendored historical v4-lanes copies UNFIXED (import trace loads none); READY last; live pin guard on the full closure |

`rehearse_entry.py --report` is a shared-tool limitation, recorded and not gating. It only probes kinds smoke/bracket
for v5 entries, and packet185 rows are `--kind view`. The packet's own report gate runs the real `bracket_job.py
--report-only` path for all five rows.

## What changed vs packet183 (all CPU-side)

* **Harness: one view per row.**
  * `bracket.py`: kind `view`, empty switch domain.
  * `bracket_config.py` / `bracket_job.py`: `--index 0..4`.
  * `screen.py`: the row loads its view's lineage; the predecessor row is required.
  * `p185_v5_compare.py`: per-row report, interval statistics, and the decision in row 4.
  * `analyze.py`: head scopes mandatory on split, forbidden on unsplit.
* **New:** `s185_decision.py`, `interval_model.py` (vendored, sha `6627ffa3...`), `build_decision_fixture.py`,
  `test_s185_decision.py`, `admission_gate.py`.
* **Removed:** S1 gates and the S1 smoke/bracket configs; packet183's waiter and window receipts moved to
  `lineage-inputs/packet183-own/`.
* **Native:** `native/full_shape_entry.cpp` re-selects the same selection per view and adds the head-switch refusal.
  The engine's native sources are unchanged apart from the include-path rewrite.

## Not claimed

* No device result, speed, exactness on device or record.
* The memory census is allocation accounting; driver residency is unmeasured.
* The un-split arm's speed is not a lever. u and B − A feed V3's go/no-go.
* V3's other inputs are not measured here: per-layer rank-1 saving, rank-0 cost and accept ordering.

[Note](../../../../notes/2026-10-22-packet185-twocard-unsplit-head.md) · [DO-NOT-REPEAT](DO-NOT-REPEAT.md) ·
[Retention](RETENTION.md) · [Lever synthesis](analysis/lever-synthesis-20261022.md)
