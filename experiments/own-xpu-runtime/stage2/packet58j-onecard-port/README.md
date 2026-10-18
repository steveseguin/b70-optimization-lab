# Packet58j: target kernels on one card

A separate source copy of frozen packet58g ports **down-tile16, route-fast and
rec-both-plus** to the target-only one-card line. Production and all eight
combinations are selectable. Arithmetic remains `iq3-p49-split32-v1`, with
all 48 layers, full BF16 KV, the same pinned expert banks and the same 18 GB
expert cache. Device exactness and speed are still pending.

Down weights are transposed in bounded, 16-row-aligned chunks at pin time.
The pointer-table kernel resolves the expert base before addressing its tile.
Copy-on-miss transfers the already-transposed expert bytes; zero-copy misses
read those same bytes in the host bank. Neither the cache accounting nor its
publication/eviction protocol changes. The separate layer-2 IQ3 p28 fix from
58g remains intact.

Route-fast uses the same rounded probabilities and tie order. Rec-both-plus
keeps the same sums, BF16 state boundaries and invalid-position/active/error
semantics. The imported implementations and their exact source hashes are in
`port-source-manifest.json`; one-card source provenance is in
`parent58g-source-manifest.json`.

E1 is excluded: expanding the IQ2 half scales adds **616,038,400 pinned bytes**
(47 layers × 2 banks × 512 experts × 640 rows × 20 bytes). That exceeds 58g's
exact bank layout budget. No reserve or cache capacity is reduced to fit it.

- [CPU build and gates](CPU-BUILD.md), [byte evidence](evidence/byte-gates.json).
- [All 80 full-size startup/submit checks](evidence/fullshape-submit-cpu.json),
  [unchanged memory plans](evidence/budget-cpu.json).
- [Coordinator commands and decision policy](WINDOW.md).
- [Retained evidence and rebuild dependencies](RETENTION.md).
- [Decisions not to repeat](DO-NOT-REPEAT.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).

The proposed card-0 bracket is production / port / production, followed by a
separate fresh record chain only if it qualifies. Every window holds the whole
host; lane-B TP2 work cannot overlap. Nothing in this packet launches itself,
posts a result or changes a live queue. The two-card improvements are motivation,
not measured one-card gains.
