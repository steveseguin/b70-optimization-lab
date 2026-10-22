# 2026-10-22: packet185, the two-card un-split head measurement (CPU preparation)

Packet: [`experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/`](../experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/README.md).
Proposal: `experiments/own-xpu-runtime/ops/lane-queue/proposed-p185-two-card-B.txt`. It was not queued.

No GPU, `/dev/dri`, device binary run, service, setting, PAUSE/STOP or queue file was touched. Nothing was committed.

## Why

Today's lever synthesis (packet185 `analysis/`) found that bundle 8's split target head makes the emission wait on rank
0's speculative half plus a suffix service. That coupling, σ ≈ 0.478 ms across six coupled split-head arms, explains
why every rank-1 → rank-0 move lost. It also caps rank-1-only levers at +0.9%.

The only lever priced at ≥ +2% is V3: un-split the head, then run layers 24-25 on rank 0 for the verified token. V3 sits
in packet177's closed placement family.

**Coordinator ruling:** packet177(b) stays closed by its letter until the attribution is measured. This packet measures
it and V3's two kill thresholds.

## What it measures

The comparison is between two selections of bundle 8:

* split head: 202,240 rows on rank 1, 46,080 on rank 0;
* full 248,320-row head on rank 1 (`target_head=production`).

**There is no one-load switch.** The split is a storage choice, and the native bracket refuses the switch in both
directions (production-shape gate). So the design is five fresh loads, one 12×128 view each, in the order C/U/C/U/C, as
five queue rows of about 217 s each (the first about 311 s). The total is about 24 min of lane B including drain
spacing.

**There is no rebuild.** The device engine is packet183's `36e476d1...` byte for byte with `dense_scales=expanded` (that
is, bundle 8), and only the selection was resealed.

The packet85 interval model splits each view into A, B and D. Rank-0 host scopes give σ on the split views.

## Decision rule

`s185_decision` appears in view row 4's summary. V3 GO requires all of the following:

* u (un-split rank-1 cost) ≤ 0.39 ms;
* decoupled B − A ≥ 0.60 ms;
* every view exact with identical draft proposals;
* control drift ≤ 3%.

Otherwise V3 is closed, and the measured attribution is appended to packet177's placement row.

**Drift.** Fresh loads drift up to about 1%, which is about 0.13 ms on B. Expected u is 0.15–0.25 ms, so the margin to
0.39 exceeds that band unless u lands near the threshold. A draft-corrected u and the control B spread are reported. B −
A is measured within one load.

## CPU numbers already measured

**Memory census:**

* rank 0: −157,322,272 B;
* rank 1: +155,750,384 B, which leaves 0.63 GB arena headroom and 2.66 GB physical free.

**Packet183's real control streams today** (split head): D 1.597 ms, A 12.49 ms, B 13.147 ms, B − A 0.652–0.668 ms, and
rank-0 suffix service 0.403 ms per cycle (`suffix_head` 0.310).

**Packet106b's real fresh-load grid** (bundle-6 era): un-split B − A 0.524 ms, split 0.480 ms, B difference +0.049 ms.

## Gates

All passed:

* reuse;
* production shape (both selections and ranks; rank 1 differs only at the head GEMV and argmax; draft identical);
* controller;
* admission;
* analysis (22 tests on real packet183, packet153 and packet106b device data);
* safety, limits, loader;
* seal and package_rows;
* entry, launch limits, worker, report;
* private-copy `lanequeue.py plan --lane B` (5/5) and `rehearse_entry.py` (5/5);
* pin guard;
* final checks and READY.

One shared-tool limitation is recorded: `rehearse_entry.py --report` only knows the smoke and bracket kinds. Packet185's
own report gate covers the real report path.

## Next

In the owner window, stop the three endpoints, keep PAUSE-A, and run the five rows on lane B (or lane A). Read
`s185_decision`:

* **GO:** build V3 on the measured u and B − A, bundling packet153's static snapshot.
* **CLOSED:** append the attribution to packet177's placement row.

## Device result (2026-10-22, lane B window 13:55-, unit lanequeue-B33): V3 GO

Five fresh loads, C/U/C/U/C, every view 13/13 exact, draft proposals and acceptance identical:

| View | Head | tok/s | hit B (ms) | hit D (ms) |
| --- | --- | --- | --- | --- |
| 0 | split (bundle 8) | 58.601 | 13.144 | 1.593 |
| 1 | full on rank 1 | 57.737 | 13.371 | 1.599 |
| 2 | split | 58.536 | 13.171 | 1.605 |
| 3 | full on rank 1 | 57.756 | 13.378 | 1.602 |
| 4 | split | 58.621 | 13.142 | 1.598 |

`s185_decision` (`v5/evidence/device-view4-production-B-p185/bracket-summary.json`): **u = 0.222 ms**
(D-corrected 0.206; control B spread 0.029 ms, so u is resolved), **decoupled B - A = 0.851 ms**
(per view 0.846 / 0.856; p10 0.793 / 0.807), control drift 0.145%, sigma (rank-0 suffix-head service on
the split views) = 0.403 ms per cycle (suffix head 0.311, import 0.025, export 0.026). Hit cycles
14.77 -> 15.01 ms, miss 25.76 -> 26.03 ms with the full head on rank 1. Both V3 kill thresholds
(u <= 0.39, B - A >= 0.60) are met by measurement; packet177's literal revisit condition (rank-0 slack
>= 1 ms) is not (0.852 ms/hit), which is why this measurement, not the price, is the authority.
**Decision: build V3** (packet186: full head on rank 1, layers 24-25 on rank 0 for the verified token).
