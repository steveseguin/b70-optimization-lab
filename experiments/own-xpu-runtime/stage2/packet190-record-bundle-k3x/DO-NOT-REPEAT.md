# Packet190 boundaries (k3x record chain)

- **Do not run the k3 storage through the four-layer chain miniature.** `rank0_layers=0-26` cannot be hosted by the
  default `--mini`; the transport decode must use packet188/189's five-layer `--pipeline-mini5` for BOTH the
  bundle-8 reference and k3x (120 fixtures). The first transport run without it reported "k3x differs: fixtures"
  (a harness-shape artefact, not an arithmetic difference).
- **Do not let KD's layer-streaming reference carry the k3-storage keys.** `engine_bracket.hpp` refuses
  `kernel_io`/`rank0_prepare`/`boundary_export` outside `rank0_layers=0-26` ("packet188 trims require the k3
  storage"). Project them by removal (`kd_reference.TARGET_ONLY_REMOVED`), together with `rank0_layers=0-23`,
  `boundary=none`, `snapshot_host=production`; the reference selection has 16 keys.
- **Do not compile the preparation probe after `guard_layout190.py` without the lineage-inputs exclusion.**
  `build_engine.limits()` counted the 202 MB of hard links under `lineage-inputs/link-targets/build/` as build
  bytes and refused; those links add no disk bytes. Packet187 avoided this by ordering, packet190 by the exclusion.
- **Do not use the ledger's full-precision record as the hard floor.** 60.659520 (the coordinator's figure) is 8e-8
  ABOVE 60.65951991975228; the floor is the rounded figure (as packet187 used 58.798109), so a WS128 of exactly
  60.659520 is refused.
- **Do not run a v5 engine through packet136's chain transport size** (packet155's W0p `shared extent`);
  `transport_gate.py` keeps the real canary and the old-size negative.
- **Do not seal ops files, packet189/188 evidence or shared scripts directly into the stage packet** (cross-packet
  mutable pins). Pin packet copies (`orchestration-snapshot/`, `lineage-inputs/`) and require live equality at
  launch; keep the bracket evidence map in the gate receipt (READY carries only its digest).
- **Do not treat the packet189 screen as a record.** Only the fresh chain's exact WS128 above 60.659520 can be
  submitted.
- **Do not rehearse `--server-dry-run` or read the LocalMaxxing key during preparation.** Coordinator's step.
- **Do not launch below the disk margin.** The launcher needs 25 GB + 3,324,718,708 B free; at seal time root free
  was ~28.4 GB (margin ~100 MB). Free space before the chain if anything else has been written.

---

# Inherited boundaries (packet187 and packet124-136, historical)

# Packet187 boundaries (V3 record chain)

- Do not run a v5 engine through packet136's chain transport size (3*SLOT+4096 vs 4*SLOT+4096+64).
- Do not let KD's layer-streaming reference inherit V3 keys; project `rank0_layers`, `boundary`, `snapshot_host`.
- Do not seal ops files, packet186 evidence or shared scripts directly into the stage packet (3,925 cross-packet
  mutable pins in packet155's copy). Pin packet copies and require live equality at launch.
- Do not key seal maps by bare leaf names; use full packet49-oracle paths or packet-root hard links.
- Do not treat the packet186 screen as a record.
- Do not rehearse `--server-dry-run` or read the LocalMaxxing key during preparation.

# Packet124 boundaries

- BASE is exactly bundle7; one sealed composition. Never retune N=80,128.
- Never edit packet118 or pin its mutable build receipt, ready file or chain output.
- A drain-only copy claims no speed gain; read the original bundle7 smoke and
  both complete matched brackets (each >=1% over both controls, all exact).
- A future runtime dimension cannot inherit those device results. It needs its
  micro gates, new CPU qualification and its own matched composite gate.
- The old drain sleep fails if time advances after the loop condition. Keep
  `test_drain_fix.py` and both recursive checker scans as readiness gates.
- Native exec requires unlimited address space and unchanged inherited limits.
  CPU resource caps belong only to explicit CPU entry processes.
- Do not pause the other lane to compensate for an unfixed copy. Fail closed.
  Normal whole-host timing reservations and fault/VRAM gates stay unchanged.
- Full model device quality and strict512 are not established by CPU checks.

## Packet124b K2 projection closeout

- Do not derive a strict three-key kernel selection by excluding known bundle
  dimensions. Bundle7 adds `other_fusion`, which escaped the old exclusion list.
  Explicitly select the three required keys; missing keys still fail.
- Do not accept startup-only coverage as Python argument/postprocessing coverage.
  Require the new orchestration all-window gate, its original-code negative
  control, the strict three-key tests and the full retained K2 timing replay.
- K2 measures inherited kernels only. Neither their mapped aliases nor the
  repaired Python projection establish a speed claim for the combined kernels.

## Packet124c oracle/copy closeout

- Never dereference the packet49 oracle authority while copying a bundle.
  Preserve directory and file symlinks, and audit both packet103 and packet97.
- Window argv interception alone does not cover queue-side admission. Require
  the real pre-LATE oracle subprocess and whole queue-loop CPU rehearsal.
- Do not redirect shared_oracle.P to conceal a broken bundle-root symlink.
- Keep external-target snapshots for the screen sealer separate from the real
  links; validate both byte identities at chain admission. Do not weaken the
  frozen sealer's repository-boundary check.

## Packet136 active composition rules (override inherited one-composition wording)

- Exactly two views: rollback_state=copy|banks. Bundle7's remaining choices and
  the preregistered 80,128-row prefix are fixed. No suffix-interleave arm.
- Native bank layout is not runtime-switchable in v5. Use the registered v4
  fresh-load C/X/C/X/C pair, both candidates at least +0.5% over every control,
  on each lane, with exact outputs and unchanged per-prompt acceptance counts.
- Require the local composed 12 × 64 smoke. Packet131b B counts only through
  verified identical native selections, binaries, dispatch and memory layout.
- Never put oracle paths in new source maps. Verify original binding and the
  real complete-oracle subprocess; fail unsafe maps during creation and plan.
- CPU preparation is not a speed result. No jobs or live queues were launched
  or changed during preparation. The chain folder must still be fresh.
