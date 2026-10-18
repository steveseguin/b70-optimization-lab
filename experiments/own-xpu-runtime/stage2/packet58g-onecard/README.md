# Packet58g: repair the one-card IQ3 expert pointer path

Copied from frozen packet58f. CPU preparation only; native output checks and
speed remain pending the coordinator's fresh K1a-first chain.

KD refused at `blk.2.expsgate`. Its gate weight is an 8,192-byte device pointer
table, but p28 treated it as a 360,448,000-byte packed IQ3_S bank. Alignment is
valid. Layer 2 keeps separate status checks and therefore bypassed the fused
submitters that already understood one-card pointers.

p28 now explicitly accepts the indirect table for cached expert calls and
resolves the selected row. The arithmetic, reduction tree, BF16 boundaries,
status checks, weights, `iq3-p49-split32-v1` oracle and full BF16 KV are unchanged.
No memory budget or reserve is reduced.

The new CPU gate runs the actual 48-layer initialization and submit paths
against distinct, page-aligned virtual allocations with production extents.
The old call fails on the exact row above. The fixed call validates all 1,486
sites (1,633 captured host operations) at short and full context. It reads no
model payload and executes no kernel. K1 now exercises the actual p28 IQ3 path
against unchanged direct p39 output, including host, device, mixed and streamed
placements. Its exact output hash remains the parent's hash.

A failed model startup with explicit no-compute proof, a complete native drain,
no remaining owned processes/Xe clients and clean kernel postflight releases
its own drain permit and lane lease. The window still fails and the queue stops.
Unknown shutdown, live owners and faults remain closed. No shared screen code
or prior coordination record is edited during preparation.

Every W window's native process uses lane-A cores `0-3,16-19` at nice 0, inherited from
the coordinator. K1, KD and all CPU preparation stay on helper cores
at nice 19. Timing receipt checks enforce the actual native placement.

- [Root cause](evidence/fullshape-root-cause.json), [full-shape gate](evidence/fullshape-submit-cpu.json).
- [Coordinator command](WINDOW.md), [build/check commands](CPU-BUILD.md).
- [CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [task note](../../../../notes/2026-10-18-own-runtime-packet58g.md).

Start at K1a under fresh `evidence/card0-58g-a`; never import an older K1 seal.
No device result, speed claim, publication or external submission is made here.
