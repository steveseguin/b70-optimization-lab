# SPEED3 closeout: draft publication and independent layer split

2026-10-15. CPU implementation and qualification only. The coordinator stopped
the device queue before this repair. No device binary, device discovery, model
weight read, real-model CPU suite or compiler matrix ran here. Archived
`build/results-*` and `build/incident-*` were left untouched.

The two requested packet-46 changes are implemented in packet45-merged3.
Device speed and real-model exactness remain pending the coordinator's windows.

## Publication and event ownership

`DraftRuntime::poll_result()` publishes only after the ordered error/token
readback completes. It no longer copies `Engine::pending` or queries every
compute event's timestamps before publication. `Engine::drain()` retains sole
ownership of those events, accounts each exactly once, checks the event-group
shape and four-second submission limit, then retires completed events. An error
or over-duration event retains the existing error/lifetime behavior.

The publication record's wire layout remains 40 bytes. Its GPU-duration field
uses -1 for deferred accounting; final request receipts expose `null` and
`draft_gpu_timing_deferred: true`, rather than claiming a zero GPU duration.
The real GPU time remains accounted in the owning engine's normal drain.

`progress_pending` avoids invoking an inactive callback around each launch and
in native progress polling. The wait loop still polls cancellation, cooperative
stop, poison and deadlines, even when the installed callback is inactive.
Both draft placements use this code. Arithmetic, kernel selection, immutable
oracles, full-state comparisons and the CopyEngine 128 MiB guard are unchanged.

The checked CPU extraction of the actual publication/drain methods passes
16 checks: no premature publication, zero timing queries at publication, three
queries for three events at drain, no repeat accounting/retirement, both
placements, sticky errors, malformed groups and two over-four-second negative
controls. See [event gate](speed3-event-gates.json).

## Explicit split and admission

`--target-split 0` preserves the placement default. `--target-split 24` selects
the 24-layer boundary. The chain helper forwards its optional **sixth argument**
to every window. Split is part of each window's sealed identity, prerequisite
identity and exactness companion comparison; mixing split receipts is refused.

| Configuration | Context | Rank-0 free bytes | Admission |
|---|---:|---:|---|
| Existing 22/26, draft rank 0 | 256 / 4096 / 32768 | Original projections retained | Unchanged |
| Existing 24/24, draft rank 1 | 256 / 4096 / 32768 | Original projections retained | Unchanged |
| New 24/24, draft rank 0 | 4096 | 2,316,749,746 (2,209.43 MiB) | Pass; 816,749,746 B above reserve |
| New 24/24, draft rank 0 | 32768 | 1,434,110,898 (1,367.68 MiB) | Refuse; 65,889,102 B below reserve |

The 32K row is a rejected projection, never an admitted launch. The wrapper
refuses it before host/device admission or output creation. The non-mini binary
also refuses that configuration outside 4096. Tiny mini fixtures exercise the
new selector at their 256 capacity without granting production admission.

The old two placement projections compare byte for byte with the preceding
seal. Actual allocation census checks still run. The SPEED2 write-set snapshot,
full-state rollback contract, small-FFN composition and all other selected
kernels are retained. The plan sweep still proves the 192 extra target commands
are absent, with 48 small-FFN groups across the two target ranks.

## Gates and evidence reuse

* **72/72 production metadata plan/dispatch rows**: two contexts, three split /
  placement configurations, target ranks 0 and 1, KD and draft plans, both
  device-measured dispatches and the all-fusions-enabled dispatch. The refused
  32K split is constructed only as metadata. No weights or arithmetic run.
* **63 mini executions, 54 full-state checks, six required-extent negative
  controls**: both controllers, all three configurations, hit, miss, correct /
  wrong MTP, terminal cancellation at four launch cuts, request boundary and
  the 32-to-64 launch-capacity transition. Every deliberate missing backup is
  detected. Mini geometry has four layers and a 2/2 boundary; the production
  22/26 versus 24/24 topology is covered by the metadata sweep, not claimed as
  a miniature production-model run.
* **16 event checks**, **10 admission checks**, plus the retained safety tests:
  9 fixture-reuse, 13 amendment, 8 audit mutation and 45 seal-binding tests.
* Final seal consumes **43 gate receipts**. Historical evidence remains bound
  to its original binaries. Fresh SPEED3 receipts bind the changed artifacts.

The exact amendment is
`packet45.speed3.single-profile-and-explicit-target-split.2026-10-15`, extending
the owner's seal-6 directive. It pins precisely `main.cpp`, `rank.hpp`,
`mtp.hpp` and the split/admission/controller Python and shell changes, plus the
qualification changes. Other production changes still refuse evidence reuse.
Passing same-build W2m, WS, WSs and WS128x oracle windows are required before
publication of speed. Historical CPU cases do not qualify this binary's
real-model exactness.

Only the changed model-entry targets were rebuilt in GNU, device and ASAN
modes, at two compile jobs. ASAN was mechanically required by
`seal_context.py:83`; it took 106.7 seconds. No icpx-host/compiler matrix or
real-model CPU gate was rerun. The first short mini attempt was invalidated by
a final wait-loop safety correction; its log/archives are retained as
`evidence/speed3/initial-*`. The full fresh gate ran after the final rebuild.

Evidence lives under [evidence/speed3](evidence/speed3), with source-bound mini
archives under `evidence/scratch-*-r*s*-*.jsonl.gz`. These retain the actual
small-model state comparisons and negative controls; rerunning the gates can
recreate their logical contents, but their original bytes are retained here.
The 2,562,935-byte `speed3-snapshot-gates.json` is intentionally retained: the
seal checks each owner's complete buffer hashes, cancellation state and archive
binding. `python3 -B speed3_snapshot_gate.py` recreates the logical evidence
under the documented CPU limits; Git retains the exact original receipt bytes.

## Forecast, not a speed result

[The accepted analysis](../../../../notes/2026-10-15-p45-hit-cycle-gap.md) gives
the attribution and A/B design. The fresh read-only check of SPEED2 receipts is
[prechange-handoff.json](evidence/speed3/prechange-handoff.json): 931 steady hits
and 255 misses per placement, positions >=100. Draft completion-to-next-HALF
send is 0.496 ms on rank-0 hits. With draft rank 1, HALF send-to-worker-receive
is 0.492 ms on hits, versus 0.010 ms on misses. The callback runs on that worker;
the controller also waits for its publication before rank-0 speculation.
These enclosing delays include work besides timestamp queries.

| Coordinator configuration | Predicted saving per hit | Predicted saving per miss | Basis |
|---|---:|---:|---|
| Cards 0–1: new 24/24, draft rank 0 | 1.6–2.1 ms | 0.1–0.8 ms | Publication 0.4–0.5 ms plus split 1.2–1.6 ms hit / -0.3 to +0.3 ms miss |
| Cards 2–3: existing 24/24, draft rank 1 | 0.4–0.5 ms | 0–0.1 ms directly credited | Earlier publication/start on hits; on misses its first profiling pass overlaps rank-0 redo |
| Optional diagnostic control: existing 22/26, draft rank 0 | 0.4–0.5 ms | 0.4–0.5 ms | Publication change alone |

Savings from removing inactive callbacks are unmeasured and receive no separate
credit. No second-pass saving is counted: the ordinary profiling drain remains.
The split estimate is a per-layer planning estimate; transfer/overlap effects
may change it. Compare the coordinator's exact token/guess streams and measured
phase envelopes before treating any forecast as a speed improvement.

## Exact coordinator commands

From repository root, inside the existing admitted **nice-0 systemd user
unit**, using the coordinator's device cores 0-3,16-19 and library environment.
These commands are supplied for the coordinator; none were executed here.
`PACKET45_DIAGNOSTIC_UNSEALED` must be unset or 0 for qualifying chains.

```bash
P=experiments/own-xpu-runtime/stage2/packet45-merged3
SUITE=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
A="$P/build/speed3-c4096-dr0-s24-gpu"
B="$P/build/speed3-c4096-dr1-gpu"

PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 0 4096 0 "$SUITE" "$A" 24
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 2 4096 1 "$SUITE" "$B" 0
```

After each corresponding chain passes, these are the standalone exactness and
speed commands. The function expands the complete window command identically
for each pair; the last two arguments select the draft owner and target split.

```bash
speed3_suite_pair() {
  local out=$1 card=$2 draft=$3 split=$4
  local common=(ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH"
    python3 -B "$P/window.py" --authorized-device-window
    --card "$card" --context 4096 --draft-rank "$draft" --target-split "$split"
    --k0 "$out/K0/window.json" --k1a "$out/K1a/window.json"
    --k1b "$out/K1b/window.json" --k2 "$out/K2/window.json"
    --w0p "$out/W0p/window.json" --kd "$out/KD/window.json"
    --dispatch "$out/K2/run0/dispatch-measured.json"
    --suite-manifest "$SUITE" --controller native --repeat 1)
  "${common[@]}" --window WS128x --output "$out/WS128x" --retain-steps 1-8,97-104 || return
  "${common[@]}" --window WS128 --output "$out/WS128" --retain-steps none \
    --exactness-window "$out/WS128x/window.json"
}
speed3_suite_pair "$A" 0 0 24
speed3_suite_pair "$B" 2 1 0
```

The helper stops at WSs; the two standalone windows above are still necessary.
The new split is selected explicitly with `24`; omitting the sixth helper
argument retains the previous placement-dependent split.

## Artifact identity

Five device executable hashes change because they link the model entry with
the host-side publication/split repair. Five GNU and five ASAN hashes change
as well; all other recorded artifacts are unchanged. Kernel arithmetic and
kernel/wire ABI are unchanged; CLI and receipt identity gain `target_split`.
The complete binary list is [BINARY-HASHES.md](BINARY-HASHES.md).

`device/own-rt-iq3`:
`724e4dee068d38c561a97e0a2814c470b7f07cc9e5ec24f0297ebd904aed8fc8`.

Final detached admission passed **108/108** checks: 104 window branches plus
three immutable-input admissions and the final seal contract. Every launcher
was blocked and every simulated window remained unexecuted/nonpassing.

| Seal artifact | SHA256 |
|---|---|
| build-receipt.json | `8460585fe53879223066a5d54799c9f105c73002adfc09fc9a743ceaee7e3fa8` |
| cpu-tests.json | `5ac961e57b769e526ee0eaf6f9fb7acaa3fe785194b1c69c9cab6c3c54fa3eb6` |
| seal6-amendment.json | `4ce5d1ff82a341bc3c208fbba6a747ea6182ea75c65b78f82e503738367a1907` |
| window-seal-admission-gates.json | `00115324ad0a0614860fbc33f4500d521ce562ddbb7aca81aedde43f428e5dbf` |
| window-seal-binding.json | `4f48ed5910f990790dafecf9b2876bce7e9bd632e014e74b3d295eb82c9b48eb` |

