# Packet188: two-card k3 composite on the V3 record line (CPU-prepared, device pending)

**Line:** Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, two B70s. **Record:** 60.659520 tok/s (packet187, LocalMaxxing
`cmvjvabyv040jrf01dricuz8s`): bundle 8 + packet153 static snapshot + packet186 V3.

**Status:** CPU-only preparation, READY for a lane-B device window (`READY-FOR-DEVICE.json`, written last). Nothing was
queued, armed, launched or committed. No GPU, `/dev/dri`, device binary run, systemd unit change, PAUSE/STOP or queue
file was touched. The only systemd calls were read-only `systemctl --user list-units 'window-*'` polls before the compile
batches (all empty; `v5/evidence/compile-poll.json`). The proposal is `ops/lane-queue/proposed-p188-two-card-B.txt`
(PROPOSAL ONLY; mirror `proposals/`).

## Ruling (coordinator, 2026-10-22, quoted)

> "Ruling: the V3 ruling on packet177 row 2 extends to a third boundary layer, on the same basis (the per-layer costs are
> measured: rank-0 boundary 0.513 ms/layer, rank-1 saving 0.463 ms/layer), and the ledger row gets that reasoning quoted.
> Build the composite you recommended."

## What packet188 is

Base: packet187's V3 line. The packet186 binary lineage is kept: the 78 parent objects are relinked unchanged and their
pins verified; only the entry TUs and one new header changed.

The lever has three parts. Each is a selection key, so a bracket can switch them inside one load:

| Part | Key (k3+trims value) | What it does |
|---|---|---|
| **k=3** | storage `rank0_layers=0-26`, `boundary=rank0-k3` | GDN layer 26 joins the verified-token boundary command (op 15) on rank 0, so the boundary runs layers 24-26. Rank 1 starts at QSA layer 27. |
| **Kernel I/O** | `kernel_io=kernel` (default `copy`) | Packet176's lever, ported to two cards (both ranks). Every synchronous upload or readback of ≤ 64 KiB becomes a `p188::KioCopy` compute kernel through pinned "kernel-io" staging. The ordered MTP/queue copies go through `io_copy`. Two readback pairs are folded into one kernel and one wait each: rank 1 reads error + next_token together, and the boundary reads error + export together. |
| **Rank-0 prepare off A** | `rank0_prepare=async` (default `sync`), rank 0 only | See the list below. |

What `rank0_prepare=async` changes in rank 0's speculative half:

* rank 0 stages its token and every lookup row in pinned memory, and loads them with ONE ordered copy and no host wait;
* the device position and token_history are captured by an ordered copy issued before the half's first kernel;
* they are checked and read only after the half's final drain (`finish_staged`);
* `image.begin` takes the known position.

This removes these synchronous round trips from A:

* the position readback;
* the token_history readback;
* the token upload;
* the lookup uploads.

The host-side lookup row assembly (memcpy) stays.

Selections (`v5/lineage/<name>/selection.json`):

| Name | sha256 | Storage | boundary / kernel_io / rank0_prepare |
|---|---|---|---|
| `v3` (the record selection, the fresh control) | `923639a9…` (= packet187) | 0-25 | rank0 / - / - |
| `v3k` (the bracket's V3 views) | `f847635e…` | 0-26 | rank0 / copy / sync (layer 26 idle on rank 0, run by rank 1) |
| **`k3trims`** (the candidate) | `b63d9a28…` | 0-26 | rank0-k3 / kernel / async |
| `k3`, `k3kio`, `k3prep` (attribution) | `a8b37a4f…`, `d2b5d894…`, `308c6a52…` | 0-26 | rank0-k3 with copy/sync, kernel/sync, copy/async |

Inside one load the native bracket switches only `boundary`, `kernel_io` and `rank0_prepare`. It refuses
`rank0_layers`, `head` and `dense_scales: metadata`, and in the 0-25 storage it refuses the trim keys
(`full-shape.json`: 21 native refusals per run).

## Priced gain (lever synthesis 2, `analysis/`)

The prices replay packet187's 1,188 WS128 intervals through the record metric: per prompt `99000 / ΣT`, then the median of
class medians. Interval model: `T = max(D, R+C+Bd) + max(B, A+offset) + G`. The replay reproduces 60.65951991975228 exactly.

Measured inputs:

* rank-1 saving s1 = **0.463 ms** per moved layer (packet186);
* rank-0 boundary c0 = **0.513 ms/layer** (packet186's Bd 1.026 ms for two layers);
* D = 1.604 ms; Bd = 1.027 ms;
* hit B = 12.418 ms, A + offset = 12.062 ms.

Arithmetic, step by step:

* **k3 alone.**
  * Changes: B − 0.463 ms; Bd 1.027 → ~1.540 ms, still inside D on 99.4% of hits.
  * Hits save 0.345 ms (14.050 → 13.705): rank 0's A now binds 88% of hits, by 0.107 ms on average.
  * Misses cost +0.067 ms (25.750 → 25.817), because the boundary is serial after C.
  * Result: **+1.49%** (grid +1.40 to +1.55% over s1 0.43-0.49 and c0 0.483-0.55), so 60.6595 × 1.0149 = **61.56 tok/s**.
* **+ kernel I/O.**
  * Round trips per interval: D 2, B 3, Bd 1, C 2, A 1, each 22.7-25.5 µs measured (packet165) against an assumed 5 µs
    kernel store.
  * Result: **+1.88%**, i.e. 61.80 tok/s. Kernel I/O on V3 alone is +0.57%; under k3 it adds +0.39 points because
    rank 0's round trips now count.
* **+ prepare off A** (0.096 ms, the measured `prepare_ms` per speculative half): **+2.39%**, so 60.6595 × 1.0239 =
  **62.11 tok/s**.
* **Chain bar.** 1.02 × 60.659520 = 61.873 tok/s.
  * k3 alone needs **≥ 0.105 ms** off rank 0's A to reach it: k3 + 0.105 ms gives +1.998%; k3 + 0.15 ms gives +2.13%.
  * The trims are what decide the chain.

The measured record-line envelope the trims are judged against comes from packet186's V3 views and the p150 scopes
(`analysis.json`):

* rank-0 half envelope 0.436 ms = half_total 12.039 − layer_body 11.603;
* of which snapshot 0.292, token_prep 0.076, token_history 0.022, and 0.046 unattributed;
* p76 retirement 0.093 per half and `prepare_ms` 0.096 per half are reported separately;
* boundary envelope 0.079, of which export 0.051.

## Binary and changed TUs

| Item | Value |
|---|---|
| Device engine `v5/build/device/own-rt-iq3` | **`d776524532f110528dea5f67f13771feb71945cf35f44247f77ef9118539eb45`** |
| CPU twin `v5/build/gnu-host/own-rt-iq3` | `e6078d069511aa0b69e34e1b1e44f4ebd426aa1df3af2a72c5761c586b3e3302` |
| Build | 8 compiler runs, 0 warning lines, 78 inherited parent objects pinned (`v5/evidence/build.json`) |

Rebuilt TUs: entry-main, `p49d_submit` (the selection keys) and `s1_submit` (unchanged source, recompiled).

`v5/k3-native.patch` diffs every native change against packet186 after the identity rewrite. It totals **+298 / −67
lines in 11 files**:

| File | Lines | Change |
|---|---|---|
| `native/engine_bracket.hpp` | +145 −30 | `refresh_v3` (stored vs executed sets), `v3_check_plan` over the stored sites, bracket domains, kio staging/kernels, `io_copy`, `stage_half_inputs`, `finish_staged`, folded readbacks |
| `native/kernel_io.hpp` (new) | +55 | `p188::KioCopy` (≤ 8 byte ranges, one work-item per byte), slot layout |
| `native-src/main.cpp` | +25 −5 | kio branches in upload/readback, `prepare_token(…, staged)`, `--pipeline-mini5` (G Q G G Q) |
| `native-src/rank.hpp` | +23 −9 | `split(…, rank0_extra)`, staged half (no sync position/history), folded rank-1 readback |
| `native/v3_boundary.hpp` | +16 −6 | `rank0_extended` returns 0/2/3; folded error + export |
| `native/full_shape_entry.cpp` | +11 −4 | stored-site census, k3/trim flags, negatives |
| `native/v3_state.cpp` | +7 −1 | trim counters, stored sites |
| `p49d_submit.cpp` (native-base) | +6 −4 | `rank0_layers 0-26`, `boundary rank0-k3`, `kernel_io`, `rank0_prepare` |
| `native-src/strict_snapshot.hpp` | +6 −3 | `begin(shared, known_position)` |
| `native-src/mtp.hpp` | +3 −5 | publication and half-input copies via `io_copy` |
| `native/bracket_boundary.hpp` | +1 | zero the kio staging at request reset |

No new device kernels apart from the byte copy. Layer 26 runs the same GDN kernels as on rank 1: the full-shape gate
checks that rank 0's k3 launches = V3 launches + exactly rank 1's layer-26 sites.

## How layer 26's state stays correct

Layer 26 is GDN: it has recurrent state, conv history and per-layer buffers, and no QSA, KV, position or lookup operator.
It gets the same treatment as packet186 gave layers 24-25: it joins the island.

1. **Rank 0 runs it only for the verified token.** It runs inside the boundary command, after rank 0's accept, and is
   guarded by accept, position and token, and by rank 1's verification. It never runs inside a speculative half.
   `v3_check_plan` checks the island over the whole **stored** set (all buffers written by layers 24-26). It also checks
   that executed boundary sites never read an idle stored layer's buffers, and that the last boundary site is
   `blk.(v3_end-1).ffn.combine` writing the streams.
2. **It is never banked and never in the speculative image** (`v3_private`). A rollback cannot touch it, and nothing
   speculative ever advanced it.
   * Full shape: the image capture is 19,025,640 B / 984 extents in every layout and start order, identical to
     packet186's V3.
   * Stored sites on rank 0: V3 60, k3 90. Rank 1 skips 60/90 half sites in the V3/k3 views.
3. **Views switch only at request reset.** That is a total reset of both ranks, with `cached_tokens` 0 and allocation
   ids preserved. In V3 views of the k3 storage, layer 26 on rank 0 is idle and rank 1 runs it, so no state crosses a
   view boundary.
4. **CPU proof** (`v5/evidence/k3-state.json`, `v5/k3_state_gate.py`):
   * **Engine part.** One rank-0 miniature engine in the k3 storage, built with GNU and Intel.
     * A 64-step direct sequence is compared against a mixed sequence on the canonical bytes of every rank-0 allocation,
       including the layer-24-26 recurrent state and the exported slot. The mixed sequence has hits, misses at **every
       cancellation cut** (rollback with redo, corrected half, accept, boundary), abandoned redos and no-guess steps.
     * 14 runs (7 selections × 2 compilers), each with 65 cases, 68 guard refusals and 2 detecting negative controls.
       The negative control advances the moved layers on a guessed token, and the bytes survive the rollback.
     * Canonical transcripts are byte-identical across k3 / k3kio / k3prep / k3trims (`d451302d954f…`) and across both
       compilers. The trims move no byte.
     * Counters prove that each trim ran: k3kio 66,757 kernel transfers; k3trims 65,694 kernel transfers + 382 ordered
       kernel copies + 191 staged halves.
   * **Two-rank pipeline part.** Five-layer miniature G Q G G Q (mini GDN 2-3 = layers 24-26, mini 4 = QSA 27), run with
     the real controllers and the real switch op 13.
     * 70 requests: a fresh production-layout reference; one-load brackets in BOTH start orders; a k3 / k3kio / k3prep /
       k3trims attribution load; a production-snapshot load; and draft suppression.
     * Every request equals the reference: tokens, all 120 per-step per-layer stream fixtures, draft proposals, draft
       final state, and every target state buffer on its owner rank.
     * Mix: 221 hits, 493 misses, 505 no-guess steps.

## Memory and host admission

From the production-shape census (`full-shape.json`, `admission.json`):

| Rank | V3 (0-25, record) | k3 storage (0-26) | Arena headroom (limit 32,212,254,720 B) | Physical free (34,242,297,856 B) |
|---|---:|---:|---:|---:|
| 0 | 30,245,049,064 | **31,374,119,922 (+1,129,070,858)** | 838,134,798 | 2,868,177,934 |
| 1 | 31,581,735,626 | 31,581,735,626 (+0) | 630,519,094 | 2,660,562,230 |

* **Rank-0 delta.** It is exactly the 65 allocations of `blk.26.*` (weights and buffers); nothing is removed.
* **Planned memory.** The plan derives the k3 ledger from packet186's V3 ledger plus that delta. Rank 0 plans
  32,003,283,826 B, leaving a plan headroom of 208,970,894 B and 2,192,513,482 B free with MTP (≥ 1.5 GB). Rank 1 is
  identical to packet186/187.
* **Pinned kernel-io staging.** 86,016 B on rank 0 and 73,728 B on rank 1, in host memory.
* **Host MemAvailable at START.**
  * V3 row: 107,667,817,956 B (as packet186/187).
  * k3 rows: **108,797,048,558 B**. This adds the layer-26 host shadow and the staging.
  * Both are plus the queue's 1 GiB.

## Device rows (proposal, lane B, PAUSE-A held)

| Row | Job | What | Expected (s) | Watchdog | Writes |
|---|---|---|---|---|---|
| 0 | `packet188-row0-smoke-k3trims-B` | k3+trims smoke, 12 × 64 + incident64, exact, first-request data proof | [270, 420], ~285 | 3600 | 240 MB |
| 1 | `packet188-row1-control-v3-B` | fresh-load V3 (packet187 record selection), 12 × 128 + incident64 | [200, 330], ~213 | 3600 | 240 MB |
| 2 | `packet188-row2-bracket-v3k-k3trims-B` | ONE load: V3 / k3+trims / V3 / k3+trims / V3, each 12 × 128 + incident64 | [460, 900], ~480 | 3600 | 1.2 GB |

* **Expected times.** They come from today's recorded lane-B rows (packet186, lanequeue-B34: smoke 278.3 s, views 209.6 /
  215.7 s, bracket 475.7 s). The total is about 1,100 s (18.3 min) including two 61 s drain spacings.
* **Order.** Each row depends on the previous one.
* **Plan.** The private-copy `lanequeue.py plan --lane B` passed all three rows (`v5/evidence/plan-B.log`). Root had
  29.98 GB free against required 25.24 / 25.24 / 26.20 GB.
* **Rehearsal.** The entry rehearsal passed (`v5/evidence/rehearse.json`).

**Decision `s188_decision`** (in the row-2 summary, or `python3 -B v5/s188_decision.py <rows 0..2>`):

* **Screen winner:**
  * every view is 13/13 exact (smoke 12/12 × 64 + incident);
  * draft proposals and per-prompt acceptance are identical across the six 128-token views;
  * V3 drift is ≤ 3% (the fresh V3 load and the three in-load V3 views);
  * AND the slower k3+trims view is **≥ 1.005 × every V3 view**.
* **Chain rule:** the same conditions AND **≥ 1.02 × every V3 view** AND **≥ 61.873 tok/s**.
* **Kill rules** (recorded in the summary, never a speed claim):
  * the k3 hit saving (V3 − k3+trims mean hit interval) is < 0.25 ms;
  * Bd > D on > 5% of k3+trims hits;
  * the trims remove < 0.105 ms of rank 0's A. A carries only the trims, because layers 0-23 are identical in both views.
* **Envelope attribution.** The summary also reports, per variant:
  * the envelope as half_total − layer_body = snapshot + token_history + token_prep + unattributed;
  * p76 retirement and `prepare_ms` per half;
  * the boundary envelope and export.

  So the trim is measured, not assumed.
* **Rule tested on REAL data** (`v5/test_s188_decision.py`, 10 tests; real inputs read where packet186/187 retained them,
  93 files pinned in `v5/evidence/analysis-real-inputs.json`):
  * **Null k3** (packet186's real V3 views as both arms): NOT A WINNER. The k3 and trims kill rules fire, and the draft
    window rule does not.
  * **Real V3 over real U** (+4.66%): winner but NOT a chain, since 60.533 < 61.873.
  * **Scalings** of the real views: 1.022 → chain; 1.015 → winner only; 1.004 → no.
  * **Refusals:** drift, inexact, changed proposals, and a missing smoke each refuse.
  * **Packet187's 12 real WS128 streams** reproduce hit 14.050 / miss 25.750 / Bd 1.027 ms, and `RECORD` equals its
    stored metric.

## Gates (receipts under `v5/evidence/`)

| Gate | Result | Receipt |
|---|---|---|
| Build (entry TUs, window poll) | PASS: 8 compiler runs, 0 warnings, 78 parent objects | `build.json`, `compile-poll.json` |
| Production-shape startup | PASS: 6 selections × 2 ranks (12 startups); 10 dual-rank loads in every start order; V3 captures and census identical to packet186; k3 delta = layer 26; 21 native refusals per run | `full-shape.json`, `shape-*.tar.gz` |
| State correctness (k3, layer 26 under every cancellation cut, trims) | PASS: 14 engine runs + 70 pipeline requests | `k3-state.json`, `k3-state-engine-*.{log,txt.gz}` |
| Controller mock | PASS: probe 12 cases + run_v3 72 cases, GNU/Intel × 2 | `controller.json` |
| Admission | PASS | `admission.json` |
| Analysis (schema, s188 on real data, envelope baseline) | PASS: 8 + 3 + 10 tests | `analysis.json`, `analysis-real-inputs.json`, `analysis-test_*.log` |
| Safety / exec limits / loader | PASS | `safety.json`, `exec-limits.json`, `loader.json` |
| Seal | PASS | `v5/cpu-seal.json` |
| package_rows | PASS: 3 rows | `package-rows.json` |
| Entry / launch limits / worker / report | PASS: 6 entry rows + 12 negatives; 12 limit rows; 13 + 13 + 65 requests + abort path; 6 report rows | `entry-gate.json`, `launch-limits.json`, `worker-gate.json`, `report-gate.json` |
| Private-copy plan `--lane B` + rehearsal | PASS | `queue-plan.json`, `plan-B.log`, `rehearse.json` |
| Pin guard (live `check_job`, 3 rows) | PASS: 1,107 pins, 31 manifests, **0 cross-packet mutable** | `pin-guard.json`, `final-pin-guard.json` |
| final_checks / `--ready` | PASS; READY written last | `final-checks.json`, `../READY-FOR-DEVICE.json` |

## Record bundle on a chain-rule win (derive like packet187)

A chain-rule win is a screen, not a record. The record needs a fresh-process chain: packet187's harness, which is
packet136's eleven-window lane-A chain on cards 0+1 with packet187's guarded `launch_chain.sh`. Exactly these things
change from packet187:

1. **Selection.** `k3trims` (`b63d9a28…`) replaces packet187's V3 selection (`923639a9…`). The changed keys are
   `rank0_layers 0-26`, `boundary rank0-k3`, `kernel_io kernel` and `rank0_prepare async`; everything else (head, static
   snapshot, dense_scales, draft) is unchanged.
2. **Engine.** The packet188 device engine `d7765245…` (with its gnu-host twin) replaces packet186's `693cc194…`, which
   packet187 reused without relinking.
3. **Memory plan.** The k3 ledger (`v5/lineage/k3trims/memory-plan.json`, sha `97a76116…`) replaces it. Rank 0 rises to
   31,374,119,922 B.
4. **Launcher host floor.** It becomes 108,797,048,558 B + 1 GiB (packet187 used 107,667,817,956 B + 1 GiB).
5. **KD projection.** KD's layer-streaming reference must project `kernel_io` and `rank0_prepare` to production, together
   with `rank0_layers`, `boundary` and `snapshot_host` (packet187's boundary). The trims move no bytes (the k3-state
   canonical identity).
6. **Bars.** The chain WS128 must beat **60.659520** (packet187) and pass every exactness gate. The chain rule already
   requires ≥ 61.873 in the screen.

Unchanged: the v5 transport size (266,304 B; packet188 adds no shared-slot bytes, and the kio staging is a separate pinned
allocation), the oracle binding, the provenance layout, the launcher refusals and the submission step (coordinator's).

## Notes and limits

* **Kernel I/O covers both ranks, but its pricing is partly assumed.** The 5 µs kernel store is assumed, while the
  22.7-25.5 µs round trips it replaces are measured.
* **The bracket's in-load V3 views are not the record storage.** They use the k3 storage with layer 26 idle on rank 0,
  +1.13 GB. Row 1 (a fresh 0-25 load of the record selection) is the check that they behave like V3. The drift bound
  covers all four V3 views.
* **The device bracket does not split k3 from the trims.** It measures k3+trims together, as instructed. The split comes
  from the A difference (trims only) and the envelope scopes. If needed, the `k3` / `k3kio` / `k3prep` selections allow
  a one-load attribution bracket later; the CPU pipeline already runs that bracket.
* **Real analysis inputs are read in place.** They are packet186's device rows, packet187's WS128 chain run and the
  packet49 oracle. They are never copied. Their path → sha256 map is `v5/evidence/analysis-real-inputs.json`.
  * That map lives outside the pin guard's walk, following packet187's bracket-gate layout. No device row reads these
    files.
  * `analysis.json` seals the map's digest, and `final_checks.py` re-hashes every file.
