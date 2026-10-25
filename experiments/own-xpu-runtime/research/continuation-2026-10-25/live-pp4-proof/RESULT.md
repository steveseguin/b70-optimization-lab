# Live existing-MTP qualification: PASSED

Boundaries [0, 13, 25, 37, 48]; proposal use True. No speed claim.
Clean terminal exit: True. All 32 baseline outputs exact: True.
All 2065 canonical target buffers/layouts exact: True.
Canonical true-pair sequence (117 steps) valid: True.
All 32 retained legacy draft head rows exact: True.
Full draft seal and quiescent host metadata valid: True.
Cross-run full draft state comparison: True.

See [summary.json](summary.json), [target comparison](target-comparison.json.gz),
[pair comparison](pair-comparison.json) and [draft state manifest](draft-state-set.json).
Full target and draft raw bytes remain in external run paths, with retained seals
and per-buffer hashes, and in the verified durable archive; preserve original files.
Legacy proposal equality does not establish raw hidden or full legacy draft-state
equality. Cross-run draft-state equality, when present, compares the two new runs.

Actual overlap coverage: 25 proposal hits, 6 misses; tentative row counts per
stage were [31, 26, 17, 0]. All 12 stage aborts were byte-verified, distributed
as [6, 4, 2, 0]. See [coverage receipt](overlap-coverage.json).

Both completed runs and their proof metadata are sealed in the verified
384,544,689-byte tmpfs archive. The [archive receipt](../live-archive-verification.json)
records its SHA256 and independently checks all 970,472,560 raw bundle bytes.
The [durable copy receipt](../live-durable-archive.json) records the independently
rehashed USB copy. Original files remain untouched.
