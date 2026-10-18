# Packet105: exact target head row split

CPU-only implementation, copied from packet97 after the committed
97e startup repair (386faa9ee). Parent packets and orchestration remain frozen.
Rank1 keeps rows [0,202240); rank0 evaluates [202240,248320) from the verified
current normalized final.mix, after its own target half. No speculative hidden
state or draft arithmetic changes. Compute-queue and copy-engine transfer
placements are separate candidates. All device quality and speed are pending.

The 1.0685% gain is packet87t’s prediction, never a measured result.

The prefix and suffix call the existing p33 Q6 kernel and round2 argmax.
The merge keeps the lowest global index on ties. Every logit's reduction and
BF16 rounding stay unchanged. Nonfinite logits retain production's sticky
error and block output; invalid diagnostic indices are not emitted tokens.

Rank1 starts a 5120-byte pinned copy after the verified final.mix producer,
submits its prefix head, then publishes the completed hidden bytes. Rank0
services that request after its own speculative half and returns a 16-byte
best-value/index/status payload. Position, fixture and sequence must match.
Suffix scratch is private and excluded from model rollback. The BCS choice
uses a dedicated copy-only Level Zero queue and refuses a missing engine.
The compute choice is the matched transfer-placement control.

The six full-size allocation checks account for an extra 157322272 device
bytes on rank0, including 155750400 weight bytes, and 155750384 fewer bytes on
rank1. This checks the existing arena limit and reserve, not actual residency.
Driver paging or insufficient live headroom must refuse a screen.

CPU gates are in [evidence/](evidence/) and [startup97e.json](startup97e.json).
They cover both compilers with fresh repeats, all 248320 loader rows, verified
hidden bytes on hit and miss paths, stale/cancel/peer-exit refusals, and all
eleven chain windows for each of the three choices. KD keeps packet97e's
draft-only host-reference projection. K0's CPU path is a structural check;
device JIT and GPU arithmetic remain pending.

The two proposed grids use production / compute split / production / BCS split /
production. Each placement must beat its own two fresh controls with exact
outputs and unchanged acceptance. Lane A independently confirms lane B and
remains the record lane. Temporary queue plans never install or execute jobs.
Per-leg JSON timing files distinguish transfer placement; hidden-export timing
includes the producer dependency wait and is not a pure DMA latency number.

For CPU reproduction, run the following scripts one at a time from this
directory with `nice -n 19 taskset -c 8-15,24-31 python3 -B SCRIPT </dev/null`:
`build_engine.py`, `cpu_gate.py`, `controller_gate.py`, `full_shape.py`,
`runtime_mock.py`, `startup_refusals.py`, and `startup97e.py`.
They use packet94's compiler lock and an 8 GiB address-space limit.
`test_p105.py` checks admission and comparisons and saves its receipt.
`prepare_packet.py` creates new immutable view seals only after all gates;
`queue_plan.py` writes only the new proposed files and plans temporary queues.
Do not overwrite a sealed view after changing its sources.

Local build caches stay below 300 MB. Rebuilds require the pinned packet97
object/source closure described in [copy-lineage.json](copy-lineage.json) and
[build-device-receipt.json](build-device-receipt.json). Fixture entry objects
are removed after linking; hash-bound fixtures and sources remain. Large raw
transcripts are retained compressed with exact hashes, including prior CPU
iterations. No model weights or binary caches are committed.
The shared CPU fixtures under `build/gnu-host` are local byte-identical copies
of the frozen packet56 fixtures, not links outside the repository. Their names
and hashes are in [the localization receipt](evidence/localized-static-files.json).
When restoring caches, copy those fixture bytes from packet56, the frozen
packet97 `build/fusion-fixtures` and `build/input` inputs, then verify the gate
hashes. The oracle manifest is a tracked local copy; full frozen oracle captures
remain external lab evidence reached through the retained static links.

[CPU closeout and remaining device gates](closeout.md) ·
[Do not repeat](DO-NOT-REPEAT.md) ·
[Work note](../../../../notes/2026-10-18-own-runtime-packet105.md)
