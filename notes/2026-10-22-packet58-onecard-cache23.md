# Packet58-onecard-cache23: the 23 GB expert-cache capacity screen on the one-card record line (CPU only)

October 22/23, 2026. CPU preparation for the one-card IQ3 own runtime (Qwen3.8 Flash-Next
UD-IQ3_XXS, the quantized compressed version, one B70). No GPU, /dev/dri, service, setting, PAUSE/STOP/queue
file, sudo or secret was touched; nothing was queued, launched or committed. packet182 and packet182c
trees are untouched. Packet: `experiments/own-xpu-runtime/stage2/packet58-onecard-cache23/`. Proposal
(not queued): `experiments/own-xpu-runtime/ops/lane-queue/proposed-p58-cache23-one-card-A.txt`.

## 1. Why

One-card synthesis 1 (archived in `packet182c-chain/analysis/`) found the record line (35.926720 tok/s,
packet182c, `cmvjejvoi03qcrf0138emu5a6`) bound by 48 serial layer bodies with no draft, and expert-cache
capacity as the only lever priced above the +0.5 % screen bar (+0.58-0.84 % for +1.5 GB). The
coordinator ruled: build the 23 GB capacity screen with the packet182c selection unchanged plus
`cache_cap max23` = 23,049,601,024 B, switched at the drained view boundary like `18GB|max`, with the
device plan re-partitioned from the 182c lifetime receipts; chain only at >= +2 % (not expected).

## 2. What was built

- **Engine rebuilt**: `083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a` (parent
  `1b41fb4d…`). Only the entry TU (device + host), the preparation probe, the wait tests and the K1
  wrapper were compiled (76 s, 0 warnings, one compiler at a time); 79 parent objects/binaries relinked
  unchanged from pinned originals. The packet is self-contained: the 23 native files and the 79 tracked
  frozen headers no longer include packet176 by absolute path (packet182 inherited those includes; a
  compile with two paths per header fails on `#pragma once`).
- **Native delta** (`native-cache23-delta.patch`, 5 files): one 23,049,601,024-byte arena per load,
  `--cache-cap 18GB|max|max23` (max = 21,552,729,600 usable = packet182c's policy byte-for-byte, proven
  by a CPU replay of the vendored cache policy under both allocations), device bound 29,963,128,848 ->
  29,828,911,360, bracket capacity dimension with kernel foreground I/O fixed in every view, probe
  expecting kernel I/O in all five views and writing its census peak.
- **Device plan** (`derive_plan.py` -> `memory-plan.json`, a STOP gate): driver overhead measured
  604,827,916 B (max over 81 loaded DRM samples of 5 chain windows minus the census) -> allowance
  671,088,640; bound 29,828,911,360; transient 784,567,808 = 402,653,184 (1.5x operator-scratch) +
  113,479,168 (>= 4x the other workspace rows) + 268,435,456 (transfer, unchanged), 2.654x the measured
  live transient peak 295,612,132; category margin 240 B. allocate() peak after growth 29,338,775,796
  (490,135,564 under the bound; the CPU probe measured the same number at production size); DRM
  projection 29,943,603,712 (556,396,288 under the unchanged 30.5 GB guard). Host admission
  98,990,252,032 -> 100,487,123,456 (+1,496,871,424 full backing).
- **Decision `s58c23_decision`** on every outcome: screen winner iff both max23 >= 1.005 x every warm
  max, 60/60 exact, drift <= 3 %; chain iff also >= 1.02 x every max view and >= 36.6452544; kills:
  inexact view, DRM > 30.5 GB (existing guard), max23 fills/token not >= 8 % below max (capacity closed
  at 23 GB), warm max < 35.2 or drift > 3 % (host disturbed, no auto-rerun); fills/token, MB/token and
  the miss-read regression reported for both arms.

## 3. Gates (all CPU, all passed)

Plan derivation (no STOP); build (0 warnings); `max` byte-identity (583 checks); production-shape
startup at production size for max and max23 under Landlock (5 view resets, 60 requests, 130 sensors,
60/60 kernel-I/O stores/loads, probe census peak <= bound); real native parser + 8 negative cases;
loader/exec-limits; real launch path to intercepted exec (K1a/K1b/WSCREEN; WSCREEN admission with the
endpoint-free MemAvailable substituted, recorded); analyzer on REAL packet182 bracket (60 exact; the
packet182 views refused as this candidate; packet176 fields identical to the committed summary) and on
the REAL packet182c WS128 record stream (12 exact, 35.92672010504166 reproduced; 15.449 fills/token,
30.63 MB/token, 0.0322 ms/MB miss-read slope); Python tests differential vs packet182 (113 vs 106, 0 new
failures, 4 stale failures fixed); drain fix; seal (1,178 inputs); proposal; imports; temporary plan;
shared `rehearse_entry --report` (smoke + bracket kinds); pin guard; `final_checks --ready`: READY
written last, pin census 1,404 pins / 52 manifests / 0 cross-packet mutable, private-copy
`lanequeue.py plan --lane A` passed.

## 4. Rows

| Row | Duration |
| --- | --- |
| `packet58cache23-one-card-v5-A`: K1a, K1b, then one load A0/B0/A1/B1/A2 = max/max23/max/max23/max, 12 x 128 tokens per view | ~13-14 min (packet182's identical shape: 793 s); plan 700-1200 s; watchdog 3600 s; host admission 100,487,123,456 B (the windows pin ~85 GB) |

## 5. Deviations and not claimed

- The brief named the proposal `proposed-p58cache23-one-card-A.txt`; the shared `ops/lane-queue/pin_guard.py`
  accepts a packet's own proposal only as `proposed-p<packet number>-*` (number `58` here), so the first
  READY was withdrawn (kept as `evidence/READY-WITHDRAWN-20261023T002855Z.json`) and the proposal is
  `proposed-p58-cache23-one-card-A.txt`. The guard is a tracked shared tool and was not edited.
- The shared rehearsal's synthetic boundary cannot express `max23`; `summarize_bracket` re-checks the
  allocation and started-empty switch, and `verify_lookup_views` (first on the device path) enforces the
  per-view capacity identity (proven by refusing packet182's real B views).
- intel-host `own-rt-iq3` not built (no gate reads it). Chain tooling not carried (a win feeds a later
  composite). No device result, speed or record; the +0.5-1.0 % is a price.
- Disk: packet 46 MB tracked + 81 MB ignored build; root free 29.65 GB at the end (floor 27 GB kept).

## Device result (2026-10-23, card 0 window 00:57-01:10 UTC, unit lanequeue-A34): screen win +1.72 %

**Measured 2026-10-23 (card 0, lane A, lanequeue-A34, 00:57-01:10 UTC): SCREEN WIN.** K1a/K1b passed; one load max/max23/max/max23/max = 35.892/**36.546**/35.929/**36.569**/35.925 tok/s (slower max23 view +1.72 % over the fastest warm max view; drift 0.01 %); every view 12/12 exact; fills per token 15.449 → 13.457 (−12.9 %), fill MB per token 30.63 → 26.68; miss-read regression 0.0322 → 0.0329 ms/MB (unchanged), unfilled intercept 25.16 → 25.04 ms; no kill rule fired; DRM guard untouched. Chain bar (36.645, +2 %) not met by 0.2 %; lanes idle, so the record chain is derived (`packet58-onecard-cache23-chain`). Evidence `screen/evidence/card0-58c23-v5-a/resident/WSCREEN/summary.json`.

Reading: +1.5 GB of admitted expert cache removed 12.9 % of the fills and the per-token miss bytes, worth 0.47 ms per token (27.75 → 27.27 ms), above the +0.6-0.8 % price (the fill-traffic and wait-contention terms scale with the bytes, as the synthesis assumed, and the measured elasticity was higher). Headroom: DRM stayed under the 30.5 GB guard with the re-partitioned plan. A second step (max24/max25) would need another re-partition and the 2.06 GB physical margin; price it from this view pair before building.

Window receipts: `lineage/window-20261023/`; endpoints restored as `*-20261023-restore16`; PAUSE-B untouched, PAUSE-A re-armed.
