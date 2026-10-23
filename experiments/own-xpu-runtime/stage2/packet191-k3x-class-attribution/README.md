# Packet191: per-class kernel cost on both ranks of the k3x record line, measured in-engine (CPU-prepared, device pending)

**Line:** Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, two B70s. **Record:** 62.345282 tok/s (packet190 k3x chain,
LocalMaxxing `cmvk51wfn001gng01fpbfy89q`). **This packet is a MEASUREMENT:** priced gain 0 tok/s; no row of it is a speed
result, a screen winner or a record row. It decides whether any kernel-class brief can honestly be priced at +2 %.

**Status:** device-measured 2026-10-23 (lane B, unit lanequeue-B37, 00:32-00:47 UTC): every view exact; sites-off reproduces the record line (62.17-62.20); **the class table is withheld** (kill rule `class_sum_vs_body_pct`: the host `layer_body` reference overlaps and is not comparable to device kernel sums; see `DO-NOT-REPEAT.md` and the note). Prepared CPU-only, READY for a lane-B device window (`READY-FOR-DEVICE.json`, written last). Nothing was
queued, armed, launched or committed. No GPU, `/dev/dri`, device binary run, systemd unit change, PAUSE/STOP or queue file
was touched. The only systemd calls were read-only `systemctl --user list-units 'window-*' 'lanequeue-*' 'packet19*'`
polls before the compile batches (no active or activating unit; the five `lanequeue-*` units listed are `failed`, not
active; `v5/evidence/compile-poll.json`). The proposal is `ops/lane-queue/proposed-p191-two-card-B.txt` (PROPOSAL ONLY;
mirror `proposals/`).

## Ruling (coordinator, lever synthesis 4, 2026-10-22, quoted)

> "Lever synthesis 4: on the k3x record line both ranks are 99.3% busy per hit and every kernel class sits at its ledger
> floor; the only family that can still reach +2% is per-layer kernel cost on both ranks (+1.32% per 0.01 ms per GDN
> layer; +2% needs 15.1 µs per GDN layer, +0.5% needs 3.8 µs). Build packet191 as a measurement: the record k3x selection
> unchanged plus packet77-style per-class site instrumentation on both ranks as an in-load view key, so each class's
> per-rank cost and its excess over the copy floor and over packet110 are measured on the line that holds the record."

## What is measured and why

The line has no in-engine per-class table under its current selection: packet77's attribution is bundle-6-era (24/24
split, old kernels), packet110's is a synthetic complete layer at the 10-18 selection, the record chain's `sites.jsonl`
are empty (p150 host scopes only), and packet128b's all-events attribution failed its overhead gate (0.728) and was
withheld. Every revisit condition of the big classes (experts, HC, route) asks for in-engine causal evidence. Packet191
produces it on the record line itself, with the instrumentation as an in-load view so the same loaded weights serve the
control and the instrumented views alternately.

**The view key `sites=off|on`** (`v5/sites-native.patch`, **+69 / −17 lines in 8 files** against packet189 after the
identity rewrite; the packet189 binary lineage is kept: the 78 parent objects are relinked unchanged with their pins
verified, only the entry TUs changed):

| File | Change |
|---|---|
| `v5/native/p191_sites.hpp` (new, 31 lines) | the recorder, replacing packet65's expert-only recorder under the same `p65timing` namespace: `sample(fixture)` = fixtures 9-16, 57-64, 105-112; `Site` carries label, fixture, position, speculative, corrected, a per-half id and the phase (`half`, `boundary`, `draft`); `record(event, override)` tags draft events `draft` |
| `v5/native-src/main.cpp` | the include; `finish()` also retains events in `pending` while the recorder is active (`profile_events||draft_timing||attribution.active()`) and records them with their site label (draft events with the override); `attribution_row` writes one `packet191.site.v1` row per event (rank, half, phase, fixture, position, speculative, corrected, label, event, start_ns, end_ns) and counts rows |
| `v5/native-src/rank.hpp` | `attribution.begin(fixture, position, speculative, "half", corrected)`: the half phase and the corrected tag (one line) |
| `v5/native/engine_bracket.hpp` | `sites` is a k3-storage key: domain `{off, on}` (absent = off, so the 19-key record selection still loads), switchable in-load with the packet188/189 keys, refused in the 0-25 storage; `refresh_v3` sets `sites_on`, `attribution.enabled = sites_on || timing==attribution`, clears the event map, and requires the profiling queue the rank already runs |
| `v5/native/v3_boundary.hpp` | `attribution.begin(..., "boundary")` before the layer 24-26 issue loop (one line) |
| `native-base/.../p49d_submit.cpp` | the key resolves to `production`; k3-storage selections have 19 keys or 20 with `sites` |
| `v5/native/full_shape_entry.cpp`, `v5/native/v3_state.cpp` | CPU fixtures: `v3-load.json` records the flag; the per-view flag check; the `sites: unknown` refusal (23 per run); the row-format proof on the real production plan; the state result records the flag and the row count |

**Where the hook sits.** `Engine::issue_site` already sets `attribution.current.label` to the site label before issuing
the site's prepared commands; `finish()` is called per issued command with its event. Under `on`, inside a sampled
half/boundary/draft, the event id is mapped to the current site (a host `std::map`, ≤ ~600 entries per half) and kept in
`pending`; at the half's own final `drain()` (after `wait(tail)`, the GPU idle; the same place `timing=class` reads
them) each event's device start/end timestamps are read from the profiling queue and one JSON row is written to
`sites.jsonl` (re-pointed per request by `request_reset`). **No kernel is added, no device memory is read, no barrier
or copy is introduced**; the timestamps are read on the host after completion. Both ranks already run profiling-enabled
queues on the record line (rank 0 always, rank 1 for the MTP draft; the rank-1 draft already has its events timed this way
every cycle). Under `off` — and in the 19-key record selection — `attribution.enabled` is false, `active()` is false, no
event is recorded, nothing is written, and the submit path is the record path plus one bool test.

**Why three windows of eight fixtures.** packet128b recorded every event and measured 0.728 of the control; the kill rule
is 0.93. The drain-time reads cost ≈ 2 µs per event (~600 per half) on the sampled halves only: 24 of 127 decode
positions, ≈ 2 % of the view at most. The windows span the record metric's 99-interval window so the context-dependent
QSA attention is seen early (positions ~77-84), mid and late; the report keeps the windows apart.

Selections (`v5/lineage/<name>/selection.json`):

| Name | sha256 | Keys | Role |
|---|---|---|---|
| `k3x` (the record selection) | `c5443bbf…` (= packet189/190) | 19 | loads as `sites=off`; the CPU identity reference; not loaded by a packet191 row |
| **`k3x-off`** | `eaba9647…` | 20 (`sites off`) | the record k3x choices + the explicit key: the control views; **row 1 loads it** |
| **`k3x-on`** | `3fee7f49…` | 20 (`sites on`) | the instrumented views; the smoke |
| `v3`, `v3k`, `k3trims` | packet189's | 16 / 19 / 19 | CPU gates only (startup identity with packet188/189) |

Storage, census and memory plan are packet188/189's, unchanged: the production-shape startup reproduces packet188's
captures and census for every k3-storage load including the two sites loads in both start orders (`full-shape.json`:
`k3_capture_identity_with_packet188`, `sites_memory_delta_bytes_per_rank = [0, 0]`).

## Binary and changed TUs

| Item | Value |
|---|---|
| Device engine `v5/build/device/own-rt-iq3` | **`cd199292efe810b8ad0d767193f5788605ef3b93a06925e9061819f66c6ddea9`** |
| CPU twin `v5/build/gnu-host/own-rt-iq3` | `8c552f31fe68d35c0ec9a0a72c87b26c7479e777de02eeef38b959073afb9701` |
| Build | 8 compiler runs, 0 warning lines, 78 inherited parent objects pinned (`v5/evidence/build.json`) |

Rebuilt TUs: entry-main (main.cpp, rank.hpp, engine_bracket.hpp, v3_boundary.hpp, p191_sites.hpp), `p49d_submit` (the key)
and `s1_submit` (unchanged source, recompiled). No new device kernel.

## Device rows (proposal, lane B, PAUSE-A held)

| Row | Job | What | Expected (s) | Watchdog | Writes |
|---|---|---|---|---|---|
| 0 | `packet191-row0-smoke-k3x-on-B` | k3x-on smoke, 12 × 64 + incident64, exact, first-request data proof, site rows on both ranks of every request | [270, 420], ~313 | 3600 | 240 MB |
| 1 | `packet191-row1-bracket-sites-B` | ONE load of `k3x-off`: off / on / off / on / off, each 12 × 128 + incident64 | [460, 900], ~480 | 3600 | 1.2 GB |

* **Expected times** come from packet189's recorded lane-B rows (lanequeue-B36, 2026-10-22): the storage and request mix
  are identical; the on views add the sampled drain-time reads (≤ 2 % of a sampled half). Total ≈ 854 s including one
  61 s drain spacing: under 15 min.
* **Order.** Row 1 depends on row 0.
* **Plan.** The private-copy `lanequeue.py plan --lane B` passed both rows (`v5/evidence/plan-B.log`), the entry rehearsal
  passed (`v5/evidence/rehearse.json`).

## The report `s191_report` (in the row-1 summary, or `python3 -B v5/s191_report.py <rows 0..1>`)

Per rank, per phase (rank 0: speculative half A = layers 0-23, corrected half C, boundary = layers 24-26; rank 1: half B =
layers 27-47 + head, draft) and per class (experts gate/up/down/act; dense = gdn.qkv/gdn.z/attention/qsa projections;
QSA attention = qsa.attention/select/pool/prepare; recurrence = gdn.recurrence/conv/gated; HC gates/low; norms;
route+small = route/router/shexpdown/ffn.combine/gdn.a; head; draft; PLE), with the per-site rows underneath:

* **ms per half** (median over sampled halves of the per-half class sum), **µs per GDN layer** and **per QSA layer**
  (medians over (half, layer) of the per-layer class sum; every site's events summed per call first — packet77's rule);
* **excess over the copy floor**: measured − (read + write bytes) / 537 GB/s on the packet72/77 byte formulas over the
  pinned header census (packet110's convention; a reference gap on useful bytes, never a realizable saving), with the
  floor coverage of the class;
* **excess over packet110**: measured − packet110's synthetic complete-layer call time at context 128 (GDN rows for GDN
  layers, QSA rows for QSA layers; `roofline.json` pinned);
* **lever eligibility**: a class is "lever-eligible by excess" only when its excess over the copy floor is ≥ 15.1 µs per GDN
  layer on **both** rank 0's speculative half and rank 1's half (≥ 3.8 µs for a screen), with the gain the ruling's
  arithmetic would give if all of it were removed (+1.32 % per 10 µs); every flagged class is listed with the mechanism
  families the DO-NOT-REPEAT corpus closes for it (`s191_report.CLOSURES`, from `analysis/dnr-class-grep.txt`) and the open
  mechanisms registered for it (`OPEN`: none for any class), so the outcome line states explicitly whether any open
  mechanism remains;
* **reported, never a condition**: the `off` views against packet189's k3x views (62.242 / 62.225, hash-pinned, read in
  place: timing equivalence of the record path within 0.5 %) and the packet190 record; the instrumentation's cost on
  A / B / Bd / D (interval means off vs on); the three windows separately; the dropped halves (cancelled, incomplete).

**Kill rules** (recorded; a measurement, never a speed claim):

1. any view not 13/13 exact, or draft proposals / per-prompt acceptance differ across the five views → STOP;
2. control drift: max/min of the three `off` views − 1 > 0.5 % → STOP (instrumentation leaking into the controls);
3. overhead: mean(on) / mean(off) < 0.93 → the class table is **withheld** (packet128: "a failed overhead gate withholds
   rankings; do not correct event times by a throughput ratio");
4. completeness: the per-half sum of every recorded class deviates from the half body (rank 0: the half's `layer_body`
   host scope; rank 1: its `half_completion_ms`) by more than 10 % (median over sampled halves) → STOP (missing events;
   an absent stream is never a zero); likewise an `off` view that wrote site rows, an `on` request without rows on either
   rank, or an unclassified label.

**Tested on REAL prior device data** (`v5/test_s191_report.py`, 11 tests; the analysis gate pins every file it reads in
`v5/evidence/analysis-real-inputs.json`, read in place, never copied): packet189 row 1's two k3x views (the off path:
1,188 intervals each, hit 13.5 / miss 25.6 ms, `layer_body` 11.6 ms, no site rows) and packet190's record chain WS128
(932 hits / 256 misses, the record metric); the engine's own CPU row format (full-shape gate: `packet191.site.v1` rows
written by the real `attribution_row` on the real plan, both ranks — every label classifies, every half layer complete,
boundary and draft phases tagged); and synthetic instrumented views built on packet189's real receipts and timing
streams with packet110's call times, through the real report path: the table reproduces packet110 (excess over packet110
≈ 0; experts ≈ 111 µs, dense ≈ 155 µs per GDN layer; experts 74 µs over the floor), the completeness rule passes against
the real `layer_body` / `half_completion` streams (4-5 %), the classes whose packet110 excess is ≥ 15.1 µs are flagged
(dense, experts, hc, norms, recurrence, route_small) with their closures and **no open mechanism**; an overhead of 0.92
withholds the table; drift, inexact, changed proposals, leaked rows, missing rank-1 rows, a removed class and an unknown
label each stop.

## Memory and host admission

From the production-shape census (`full-shape.json`, `admission.json`), identical to packet188/189:

| Rank | k3 storage (0-26), `sites=off` | `sites=on` delta | Arena headroom (limit 32,212,254,720 B) | Physical free (34,242,297,856 B) |
|---|---:|---:|---:|---:|
| 0 | **31,374,119,922** | **0** | 838,134,798 | 2,868,177,934 |
| 1 | 31,581,735,626 | 0 | 630,519,094 | 2,660,562,230 |

* `sites=on` allocates nothing on either device: the recorder is a host `std::map` of event ids (≤ ~600 entries per sampled
  half, cleared at the half drain) and the rows are buffered file writes (~60 KB per sampled half). The plan is
  packet188's derivation (`97a76116…`): rank 0 32,003,283,826 B, headroom 208,970,894 B, 2,192,513,482 B free with MTP.
* **Host MemAvailable at START:** **108,797,048,558 B** (= packet189's k3x rows: the recorder's host footprint is in the
  noise of the 1 GiB the queue adds), plus the queue's 1 GiB.

## Gates (receipts under `v5/evidence/`)

| Gate | Result | Receipt |
|---|---|---|
| Build (entry TUs, unit poll) | PASS: 8 compiler runs, 0 warnings, 78 parent objects | `build.json`, `compile-poll.json` |
| Production-shape startup | PASS: 6 selections × 2 ranks (12 startups); 12 dual-rank loads incl. the two sites loads in both start orders; captures and census identical to packet188; `sites` delta 0 B; 23 native refusals per run; the row-format proof on both ranks | `full-shape.json`, `shape-*.tar.gz` |
| k3x-off / k3x-on byte identity | PASS: 4 engine runs (GNU k3x / k3x-off / k3x-on, Intel k3x-on): canonical transcripts all `d451302d…` (= packet188/189's), 65 cases, 68 refusals, 2 negatives each; 44 pipeline requests in both start orders equal the reference | `k3-state.json`, `k3-state-engine-*.{log,txt.gz}` |
| Controller mock | PASS | `controller.json` |
| Admission | PASS: host 108,797,048,558 B | `admission.json` |
| Analysis (schema, s191 on real packet189/190 data, engine format, synthetic instrumented views) | PASS: 8 + 3 + 11 tests | `analysis.json`, `analysis-real-inputs.json`, `analysis-test_*.log` |
| Safety / exec limits / loader | PASS | `safety.json`, `exec-limits.json`, `loader.json` |
| Seal | PASS | `v5/cpu-seal.json` |
| package_rows | PASS: 2 rows | `package-rows.json` |
| Entry / launch limits / worker / report | PASS | `entry-gate.json`, `launch-limits.json`, `worker-gate.json`, `report-gate.json` |
| Private-copy plan `--lane B` + rehearsal | PASS | `queue-plan.json`, `plan-B.log`, `rehearse.json` |
| Pin guard (live `check_job`, 2 rows) | PASS: 0 cross-packet mutable | `pin-guard.json`, `final-pin-guard.json` |
| final_checks / `--ready` | PASS; READY written last | `final-checks.json`, `../READY-FOR-DEVICE.json` |

## Notes and limits

* **Expected outcome, honestly** (lever synthesis 4): the synthetic table already puts every large excess in classes with
  measured closures; the likely result is a confirmation that no class has ≥ 15.1 µs per GDN layer of excess reachable by
  an open mechanism, which closes the two-card kernel lane at 62.35 until a new mechanism exists. The result that would
  matter is an in-engine excess in a class the synthetic fixture under-represents (QSA attention at longer contexts, HC
  gates, route), ≥ 0.27 ms per half on both ranks.
* **The honest risk is the overhead gate.** If the sampled drain-time reads cost more than 7 % of a view, the table is
  withheld (never ratio-corrected) and the next packet records fewer fixtures; the off views remain valid controls.
* **The off views are the record path, proven on CPU** (canonical transcripts of every rank-0 allocation and the exported
  slot after every step, identical for the 19-key `k3x`, `k3x-off` and `k3x-on`); their timing equivalence to packet189's
  k3x views is reported at device time.
* **DO-NOT-REPEAT corpus.** All 223 DO-NOT-REPEAT.md files under stage2 were grepped (`analysis/dnr-class-grep.txt`)
  before the rows were finalised: no row closes an in-engine per-class attribution view on the k3x line; the rows that
  bind the analyzer (packet128's withheld rankings, packet77's call-sum rule, packet140's "packet110 is not a floor",
  packet157's "an absent stream is never a zero") are built into `s191_report`.
