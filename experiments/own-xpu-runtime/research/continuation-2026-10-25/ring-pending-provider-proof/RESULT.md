# Provider survival through target rollback: PASSED

All 32 output tokens, 2065 target buffers and
73 canonical draft allocations match accepted replay.
All 117 canonical true pairs and 32 recursive predictions match.
Two target aborts discarded three rows after provider advancement; full canonical,
pinned and private bytes, host/Sequence state and prepared descriptor identities survived.
Provider calls exercised pending depths 2, 2 and 1, including older ACCEPT without rewind.

[Summary](summary.json), [target proof](target-comparison.json.gz),
[draft proof](draft-comparison.json.gz), [native survival receipts](stage0/ring-provider-survival.jsonl).
Tentative inputs were scripted to force actual target rejection. Recursive proposals
were discarded. This is not rolling inference, a speed result or CPU-reference equivalence.
Raw bundles remain external with retained metadata pending durable archival.
