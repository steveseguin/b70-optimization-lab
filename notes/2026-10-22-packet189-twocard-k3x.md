# 2026-10-22: packet189, k3x (packet188's k3 + trims with the boundary export on the copy engine), CPU preparation

Packet: [`experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/`](../experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/README.md).
Proposal (PROPOSAL ONLY, never queued): `experiments/own-xpu-runtime/ops/lane-queue/proposed-p189-two-card-B.txt`.

No GPU, `/dev/dri`, device binary run, systemd change, PAUSE/STOP or queue file was touched. Nothing was queued, armed,
submitted or committed. The only systemd calls were read-only `systemctl --user list-units 'window-*' 'lanequeue-*'`
polls before each compile batch; no unit was active or activating (five failed, inactive lanequeue units were listed).

## Why

Packet188 measured k3 + trims on lane B (lanequeue-B35): a loss, −0.26% against the fastest V3 view. Lever synthesis 3
(`analysis/lever-synthesis-3-20261022.md` in the packet) split the +0.974 ms boundary growth with the rank-0 host scopes:
`boundary_body` +0.459 ms (the GDN layer-26 kernels, equal to the 0.463 ms rank 1 saved per layer and below the priced
0.513) and `handoff_export` +0.540 ms for the SAME 20,480 bytes, because `kernel_io=kernel` routed the boundary export
through the per-byte `KioCopy` readback (28.9 ns/byte) instead of the copy engine (2.6 ns/byte). Packet188's D of 0.43 ms
was a model artifact (the op-9 command returns after the nonblocking host issue; the draft wall was 1.537 ms).

The coordinator's ruling: "Packet188's loss is attributed to its own export path, not to the third boundary layer ... The
k=3 ruling stands; packet189 re-measures k3 + trims with the export on the copy engine (k3x), and reads D from the draft's
observed wall time."

Priced on packet187's record intervals with only the export repaired: hits 14.050 → 13.52 ms (ready max(1.537, 1.466),
race 11.970), misses 25.750 → 25.61 ms; **+2.74%, 62.32 tok/s** (pessimistic corner +2.27%, 62.04; optimistic +3.01); the
chain bar is 61.873.

## What was built

Base: packet188, copied with an identity rewrite (`copy_packet189.py`; 2,182 files, 266 rewrites, 1,467 hard links). The
packet186 binary lineage is kept: the 78 parent objects are relinked unchanged; entry-main and `p49d_submit` are rebuilt,
`s1_submit` recompiled. The device engine is `87eec6453a2a9a9bfe30ed19466c6a70644d9cd168f734be87d2f0a17b776af4` (8 compiler runs, 0 warnings). The native delta is
**+38 / −15 lines in 6 files** (`v5/k3x-native.patch`).

One new execution key, switchable in-load like `boundary`/`kernel_io`/`rank0_prepare`:

* **`boundary_export=copy`** (k3x, v3k): the 20,480-byte layer-end stream is read back on the copy engine into the pinned
  slab and memcpy'd to the shared slot, V3's record path, even under `kernel_io=kernel` (`readback(..., copy_engine=true)`
  bypasses the kio routing of ≤ 64 KiB requests). The 4-byte error check stays a kernel read.
* **`boundary_export=kernel`** (k3trims): packet188's folded `kio_read_many` readback, byte for byte (kept for a later
  attribution view; no packet189 device row uses it).
* k3-storage selections carry 19 keys; the engine refuses 18-key ones (the export path is always named). The `v3` record
  selection (16 keys, `923639a9…`) is untouched.

**Selection k3x:** `rank0_layers 0-26`, `boundary rank0-k3`, `kernel_io kernel`, `rank0_prepare async`, `boundary_export copy`
(`c5443bbf…`). Storage, census and memory plan are packet188's: the production-shape startup reproduces packet188's
captures and census for V3 and for every k3-storage load; the image capture stays 19,025,640 B / 984 extents.

**Decision `s189_decision`:** D is `draft_rows.draft_wall_ms` (publication observed), never op 9. Screen winner iff the
slower k3x view ≥ 1.005 × every V3 view (three in-load + packet188's fresh row 1 at 60.50488520482965, hash-pinned and
read in place), every view exact, identical proposals and acceptance, V3 drift ≤ 3%; chain rule iff also ≥ 1.02 × every V3
view AND ≥ 61.87271031814733. Kill rules recorded: `handoff_export` > 0.10 ms, `boundary_total` > 1.60 ms, k3 hit saving
< 0.35 ms, boundary > draft wall on > 10% of hits, A trim < 0.105 ms.

**Rule tested on the REAL packet188 rows:** with packet188's k3trims views relabeled k3x the analyzer reports the measured
numbers (60.526/60.564/60.536/60.382/60.540, fresh 60.505, export 0.592 ms, boundary 2.005 ms, hit saving 0.071 ms,
boundary over the draft wall on 100% of hits, A trim 0.142 ms, D 1.586 → 1.537 vs op 9 1.608 → 0.427) and says "not a
screen winner" with four kill rules fired and the trims rule passed. The synthesis-3 replay reproduces the record
60.65951991975228 to 1e-9, the two measured k3trims views exactly through the draft-wall identity, and the +2.7398524525334977%
k3x price.

**CPU proof of the export identity:** the k3 state engine (every cancellation cut, 68 guard refusals, 2 detecting negative
controls) run for k3x with GNU and Intel and for k3trims with GNU: the canonical transcripts, which hash every rank-0
allocation and the exported shared slot after every step, are identical to each other and to packet188's retained
k3/k3trims transcript (`d451302d954f…`), while the counters show k3x ran only copy-engine exports and k3trims only kernel
ones. The two-rank five-layer miniature ran V3/k3x/V3/k3x/V3 in both start orders (44 requests) against a fresh
production-layout reference: tokens, 120 fixtures, proposals, draft and target state all equal.

## Device design (lane B, about 14 min)

Rows (row 1 depends on row 0; watchdog 3600 s each):

0. k3x smoke (12 × 64 + incident64, exact, first-request data proof), ~313 s;
1. one load V3 / k3x / V3 / k3x / V3 (12 × 128 + incident64 each), ~480 s.

No fresh V3 row: packet188 row 1 is the fresh reference (−0.05% vs the in-load V3 views of the same storage).

Memory is packet188's: rank 0 31,374,119,922 B (headroom 838,134,798 B), rank 1 31,581,735,626 B; host admission
108,797,048,558 B + 1 GiB.

## Gates

All passed (receipts under `v5/evidence/`): build; production-shape startup (8 startups, 8 dual-rank loads, V3 and k3
identity with packet188, 22 native refusals per run); k3x state + export identity; controller; admission; analysis (8 + 3 +
13 tests, real inputs pinned in place); safety, exec limits, loader; seal; package_rows (2 rows); entry, launch limits,
worker, report; private-copy plan `--lane B` and rehearsal; pin guard (1,109 pins, 0 cross-packet mutable);
final_checks `--ready` (READY written last). Root free stayed above 29 GB; the build directory is 65 MB.

## Mistakes caught during preparation

* **The counters contradicted "k3trims is packet188 byte for byte".** The first state-gate run showed one copy-engine
  export under `boundary_export=kernel`: with retained fixtures (`captured_count > 0`) packet188 skipped the folded readback
  and fell to `e.readback`, which its kio routing turned into a `kio_readback`; my first cut forced that fallback onto the
  copy engine. Fix: the fallback follows the key (`copy_engine = !export_kernel`), so `kernel` is packet188's path in both
  branches and the counters count paths, not branches. Device rows never retain fixtures, so no device behaviour was at
  stake; the proof is cleaner.
* **The identity rewrite missed the hyphenated schema literal.** `s188_decision` → `s189_decision` left
  `packet188.s188-decision.v1` in the compare module's PENDING record. Caught by a grep for `s188-decision`; the copy
  receipt documents the rewrites.
* **A null-candidate test asserted exact zero.** With the V3 views 0/2 as the candidate against the mean of 0/2/4 the hit
  saving is −0.002 ms (view jitter), not 0; the test now bounds it at 0.01 ms and still requires the hit-saving and trims
  kill rules to fire.
* **Stale lineages from the copy.** packet188's `k3`, `k3kio`, `k3prep` lineage directories and its three row configs came
  with the copy; they were removed before `make_lineages.py` wrote the 19-key selections, so the seal closure holds only
  registered lineages.

## Device result (2026-10-22, lane B window 21:17-21:32 UTC, unit lanequeue-B36): WIN, chain rule met

| Row | Content | Rates (tok/s, class-balanced) | Exact |
| --- | --- | --- | --- |
| 0 | k3x smoke, 12 x 64 + incident64 | smoke, no verdict (281 s); boundary 1.48 ms/cycle, export 0.054 ms | 13/13, draft proposals identical, timing-data proof passed |
| 1 | one load, V3 / k3x / V3 / k3x / V3 (k3 storage) | 60.615 / **62.242** / 60.444 / **62.225** / 60.498 | every view 13/13 exact, draft proposals and acceptance identical |

Fresh V3 reference: packet188 row 1, 60.505 (pinned in place, sha `4ff1ec14…`). `s189_decision`: **screen winner and chain
rule met**: the slower k3x view is +2.66 % over the fastest V3 view (bar +2 %) and above 61.873 (1.02 x the record); V3 drift
0.28 %; fresh vs in-load V3 +0.01 %. No kill rule fired: handoff_export 0.053 ms (bar 0.10), boundary_total 1.481 ms (bar 1.60),
k3 hit saving 0.530 ms (bar 0.35), boundary over the draft wall on 0 % of hits (bar 10 %), A trim 0.141 ms (bar 0.105).

Hit means (ms, V3 -> k3x): A 12.096 -> 11.955, B 12.432 -> 11.923, Bd 1.030 -> 1.481, draft wall D 1.587 -> 1.532, elapsed
**14.062 -> 13.531**; misses 25.770 -> 25.569. Rank 1 binds 26 % of hits (was 100 %); the boundary trails the draft wall by
0.05 ms, so the two ranks and the draft are now balanced to within 0.1 ms, as lever synthesis 3 predicted (+2.74 % priced,
+2.66 % measured against the fastest V3 view, +2.9 % against the mean).

The export fix is visible directly: packet188's k3trims boundary was 2.005 ms (export 0.592); k3x's is 1.481 ms (export
0.053) for the same 20,480 bytes.

Next: packet190 record bundle (packet187's eleven-window chain on cards 0+1 with the k3x selection, packet189's engine,
the k3 memory plan and host floor), then submission if WS128 beats 60.659520.

Window receipts: `lineage/window-20261022/` in the packet. Endpoints restored as `*-20261022-restore13`; PAUSE-A untouched,
PAUSE-B re-armed.
