# Packet184 negative-result index (two-card session checkpoints)

No device result exists yet; this preparation closes no lever. After the lane-B window, append one
row per row outcome from `v5/evidence/device-<kind>-B-p184/summary.json` (`first_failed_gate` on a
failure). Packet153's own boundaries, which this copy inherits unchanged, are kept in its packet:
[packet153 DO-NOT-REPEAT](../packet153-snapshot-host/DO-NOT-REPEAT.md).

Checked before design (every stage2 `DO-NOT-REPEAT.md`, packet183's, the session-swap packets
179/180/181): no row closes TP2 checkpoints. Lessons reused, not reopened:

* packet32: the PLE hash state mutates through its input pointer: PLE history is saved whole (it is a
  banked temporal state on rank 0: active, spare and reserve).
* packet37 / packet62: buffers move only together with their prepared commands: restore uploads into
  the live allocations of each logical bank role after the request reset; no prepared command or
  allocation id changes (production-shape capture after restore == fresh engine at N).
* packet44 / packet71: restore needs extent, history and lookup metadata, not bytes alone:
  `history0/1` restored, `admit_position(N)` re-derives extents, lookup ids are recomputed per token.
* packet18 / packet19: no SYCL object outlives its owner; a synchronous mock is not first-device
  evidence: the CPU sessions are real two-rank processes, and the device rows are still required.

| Date | Mistake found during CPU preparation | Required behavior |
| --- | --- | --- |
| 2026-10-22 | v5 bundle-8 binaries refuse `--mini` (the p149 probe exchange asserts production geometry), so no packet ran real two-rank CPU sessions on this line | build the probe only at production geometry (inert under `probe: off`, same device allocation order) and use `v5/lineage/mini/selection.json` (experts/head relaxed; packet153 switch-gate precedent) |
| 2026-10-22 | treating the rank-1 `streams` buffer as a rewritten intermediate (the one-card rule) | it is the input of the next MTP draft step at a boundary: save it whole on the draft rank |
| 2026-10-22 | a receipt field `X` holding another packet's path next to `X_sha256` | the pin guard reads it as a cross-packet mutable pin: name provenance `origin` / `origin_digest`, or copy the bytes into the packet |
| 2026-10-22 | report fixtures as JSON for `ops/rehearse_entry.py` | its report sandbox reads repository `.py` sources only: generated Python fixture module (`v5/report_fixture_data.py`), and the report must read only the run directory |
| 2026-10-22 | leaving production-shape scratch under `v5/build` | the compile turn enforces the packet's 300 MB build cap: delete fixtures/blobs after writing the receipt |
| 2026-10-22 | an 18-digit integer reader for manifests | shard `mtime`/`ctime` are 19-digit nanosecond stamps: 19 digits with an explicit int64 range check |
| 2026-10-22 | counting only argmax tokens in mini CPU sessions | synthetic weights give constant tokens and guesses: gate on byte equality of every saved buffer and on the draft-cache control |
