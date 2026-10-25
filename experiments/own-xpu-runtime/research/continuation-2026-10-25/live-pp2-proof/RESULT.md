# Live existing-MTP qualification: FAILED

This first audit was refused by the new comparator because it expected I32
for the draft position scalar. The native sealed layout correctly declares
U32[1]; both encode the observed nonnegative position 117 identically. No
native bytes were changed. The comparator now admits either integer layout
while still requiring exact layout equality across runs, with a regression
test. The corrected audit of the same run [passed](../live-pp2-proof-v2/RESULT.md).

Boundaries [0, 23, 48]; proposal use False. No speed claim.
Clean terminal exit: True. All 32 baseline outputs exact: True.
All 2065 canonical target buffers/layouts exact: True.
Canonical true-pair sequence (117 steps) valid: True.
All 32 retained legacy draft head rows exact: True.
Full draft seal and quiescent host metadata valid: False.
Cross-run full draft state comparison: False.

See [summary.json](summary.json), [target comparison](target-comparison.json.gz),
[pair comparison](pair-comparison.json) and [draft state manifest](draft-state-set.json).
Full target and draft raw bytes remain in external run paths, with retained seals
and per-buffer hashes. Durable archival remains pending; preserve original files.
Legacy proposal equality does not establish raw hidden or full legacy draft-state
equality. Cross-run draft-state equality, when present, compares the two new runs.
