# Packet189: k3x, packet188's k3 + trims with the boundary export back on the copy engine (CPU-prepared, device pending)

**Line:** Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, two B70s. **Record:** 60.659520 tok/s (packet187, LocalMaxxing
`cmvjvabyv040jrf01dricuz8s`): bundle 8 + packet153 static snapshot + packet186 V3. **Chain bar:** 61.87271031814733 tok/s.

**Status:** prepared CPU-only, READY for a lane-B device window (`READY-FOR-DEVICE.json`, written last). Nothing was
queued, armed, launched or committed. No GPU, `/dev/dri`, device binary run, systemd unit change, PAUSE/STOP or queue
file was touched. The only systemd calls were read-only `systemctl --user list-units 'window-*' 'lanequeue-*'` polls before
the compile batches (no active or activating unit; `v5/evidence/compile-poll.json`). The proposal is
`ops/lane-queue/proposed-p189-two-card-B.txt` (PROPOSAL ONLY; mirror `proposals/`).

## Ruling (coordinator, 2026-10-22, quoted)

> "Packet188's loss is attributed to its own export path, not to the third boundary layer: boundary_body rose 0.459 ms
> (the GDN layer-26 kernels, equal to the 0.463 ms saved on rank 1) while handoff_export rose 0.540 ms for the same 20,480
> bytes because v3_boundary.hpp routed the export through kio_read_many (KioCopy, one work-item per byte into pinned host
> memory, 28.9 ns/byte) instead of the copy-engine readback (2.6 ns/byte). The k=3 ruling stands; packet189 re-measures k3 +
> trims with the export on the copy engine (k3x), and reads D from the draft's observed wall time."

The k=3 ruling it refers to (coordinator, 2026-10-22, packet188): "the V3 ruling on packet177 row 2 extends to a third
boundary layer, on the same basis (the per-layer costs are measured: rank-0 boundary 0.513 ms/layer, rank-1 saving 0.463
ms/layer)".

## What changed from packet188

Base: packet188 (`copy_packet189.py`, receipt `lineage/packet189-copy.json`: 2,182 files, 266 identity rewrites, 1,467
hard-linked history files, one history file rewritten for its identity literal). The packet186 binary lineage is kept: the
78 parent objects are relinked unchanged with their pins verified; only the entry TUs changed.

**1. The execution key `boundary_export=copy|kernel`** (`v5/k3x-native.patch`, **+38 / −15 lines in 6 files**, diffed
against packet188 after the identity rewrite):

| File | Change |
|---|---|
| `native/v3_boundary.hpp` | the export path selection (below) and two run counters |
| `native/engine_bracket.hpp` | `boundary_export` is a k3-storage key: domain `{copy, kernel}`, switchable in-load with `boundary`/`kernel_io`/`rank0_prepare`, refused in the 0-25 storage; `refresh_v3` sets `export_copy` (default `copy` when the key is absent) and requires the key to be explicit in every k3-storage selection |
| `native-src/main.cpp` | `readback(c, src, n, bool copy_engine=false)`: `copy_engine=true` bypasses the kernel-io path |
| `p49d_submit.cpp` (native-base) | the key resolves to `production`; k3-storage selections have 19 keys (18-key ones are refused) |
| `native/full_shape_entry.cpp` | the flag is checked per view; one more native refusal (`boundary_export: unknown`; 22 per run); `v3-load.json` records the flag |
| `native/v3_state.cpp` | the result records `boundary_export` and the two run counters |

The exact export code path (`v3_boundary.hpp`, `v3_boundary_step`), packet188 → packet189:

```diff
- std::vector<uint8_t> folded; // packet188 kernel_io=kernel: error + exported stream in ONE kernel readback
- if(e.kio_active&&captured_count==0)p150::measure("handoff_export",r.position,false,[&]{folded=e.kio_read_many(0,{{e.buffers[0].at("error").id,4},{e.buffers[0].at("streams").id,bytes}});});
+ std::vector<uint8_t> folded; // packet188 kernel_io=kernel + boundary_export=kernel: error + exported stream in ONE kernel readback
+ const bool export_kernel=e.kio_active&&!e.export_copy; // packet188's kio path (folded; kio_readback when fixtures are retained)
+ if(export_kernel&&captured_count==0)p150::measure("handoff_export",r.position,false,[&]{folded=e.kio_read_many(0,{{e.buffers[0].at("error").id,4},{e.buffers[0].at("streams").id,bytes}});});
  {int error=0;if(!folded.empty())std::memcpy(&error,folded.data(),4);else error=e.integer(0,"error");
   require(!error,"sticky rank error in the V3 boundary (never rolled back)");}
  ...
  if(!folded.empty())std::memcpy(shared,folded.data()+4,bytes); // folded = error (4 B) followed by the exported stream (bytes)
- else p150::measure("handoff_export",r.position,false,[&]{auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes);std::memcpy(shared,raw.data(),bytes);});
+ else p150::measure("handoff_export",r.position,false,[&]{auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes,/*copy_engine=*/!export_kernel);std::memcpy(shared,raw.data(),bytes);});
+ ++(export_kernel?e.export_kernel_runs:e.export_copy_runs);
```

* `copy` (k3x, v3k, v3): the 20,480-byte layer-end stream is read back by `ownrt::CopyEngine` into the pinned slab and
  memcpy'd to the shared slot, exactly packet186/187's path, even when `kernel_io=kernel`. Without `copy_engine=true`
  packet188's `readback` would have routed the ≤ 64 KiB request through `kio_readback` (KioCopy). The 4-byte error check
  stays a kernel read when `kernel_io=kernel` (`e.integer` → `readback` → kio); the bytes are the same.
* `kernel` (k3trims): packet188's behaviour, byte for byte: error + stream folded into one KioCopy readback.
* Every other small kio transfer (rank 1's folded error + next_token, the draft merge copy, the staged token and lookup
  loads, the publication) stays a kernel. The `p188::KioCopy` kernel and its namespace are unchanged (packet188's).

Selections (`v5/lineage/<name>/selection.json`; the k3-storage ones carry 19 keys):

| Name | sha256 | Storage | boundary / kernel_io / rank0_prepare / boundary_export |
|---|---|---|---|
| `v3` (the record selection; not loaded by a packet189 row) | `923639a9…` (= packet187) | 0-25 | rank0 / - / - / - |
| `v3k` (the bracket's V3 views) | `92f5fcf7…` | 0-26 | rank0 / copy / sync / copy |
| **`k3x`** (the candidate) | `c5443bbf…` | 0-26 | rank0-k3 / kernel / async / **copy** |
| `k3trims` (packet188's candidate, CPU gates only) | `9a028b43…` | 0-26 | rank0-k3 / kernel / async / kernel |

Storage, census and memory plan are packet188's, unchanged: the production-shape startup reproduces packet188's captures
and census for the V3 selection and for every k3-storage load (`full-shape.json`: `v3_capture_identity_with_packet188`,
`k3_capture_identity_with_packet188`).

**2. The decision rule reads D from the draft's observed wall.** `s189_decision.intervals_v3` replaces the op-9 command
duration with `draft_rows.draft_wall_ms` (publication observed) at the same position and keeps the op-9 value as `D_op9`
(reported only). Packet188's D of 0.43 ms under the trims was a model artifact: with `rank0_prepare=async` the rank-1
controller stamps op 9 complete after its nonblocking host issue; the draft really completed 1.537 ms later (V3 1.586).

**3. Two rows, no fresh V3 row.** Packet188 row 1 (the record selection loaded fresh on this lane, 60.50488520482965,
2026-10-22) is the fresh reference: `s189_decision.FRESH_V3` pins its `bracket-summary.json` by sha256
(`4ff1ec14…`) and reads it in place.

## Binary and changed TUs

| Item | Value |
|---|---|
| Device engine `v5/build/device/own-rt-iq3` | **`87eec6453a2a9a9bfe30ed19466c6a70644d9cd168f734be87d2f0a17b776af4`** |
| CPU twin `v5/build/gnu-host/own-rt-iq3` | `a50588a9e89adacb14cefcc53dd271cbd8054b81fe076dbca81d7b779d99f6c6` |
| Build | 8 compiler runs, 0 warning lines, 78 inherited parent objects pinned (`v5/evidence/build.json`) |

Rebuilt TUs: entry-main, `p49d_submit` (the new key) and `s1_submit` (unchanged source, recompiled). No new device kernel.

## Priced gain (lever synthesis 3, `analysis/`)

The prices replay packet187's 1,188 WS128 intervals through the record metric: per prompt `99000 / ΣT`, then the median of
class medians, with `T = max(D, R+C+Bd) + max(B, A+offset) + G`. `analysis/replay_k3x.py` reproduces 60.65951991975228 to
1e-9 and reproduces both measured k3trims views exactly through the draft-wall identity (`ready = max(draft_wall + 0.006,
Bd)`: 60.5644 / 60.3824). The analysis gate and `test_s189_decision.py` re-run it.

Measured inputs (packet188 row 2, hit means, ms; V3 → k3trims):

| | V3 | k3trims | Δ |
|---|---:|---:|---:|
| `boundary_body` (layers 24-25 → 24-26) | 0.9505 | 1.4096 | **+0.459** (the GDN layer-26 kernels) |
| `handoff_export` (the same 20,480 B) | 0.0528 | 0.5925 | **+0.540** (2.58 → 28.9 ns/byte) |
| `boundary_total` (Bd) | 1.032 | 2.005 | +0.974 |
| draft wall (D) | 1.586 | 1.537 | −0.049 |
| B (rank-1 half) | 12.432 | 11.893 | −0.539 |
| A (rank-0 speculative half) | 12.112 | 11.970 | −0.142 |
| C (corrected half, misses) | 11.811 | 11.712 | −0.099 |
| hit elapsed | 14.060 | 13.989 | −0.071 |
| miss elapsed | 25.778 | 26.154 | +0.376 |

Arithmetic for k3x (the k3trims deltas with the export repaired to V3's 0.053 ms):

* **Hits.** ready = max(D 1.537, Bd 1.466) ≈ 1.55 (the boundary is 1.466 = 2.005 − 0.540, below the draft on every hit:
  mean margin 0.072 ms); race = max(B 11.893, A + offset 11.970) = 11.970; + G 0.013 → **13.52 ms** (−0.54 ms, −3.8%).
* **Misses.** R 0.290 + C 11.712 + Bd 1.466 + B 12.123 + G 0.015 → **25.61 ms** (−0.17 ms); packet188's misses lost 0.376
  ms only because the +0.974 ms boundary is serial on the miss path.
* **Replay.** 60.6595 → **62.32 tok/s, +2.74%** on the record intervals; +2.65…+2.73% on packet188's three in-load V3
  views (62.14-62.19); +2.56…+2.76% rebuilt directly from the two measured k3trims views with only the export repaired.
* **Sensitivities.** draft not faster at all +2.50; export 0.083 ms +2.70; B saving only 0.50/0.45 +2.65; A trim only 0.105
  +2.56; **everything pessimistic together +2.27% (62.04 tok/s, still above the 61.873 bar)**; everything optimistic +3.01.
* **Noise.** A single candidate view carries about ±0.3% (prompt-level jitter in 4 of 12 prompts); V3 drift was 0.058%
  across four views; the fresh chain sat +0.2% above in-load views in packet187/188.

## Device rows (proposal, lane B, PAUSE-A held)

| Row | Job | What | Expected (s) | Watchdog | Writes |
|---|---|---|---|---|---|
| 0 | `packet189-row0-smoke-k3x-B` | k3x smoke, 12 × 64 + incident64, exact, first-request data proof | [270, 420], ~313 | 3600 | 240 MB |
| 1 | `packet189-row1-bracket-v3k-k3x-B` | ONE load: V3 / k3x / V3 / k3x / V3, each 12 × 128 + incident64 | [460, 900], ~480 | 3600 | 1.2 GB |

* **Expected times** come from packet188's recorded lane-B rows (lanequeue-B35): smoke 313 s, bracket 480.0 s. The total
  is about 854 s (14.2 min) including one 61 s drain spacing: under 15 min.
* **Order.** Row 1 depends on row 0.
* **Plan.** The private-copy `lanequeue.py plan --lane B` passed both rows (`v5/evidence/plan-B.log`), the entry rehearsal
  passed (`v5/evidence/rehearse.json`).

**Decision `s189_decision`** (in the row-1 summary, or `python3 -B v5/s189_decision.py <rows 0..1>`):

* **D := `draft_rows.draft_wall_ms`** (publication observed), never the op-9 duration.
* **Screen winner:** every view 13/13 exact (smoke 12/12 × 64 + incident); draft proposals and per-prompt acceptance
  identical across the five 128-token views; V3 drift ≤ 3% over the three in-load V3 views PLUS packet188's fresh V3 row 1;
  AND the slower k3x view is **≥ 1.005 × every V3 view** (the three in-load views and the fresh 60.50488520482965).
* **Chain rule:** the same AND **≥ 1.02 × every V3 view** AND **≥ 61.87271031814733 tok/s**.
* **Kill rules** (recorded in the summary, never a speed claim):
  * `handoff_export` mean on the k3x views > 0.10 ms (the export is not on the copy path; priced 0.053);
  * `boundary_total` mean on the k3x views > 1.60 ms (layer 26 costs more than 0.57 ms at the boundary; priced 1.466);
  * the k3 hit saving (V3 − k3x mean hit interval) < 0.35 ms (priced 0.51-0.54; packet188 measured 0.071 with the kio export);
  * the boundary exceeds the draft wall on > 10% of k3x hits (priced 0%; mean margin 0.072 ms);
  * the trims remove < 0.105 ms of rank 0's A (packet188 measured 0.142).
* **Reported, not a condition:** `rank1_binds_emission` on k3x hits (priced ~3%), the miss interval, the envelope
  attribution (half_total − layer_body = snapshot + token_history + token_prep + unattributed; boundary_total −
  boundary_body = export + rest), `D_op9`.
* **Rule tested on REAL packet188 data** (`v5/test_s189_decision.py`, 13 tests; the analysis gate pins every file it reads
  in `v5/evidence/analysis-real-inputs.json`, read in place, never copied):
  * **packet188 row 2 with k3trims relabeled k3x: NOT A SCREEN WINNER** at the measured numbers: rates 60.526 / 60.564 /
    60.536 / 60.382 / 60.540, fresh 60.505, min gain −0.260%, drift 0.058%; kill rules fired: `handoff_export` 0.5922 ms,
    `boundary_total` 2.0050 ms, hit saving 0.0709 ms, boundary over the draft wall on 100% of hits; the trims rule passed
    (0.1424 ms); D 1.586 → 1.537 (op 9: 1.608 → 0.427); `boundary_body` +0.4596, `handoff_export` +0.5394.
  * **Null k3x** (V3 views as the candidate): not a winner; hit-saving and trims rules fire.
  * **Scalings** of the real views: 1.025 → chain; 1.021 → winner only (61.81 < 61.873); 1.015 → winner only; 1.004 → no.
  * **Refusals:** drift, inexact, changed proposals, a missing smoke and a wrong candidate variant each refuse.
  * **Packet187's 12 real WS128 streams** reproduce hit 14.050 / miss 25.750 / Bd 1.027 ms, and `RECORD` equals its stored
    metric; the draft wall is below op 9 there too.
  * **The replay** reproduces the record to 1e-9 and prices k3x at **+2.7398524525334977% (62.321501263968656 tok/s)**; the
    pessimistic corner stays above the chain bar.

## How the k3 state guards and the export identity hold for k3x

Layer 26 is GDN and stays inside the V3 island exactly as in packet188: it runs only in the boundary command, after rank
0's accept, guarded by accept, position and token and by rank 1's verification; it is never banked and never in the
speculative image (`v3_private`); views switch only at request reset. The production-shape image capture is **19,025,640
B / 984 extents** in every layout and start order (= packet186/188). Stored sites on rank 0: V3 60, k3 90; rank 1 skips
60/90 half sites.

**CPU proof** (`v5/evidence/k3-state.json`, `v5/k3_state_gate.py`), lean as instructed:

* **Engine part.** One rank-0 miniature engine in the k3 storage: k3x with GNU and Intel, and k3trims with GNU as the
  in-binary export partner (3 runs; packet188's 14-run grid is retained and pinned). Each run: 65 cases, 68 guard refusals,
  2 detecting negative controls (the moved layers advanced on a guessed token survive the rollback). The canonical
  transcript hashes every rank-0 allocation **and the exported shared slot** after every step. k3x's transcript equals
  k3trims' and packet188's retained k3/k3trims transcript (`d451302d954f…`): **the copy-engine and KioCopy export paths
  deliver byte-identical export bytes**, and the k3x engine moves no byte packet188 did not. The counters prove which path
  ran (k3x: copy-engine export runs only; k3trims: kernel runs only).
* **Two-rank pipeline part.** The five-layer miniature G Q G G Q with the real controllers and the real switch op 13: a
  fresh production-layout reference and one-load brackets V3/k3x/V3/k3x/V3 in BOTH start orders (44 requests). Every
  request equals the reference: tokens, all 120 per-step per-layer stream fixtures, draft proposals, draft final state and
  every target state buffer on its owner rank. Boundary views issue one boundary per rank-0 accept; rank 1 never runs a
  moved layer.

## Memory and host admission

From the production-shape census (`full-shape.json`, `admission.json`), identical to packet188:

| Rank | V3 (0-25, record) | k3 storage (0-26) | Arena headroom (limit 32,212,254,720 B) | Physical free (34,242,297,856 B) |
|---|---:|---:|---:|---:|
| 0 | 30,245,049,064 | **31,374,119,922 (+1,129,070,858)** | 838,134,798 | 2,868,177,934 |
| 1 | 31,581,735,626 | 31,581,735,626 (+0) | 630,519,094 | 2,660,562,230 |

* The rank-0 delta is exactly the 65 allocations of `blk.26.*`; nothing is removed. The plan (packet188's derivation,
  `97a76116…`) gives rank 0 32,003,283,826 B, headroom 208,970,894 B, 2,192,513,482 B free with MTP.
* Pinned kernel-io staging: 86,016 B on rank 0 and 73,728 B on rank 1 (host). The export path adds no allocation.
* **Host MemAvailable at START:** k3x rows **108,797,048,558 B** (= packet188's k3 rows), plus the queue's 1 GiB.

## Gates (receipts under `v5/evidence/`)

| Gate | Result | Receipt |
|---|---|---|
| Build (entry TUs, unit poll) | PASS: 8 compiler runs, 0 warnings, 78 parent objects | `build.json`, `compile-poll.json` |
| Production-shape startup | PASS: 4 selections × 2 ranks (8 startups); 8 dual-rank loads in both start orders; V3 and k3-storage captures and census identical to packet188; k3 delta = layer 26; image 19,025,640 B; 22 native refusals per run | `full-shape.json`, `shape-*.tar.gz` |
| k3x state + export identity | PASS: 3 engine runs (k3x GNU/Intel, k3trims GNU) + 44 pipeline requests | `k3-state.json`, `k3-state-engine-*.{log,txt.gz}` |
| Controller mock | PASS: probe 12 cases + run_v3 72 cases, GNU/Intel × 2 | `controller.json` |
| Admission | PASS: host 108,797,048,558 B | `admission.json` |
| Analysis (schema, s189 on real packet188/187 data, replay, envelope baseline) | PASS: 8 + 3 + 13 tests | `analysis.json`, `analysis-real-inputs.json`, `analysis-test_*.log` |
| Safety / exec limits / loader | PASS | `safety.json`, `exec-limits.json`, `loader.json` |
| Seal | PASS | `v5/cpu-seal.json` |
| package_rows | PASS: 2 rows | `package-rows.json` |
| Entry / launch limits / worker / report | PASS: 4 entry rows + 8 negatives; 8 limit rows; 13 + 65 requests + abort path; 4 report rows | `entry-gate.json`, `launch-limits.json`, `worker-gate.json`, `report-gate.json` |
| Private-copy plan `--lane B` + rehearsal | PASS | `queue-plan.json`, `plan-B.log`, `rehearse.json` |
| Pin guard (live `check_job`, 2 rows) | PASS: 1,109 pins, 36 manifests, **0 cross-packet mutable** | `pin-guard.json`, `final-pin-guard.json` |
| final_checks / `--ready` | PASS; READY written last | `final-checks.json`, `../READY-FOR-DEVICE.json` |

## Record bundle on a chain-rule win (derive like packet187)

A chain-rule win is a screen, not a record. The record needs a fresh-process chain: packet187's harness, which is
packet136's eleven-window lane-A chain on cards 0+1 with packet187's guarded `launch_chain.sh`. Exactly these things
change from packet187:

1. **Selection.** `k3x` (`c5443bbf…`) replaces packet187's V3 selection (`923639a9…`). The changed keys are `rank0_layers
   0-26`, `boundary rank0-k3`, `kernel_io kernel`, `rank0_prepare async` and `boundary_export copy`; everything else
   (head, static snapshot, dense_scales, draft) is unchanged.
2. **Engine.** The packet189 device engine `87eec645…` (with its gnu-host twin `a50588a9…`) replaces packet186's
   `693cc194…`, which packet187 reused without relinking.
3. **Memory plan.** The k3 ledger (`v5/lineage/k3x/memory-plan.json`, sha `97a76116…`, = packet188's) replaces it. Rank 0
   rises to 31,374,119,922 B.
4. **Launcher host floor.** It becomes 108,797,048,558 B + 1 GiB (packet187 used 107,667,817,956 B + 1 GiB).
5. **KD projection.** KD's layer-streaming reference must project `kernel_io`, `rank0_prepare` and `boundary_export` to
   production, together with `rank0_layers`, `boundary` and `snapshot_host` (packet187's boundary). The trims and the
   export path move no bytes (the k3-state canonical identity).
6. **Bars.** The chain WS128 must beat **60.659520** (packet187) and pass every exactness gate. The chain rule already
   requires ≥ 61.873 in the screen.

Unchanged: the v5 transport size (266,304 B), the oracle binding, the provenance layout, the launcher refusals and the
submission step (coordinator's).

## Notes and limits

* **This is a re-open of a measured loss, on the coordinator's ruling.** Packet188's DO-NOT-REPEAT row stays closed for
  the kio-export composite as built; the packet189 row is pending for k3x (`DO-NOT-REPEAT.md`).
* **The honest risk is not the price but a surprise in the copy-engine export under `kernel_io=kernel`.** Kill rule 1
  (`handoff_export` > 0.10 ms) catches it in the first view; the CPU proof shows the bytes are identical, not the time.
* **The bracket's in-load V3 views are not the record storage.** They use the k3 storage with layer 26 idle on rank 0.
  Packet188 row 1 (a fresh 0-25 load of the record selection, −0.05% vs the in-load views) ties them to the record line;
  the drift bound covers all four V3 views.
* **Real analysis inputs are read in place.** They are packet188's three device rows, packet187's WS128 chain run, the
  packet49 oracle and the two packet186 incident64 fixtures. Their path → sha256 map is
  `v5/evidence/analysis-real-inputs.json`, outside the pin guard's walk (packet187/188's bracket-gate layout); no device
  row reads these files. `analysis.json` seals the map's digest, and `final_checks.py` re-hashes every file.
* **DO-NOT-REPEAT corpus.** All 295 DO-NOT-REPEAT.md files under stage2 were grepped (`analysis/dnr-list.txt`, the
  lever-synthesis-3 corpus) before the rows were finalised: no row mentions the boundary export path, `boundary_export`,
  `handoff_export` or a GDN-only k=3 with the copy export; the only k=3 closure is packet188's own row, re-opened by the
  ruling above. The packet176/171b rows ("do not re-test the kernel path as a queue memcpy") are not touched: the small
  kio transfers stay kernels; only the 20 KiB export returns to the copy engine the record already uses.
