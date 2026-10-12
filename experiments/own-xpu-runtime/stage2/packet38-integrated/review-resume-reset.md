# Independent request-reset review after the disk-full interruption

Source review passed with no blocking finding. This review read the current
ROLLBACK.md inventory and implementation directly; it did not trust earlier
receipts, compile, execute any binary, or contact devices. Current reviewed
source SHA-256 hashes are in review-resume-reset.json. CPU gate results must
be regenerated or independently verified by the parent session.

Both ranks reject unresolved candidates, drain, and reject a poisoned/sticky
target error before reset. Rank 0 returns to parity zero with allocation IDs,
prepared bindings and command vectors moving together. All live mutable
allocations, including QSA tails, target scratch, both state banks and private
draft state, are cleared in place; weights, RoPE and the pinned slab survive.
Constants, PLE metadata and EOS history are restored. Host histories, lookup
IDs, selected experts, FP32 validity, request counters and timing reset. Draft
position and disabled state reset. Streaming halves already return with no
loaded layer. No allocation release invalidates prepared captures.

A fresh controller instance supplies history, script cursor, result and
acceptance counters per request. Shared publications and the native mailbox
are cleared only after both RESET replies, when both processes have returned
to socket commands. Socket framing sequences and the overall cooperative
deadline remain launch-scoped supervision state. Reset uploads finish before
request timing counters are cleared.

The original order-independence gate omitted standalone target scratch and
host lookup/selected metadata from its observed inventory. This review added
request_state_inventory.hpp, called only at request boundaries. It hashes all
standalone live target mutable allocations without retaining raw scratch, and
records lookup-ID hashes, selected experts, loaded-layer state, FP32 cache
labels/extents, bank parity, logical event, histories and poison status. The
suite order gate now requires and compares this record for both ranks as well
as its existing plan/bank, draft, token, counter and fixture evidence.

The new evidence helper performs readbacks only after drain and mutates no
model allocation; its transfers are outside timed requests. Its largest
transient readback is the existing 256 MiB target operator scratch. No raw
scratch is written to disk. The parent must compile and run the extended gate;
this review does not claim that it has passed. Device request-order proof
remains pending coordinator windows.

Fresh expanded order proofs passed in the parent session against host binary
`a9a4af196369a0050a4e0f72db840035dd078bace1237f153f1da3670bc75ecb`.
The subsequent Python-only storage change keeps the same exact-byte proof in
`state-evidence.json.gz`: target state hashes are verified against their raw
files, every snapshot file receives a SHA-256, metadata is retained as exact
text, and the archive is decompressed and verified before deleting raw state.
All eight fixture steps remain raw for the suite oracle checker. Every reset
admits one raw snapshot reserve and cleans it before the next request.
`test_state_retention.py` checks hash/metadata preservation, fixture retention
and refusal to discard corrupt state. Fresh integrated suite/controller gates
after this storage change remain the parent session's responsibility.

Final source rereview includes the wrapper safety changes: receipt or archive
write failure cannot bypass the suite's stop/finally-close path, and stop-pipe
signalling is attempted even when failure diagnostics cannot be written. Both
RESET acknowledgements still precede shared-memory clearing and state retention.
Retention performs no target/draft computation, and comparisons still use the
same complete byte hashes. ROLLBACK.md and SUITE.md now describe the expanded
inventory and verified archive retention. The source review passes; this is
not a substitute for the parent's final integrated runtime gates.

Final export/cleanup review found and closed the nested-archive evidence gap.
`storage.py` and `cleanup.py` now preserve exact nested gzip metadata instead
of retaining only its outer hash. They use a streamed JSONL/gzip format with
per-file hashes and bounded base64 chunks, check disk admission before writes,
and verify all retained contents before removal. Suite export binds state
archive and runtime-inventory hashes, checks one nonempty clean teardown owner,
and validates frozen prompt coverage and exposed identity fields. The CPU suite
campaign archives scratch and logs only after successful export. Six synthetic
tempfile-only checks passed in `suite-export-retention-gates.json`; no native
ranks ran for those tests. The final native-mini gate's single reset boundary
still captures the completed request before preparing the next and preserves
the same archived-state comparison. Its current source hash is included below.

The final narrow storage race fix was independently re-read. `build_size`
skips only `FileNotFoundError` for members removed between discovery and type,
symlink or stat checks. Permission and other I/O failures remain errors; the
root-space and build-space thresholds are unchanged. The three mocked race
checks and the rerun six synthetic export/retention checks were parsed and
all their recorded source hashes verified against current files. This review
did not rerun tests or launch ranks.
