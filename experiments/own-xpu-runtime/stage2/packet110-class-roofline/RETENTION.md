# Retention and restoration

`rope.bf16` is a 4,194,304-byte immutable arithmetic constant copied from
packet107 (and originally packet97), not model weights or a cache. Its hash
and origin are in `source-origin.json`; `seal.json` also pins its consumed
bytes. The isolated fixture requires it at this path. Restore from packet107
only after verifying that hash; no older copy is removed or consolidated.

`build/` is ignored and contains 55,849,804 logical bytes, below the 100 MB
budget. The source mirror, layer object and executable are rebuildable using
`build_engine.py`; its receipts retain compiler/link commands, parent objects
and source/artifact hashes. Parent packet97 objects remain read-only and must
be available to rebuild this lab experiment. This is not a standalone public
recipe. Each temporary parent-proof link is hashed and removed by its builder.

`evidence/timing-qsa-B-{1,2}.jsonl.gz` preserves every original packet107
iteration byte, including warm-ups and specialised rows; only current rows
enter this analysis. Gzip decompression is verified against the original raw
bytes and SHA256 in `roofline.json`. The original frozen evidence is untouched.
The snapshots allow analysis without the original untracked raw folders.
Window/native receipts preserve measurement identity and drain status.

CPU comparison logs, initial test failure, final tests, build receipts, source
pins, closure-input hashes and the proposal remain tracked. The initial test
failure selected an alternating specialised row instead of the intended second
current row; the corrected negative fixture targets the current row explicitly.
No validator rule or production arithmetic was relaxed.
