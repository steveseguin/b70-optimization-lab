# 2026-10-23: packet194, the exp-diet gate/up kernel in the k3x record engine (CPU preparation only)

Packet: `experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/`. No device work has run. Nothing is queued.
Screen only; never a record claim.

## Why

packet193 (lane B, card 2, 2026-10-23 04:27 UTC) measured its exact gate/up instruction diet `exp-diet` at 57.92 vs 73.85 µs
cold (0.784, both launch orders) and 36.0–36.2 vs 46.77 µs warm (0.77), byte-identical on every claimed stratum on device.
Coordinator ruling (quoted in the README): integrate `exp-diet` into the k3x record engine behind an in-load key
`expert_gateup=production|diet`, prove engine-level exactness on CPU, screen on lane B with one load
k3x / k3x+diet / k3x / k3x+diet / k3x; screen bar +0.5 %, chain bar +2 % AND ≥ 63.592 tok/s; kill rules inexact /
proposals / acceptance / k3x drift > 0.5 % / per-layer gate/up saving < 5 µs.

## What was built

* Packet189's harness copied with identity rewrites (2,217 files; history hard-linked). The packet193 header
  `p193_diet.hpp` copied byte for byte (sha256 `aab37609…`) into the engine's checked tree.
* `p193diet::GateUp` registered as Arm 13 beside the production `p90exp::Kernel<IQ2_S,2560,64,false,true>` in
  `p49d_expert_submit.cpp`; a six-argument `p49d::expert(…, experts, gateup)` whose `production` is the unchanged
  five-argument record dispatch; `diet` on any non-halfcache gate/up layout refuses. The key is a k3-storage key (20-key
  selections; the 19-key record selection `c5443bbf…` loads unchanged = production), switchable in-load with the other
  execution keys; `prepare_commands` passes it per expert site and counts diet sites.
* Four TUs rebuilt (entry-main, p49d_submit, s1_submit, p49d_expert_submit) over 76 pinned parent objects; 0 warnings.
  `v5/p194-native.patch`: +57 / −16 lines in 7 files.

## Exactness proofs (all CPU)

* `kernel_identity.py`: packet103's pinned device `p49d_expert_submit.o` vs the rebuilt one, split per kernel
  (`sycl-post-link -split=kernel`), SPIR-V text: all 25 inherited kernels opcode- and canonically identical (incl. the
  record gate/up and down kernels); exactly 4 kernels added, all `p193diet`.
* `diet_fixture_gate.py`: the real `p49d::expert` with the record selection strings on GNU and Intel host twins:
  packet162b's real layer-0/24 rows and synthetic exp-halfcache banks, 14 strata (normal, partial routes, invalid expert,
  inactive, error-preset, NaN / Inf / subnormal inputs): every byte equal, 0 payload-order rows; six-argument production ==
  five-argument record dispatch; 6 refusals.
* `p194_v5_full_shape.py`: the 20-key k3x load captures exactly packet189's k3-storage capture (and v3 / v3k→k3x-record as
  packet189); the diet views differ only in the kernel of the exp-halfcache `expert_gate_up` sites; census identical (diet
  delta 0 B per rank); 23 native refusals; 10 real-parser startups.
* `k3_state_gate.py`: k3x-record / k3x / k3x-diet (GNU) and k3x-diet (Intel) miniature engines: canonical transcript
  `d451302d…` = packet189's for every run; two-rank five-layer brackets in both start orders equal the reference. The
  miniature has no halfcache layout, so the diet is inert there and counted; at production shape an inert diet refuses.

## Rows (PROPOSAL ONLY) and decision

`ops/lane-queue/proposed-p194-two-card-B.txt`: row 0 `packet194-row0-smoke-k3x-diet-B` (~313 s), row 1
`packet194-row1-bracket-k3x-diet-B` (~476 s), watchdog 3600 s each, host admission 108,797,048,558 B + 1 GiB (unchanged
from packet189; the diet adds 0 B). `s194_decision` tested on packet189 row 1's real k3x views (null: not a winner, the
saving rule fires) and packet190's WS128 chain (reproduces the record 62.345281904743764). Priced: +1.4 % (10.8 µs warm)
to +2.1 % (15.9 µs cold) at +1.32 % per 0.01 ms per GDN layer.

## Deviations from the brief

* The brief's "k3-state proof on the k3x+diet selection": run as asked, but the miniature cannot execute the diet kernel
  (no exp-halfcache layout); the proof shows the key moves no byte (canonical identity) and counts the inert sites; the
  kernel-level engine proof is the dispatch fixture on real rows plus the production-shape launch census. At production
  shape the IQ3_S expert layers (p28 registry kernels) keep their kernel under the diet and are counted as other-layout
  sites; a selected diet with zero exp-halfcache sites refuses.
* The whole rebuilt `p49d_expert_submit.o` cannot be byte-compared with the pinned object (paths in the bundle); the
  per-kernel SPIR-V identity gate replaces that comparison.
* The pinned header brings three undispatched kernels (the dropped candidates and the activation twin) into the device
  image; they add no launch and no allocation.
* `k3trims` is not carried as a lineage (packet188's closed candidate; its CPU gates were packet189's).
* The owner's endpoint-restore window (`window-p193-driver … -restore19`) was active during preparation; the build engine
  tolerates restore windows per the brief and refuses every other active window/lanequeue/packet unit.
* Two preparation mishaps, both harmless to the packet: a `pgrep -f` self-match killed my own shell twice (the memory note
  stands), and one stale build was stopped by pid and redone; every receipt comes from the final serial chain.
