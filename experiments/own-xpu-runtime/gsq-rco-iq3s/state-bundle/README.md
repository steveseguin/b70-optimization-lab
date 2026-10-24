# Lossless target-state evidence bundles

This is an additive evidence-format change to the exact combined attention/QKV
Engine. It does not change model arithmetic, precision, allocation layout,
controller, RESET protocol or timing mode. The original source remains frozen;
[overlay.patch](overlay.patch) records the private entry/rank and adapter delta.
One entry is rebuilt, with the other39 original objects unchanged and their
per-translation-unit dependencies checked.

[bundle.hpp](bundle.hpp) streams the existing target readback buffers into one
uncompressed `state.bundle` per rank/request. `state-index.tsv` records each
original buffer filename, contiguous offset, size and SHA256. `state.json` is
byte-identical to the old writer, including its absence of a trailing newline.
`state-seal.txt` binds bundle/index/state hashes and extent. The existing five
draft payload files remain unchanged.

The [independent reader](reader.py) reads the actual bytes, validates the exact
inventory in `state.json`, all range bounds and hashes, and reconstructs the old
logical filename→SHA256 map. It rejects missing, duplicate or extra entries,
gaps, overlaps, trailing bytes, aliases and incomplete captures. It never accepts
an index hash as a substitute for reading the payload. Per-rank payload is
bounded256MiB, metadata1MiB and4096rows; streaming chunks are64KiB.

Fresh capture uses exclusive partial files, checked writes/fsync/close,
no-overwrite hard-link publication and a seal published last. A sealed repeated
DUMP rechecks every stored range against both its original hash and the newly
read current target bytes, combines whole-file hashing in the same pass, and
verifies unchanged state JSON and file identities. It never overwrites sealed
bytes. Incomplete files and mismatches refuse further progress and remain for
inspection. A seal alone is insufficient: final directory-fsync can fail after
publication, so successful RPC and normal RESET/FINISH closure remain required.

Nine CPU tests passed with the actual C++ writer and independent Python reader,
including write/fsync/close failure, interruption after linking and after
reopening, corruption, repeated-dump disagreement and malformed inventories.
The lifecycle fixture uses the actual adapter with synthetic RPC responses; it
is not an actual full Engine Host qualification. The final test-only correction
reused the unchanged compiled writer binary and retained its earlier proof.

Two tiny NTFS pilots failed safely before a seal: no-replace rename refused,
then a stale old-handle link-count check refused. Corrected pilot c passed using
the same C++ writer,261 payload bytes, independent full readback and unchanged
repeated capture. Its logs establish old-FD link-count2 versus newly opened
final-FD link-count1 on all four publications. Exact source/proofs, failure logs
and partials are retained; see [CORRECTIONS.md](CORRECTIONS.md). No failed pilot
was retried in place.

The [two-arm qualification](qualification.py) uses original prompt00,
target-only then MTP, cap128, one persistent pair and no warmups. Every arm must
match the original independently audited baseline tokens and logical state map.
RESET redumps the first arm; an explicit second DUMP verifies the last arm before
normal FINISH (which itself only dumps draft state). After owner closure, both
bundles are independently read again. Five mocked qualification tests passed,
including first-arm mismatch stopping the second request and preservation of
the original retained-owner exception.

The [coordinator](once.py) reuses the frozen passive monitor and lifecycle, with
fixed `gsq-state-bundle-a` unit/control/evidence paths and unchanged combined
device-memory forecast. Root alone admits and launches the reviewed plan.
Three dumps (initial blank plus two requests) forecast694,327,500 raw bytes plus
64MiB metadata; root128MiB cache and external2GiB reserve remain. This is format
correctness, with no speed claim. The build helper never invokes the native
binary.

Bundles reduce approximately2,108 target files/request to four files/rank,
while preserving all target bytes and the existing draft files. A full suite
still needs about6.25GB raw payload capacity; verified compression of closed
bundles remains necessary before another suite when free space is insufficient.
No native compression or automatic archival/pruning is added.

Current proof paths are [CPU tests](evidence/cpu-proof.json),
[NTFS pilot](evidence/fs-pilot.json),
[qualification mocks](evidence/qualification-tests.json) and
[core independent review](evidence/independent-core-review.json).
The [original proposal](PROPOSAL.md) remains unchanged as design history.
