# GPU-first fix loop for screens

Owner instruction for experiments: **build → one CPU byte-identity fixture for
the changed class → seal → screen**. Do not rerun multi-hour all-class CPU
qualification before every idea's first device contact. The coordinator still
owns device admission. This shortened path applies to diagnostic screens;
it does not replace the full chain required for a record or submission.

1. Make a separate candidate source directory on `main`; preserve sealed
   packets. Build only the changed objects and the compatible engine binary,
   serially and within the admitted storage/memory budget. Use nice19, cores
   4–15/20–31 and `python3 -B` for CPU helpers. Bind compiler flags, command and
   source hashes in its build receipt. No model payload reads, large pins or
   device discovery are CPU preparation.
2. Run one small CPU fixture that covers the changed kernel/engine class.
   Compare all output bytes to the unchanged class's CPU reference, including
   state bytes when the change affects state or request reset. Keep the raw
   expected and actual bytes, command and receipt. A mathematical/arithmetic
   change needs its own oracle decision; it cannot pass by loosening equality.
3. Seal the candidate's source/build identity, exact-byte fixture, binary,
   dispatch, selection and memory plan. Existing packet 56 and 58 seals are
   consumed directly; do not regenerate them for a screen.
4. Run one admitted screen. Failure is evidence for the next fix. A promising
   result proceeds to the full sealed chain and its fresh-process correctness
   and speed gates. No screen automatically queues a chain or submits anything.

For a new candidate, `seal.py` accepts the following small, explicit contracts.
Paths in `sources` are repository-relative; artifact and gate paths are
candidate-relative. `passed: true` alone is insufficient: the helper rehashes
the sources, compiled artifacts and both byte files before writing a new seal.

The build receipt contains `passed: true`, `device_executed: false`, `sources`
(or `sources_sha256`) mapping source paths to SHA256, and `artifacts` (or
`binaries`) mapping native artifact paths to SHA256. Include the build recipe
and compiler/command receipt in that source closure. These fields are already
provided by the packet 58 builder. The byte-fixture receipt is:

```json
{
  "schema": "own-runtime.screen.byte-fixture.v1",
  "passed": true,
  "device_executed": false,
  "changed_class": "the class changed by this candidate",
  "command": ["the", "actual", "CPU", "fixture", "command"],
  "build_receipt_sha256": "SHA256 of the candidate build receipt",
  "sources": {"repo/relative/reference-and-fixture-source": "SHA256"},
  "expected": {"path": "fixture/expected.bin", "sha256": "SHA256"},
  "actual": {"path": "fixture/actual.bin", "sha256": "the same SHA256"}
}
```

Run from the repository root, with `CANDIDATE` set to the new candidate folder:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage2/screen/seal.py \
  --profile tp2 --lineage "$CANDIDATE" \
  --build-receipt "$CANDIDATE/build-device-receipt.json" \
  --fixture "$CANDIDATE/fixture/receipt.json" \
  --binary "$CANDIDATE/build/device/own-rt-iq3" \
  --dispatch "$CANDIDATE/dispatch-speed6.json" \
  --output "$CANDIDATE/screen-seal.json"
```

Then use the documented screen command with `--lineage "$CANDIDATE"` and
`--seal "$CANDIDATE/screen-seal.json"`. Choose `--profile onecard` for a
packet 58 ABI candidate. A screen seal is explicitly diagnostic and cannot
stand in for a full-chain seal. Changing the memory envelope or protocol is
outside these profiles and requires updating their safety checks first.
