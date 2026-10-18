# Retention

Keep this packet's copied native sources, all links, bindings, generated source
patch, CPU receipts and probe plan. Keep raw device events, both model windows,
state-equality verdicts and fault/drain receipts under evidence/probe-B, within
200 MB. They are ignored for Git until reviewed; do not remove them based on a
summary. No model weights or full mutable-state snapshots are copied to disk.

Keep the failed `evidence/probe-B/` byte-for-byte. Packet141b records its hashes,
original build/seal/readiness receipts, loader reproduction, real-argv traces and
early-exception tests in `evidence/repair141b/`. The repaired attempt uses
`evidence/probe-B-repair141b/`. The analyzer never writes inside an input attempt.

`runtime/libumf.so.1` is an unmodified 321,648-byte Intel UMF 1.1.0 library,
vendored to close the Level Zero adapter's missing dependency without changing
the shared environment or another packet. Its source path/hash and Apache 2.0
with LLVM exceptions license and third-party notices are retained alongside it.
Restore from the exact installed source in `runtime/provenance.json` and verify
the hash. The device binary records it as a needed dependency and carries the
packet-local runtime search path; no global library or setting is changed.

Keep `compiled-sources/` and `compiled-source-snapshots.json`: these are exact
copies of the source bytes named by the compiler receipt, checked before copying.
Original compile paths are provenance, and canonical parent ELF objects remain
immutable build inputs. Historical JSON receipts are gzip archives so the pin
guard cannot mistake old identities for current launch dependencies; each was
decompressed and compared byte-for-byte before its redundant raw copy was removed.

`inputs/incident-retrospective/vocab.bin` is 2,839,437 bytes. Together with the
local plan and identity files it replaces a shared-tree input link without
changing one byte or the suite hash. Restore from
`../suite-inputs-20261012/incident-retrospective/` only after checking the suite's
input hashes. This copy closes a mutable dependency and is required by input
admission; its size is not a reason to discard it. Five root-level aliases point
only inside this packet, so the generic pin reader and input gate hash the same
bundle bytes. All 182 original native/build links are unchanged.

Build outputs are ignored and reproducible by build_engine.py and full_shape.py
against their hash-bound original kernel objects. Parent objects are required
reproduction dependencies, not disposable caches. Copied links are reproduced
by preserve_links.py from symlinks.json. The oracle authority stays external.

`rope.bf16` is 4,194,304 bytes. Retain its exact packet136 bytes because the
owner requested a frozen source copy including runtime constants. It is consumed
by the inherited rope loader and provenance checks. Restore it from
`../packet136-record-bundle/rope.bf16`, verifying `copy-provenance.json`; do not
regenerate or deduplicate it without changing the frozen-copy contract.
Inherited whitespace in p109_route.hpp and the exact prompt is retained on
purpose. The generated unified patch includes an ordinary blank context line.
