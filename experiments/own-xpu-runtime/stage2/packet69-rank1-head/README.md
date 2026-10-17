# Packet69 rank1 head and draft

[Task note](../../../../notes/2026-10-17-own-runtime-packet69.md),
[measurement command](WINDOW.md).

The root is the immutable outputs-unchanged measurement packet, copied from
packet64-attribution (itself packet64-record-bundle plus observation). Candidate
code is separate under `candidates/`. GPU execution belongs to the coordinator.
No speed or model-quality qualification is claimed from CPU preparation.

`build/` contains local generated mirrors, inherited hardlinked objects and
new entry binaries; no model weights. Parent objects remain at their recorded
paths in `build-device-receipt.json`. Keep that receipt and parent sources;
`build_engine.py` records the serial rebuild. Do not delete parent artifacts.
The new build stays below 1 GB. All raw device evidence remains local except
small reports and receipts. The copied `rope.bf16` is the existing exact
arithmetic dependency and is retained with its original bytes.
