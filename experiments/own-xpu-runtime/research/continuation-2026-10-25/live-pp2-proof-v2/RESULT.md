# Live existing-MTP qualification: PASSED

This corrects the comparator-only I32/U32 position declaration error documented
in the [preserved first audit](../live-pp2-proof/RESULT.md). Both audits read the
same native output; no GPU rerun was required.

Boundaries [0, 23, 48]; proposal use False. No speed claim.
Clean terminal exit: True. All 32 baseline outputs exact: True.
All 2065 canonical target buffers/layouts exact: True.
Canonical true-pair sequence (117 steps) valid: True.
All 32 retained legacy draft head rows exact: True.
Full draft seal and quiescent host metadata valid: True.
Cross-run full draft state comparison: None.

See [summary.json](summary.json), [target comparison](target-comparison.json.gz),
[pair comparison](pair-comparison.json) and [draft state manifest](draft-state-set.json).
Full target and draft raw bytes remain in external run paths, with retained seals
and per-buffer hashes, and in the verified durable archive; preserve original files.
Legacy proposal equality does not establish raw hidden or full legacy draft-state
equality. Cross-run draft-state equality, when present, compares the two new runs.

Both completed runs and their proof metadata are sealed in the verified
384,544,689-byte tmpfs archive. The [archive receipt](../live-archive-verification.json)
records its SHA256 and independently checks all 970,472,560 raw bundle bytes.
The [durable copy receipt](../live-durable-archive.json) records the independently
rehashed USB copy. Original files remain untouched.
