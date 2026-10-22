# Two-card lever synthesis 3: after packet188 (2026-10-22, CPU-only, read-only on the repo)

**Line:** Qwen3.8 Flash-Next UD-IQ3_XXS, own Xe runtime, two B70s. **Record:** 60.659520 tok/s (packet187 V3 chain,
LocalMaxxing `cmvjvabyv040jrf01dricuz8s`). **Chain bar:** 61.873 tok/s (+2%). **Screen bar:** +0.5% over every V3 view.

**Packet188 result (lane B, 2026-10-22):** one-load V3 / k3+trims / V3 / k3+trims / V3 = 60.526 / **60.564** / 60.536 /
**60.382** / 60.540; fresh V3 control 60.505. Slowest k3+trims vs fastest V3: **−0.26%**. Not a screen winner.

Nothing here was built, run on a device, queued, committed or written into the repo. All numbers are arithmetic on the
retained per-interval receipts and rank-0 host scopes of packet188 row 2 and packet187's WS128 chain. Scripts beside this
file: `replay_k3x.py` (decomposition and every price; output `replay-k3x-output.json`), `k3x_spread.py` (per-prompt spread;
`k3x-spread-output.json`), `dnr-list.txt` / `all-dnr.txt` (all 295 DO-NOT-REPEAT files under stage2, grepped before
proposing). The replay reuses lever synthesis 2's loader and record metric (`packet188 analysis/replay_v3.py`, imported
read-only) and reproduces 60.65951991975228 to 1e-9 and the measured k3trims views exactly (see §1.2).

## 0. Answer

* **A.** Layer 26 did not cost 0.97 ms. The GDN layer-26 kernels cost **0.459 ms** at the boundary (`boundary_body`
  0.9505 → 1.4096), exactly the 0.463 ms rank 1 saved per layer and below the priced 0.513. The other **+0.540 ms** is
  the `handoff_export` scope (0.0528 → 0.5925) for the **same 20,480 bytes**: under `kernel_io=kernel` the boundary's
  export readback goes through the one-work-item-per-byte `KioCopy` kernel into pinned host memory
  (`v3_boundary.hpp`: `if(e.kio_active&&captured_count==0) … e.kio_read_many(…{error,4},{streams,bytes})`),
  at **28.9 ns/byte** instead of the copy engine's 2.6 ns/byte. It is a transfer-path effect, not a state-size effect: no
  GDN recurrent/conv state crosses the boundary (rank 0 owns 24–26's state; only the layer-end residual streams, 4·h·2
  bytes with h = 2560, are exported, unchanged from V3). D fell from 1.61 to 0.43 ms because the interval model's D is the
  op-9 command duration, and under the trims the draft command returns after its nonblocking host issue (0.42 ms busy);
  the draft's real completion is in the receipts' `draft_rows.draft_wall_ms` (publication observed): **1.586 ms in the V3
  views, 1.537 ms in the k3trims views**. The draft did not get faster by 1.18 ms; it got faster by 0.049 ms.
* **B.** V3 + `kernel_io=kernel` with the export on the copy engine (k=2, trims on): rank 1's B loses **0.080 ms/hit**
  (B −0.539 minus the moved layer 0.459; miss B −0.034), the draft loses **0.049 ms**, rank 0's C loses 0.099 ms (misses)
  and A loses 0.142 ms (never binds on V3). Replay over packet187's 1,188 intervals: **+0.79%** (61.14 tok/s); the
  rank-1 part alone +0.66%, the B part alone +0.43%. `rank0_prepare=async` alone on V3: **+0.00%**. The rank-1 kio saving
  is real, not noise: B is stable to 0.001 ms between the two k3trims views and to 0.006 ms between the three V3 views;
  the 0.3% view spread is prompt-level jitter in 4 of 12 prompts (§3.1). `kernel_io=kernel` **as built** on V3 (export
  through KioCopy) prices **+0.10%**: the +0.54 ms export sits inside the draft window on hits but on the serial path of
  every miss.
* **C.** On the V3 line nothing single reaches +2% (as in synthesis 2). The ranked prices (packet187 replay):
  k3 + trims **with the export on the copy engine ("k3x") +2.74%** (62.32; range +2.27…+3.01, every pessimistic
  assumption together +2.27); k3 alone (copy export) +1.56%; kio-x on V3 +0.79%; rank-1 kio only +0.66%; rank-0 trims
  only +0.13%; boundary export removed entirely +0.07%; a QSA layer in the boundary: none adjacent is admissible (23 and
  27 are QSA; 23 → −0.66%, 27 illegal and −1.21%); overlapping the boundary with rank 1's next half: nil on hits (rank 1
  runs the draft during the boundary), impossible on misses (layer 24 needs C's layer 23). Misses got +0.376 ms worse
  under k3+trims because the +0.974 ms boundary is serial on the miss path (R+C+Bd) and only C −0.099 and B −0.493 offset
  it: 0.974 − 0.099 − 0.493 + 0.016 (R) ≈ +0.38. Under k3x misses improve by 0.16 ms.
* **D.** ONE packet: **k3x = packet188's k3+trims with the boundary export back on the copy-engine readback** (new
  execution key `boundary_export=copy`, everything else k3trims). Priced **+2.7% (range +2.3…+3.0)**: 62.14–62.19 in-load
  against V3 60.53–60.54, 62.32 on the record replay, chain estimate ≈ 62.1–62.4 vs the 61.873 bar. Two rows, about 14 min
  of lane B. **It is a re-open:** `docs/own-runtime.md` records "loss, k=3 closed: GDN layer 26 at the rank-0 boundary
  costs 0.97 ms (0.54 in the export)". The row itself separates the 0.54; this synthesis shows that 0.54 is the KioCopy
  export path, measured against the copy-engine path for the same bytes inside the same bracket. The coordinator must rule
  on the re-open (the packet177-row-2 → V3 pattern). If refused, the best open lever is kio-x on V3 at +0.79%, a screen-bar
  result only.

## 1. Inputs, identity and the one measurement trap

### 1.1 Data

* packet188 row 2: `v5/evidence/device-row2-bracket-v3k-k3trims-B-p188/run/views/{00,02,04}-control` (V3, k3 storage,
  layer 26 idle on rank 0) and `{01,03}-candidate` (k3trims); 12 prompts × 99 intervals = 1,188 per view. Per interval:
  the packet85 vendored model + boundary (`s188_decision.intervals_v3`), plus `draft_rows.draft_wall_ms` and the rank-0
  p150 scopes `boundary_body` / `handoff_export` / `boundary_total` joined by position.
* packet187 `build/device-cards01-p187-a/WS128/run/repeat-1`: the 1,188 record intervals (replay = 60.65951991975228).
* Identity: `T = max(D, R + C + Bd) + max(B, A + offset) + G`; metric = per prompt 99000/ΣT, median of class medians.

### 1.2 What D measures in each variant (the trap)

The draft is nonblocking in BOTH variants (`draft_rows` carry `nonblocking: true` / `draft_gpu_timing_deferred`). What
differs is when the rank-1 controller stamps op 9 complete:

| | V3 views | k3trims views |
|---|---:|---:|
| op-9 duration = model **D** (hit mean) | 1.608 | **0.427** |
| `draft_wall_ms` = publication observed (hit mean, p5–p95) | **1.586** (1.568–1.647) | **1.537** (1.516–1.562) |
| rank0_idle_waiting_for_guess (mean) | 0.006 | 0.0002 |
| rank-1 half start after draft start (p50) | 1.614 | 2.062 |

In V3 the controller sits in the op-9 command until the publication (D = draft_wall + 0.02); in k3trims it returns after
the 0.42 ms host issue and polls the publication while waiting for the 2.0 ms boundary. So "Bd > D on 100% of hits" is
true but says nothing: the boundary (2.005) also exceeds the real draft (1.537), by 0.468 ms. **Model check:** rebuilding
each k3trims view with `ready = max(draft_wall + 0.006, Bd)` reproduces its measured rate exactly (60.5644 / 60.3824),
because Bd binds every hit either way. Any future k3 decision must read D from `draft_wall_ms`, not from op 9.

### 1.3 Measured components (means, ms; `replay_k3x.py` §A)

| | V3 hit | k3trims hit | Δ hit | V3 miss | k3trims miss | Δ miss |
|---|---:|---:|---:|---:|---:|---:|
| Bd (boundary_total) | 1.0317 | 2.0054 | **+0.974** | 1.0304 | 2.0050 | +0.975 |
| boundary_body (layers 24–25 → 24–26) | 0.9505 | 1.4096 | **+0.459** | 0.9495 | 1.4108 | +0.461 |
| handoff_export (20,480 B) | 0.0528 | 0.5925 | **+0.540** | 0.0529 | 0.5910 | +0.538 |
| boundary envelope other | 0.028 | 0.003 | −0.025 | | | |
| draft_wall | 1.586 | 1.537 | **−0.049** | 1.587 | 1.537 | −0.050 |
| B (rank-1 half) | 12.432 | 11.893 | **−0.539** | 12.616 | 12.123 | −0.493 |
| A (rank-0 speculative half) | 12.112 | 11.970 | **−0.142** | 12.109 | 11.968 | −0.142 |
| C (corrected half) | | | | 11.811 | 11.712 | **−0.099** |
| R | | | | 0.305 | 0.290 | −0.015 |
| G | 0.020 | 0.013 | −0.007 | 0.016 | 0.015 | |
| ready | 1.608 | 2.005 | +0.398 | 13.146 | 14.007 | +0.861 |
| race | 12.432 (B) | 11.971 (A) | −0.461 | 12.616 | 12.132 | −0.484 |
| **elapsed** | **14.060** | **13.989** | **−0.071** | **25.778** | **26.154** | **+0.376** |

Rank-1 host envelope (B − half_completion): V3 0.04 ms, k3trims 0.03 ms; `prepare_ms` on rank 1 is 0. Rank 1's half is
kernel-bound: there is nothing to trim on rank 1's host side.

## 2. A: why layer 26 cost 0.97 ms, and why D fell

**Kernel part: 0.459 ms.** `boundary_body` grew 0.9505 → 1.4096. That is the GDN layer-26 kernel time, equal to the rank-1
saving per layer (0.463, packet186) and to what B gave back beyond the kio part. The priced 0.513 ms/layer was
packet186's 1.026/2, which amortised the fixed boundary envelope (0.08) into each layer; the marginal third layer carries
no new fixed part (the "other" envelope even fell 0.025 ms because the error readback was folded into the export).

**Export part: +0.540 ms, a path effect.** `v3_boundary.hpp`: when `kio_active`, error (4 B) + streams (`bytes = 4·h·2 =
20,480`) are read back by ONE `KioCopy` kernel (`kernel_io.hpp`: `parallel_for(range(total))`, one work-item per byte,
each storing one byte into pinned USM host memory across PCIe); otherwise `e.readback` (copy engine) then `memcpy` to the
shared slot. Same bytes, same slot (`require(bytes<=slot_bytes)`; the v5 transport is unchanged at 266,304 B):

* V3: 0.0528 ms = 2.58 ns/byte (copy engine, ~0.4 GB/s effective with latency);
* k3trims: 0.5925 ms = 28.9 ns/byte (~35 MB/s: byte-granular uncached host stores);
* it also jitters: 0.582 (view 1) → 0.602 (view 3), the only component that moved between the two candidate views.

Not a state-size effect: GDN recurrent state, conv history and per-layer buffers of 24–26 stay on rank 0 (never banked,
never imaged, never exported). Not serialization of the layer: the boundary was already a serial command. Every other kio
transfer in the composite is tiny or device-side and measured as a saving: rank 1's folded error+next_token (8 B,
host_waits 3 → 2, B −0.080), the draft's merge copy (20 KiB device→device kernel, draft −0.049), the publication (8 B),
rank 0's staged token + lookup loads (host→device, A −0.142, C −0.099). The one pathological case is the one large
device→host readback, and the `≤ 64 KiB` rule let it in.

**Why D fell to 0.43:** §1.2. The real draft completion fell 1.586 → 1.537 (kio on rank 1's draft path).

**Why hits only broke even:** ready rose +0.398 (boundary 2.005 replaced the draft 1.608 as the gate) while the race
fell −0.461 (A 11.970 now binds; B 11.893). Net −0.071 (−0.5% of a hit). With the export at V3's cost the boundary would
be 1.466, below the real draft 1.537 on every hit (0/932 exceed, margin 0.072 mean), and the hit cycle would be
max(1.537, 1.466) + 11.970 + 0.013 ≈ **13.52** (−0.54 ms, −3.8%).

**Why misses got 0.376 ms worse:** misses are serial on rank 0 (R + C + Bd) then B: +0.974 (Bd) − 0.099 (C) − 0.015 (R)
− 0.493 (B) + 0.009 (G, offset) = +0.376. With the copy-engine export: +0.434 − 0.099 − 0.015 − 0.493 ≈ **−0.17**.

## 3. B: V3 + kernel_io only (k=2), and prepare=async on V3

Derivation of what kio removes from rank 1's B: B fell 0.539 on hits and 0.493 on misses; the moved layer is 0.459
(boundary_body growth, the same kernels); remainder **0.080 (hits) / 0.034 (misses)**. Rank 1 had 3 synchronous round
trips per half at 22.7–25.5 µs (packet165): folding two into one kernel readback and removing a copy-engine wait
plausibly saves 0.03–0.08; the hit/miss difference (0.046) is the miss-B "warm after idle" variance (packet144's 0.223
term), not a view effect: B is reproducible to 0.001 ms across the two k3trims views. The draft saves 0.049 (draft_wall).

Replay on packet187's intervals (`replay_k3x.py`, prices_p187):

| Lever on V3 (k=2) | hit ms | miss ms | rate | gain |
|---|---:|---:|---:|---:|
| V3 identity | 14.050 | 25.750 | 60.660 | 0 |
| kernel_io on rank 1 only: B −0.080/−0.034, draft −0.049 | 13.921 | 25.716 | 61.061 | **+0.66%** |
| … B part only (no draft part) | 13.970 | 25.716 | 60.919 | +0.43% |
| … low case (B −0.03, D −0.03) | 13.990 | 25.720 | 60.858 | +0.33% |
| **kio-x**: kio both ranks, export on copy engine, + prepare async (A −0.142, C −0.099) | 13.921 | 25.617 | 61.140 | **+0.79%** |
| rank0_prepare=async alone (A −0.047) | 14.050 | 25.750 | 60.660 | **+0.00%** |
| all rank-0 trims alone (A −0.142, C −0.099) | 14.050 | 25.652 | 60.737 | +0.13% (misses only) |
| kernel_io=kernel AS BUILT on V3 (export via KioCopy, Bd +0.54) + trims | 13.926 | 26.132 | 60.719 | +0.10% |

In-load (packet188's three V3 views): kio-x +0.79% on each. So "V3 + kernel_io" is a **screen-bar** lever (+0.66…+0.79%)
only if the export stays on the copy engine; as the key is built today it is +0.10%. `rank0_prepare=async` is worth
nothing on V3 because rank 1 binds every hit by 0.32 ms (B 12.432 vs A + offset 12.112).

### 3.1 Noise

The two k3trims views differ by 0.30% in the metric but by only 0.12% in the pooled interval (16.601 vs 16.620 ms); the
uniform part is the export jitter (+0.020 ms/hit). Per prompt, 8 of 12 agree within ±0.13% and four move by about ±0.8%
(customer-email +0.83, decision-memo −0.83, performance-hypotheses −0.78, release-plan −0.87): prompt-level host jitter
that the class-median metric picks up. The V3 views drifted 0.058% across four views. A single candidate view therefore
carries about ±0.3% of metric noise; the +0.66…+0.79% kio prices are above that, the +0.13%/+0.10% ones are not.

## 4. C: every remaining open lever on the V3 line, ranked

Facts: rank 1 binds 100% of V3 hits by 0.320 ms (B − A − offset; p5 0.246, min 0.116); the draft window slack is
draft_wall − Bd = 0.555 mean (p5 0.527); boundary 1.03; misses 21.55% of intervals, 33.5% of time.

| # | Lever | Arithmetic (ms per interval → metric) | Price | Bar |
|---|---|---|---:|---|
| **1** | **k3x: layers 24–26 on rank 0 + both trims + export on the copy engine** | hits: ready max(1.537, 1.466) ≈ 1.55; race max(11.893, 11.970) = 11.970; +G → 13.52 (−0.53). misses: 0.290 + 11.712 + 1.466 + 12.123 + 0.015 = 25.61 (−0.17) | **+2.74%** record replay (62.32); +2.65…+2.73% on the three in-load V3 views (62.14–62.19); +2.56…+2.76% rebuilt directly from the two measured k3trims views with only the export repaired | **chain** (62.1–62.4 vs 61.873) |
| 2 | k3 alone, export on copy engine (no trims) | hits: max(1.586, 1.49) + max(11.97, 12.11) → 13.705 (−0.345); misses +0.017 | +1.56% | screen, not chain (synthesis 2 said +1.49) |
| 3 | kio-x on V3 (k=2; kio both ranks, export on copy engine, prepare async) | hits −0.129 (B 0.080 + D 0.049); misses −0.133 | +0.79% | screen only |
| 4 | kio on rank 1 only | hits −0.129; misses −0.034 | +0.66% | screen only |
| 5 | rank-0 trims only (A −0.142, C −0.099) on V3 | hits 0 (A does not bind); misses −0.099 | +0.13% | below |
| 6 | shrink/remove the boundary export (0.053, copy engine) | hits 0 (inside the draft window); misses −0.053 → 0.2155 × 0.053 = 0.011 pooled | ≤ +0.07% | below |
| 7 | k=3 moving a QSA layer instead of 26 | map: QSA every 4th layer = 3, 7, …, 23, 27, …; 24–26 GDN. Adjacent QSA are 23 (below) and 27 (above). 23–25: Bd +0.52, A −0.46 (A does not bind) → −0.66%; also puts KV/position/lookup in the island. 24–27: illegal (QSA) and −1.21% even if GDN (boundary overflows the draft window) | −0.66% / illegal | closed (packet188 DNR "Do not add QSA layer 23 or 27") |
| 8 | partially overlap the boundary with rank 1's next half | hits: rank 1 runs the draft (1.54) during the boundary (1.03); its half cannot start before layer 25/26's stream exists; nothing to overlap. misses: the boundary needs C's layer-23 stream (packet144 "Layer24 requires layer23 streams") | 0 | closed |
| 9 | kernel_io=kernel as built on V3 | export +0.54 serial on misses | +0.10% | below |
| 10 | rank0_prepare=async alone on V3 | A −0.047, A never binds | 0 | below |

What the scope totals point at beyond #1: under k3x rank 0's A (11.970) binds the race by 0.077 and the draft (1.537)
binds the ready side by ~0.07, so the line is balanced to within 0.08 ms on both sides; further single-side cuts saturate
fast (k3x + 0.05 off A +2.95%, + 0.10 off A +3.06%, + 0.20 off A +3.10%; + 0.10 off the draft +3.15%; + 0.10 off B
+2.87%; + 0.10 off the boundary +2.88%). The remaining rank-0 A envelope after the trims is 0.302 ms (snapshot capture
0.246, token_prep 0.052, unattributed 0.004) plus p76 retirement 0.101: a later packet could take ~0.08 of it for about
+0.3% on top of k3x, nothing more.

**Reaches +2%:** only #1. **Reaches +0.5%:** #1, #2, #3, #4.

## 5. D: the one next packet

**Packet189 "k3x": packet188's k3+trims with the boundary export on the copy-engine readback.** This is a re-open of the
k=3 row closed today (`docs/own-runtime.md`: "loss, k=3 closed: GDN layer 26 at the rank-0 boundary costs 0.97 ms (0.54
in the export) against 0.54 ms saved on rank 1"). Re-open basis, for the coordinator's ruling: the 0.54 is the KioCopy
export path (code: `v3_boundary.hpp` kio branch; `kernel_io.hpp` one work-item per byte to USM host), measured at 28.9
ns/byte against the copy engine's 2.6 ns/byte for the identical 20,480 bytes in the same one-load bracket; the layer-26
kernel cost (0.459) is below the priced 0.513; and the real draft completion (1.537) leaves a 0.072 ms draft-window
margin over the repaired boundary (1.466) on 932/932 hits. No DNR row closes a copy-engine export (it is V3's record
path) or a GDN-only three-layer boundary with a verified token (the coordinator's k=3 ruling stands); packet176's "do not
re-test the kernel path as a queue memcpy" is not touched (the small kio transfers stay kernels; only the 20 KiB export
returns to the copy engine it already used in the record).

**Build (entry TU only, no new kernels):** a fourth execution key `boundary_export = copy | kernel` (default `copy`:
`e.readback` of the streams + `memcpy` to the slot, exactly V3's path; the 4-byte error check may stay a kio read or
`e.integer`; `kernel` = packet188's folded `kio_read_many`, kept so `k3trims` stays reproducible). Switchable in-load like
`boundary` / `kernel_io` / `rank0_prepare`. Storage unchanged (`rank0_layers=0-26`, the packet188 k3 census: rank 0
31,374,119,922 B; host floor 108,797,048,558 B + 1 GiB). Also fix the decision's D: read `draft_wall_ms` from
`draft_rows` for every rule that compares the boundary with the draft.

**Selections:** `v3k` (control, as packet188) and **`k3x`** = `rank0_layers 0-26`, `boundary rank0-k3`, `kernel_io kernel`,
`rank0_prepare async`, `boundary_export copy`. Keep `k3trims` (`boundary_export kernel`) available for a later attribution
view; do not put it in this window.

**Rows (lane B, PAUSE-A held), about 14–15 min:**

| Row | Job | Content | Expected (s) |
|---|---|---|---|
| 0 | `packet189-row0-smoke-k3x-B` | k3x smoke, 12 × 64 + incident64, exact, first-request data proof | ~313 (packet188 row 0 took 313) |
| 1 | `packet189-row1-bracket-v3k-k3x-B` | ONE load: V3 / k3x / V3 / k3x / V3, 12 × 128 + incident64 each | ~480 (packet188 row 2: 480.0) |

No fresh-V3 control row: packet188 row 1 already measured the record selection fresh (60.505) against the same k3
storage's in-load V3 (60.526–60.540, −0.05%); the storage and the V3 execution are unchanged, so that row is the fresh
reference (state this in the decision). Total ≈ 313 + 61 + 480 ≈ 854 s plus drain spacing: under 20 min.

**Decision rule (`s189_decision`, same shape as s188):**

* screen winner: every view 13/13 exact; draft proposals and per-prompt acceptance identical across the five 128-token
  views; V3 drift ≤ 3% over the three in-load views and packet188's fresh 60.505; AND the slower k3x view ≥ 1.005 × every
  V3 view;
* chain: the same AND the slower k3x view ≥ 1.02 × every V3 view AND ≥ 61.873 tok/s; then derive the record bundle from
  packet187 as packet188's README already specifies, with `boundary_export` added to the KD projection keys.

**Kill rules (recorded; D := `draft_wall_ms`, never op 9):**

1. `handoff_export` mean on the k3x views > 0.10 ms → the export is not on the copy path; stop (priced 0.053).
2. `boundary_total` mean on k3x hits > 1.60 ms → layer 26 costs more than 0.57 at the boundary; stop (priced 1.466).
3. k3 hit saving (V3 hit elapsed − k3x hit elapsed) < 0.35 ms → stop (priced 0.51–0.54; packet188's 0.25 was for k3
   alone without trims).
4. boundary_total > draft_wall on > 10% of k3x hits → report and do not chain (priced 0%; mean margin 0.072; both p5–p95
   spreads are ±0.025).
5. trims: A(V3) − A(k3x) < 0.105 ms → stop (measured 0.142 in packet188; must reproduce).
6. report, not a condition: `rank1_binds_emission` on k3x hits (priced ~3%), miss elapsed (priced 25.61 vs V3 25.78).

**Priced gain and uncertainty.** Central **+2.7%**: 62.32 on the record replay; 62.14–62.19 in-load vs 60.53–60.54 (and
+2.77% vs the fresh 60.505). Rebuilt from the measured k3trims intervals with only the export repaired: 62.19 / 62.19
(guess latency 0.006) down to 62.09 / 62.10 (latency 0.03, export 0.083). Sensitivities on the record replay: draft not
faster at all +2.50; export 0.083 +2.70; B saving only 0.50/0.45 +2.65; A trim only 0.105 +2.56; **everything pessimistic
together +2.27** (62.04); everything optimistic +3.01. Per-prompt k3x gains run +2.19…+3.04% (min bug-report-synthesis,
the 83/127 hit-rate prompt). Measurement noise: a single candidate view carries ~±0.3% (§3.1); V3 drift 0.06%; the fresh
chain sat +0.2% above in-load views in packet187/188. So the chain bar (61.873) is cleared by ≥ 0.3% even in the
pessimistic corner, and the screen bar by a wide margin; the honest risk is not the price but the ruling (re-open) and
any surprise in the copy-engine export under `kernel_io=kernel` (kill rule 1 catches it in the smoke).

**If the re-open is refused:** the best open lever is kio-x on V3 at +0.79% (screen bar, not chain; its honest range
+0.33…+0.79%); it needs the same `boundary_export=copy` fix, since the key as built is +0.10%.

## 6. Rows checked (all 295 DO-NOT-REPEAT files under stage2; `all-dnr.txt`)

* packet188 DNR: "Do not run layer 26 (or 24-25) inside a speculative half, or before the accept" (respected: k3x is the
  same boundary command); "Do not add QSA layer 23 or 27 to the boundary" (respected; #7 priced as a loss anyway); "Do not
  read the k3+trims vs V3 difference as k3 alone" (this synthesis attributes from the scopes: body 0.459 / export 0.540 /
  B −0.539 / A −0.142); "Do not start a record chain below the chain rule" (kept); the pending row's kill readings are the
  inputs here. The DNR file still says "Pending"; the closure wording is in `docs/own-runtime.md` and the 10-22 note.
* packet186: the four boundaries (no speculative moved layers, no slim layout, smoke not a speed result, no chain below
  the rule) all hold for k3x.
* packet187: KD projection must carry the new key (`boundary_export`) with `rank0_layers`, `boundary`, `snapshot_host`,
  `kernel_io`, `rank0_prepare`.
* packet177 row 2 (placement closed; V3 and k=3 admitted by ruling) and row 3 ("nothing to port … +0.6% if removed"):
  the kio-x price +0.79% is consistent; kio stays a component.
* packet176 / 171b: "B arm is a compute kernel path … do not re-test as a queue memcpy"; "do not move one-card foreground
  copies onto the compute queue as memcpy". k3x does neither: the export returns to the copy-engine readback the record
  already uses.
* packet144 (miss path rows), packet148 (no silent placement changes; this one is explicit), packet120 (speculative
  layer move, not this), packet183 (`dense_scales` stays expanded), packet185 (no in-load head/storage switch: the bracket
  switches execution keys only).
* No row anywhere mentions the boundary export path, `boundary_export`, `draft_wall`, or a GDN-only k=3 with the copy
  export; the only k=3 closure is today's packet188 row, which this document asks to re-open on the attribution above.

## 7. Scripts

* `replay_k3x.py` — loads packet187's 1,188 intervals and packet188's five views (+ `draft_wall`, boundary scopes),
  verifies the record replay (diff < 1e-9) and the k3trims identity check, prints §1.3, every price in §3–§4 and the
  sensitivities; writes `replay-k3x-output.json`.
* `k3x_spread.py` — per-prompt and per-class k3x gains on each V3 view and the measured per-prompt spread between the two
  k3trims views; writes `k3x-spread-output.json`.
* `dnr-list.txt`, `all-dnr.txt` — the DO-NOT-REPEAT corpus grepped for §6.
