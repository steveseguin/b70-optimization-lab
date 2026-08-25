# Qwen target-Q8/F16 TP1 fa0 graph-port parent sentinel R2 result

State: **failed before any GPU benchmark arm**.

The sealed R2 packet passed all static gates and created its immutable output
root. Model-view verification completed, but the inherited campaign-receipt
builder then read `runtime.source_provenance`. The R2 manifest places that
limitation at `source.provenance`, so Python raised `KeyError` while creating
`campaign-identity.json`.

This was a bookkeeping/schema mismatch, not a GPU or graph failure. The GPU
compute gate, graph-off control arm, and graph-on candidate arm never started.
Post-exit inspection found no llama or sentinel processes, and cleanup passed.

The R2 root remains immutable. It cannot be reused or promoted. The only valid
retry is a distinct create-only campaign that preserves the sealed source,
binary, backend, DSO, model, and two-arm identities while correcting the
provenance lookup. R2 grants no curve, site, speed, quality, record, or protected
graph-off replacement authority.
