# SPEED5 closeout: admitted 23/25 target split

2026-10-15. Applied the design patch from `36e59bd10` over the SPEED4 runtime
(`eabc13242`). The coordinator stopped the queue before these edits. CPU
qualification is complete; SPEED5 device exactness and speed remain pending.
The coordinator reports SPEED4 passed both pairs; its 24/24 dr0 class-balanced
38.1185 was within noise of the frozen SPEED3 record. No prior result is replaced.

## Configuration and scope

`--target-split 23 --draft-rank 1 --context 4096` selects 23 target layers on
rank 0, 25 on rank 1, and the official draft on rank 1. The chain helper accepts
23 as its sixth argument. The new identity is required in every prerequisite.
At 4K, free allocation capacity is 7,636,189,332 bytes on rank 0 and
1,858,131,808 on rank 1: **341.54 MiB above the unchanged 1.5 GB reserve** on
the limiting card. At 32K rank 1 has only 1,314,969,440 bytes free; admission
refuses it before output creation or device admission. The production CLI
independently refuses that context/placement combination.

Every pre-existing configuration and memory row is unchanged: default 22/26 dr0,
default 24/24 dr1, and explicit 24/24 dr0 at 4K. As in the approved design patch,
split23 also has dr0 coverage/admission at 4K/32K, but the requested device arm
and commands below use only dr1 at 4K. Split25 remains unsupported. Explicit
split default output names gain `-s23`/`-s24`; explicitly supplied paths win.

Only option validation and the existing plan boundary selection change in the
compiled closure (`main.cpp`, `rank.hpp`). Arithmetic, selected kernels, dispatch
rules, SPEED2 write-set capture, SPEED3 draft publication, SPEED4 redo restore,
full-state rollback, exactness comparisons and runtime safety checks are retained.
No opcode, kernel layout or shared-mailbox ABI changes.

## Fresh gates and evidence reuse

- **120/120** plan/dispatch rows: both contexts, five configuration families,
  target rank0/rank1, KD and draft plans, both measured dispatches and forced
  fusion dispatch. No model arithmetic or weight bytes in this gate. Per-site
  write bounds and complete redo-bank coverage are checked; the 192-command
  small-FFN saving is retained. [Gate](speed5-plan-gates.json).
- **62/62** mini executions and **52/52** full-state checks, including **four**
  deliberately missing required extents detected by the comparator. Both split23
  placements and both controllers cover hit, miss, MTP, wrong guesses, partial
  cancellation followed by redo, terminal/request boundaries and abandoned redo.
  Mini geometry is 2/2; production 23/25 geometry is the metadata proof above,
  then the coordinator's device suites. [Gate](speed5-snapshot-gates.json).
- **9/9** admission tests, including 32K refusal, refusal before output/device
  contact, unchanged old rows, census bounds and prerequisite split identity.
  [Gate](speed5-admission-gates.json).
- Source/evidence binding: fixture delta **9/9**, seal amendment **16/16**, audit
  mutation **8/8**, seal binding **45/45**. Final detached admission **156/156**
  (152 window branches, three input-suite checks and the seal contract), with
  every launcher blocked and every simulated window failed/unexecuted. The
  real fault latch is unchanged. [Binding](window-seal-binding.json).

The first seal-binding unit run found the design patch's mock fixture still
listed 108 checks. The fixture now includes the 48 added split23 checks; the
runtime checker was not weakened. The failed log is preserved at
[evidence/speed5/initial-test_seal45_bindings.log](evidence/speed5/initial-test_seal45_bindings.log).
The finalizer is idempotent when appending its written reuse justification.
No compiled-source correction or additional rebuild was needed for this test fix.

Named extension: `packet45.speed5.explicit-split23.2026-10-15`, under
`packet45.fix6.device-oracle-authority.2026-10-15`. It pins the exact changed
source set and requires fresh plan, mini and admission receipts. Existing
real-model execution evidence remains historical; no real-model CPU suite or
compiler matrix was rerun. W2m, WS, WSs and WS128x against the immutable
arithmetic-v2-detmath oracle remain the real-model exactness authority. Any speed
publication must cite their passing current-identity device receipts.

GNU rebuilt in 33.59 s, device in 40.73 s, and required ASAN in 105.62 s.
ASAN provenance is forced by `seal_context.py:83`. Builds used at most two jobs,
nice 19, ionice 3, cores 4–15,20–31 and OMP_NUM_THREADS=2. The Intel host build
was reused under the amendment. No device binary was executed. The seal binds
**49 gate receipts and 41 artifacts**; older counts in it explicitly remain
historical evidence, not fresh SPEED5 tests.

## Disk and retained artifacts

Root had 27.32 GB free at the start and remained above 27.27 GB at every check;
the final value is recorded in [storage-closeout.json](evidence/speed5/storage-closeout.json).
This preserves the owner's 22 GB combined floor/reserve/buffer requirement.
Mini case scratch was hash-archived and removed per case; its empty parent was
removed. The metadata proof executable/source (836,809 bytes total) remains
because the seal directly hashes it. The 1.26 MB plan gate is retained intact
for its 120 checked rows; rerun `speed5_plan_gate.py` to regenerate it. The 2.02 MB
snapshot gate retains complete per-case state/event evidence for the comparator
and negative controls; exact historical bytes live in this commit, while a fresh
`speed5_snapshot_gate.py` run requires a new seal. The plan gate's duplicate
row-only output was compressed with a verified byte-for-byte round trip before
removing the raw copy. [Retention receipt](evidence/speed5/plan-sweep-retention.json).
No `build/results-*` symlink or target, `build/incident-*`, `build/speed3-*`, or
`build/speed4-*` was modified. No fault latch was cleared.

## Coordinator commands

Run from the repository root in the coordinator's admitted nice-0 systemd unit,
on its device-window cores 0–3,16–19, with the approved LD_LIBRARY_PATH. These
commands are supplied only; this repair session did not run them. The helper ends
at WSs. Run each matching WS128x/WS128 pair after that pair's chain passes. The
two card pairs have distinct fresh output paths.

```bash
P=experiments/own-xpu-runtime/stage2/packet45-merged3
SUITE=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
A="$P/build/speed5-c4096-dr1-s23-cards01-gpu"
B="$P/build/speed5-c4096-dr1-s23-cards23-gpu"
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 0 4096 1 "$SUITE" "$A" 23
PACKET45_DIAGNOSTIC_UNSEALED=0 bash "$P/coordinator_windows.sh" 2 4096 1 "$SUITE" "$B" 23

speed5_suite_pair() {
  local out=$1 card=$2
  local common=(ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" OMP_NUM_THREADS=2
    python3 -B "$P/window.py" --authorized-device-window
    --card "$card" --context 4096 --draft-rank 1 --target-split 23
    --k0 "$out/K0/window.json" --k1a "$out/K1a/window.json"
    --k1b "$out/K1b/window.json" --k2 "$out/K2/window.json"
    --w0p "$out/W0p/window.json" --kd "$out/KD/window.json"
    --dispatch "$out/K2/run0/dispatch-measured.json"
    --suite-manifest "$SUITE" --controller native --repeat 1)
  "${common[@]}" --window WS128x --output "$out/WS128x" --retain-steps 1-8,97-104 || return
  "${common[@]}" --window WS128 --output "$out/WS128" --retain-steps none \
    --exactness-window "$out/WS128x/window.json"
}
speed5_suite_pair "$A" 0
speed5_suite_pair "$B" 2
```

The design forecast is about 0.84 ms/hit and 1.55 ms/miss saved versus the
24/24 dr1 SPEED3 calibration, with substantial layer-cost uncertainty. It is
not a measured SPEED5 speed claim. Both pair runs and the coordinator's matched
confirmation determine adoption; keep the twelve cold prompts and all oracle
comparisons unchanged. [Design and uncertainty](../../../../notes/2026-10-15-p45-split-sweep-design.md).

## Seal and device identity

Fifteen rebuilt hashes changed: five GNU, five device and five ASAN. All fifteen
were linked after the last compiled-source edit. [Artifact comparison](evidence/speed5/artifact-identity.json).

Device `own-rt-iq3`: `1523e02958ecc14f96407a7d788790078fa7ab00a98604e377818ab9c6ed1fae`.
Device binaries changed; arithmetic and ABI did not.

| Seal artifact | SHA256 |
|---|---|
| build-receipt.json | `14123110115001cbd74e3f6d21a7bd556607f45827d0761b4806854b85bd28b4` |
| cpu-tests.json | `1aa7b337738c5ee5f5b8293a099ef340a7772861c89d55392ac0f3245dec646e` |
| seal6-amendment.json | `26ae53a136b159c39356912850fb8620a917bc07876409071f9bfc59041daad0` |
| window-seal-admission-gates.json | `574e84ea95cca43e95b95679a17b1f438ed46bb41242029cf40a0ede2d0d07a0` |
| window-seal-binding.json | `62170125412c20dc337dd9749f57987c5c4113f4e6f50b5131cbc481d02b40ab` |
