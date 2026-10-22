# Pre-fix receipts (pin-guard refusal, 2026-10-21)

These are the receipts packet178 carried at commit 136fce072, kept as
evidence. With them the lane-queue pin guard refused both device rows before
launch: 1056 cross-packet mutable pins.

- `build.json` keyed `relocated_source_sha256` by the original archive member
  paths (other packets' source trees, such as packet103, packet58j and
  packet165). The current receipt keys the same 962 hashes by the in-packet
  relocated path `one-card/native-portable/<member>`. The member name is the
  original repo-relative path, listed in `../portable/native-build.json`.
- `native-sequence.json` (and its progress file) pinned 92 headers in
  packet163's `one-card/native-source` and two files in packet163's
  `build/preparation163`. The probe now compiles against frozen copies in
  `../../lineage-inputs/preparation163` and this packet's own relocated tree
  under `native-portable/`. That tree is byte-identical to packet163's tree
  once the root path is relocated (99 of 99 files). The probe also links this
  packet's portable-rebuild objects instead of packet163's objects. The sensor
  stream hashes match the earlier run exactly.
- `seal.json`, `READY-FOR-DEVICE.json` (one-card) and
  `root-READY-FOR-DEVICE.json` (packet root) are the matching pre-fix seal and
  READY files.

Two more defects came to light during the fix. `evidence/portable-inputs.json`
pinned its vendored files by bare name, which the guard resolves to a missing
file at the packet root; it now uses packet-relative paths. Also, READY (not
the seal) links the evidence receipts, so a plan run before READY cannot see
them. `final_checks.py --ready` now runs the guard after writing READY and
withdraws READY if the guard refuses.

The device binary did not change (sha256 6fa840ab...bf10).

SHA-256 of the copies:

    0b53c7af86679637309abf0d201a5a4050bd1f2cec39950252ba9273dd875149  build.json
    1c939287535610c7a069e2ea110c59c6bb921342a25d86c66924e62eac421ce8  native-sequence.json
    36b288c66fcdb003154528aa1b7f4de59aa60fe7b64d15c4d1ca2a5b08ab1f7c  native-sequence-progress.json
    632ad16c226f0b4179727e1394902f7301ea835763cc73cc60ed99163ce1d68a  READY-FOR-DEVICE.json
    8badcc2edf1fd2283d152b448fa65a09e1fab9d17b952dbfd313f9381d2f475a  root-READY-FOR-DEVICE.json
    fae2643f096bdf817a7216fdf467f1098112fee0e54c6af0bfad8e7782aed34e  seal.json
