# packet179 pin fix (2026-10-21)

The packet was committed READY-FOR-DEVICE in `4250d39d`, but the lane queue's
pin guard (`ops/lane-queue/pin_guard.py`) refused both proposal rows before
launch: **123 cross-packet mutable pins**. `plan-after-ready-refused.log` is
the real planner's output against a scratch copy of the proposal.

## Why the earlier plan passed

`check_queue_rows.py` ran after `package_rows.py` (seal 09:59:49, plan
09:59:59), but before `final_checks.py --ready`. The pin guard follows hash
links from `READY-FOR-DEVICE.json` (`checks` map) into
`evidence/native-sequence.json` and `evidence/checkpoint-probe.json`, so those
receipts' pins only entered the closure when READY was written (10:00:19).
`seal.json` does not link the evidence receipts.

## What was refused

1. `native-sequence.json` `sources_sha256`: 92 headers under
   `packet163-full-gate/one-card/native-source/...` and
   `packet163-full-gate/one-card/build/preparation163/{fixture.cpp,probe-main.cpp}`.
   The probe compiled packet163's preparation sources, whose absolute includes
   point into packet163's native-source tree.
2. `checkpoint-probe.json` `ancestor_objects_sha256`: 29 packet58aj gnu-host
   objects under `frozen-inputs/.../build/gnu-host/CMakeFiles/` are symlinks
   into `packet58aj-onecard-resident/build/inherited-objects/`, so the guard's
   parent-binary exception does not apply (the 4 real `build/gnu-host/*.o`
   files did pass).

## Fix

- `native_sequence_probe.py`: byte-identical copies of packet163's
  `build/preparation163/{probe-main.cpp,mock_device.hpp,fixture.cpp}` are kept
  in `one-card/lineage-inputs/preparation163/` (sha256 asserted equal to
  packet163 on each run: `61442ae85ac935ef...`, `cc7676e76ab44690...`,
  `26240bbc175f3d5d...`). The build copies redirect the absolute include root
  `packet163-full-gate/one-card/native-source` to this packet's
  `one-card/native-source`, and the link objects to this packet's
  `build/objects` (byte-identical to packet163's; asserted for each linked object).
  Every compiled dependency under `native-source` is asserted equal to
  packet163's copy modulo that path string. The Landlock grant no longer
  includes any packet163 path.
- `checkpoint_probe.py`: the 33 ancestor objects are copied (dereferenced) to
  `one-card/build/gnu-host-ancestor/<path under packet58aj>` and linked from
  there in the same order. Each is asserted equal to its pin in
  `packet58aj-onecard-resident/build-receipt.json` `sources`. These ~19 MB
  are committed because the receipt pins them and the guard re-hashes them at
  admission.
- `check_queue_rows.py` refuses a missing or stale `seal.json`, a private
  plan queue that differs from the proposal, and any existing READY (a stale
  READY's links would join the planner's closure; the pre-fix READY files
  were withdrawn after being copied here). `final_checks.py --ready` runs
  the pin guard on the proposal rows after writing READY, and removes READY
  again if the guard refuses.

## Outcome before resealing

- Native sequence: same 13 requests, 14 resets, 56 sensor-stream hashes and
  probe stdout as before. The probe binary differs only through the path
  strings.
- Checkpoint probe: same compile argv, object hashes, link order, probe
  binary sha256 (`2c519746707cdf54...`), round trip, 6 refusals and per-run
  return codes/output tails.
- The device binary `build/device/own-rt-iq3` (`8d18538475e00200...`), the
  kernel objects and `evidence/build.json` were not touched.

Files here are the pre-fix receipts: `native-sequence.json`,
`native-sequence-progress.json`, `checkpoint-probe.json`, `seal.json`,
one-card `READY-FOR-DEVICE.json`, packet-root `root-READY-FOR-DEVICE.json`,
and `plan-one-A.log` (the plan that passed before READY existed).
