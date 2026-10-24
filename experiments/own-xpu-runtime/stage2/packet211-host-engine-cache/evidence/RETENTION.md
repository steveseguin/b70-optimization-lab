# Retained proof artifacts

`host-proof.json` retains every normalized cache transaction, route record,
pointer generation, comparison and owner disposition from the designated run.
The read-only tests and independent artifact audit consume it directly. Its
4,605,886-byte copy in `authority-tests-1792801429531052162/` freezes the exact
input consumed by that test attempt; keep both identities even though their
current bytes match. Restore either from this commit, then verify the hashes
in the authority receipt and independent review before using it.

`raw-host-proof.tar.gz` preserves all 1,709 original files, including state
blobs, output, event logs and failure evidence. It is the complete raw basis
for independently checking the summary; the member paths, sizes and SHA-256
values are in `raw-host-proof-index.json`. Restore into a new empty directory
and verify every member against that index before analysis. The original
local run directory remains intact. The archive and both summaries are
durable research evidence, not transient build products.

The final repository hygiene check reports these three size warnings and
zero errors. No evidence was removed to suppress a warning.
