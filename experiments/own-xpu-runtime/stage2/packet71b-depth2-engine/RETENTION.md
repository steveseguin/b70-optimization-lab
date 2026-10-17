# Retained inputs and evidence

`packet71-copy.json` records the frozen tracked packet71 inputs before editing.
`packet68c-import.json` is inherited provenance for packet71's original import;
it does not assert the subsequently edited HC header or fixture is unchanged.
The current build receipt and screen seals bind packet71b's actual source bytes.
Copied packet71 fixture/transaction receipts and `milestones/` are historical;
only `fixture/m2-receipt.json` is the new changed-class arithmetic gate.

The copied 4 MiB `rope.bf16` is a pinned target constant needed at build/runtime.
Restore the exact bytes from packet71 and verify the copy manifest. Keep it even
though another packet contains the same data.

The four approximately 3.1 MiB `fixture/{gnu-host,intel-host}-{expected,actual}.bin`
files retain actual independently produced output bytes for both compilers.
They include the previous dense/expert/HC cases plus router outputs and partials
and route outputs, full scratch, sticky controls and untouched input bytes.
Their consumers are `fixture/m2-receipt.json` and both screen seals. Rebuild the
host arithmetic fixtures with `build_engine.py`, then restore with
`batch_cpu_gate.py`; all four SHA256 values must match the receipt. These are
valuable evidence, not generated caches; size/duplicate content is no reason to
discard them. The older 153 KiB expected/actual streams remain copied history.

Build objects, checked-source mirrors and binaries stay ignored; recorded
commands and hashes permit the originating-host rebuild with its verified parent
objects. The build is about 95 MiB. No weights, device outputs, credentials or
host caches are included.

The failed first device compile is retained in `evidence/build-attempt1/`. It
exposed the guard included both directly and via the checked mirror; the new
header guard fixes that. `evidence/seal-attempt1/` retains a refused plan: external
oracle-result symlinks cannot be passed through the generic repository-source
path gate. Those data remain checked by the existing packet49 binding and the
worker import audit; no path check was weakened. Successful receipts are at the
packet root and under `evidence/` and `screen/`.
