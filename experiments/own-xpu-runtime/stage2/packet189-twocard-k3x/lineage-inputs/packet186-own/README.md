# Packet186: two-card V3 (verified-boundary rebalance) on the bundle-8 line

CPU preparation only. No device run, queued job, speed result or submission is claimed. The four lane-B rows are a
PROPOSAL (`experiments/own-xpu-runtime/ops/lane-queue/proposed-p186-two-card-B.txt`); the window driver decides.

Packet185 ran on lane B on 2026-10-22 (14:00-14:22 UTC, unit lanequeue-B33) and decided **V3 GO**: u = 0.222 ms,
decoupled B - A = 0.851 ms, sigma = 0.403 ms/cycle, every view 13/13 exact, drift 0.145 %. This packet builds V3.

## What V3 is

* The full 248,320-row target head is on rank 1 (`head: production`): no merge, no rank-0 suffix service.
* Rank 0 also holds the GDN layers 24-25 (`rank0_layers: 0-25`). After every rank-0 accept that a rank-1 half
  will consume, the controller sends one **boundary** command (op 15). Rank 0 runs layers 24-25 for that
  accepted, verified token inside rank 1's draft window, then exports the layer-25 residual stream.
* Rank 1 starts at layer 26 (`boundary: rank0`). The draft is unchanged (rank 1, MTP).
* Bundled with packet153's static snapshot descriptors (`snapshot_host: static`; see "Static snapshot").

## Priced gain with the measured numbers

Script: `analysis/price_v3_measured.py`, output `analysis/price-v3-measured.json`. It is a per-interval replay over
packet185's two un-split views. Those views have V3's head placement: 2 x 12 prompts x 99 intervals of real D, A,
B, R, C, offset and G (`analysis/p185-intervals.json.gz`, extracted read-only by `analysis/extract_p185_intervals.py`
with each receipt's sha256). Rates use the class-balanced median metric. The identity replay reproduces every
packet185 view rate to 1e-7.

Per interval:

* ready = max(D, R + C' + accept + 2*c0 + x)
* race = max(B - 2*s1, A - x - dS + offset)
* T = ready + race + G

Here x is the measured rank-0 `handoff_export`, about 0.07 ms/cycle. It moves from the speculative half into the
boundary. C' = C - x. accept is 0.0003 ms/cycle (measured). dS is the static-snapshot saving.

| Case | V3 tok/s | vs best control 58.621 | Record bar 59.974 |
|---|---:|---:|---|
| central (s1 0.48, c0 0.55) | 60.167 | **+2.64 %** | yes |
| anchored: s1 = c0 = 0.483 measured (rank-0 layer_body 11.59 ms / 24), +0.05 ms per command | 60.239 | +2.76 % | yes |
| anchored + static (dS 0.335, packet153's measured merge-wait growth) | **60.353** | **+2.95 %** | yes |
| coordinator corner c0 = 0.73 | 59.891 | +2.17 % | no |
| coordinator corner s1 = 0.39 | 59.618 | +1.70 % | no |
| both corners (s1 0.39, c0 0.73) | 59.348 | +1.24 % | no |
| consistent low (s1 = c0 = 0.39, same kernels on identical cards) | 59.822 | +2.05 % | no |
| one layer only (k = 1) | 58.975 | +0.60 % | no |

* **Arithmetic (central).** Hits go from 14.770 to 14.075 ms. That is D 1.60 + max(B'' 12.415, A' 12.455) + G 0.02.
  A' is about 12.455 and B'' is B_u 13.375 - 2 x 0.48 = 12.415, so rank 0's A binds by 0.04 ms.
* **Misses** go from 25.71 to 26.15 ms. The boundary (about 1.1 + 0.07 ms) is serialized after the corrected half,
  because R + C' + boundary is longer than D.
* **Pooled** saving is (0.695 x 932 - 0.44 x 256) / 1188 = 0.45 ms per interval, which gives +2.64 %.
* **Break-evens for +2 %:** c0 at most 0.768 ms per layer; s1 at least 0.415 ms; at most 0.436 ms of extra boundary
  latency per command. For +0.5 %, s1 must be at least 0.29.
* **Corners.** s1 below 0.415 or c0 above 0.768 drops V3 under the chain rule. The bracket measures s1 directly:
  `s186_decision.measured.s1_rank1_saving_per_moved_layer_ms = (B_u - B_v3) / 2`.

## Accept ordering

* Rank 0's command order per cycle is: [rollback, corrected half on a miss] -> **accept** -> **boundary** -> wait
  for the draft -> speculative half.
* The accept is host-only: packet185 measured 0.3 µs per cycle. It never waits on GPU work, so it does not
  serialize ahead of the two layers.
* The costly "capture" (`snapshot`, 0.65 ms per cycle; about 0.25 ms with static) is the speculative image capture
  at the start of the *next* half. It runs after the boundary and after the draft wait, as it does today.
* So no second order is needed as a view. (The earlier 0.743 ms "accept" figure was packet150's snapshot+accept+rollback
  scope, not the accept.)

## How the moved layers' state is kept correct

Layers 24-25 on rank 0 never see a guessed token:

1. **Not banked and not in the speculative image.** `banks()` skips them. `Engine::v3_private` holds every buffer
   written only by the moved layers, and the vendored `v5/native-src/strict_snapshot.hpp` excludes it from the image.
   * `Engine::v3_check_plan` proves at load that the moved layers form a closed island. They read only their own
     buffers plus `streams/active/error`. They contain no QSA/position/lookup operator. No other rank-0 launch reads
     or writes their buffers.
   * At production shape the image capture is unchanged: 19,025,640 B and 984 extents in both layouts
     (`full-shape.json` `image_census`).
2. **Only the boundary command issues them**, and it refuses unless:
   * the previous rank-0 command was the ACCEPT of a completed half for exactly this (position, token);
   * no candidate is pending.

   A speculative half is accepted only on a hit. A miss is rolled back, corrected with the verified token, then
   accepted.
3. **Decode positions are cross-checked against rank 1.** For every decode position (fixture >= 2), the token must
   also equal rank 1's published verification for that position. Redo uses the same check.
4. **No rank-0 half starts while an accepted position still waits for its boundary.** So the layer-23 stream the
   boundary consumes is the accepted one.
5. **Resets clear the pending flag.** Request reset and the bracket boundary clear it. Reset zeroes every state byte,
   as for all allocations.

Rollback therefore has nothing of theirs to restore, and needs nothing.

CPU proof (`v5/evidence/v3-state.json`, gate `v5/v3_state_gate.py`):

* **Engine part** (`v5/native/v3_state.cpp`; GNU and Intel host compilers x snapshot production/static): a 64-step
  speculative sequence equals a direct, never-speculative sequence on the canonical bytes of every rank-0 allocation.
  * The sequence mixes hits, misses at every live cancellation cut (rollback + redo), abandoned redos and no-guess
    steps.
  * The moved layer's state is compared separately at every step.
  * Each run has 65 cases and 68 guard refusals that leave the owner unchanged. The guards cover: boundary with a
    pending guess, wrong token, wrong position, second boundary, boundary without accept, token differing from rank
    1's verification, and a half before the pending boundary.
  * **Negative control:** advancing the moved layer on a guessed token and then rolling back is detected (2 of 2).
* **Two-rank pipeline part** (the packet186 gnu-host engine with the real native controllers `run`/`run_v3`, the
  real bracket switch op 13 and the vendored packet56 transport):
  * one fresh production-layout reference;
  * one-load miniature brackets U/V3/U/V3/U and V3/U/V3/U/V3, a static-off V3 view and a draft-suppression load;
  * 54 requests in total: MTP draft, scripted hit/miss/no-guess mix, no draft, and EOS stop. Together they contain
    169 hits, 377 misses and 397 no-guess steps.
  * Every request equals the reference in tokens, all 96 per-step per-layer stream fixtures (merged over ranks),
    draft proposals, draft final state and all 192 per-layer target state buffers (owner rank by layout).
  * V3 views issued one boundary per rank-0 accept. Rank 1 never ran the moved layer in a V3 view.
* **Controller mock** (`v5/native/v3_controller_test.cpp`, in `controller.json`): `run_v3` against `run` with three
  recurrences, enforcing the guards. 72 cases per compiler: all-hit, all-miss, mixed, no-guess, native draft, overlap
  on/off and EOS. Tokens, proposals and all three states match.

To run the miniature engine at all, the p149 probe exchange (selection `probe: xchg`, never bundle 8) is now built
only at production geometry. packet184 found the same limitation. Production allocation order is unchanged, as the
bundle-8 capture identity below shows.

## What changed (entry/new TUs only; every kernel object byte-identical)

* **78 packet136/103 parent objects** are relinked unchanged; each sha256 pin is verified before every link
  (`immutable-binaries.json`).
* **Recompiled TUs:** entry-main, p49d_submit and s1_submit. s1_submit's source is unchanged and recompiled as
  packet183 did. 8 compiler runs, 0 warning lines.
* **Device binary** `v5/build/device/own-rt-iq3` sha256 `693cc194bb577cd20f95e63f06bf6e463074944e2d1193f8c3ed1a8a4528d739`;
  gnu-host `9035149a8cce1f98be9bdcb687bab5dc9a684b969292da2750d86736466ef5c9`.

| File | Change (diff lines vs packet185) |
|---|---|
| `native-base/.../p49d_submit.cpp` | keys `rank0_layers` {0-23, 0-25} and `boundary` {none, rank0}; 14 or 16 keys (6) |
| `v5/native-src/rank.hpp` | split with the rank-0 layout, banks skip, half skip mask, no rank-0 export under V3, op 15, accept hook, `run_v3` selection, p149 probe only at full geometry (40) |
| `v5/native-src/strict_snapshot.hpp` (vendored) | exclude `v3_private` from the image (6) |
| `v5/native-src/main.cpp` | `refresh_v3()` at Engine construction (1) |
| `v5/native/engine_bracket.hpp` | V3 flags, island proof, skip mask; bracket switch of `boundary`/`snapshot_host` for V3-layout loads only, `dense_scales` closed to expanded (63) |
| `v5/native/v3_boundary.hpp` (new, 79) / `v5/native/v3_controller.hpp` (new, 49) | boundary command and guards / `native38::run_v3` |
| `v5/native/full_shape_entry.cpp` | V3 layouts, image/bank census, V3 refusals (35; fixture only) |

The full patch against packet185's rewritten sources is `v5/v3-native.patch`.

## Production-shape gate (`v5/evidence/full-shape.json`)

* **Loads:** production (bundle 8), and the V3 dual layout started from U and from V3. Each load has five bracket
  resets on both ranks, so every selection, both start orders and both ranks are covered.
* **Captures:**
  * Every view's capture equals the fresh startup. U and V3 captures are identical.
  * **The production captures equal packet185's bundle-8 captures** (`bundle8_capture_identity_with_packet185`).
* **Commands:**
  * Rank 0 in the dual layout issues the 533 production commands plus 40 layer-24/25 commands. Their kernels, shapes
    and bindings equal rank 1's own layer-24/25 sites.
  * Rank 1 issues the same commands except the target-head sites (packet185's un-split head).
* **Half-skip census:** rank 0 skips 60 sites in every half; rank 1 skips 60 in V3 views and 0 in U views.
* **Refusals:** 16 (production) or 19 (dual) native refusals per run. In-load `rank0_layers`, head and
  `dense_scales: metadata` switches all refuse.
* **Real-parser startup** (`--startup109`) of all three selections on both ranks reproduces the census.

## Memory and admission

Full-shape census, actual allocation calls (`v5/evidence/admission.json`):

| | Rank 0 | Rank 1 |
|---|---|---|
| Bundle 8 device bytes / arena headroom | 28,144,229,620 / 4,068,025,100 | 31,425,985,242 / 786,269,478 |
| V3 dual layout delta | **+2,100,819,444** = layers 24-25 +2,258,141,716 (130 allocations) - split-head suffix/p105 157,322,272 | **+155,750,384** (46,080 head rows; packet185 un-split) |
| V3 device bytes / arena headroom | 30,245,049,064 / **1,967,205,656** | 31,581,735,626 / **630,519,094** |
| Ledger (plan) arena headroom / free with MTP | 1,338,041,752 / 3,321,584,340 (>= 1.5 GB) | 1,373,494 / 2,030,187,830 (identical to packet185 un-split, which ran) |

* **Host admission** at START: bundle-8 rows need 105,411,248,128 B MemAvailable. The V3 rows (smoke, bracket) need
  107,667,817,956 B, which adds the device delta's host shadow.
* Both figures exclude the queue's extra 1 GiB.
* Packet185's windows started at 120.6-120.8 GB available.

## Static snapshot (packet153) is bundled, from its receipts

* **Packet153's receipts:**
  * one-load bracket 2026-10-19: 13/13 exact in all five views, identical proposals, drift 0.057 %;
  * `capture_snapshot` host scope -0.404 ms/cycle;
  * merge/handoff waits +0.33 ms/cycle, so +0.35 % net on the split-head line.
* **Why it adds more here.** Under V3, rank 0's speculative half A binds the emission. The host saving therefore
  reaches the critical path until rank 1's B'' binds:
  * +0.17 % central (A binds by 0.04 ms);
  * up to +0.9 % if s1 is 0.55.
* **Reopens nothing.** Packet153 closed static only "alone" ("could join a future composite bundle"), and the static
  tables are prepared at load in every selection.
* It is switched in-load with `boundary`, so the bracket measures V3 + static against U, and the controls against
  bundle 8.

## Rows (proposal only; lane B; each depends on the previous one)

| Row | Kind | Load | Views | Expected | Plan / watchdog | Writes |
|---|---|---|---|---:|---|---:|
| 0 | smoke | v3 | V3: incident64 + 12 x 64, exact, first-request data proof | ~300 s (first row, cold) | 300-420 / 3600 s | 240 MB |
| 1 | view | production | bundle-8 control: incident64 + 12 x 128 | ~217 s | 200-330 / 3600 s | 240 MB |
| 2 | bracket | u | U/V3/U/V3/U, one load, incident64 + 12 x 128 each | ~486 s | 480-900 / 3600 s | 1.2 GB |
| 3 | view | production | bundle-8 control; decides `s186_decision` | ~217 s | 200-330 / 3600 s | 240 MB |

* **Timing sources:** today's recorded rows. Packet185 views took 311.5 s for the first load, then 211-215 s each;
  packet183's smoke took 299.2 s and its bracket 479.7 s.
* **Total** is about 300 + 217 + 486 + 217 + 3 x 61 s drain spacing = 1,403 s (23.4 min).

**Decision `s186_decision`** (row 3's `bracket-summary.json`, or `python3 -B v5/s186_decision.py <rows 0..3>`):

* **Screen winner:** the slower V3 view is at least 1.005 x every control view (2 split-head + 3 U). Every view must
  also be exact, with identical draft proposals and acceptance, and drift must be at most 3 % for both the split
  controls and the U views.
* **Chain rule:** the same conditions, AND the slower V3 view is at least 1.02 x the faster split-head control, AND at
  least 1.02 x 58.798109 = 59.974 tok/s.
* **Tested on real data:** packet185's views (a V3 equal to bundle 8 is NOT a winner), packet183's real bracket
  (NOT a winner), and scaled real numbers for every branch (`v5/test_s186_decision.py`).

## What the next record bundle needs (only if the chain rule is met)

A fresh-process record chain on cards 0+1, like packets 136/143. Copy packet136 (bundle 8, record
`cmve4dtir007wrf01k57sdf23`, 58.798108759182306) into a new packet and add exactly this composition:

1. **Engine.** packet186's three entry objects over the same 78 pinned parent objects, rebuilt in the bundle packet
   from packet186's sources (`v5/native-src`, `v5/native`, `native-base/.../p49d_submit.cpp`). The rebuilt
   device ELF must hash-match `693cc194...`, or be re-qualified.
2. **Selection.** `v5/lineage/v3/selection.json` (16 keys: bundle 8 plus `head: production`, `rank0_layers: 0-25`,
   `boundary: rank0`, `snapshot_host: static`). Use `dispatch-speed6.json` unchanged and the dual memory plan
   `v5/lineage/v3/memory-plan.json`.
3. **Chain placement and admission.** `draft_rank 1`, `target_split 0`, layer boundary 24, target layers [26, 24].
   Host admission is 107,667,817,956 B plus the queue's 1 GiB. Card memory follows the table above.
4. **Chain harness.** packet136's chain harness, with a new chain registration that carries the V3 identity
   (selection sha256, binary sha256, `rank0_layers`/`boundary` in the benchmark identity).
5. **Run order.** The exact composed lane-A smoke first, then the fresh chain on `build/device-cards01-<packet>`. The
   output must be fresh (reuse refuses).
6. **Metric and submission.** The WS128 suite with the class-balanced metric (99000 / sum(T)), exact against
   `iq3-p49-split32-v1`, BF16 KV and the owner-authorized 128-token scope. Submission is prepared from the finished
   chain only, against `record-threshold.json` (supersedes `cmve4dtir007wrf01k57sdf23`).
7. **Not needed.** The slim layout (rank 1 dropping its idle layers 24-25, freeing about 2.26 GB) is a memory-only
   variant. It is not required: the dual layout fits and is the measured one.

## Device-busy compile rule

The coordinator's rule was: no compiler while `window-p185-driver.service` is active or activating.

* Code was written and sources were read while the unit was active. Session checks read active at 14:23 and 14:34
  UTC, then inactive at 14:46:51 and 14:52:54 UTC.
* The first compile started at 14:52:54 UTC, after the build's own poll also read `inactive`.
* The 90-minute deadline was never needed. Every build re-polls; see `v5/evidence/compile-poll.json`.

## Gates and receipts (`v5/evidence/`)

| Gate | Receipt |
|---|---|
| build (8 compiles, 0 warnings, 78 pins) | `build.json`, `compile-poll.json`, `engine-commands.json` |
| production-shape (every selection, both ranks, both start orders) | `full-shape.json` + `shape-*.tar.gz` |
| V3 state correctness (engine + two-rank miniature brackets) | `v3-state.json`, `v3-state-engine-*.txt.gz` |
| controller (probe mock + run_v3 vs run) | `controller.json` |
| admission (three lineages, attributed delta) | `admission.json` |
| analysis (variants, boundary scopes, s186 rule on real data) | `analysis.json` |
| safety / exec limits / loader | `safety.json`, `exec-limits.json`, `loader.json` |
| seal | `../cpu-seal.json` |
| package_rows -> check_queue_rows (entry, launch limits, worker, report, private-copy queue plan, pin guard) | `package-rows.json`, `check-queue-rows.json`, `entry-gate.json`, `launch-limits.json`, `worker-gate.json`, `report-gate.json`, `queue-plan.json`, `plan-B.log`, `pin-guard.json` |
| final checks, READY written last | `final-checks.json`, `final-pin-guard.json`, `../READY-FOR-DEVICE.json` |

See `DO-NOT-REPEAT.md` and `RETENTION.md`.
