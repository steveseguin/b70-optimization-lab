# Packet115 expert LARGE images — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can module-wide LARGE revive exact expert designs rejected for spills, while
preserving packet103 after103x half-cache/tile16 and `iq3-p49-split32-v1`?
CPU-only preparation on steve-b70s, October 18, 2026, within the two-hour box.
Installed icpx 2026.0.0 and ocloc 26.18.38308.1, BMG-G31 AOT target.

## Outcome

Module-wide LARGE works: 256 GRFs, zero scratch allocations, scratch messages
or flag spills for all four final designs. Both compilers pass two fresh byte
runs per view. Two micro proposals and a conditional one-load B proposal pass
temporary queue planning. No device job ran in preparation. Performance and
device output equality remain unmeasured; no candidate is promoted.

## What worked

Separate expert AOT libraries isolate allocation mode. Distinct kernel names
prevent default/LARGE identity merging. Packet103's prepared-submit overlay
preserves capture across the library boundary. E5's common epilogue eliminates
flag spills without changing its independent FP32 chains or tree. The v5 copy
changes only the runtime expert selector and checks both ranks, allocation
identity, complete resets and fresh protocol repeats.

## What failed or remains uncertain

The initial E5 epilogue spilled flags and failed Gate 1; its replacement passes.
CPU startup audit fields needed explicit packet-local extensions, retained with
the failed diagnostics. CPU evidence and offline zero-spill reports do not
establish physical occupancy, device arithmetic or speed. E3 is a provisional
sealed view; the actual micro winner is unknown. The CPU-only winner preparer
checks just the eventual production/winner pair before device admission.

## Evidence and patches

[Copied kernels and provenance](kernels/README.md),
[linked images](evidence/images.json), [CPU bytes](evidence/cpu-byte-identity.json),
[rejected E5](evidence/e5-first/), [micro plans](evidence/micro-queue-plan.json),
[v5 startup](v5/evidence/full-shape.json), [v5 reset](v5/evidence/reset-bytes.json),
[v5 protocol](v5/evidence/protocol.json), [v5 plan](v5/evidence/queue-plan.json),
[work note](../../../../notes/2026-10-18-own-runtime-packet115.md),
[retention and rebuild](RETENTION.md).

## When to revisit

The coordinator may run the two fresh micros. Every candidate must be at most
0.85 of both production controls in both orders and processes, with every
output byte exact. Only a qualifying candidate can proceed to the one-load
model bracket and its unchanged oracle/acceptance gates. No server is retained.
