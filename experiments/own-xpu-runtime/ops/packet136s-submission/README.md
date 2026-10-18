# Packet136s submission preparation copy

Packet136's completed chain could not prepare its submission: the original
validator indexed `seal.sources[packet136/oracle/suite_check.py]`, although
packet136 deliberately excludes external oracle symlink paths from that map.
The original raises `KeyError` before creating output.

This directory copies the submission entry points and their local dependencies
from `../packet136-orchestration/`. Original hashes are retained in
[copied-sources.json](copied-sources.json). Only the oracle-checker binding block
in [submission_evidence.py](submission_evidence.py) differs. No sealed packet or
orchestration file is edited or resealed.

If a direct checker source pin exists, it remains mandatory. Otherwise, only
packet136's chain-seal schema may use the fallback. The fallback verifies:

1. The binding file against the packet's sealed source hash and embedded
   `shared_oracle` object, including schema, arithmetic and binary identity.
2. The packet49 oracle build and arithmetic bytes against the shared binding.
   The existing checks also bind these bytes through `oracle_inputs_sha256`
   and the oracle completion receipt.
3. The checker hash in that binding against the checker hash in packet49's
   own sealed oracle build receipt, then against the actual bundled checker.

The unchanged adapter checks that the packet's oracle symlink resolves to
packet49 and validates the live authority files. Saved-bundle replay checks
the same hash chain using only retained evidence bytes. Any missing or changed
link refuses; there is no unchecked hash fallback.

`parent_seal_sha256` is **not** packet124c's current build receipt hash. It
identifies `packet136/lineage-inputs/packet56-chain-input.json`. This fix uses
the permitted packet49 oracle-build binding instead of asserting a false
parent relationship. [audit.json](audit.json) records the inspected hashes.

[test_oracle_binding.py](test_oracle_binding.py) exercises the real finished
chain, reproduces the original exception, verifies the copy, rejects tampered
checker/binding bytes, independently tests the authority-build cross-check,
preserves direct-pin priority and proves every other source byte unchanged.
The final [seven-test log](tests-final.log) passes.

Use only `prepare_submission.py` and `submission.py` for this repair. The
copied adapter/dependencies retain their original bytes and are not a new
orchestration or resealing toolset. Runtime dependencies remain read-only in
the original packet. Preparation requires a fresh output directory.

The [work note](../../../../notes/2026-10-18-own-runtime-packet136s.md) records
the exact commands, local and authenticated server dry-run results, scope,
memory usage and packet139 inspection. **No real submission was performed.**
The label's inherited `20261017` suffix is unchanged; preparation ran October 18.

The generated `prepared-a/evidence.json.gz` is 5,555,101 bytes and must remain
with its result and attestation: replay and payload validation consume its
original receipt bytes. It is evidence, not a cache. Restore exact bytes from
this commit if lost; do not silently regenerate it from subsequently changed
live receipts. The result JSON pins its SHA-256. Raw large KD fixture arrays
retain the original validator's digest-only policy.
