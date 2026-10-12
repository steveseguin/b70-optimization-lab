# Independent request-reset review after the disk-full interruption

Source review passed with no blocking finding. This review read the current
ROLLBACK.md inventory and implementation directly; it did not trust earlier
receipts, compile, execute any binary, or contact devices. Current reviewed
source SHA-256 hashes are in review-resume-reset.json. The final parent-run
CPU order-gate receipt has been parsed and checked as described below; this
reviewer did not independently execute that native gate.

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
scratch is written to disk. The final parent-run CPU gate passed after the
retention and warm-up changes. Device request-order proof remains pending
coordinator windows.

Fresh expanded order proofs passed in the parent session against host binary
`a9a4af196369a0050a4e0f72db840035dd078bace1237f153f1da3670bc75ecb`.
The subsequent Python-only storage change keeps the same exact-byte proof in
`state-evidence.json.gz`: target state hashes are verified against their raw
files, every snapshot file receives a SHA-256, metadata is retained as exact
text, and the archive is decompressed and verified before deleting raw state.
All eight fixture steps remain raw for the suite oracle checker. Every reset
admits one raw snapshot reserve and cleans it before the next request.
`test_state_retention.py` checks hash/metadata preservation, fixture retention
and refusal to discard corrupt state. The final parent-run order proof below
covers this storage path.

Final source rereview includes the wrapper safety changes: receipt or archive
write failure cannot bypass the suite's stop/finally-close path, and stop-pipe
signalling is attempted even when failure diagnostics cannot be written. Both
RESET acknowledgements still precede shared-memory clearing and state retention.
Retention performs no target/draft computation, and comparisons still use the
same complete byte hashes. ROLLBACK.md and SUITE.md now describe the expanded
inventory and verified archive retention. The source review passes; this is
separate from the verified parent-run CPU result and from pending real-model
and device evidence.

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

The distinct warm-up correction was independently checked against reset. The
bounded selector uses a deterministic five-token sequence absent from every
five-token span in admitted inputs and is independent of input order. It
changes only warm-up input selection and receipt metadata. Both rank RESETs
still follow warm-up before the first measured request, clearing full target,
draft, host history, mailbox and counters as before. The ten no-rank warm-up
checks were parsed and their source hashes verified. The six export/retention
receipt hashes remain current; that receipt does not bind suite.py, so no
redundant execution was performed. The final CPU reset result below includes
the subsequent warm-up/EOS refinement; device windows remain parent-session work.

The final EOS refinement is confined to the excluded warm-up: a keyword-only
flag passes no terminating EOS tuple and requires exactly two outputs. Every
measured request retains the normal tuple. The following complete RESET is
unchanged, so neither a synthetic EOS token nor its state/history survives into
a measured request. Eleven warm-up checks are source-bound and verified. The
five lightweight state-retention checks were rerun successfully against the
final suite/storage sources; no rank or device process ran.

Final parent-run CPU evidence was independently inspected after all warm-up
changes. `suite-gate-results.json` passes four proofs: Python/native controllers
with none/MTP, each running three prompts in two orders under resident prepared
owners and argument auditing. All twelve prompt comparisons have equal
per-order hashes, 32 retained fixture files, and 210 state-evidence files without
draft or 216 with MTP. The receipt's binary SHA-256 matches a fresh hash of the
current GNU host binary:
`a9a4af196369a0050a4e0f72db840035dd078bace1237f153f1da3670bc75ecb`.
This reviewer verified the receipt, proof fields and binary identity; the parent
executed the gate. The five real-oracle schema checks in that receipt are
oracle-derived fixture checks, not real-model runtime executions. Device
request-order and real-model suite execution remain separate evidence.

Final receipt-metadata rereview: suite.py now derives decode event count,
numerator, endpoints and clipped rank occupancy from a local non-EOS timing-row
slice. It leaves emitted tokens, original timing rows, request execution,
warm-up and reset unchanged. Eighteen authority-agent synthetic metadata checks
were parsed and their current test/source files reviewed; the receipt itself
does not bind source hashes, so this review records those hashes separately.
Eleven warm-up and nine export/retention checks have current source bindings.
The parent reran all five reset-retention checks after the metadata-only diff;
this reviewer independently parsed the new passing receipt and checked every
source hash against current files. No independent re-execution is claimed.

The compiler-selection diff was also reread: CPU suite qualification checks
five Intel host correctness receipts before launch; export binds both launch
executable paths and every request hash to that qualified binary, then rechecks
the binary at export completion. This changes qualification identity only;
request/reset implementation is unchanged.

Final cleanup rereview: capture scans require packet-local build/direct child
directories and ordinary nonsymlink named files. Compression refuses existing
outputs, including dangling output symlinks, checks exact decompression before
unlinking rows, and records both hashes. Agreement reading accepts original or
gzip rows without changing parsed values. Six packet-local synthetic checks
passed, including both input symlink cases, both output collisions, exact gzip
reading and unchanged `.bin`/`.bf16` KD fixtures. Full agreement after real
cleanup remains the parent's separate check; no rank/device process ran here.

Final preflight rereview: inherited Intel correctness receipts are checked
against their actual p33 dispatch, while the p38 suite dispatch is independently
validated and bound alongside current p30/capacity kernel gates, source hashes
and child/binary receipts. This qualification-only correction leaves the suite
launch command, controller and request/reset paths unchanged. No tests or ranks
were launched for this source review.
