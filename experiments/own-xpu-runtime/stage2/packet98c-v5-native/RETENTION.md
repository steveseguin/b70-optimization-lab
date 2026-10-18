# Packet98c retention

Keep compact CPU receipts, native/wrapper seals, source snapshots and failed
preparation logs. Generated build caches and miniature fixtures are ignored.
No model weights or secrets are stored here.

`retain_shape.py` archives every member of each completed full-shape scratch
directory, then reads the archive and verifies every original SHA256 before
removing that scratch directory. Receipts record compressed and original sizes,
member counts and archive hashes. Archives preserve capture arguments, reset
receipts and allocation censuses needed to audit the numeric full-shape proof.
They are evidence, not redundant downloadable model artifacts. Restore an archive
to an empty scratch directory with tar; no runtime consumer depends on extraction.

The 12,583,130-byte generated fusion-rope header is excluded from Git. Its
hash-pinned original is in `source-copy-provenance.json`; `restore_rope.py`
copies and verifies it from packet97's checked bundle. Other native snapshots
are small tracked files. Packet97 linked object files remain read-only local
dependencies bound by hashes, not copied build bloat. No parent orchestration
output is a build or admission dependency.
