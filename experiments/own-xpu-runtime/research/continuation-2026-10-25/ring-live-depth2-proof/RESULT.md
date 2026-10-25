# Actual depth-two provider qualification: PASSED

All 32 output tokens match. All 2065 target buffers and
73 canonical draft allocations compare exactly.
All 117 true pairs and 32 recursive d1/d2 predictions match
retained evidence; every recursive restore was byte-verified.

[Summary](summary.json), [target state comparison](target-comparison.json.gz),
[draft state comparison](draft-comparison.json.gz). Proposals were discarded;
target owners were quiescent throughout provider borrowing. This does not yet
qualify consuming recursive proposals, target/provider overlap or a speed gain.
The [durable archive receipt](../ring-live-depth2-durable-archive.json) and
[complete restoration check](../ring-live-depth2-reuse-archive.json) retain all
new evidence and reconstruct all 472,202,828 raw bytes, including the separate
FINISH draft dump. Every raw payload, seal, index and state JSON is byte-identical
to an already durable portable-live member, so the new packet reuses those exact
bytes. The complete tmpfs archive and original run remain preserved.
