# Packet58c: one-card pinned-host memory accounting

October 17, 2026, four-card host. CPU-only repair of the wrapper around the
one-card engine. No GPU, model, service, compiler, sudo, power, memory, swap,
page-cache or reboot action. The memory fence remains unchanged.

The new [packet58c](../experiments/own-xpu-runtime/stage2/packet58c-onecard/README.md)
separates completed pinned expert bytes from remaining GPUActive growth.
It keeps the original 118,308,908,048-byte available-memory admission and
8,589,934,592-byte reserve. A second check bounds pinned bytes, remaining
shadow, full anonymous RSS and the full file-backed allowance together.
Nothing is subtracted twice. Every earlier memory, fault, teardown and quality
stop remains in place. Invalid or incomplete progress cannot invent pin credit.

## What the old evidence says

KD completed 78 expert tensors in layers 0–25: **26,424,115,200 pinned bytes**.
The old shadow bound was **26,409,219,600 bytes**, 14,895,600 bytes smaller.
The loader then began layer 26 before its cooperative stop. The engine's
`safe_to_exit` receipt is true. This is consistent with pinned host USM being
counted in GPUActive and incorrectly charged as additional device shadow.

There is no aligned sample history to prove the correspondence over time.
The native `host-memory.jsonl` holds just `before_load` and `end`, and progress
rows have no timestamps. The supervisor discarded the offending sample when
its check raised. Its last retained sample is from draining: GPUActive
5,818,572,800 bytes and MemAvailable 115,026,112,512 bytes. The native endpoint
snapshots show 120,966,356,992 and 120,907,894,784 bytes available; those are
**not a measured loading minimum**. 58c logs every accounting sample, including
the offending one, with a timestamp and the exact completed-pin credit used.

The retained closed environment contains neither `NEOReadDebugKeys` nor
`EnableDeferBacking`. The [older multi-card shadow note](../experiments/ltx25-b70/notes/2026-10-04-host-ram-shadow-of-vram.md)
describes `EnableDeferBacking=0` for a different allocation path; it was not
active here and is not introduced by this repair. Both keys remain forbidden.
The complete shadow allowance is retained.

## Checks and retained proof

- All **57** CPU wrapper/admission/provenance tests pass, including thirteen
  new sensor tests. They replay the three retained observations with zero pin
  credit because their timing is not aligned to progress. The missing failed
  sample is not fabricated; crossing reconstructions are labeled synthetic.
- Synthetic full-pin plus allowed-shadow accounting passes. True shadow one
  byte over its bound stops at zero, partial and full pin. A combined host
  overrun stops even while shadow and the old anonymous ceiling are legal.
- Partial JSON writes get no credit; unknown, repeated, wrong-size, truncated
  or disappeared progress fails closed. K1 retains its 4 GiB GPUActive cap.
- **164 native source files and four binaries** are unchanged from 58b. No
  compile or native binary execution was needed. Copied binaries total
  61,256,768 bytes; compiler caches were not copied.
- Fresh seal creation and verification pass. Parent 58b seal verification and
  all captured parent source/latch hashes pass unchanged.
- The inherited one-card submission-ledger pin was stale. The current ledger
  still has only two-card records for this IQ3 model; only 58c's ledger hash
  was refreshed. No result was submitted and no threshold was invented.

[Replay data](../experiments/own-xpu-runtime/stage2/packet58c-onecard/evidence/sensor-replay.json),
[CPU log](../experiments/own-xpu-runtime/stage2/packet58c-onecard/evidence/python-cpu-gates.log),
[native identity proof](../experiments/own-xpu-runtime/stage2/packet58c-onecard/evidence/unchanged-native.json),
[original KD evidence pins](../experiments/own-xpu-runtime/stage2/packet58c-onecard/evidence/58b-kd/source-manifest.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet58c-onecard/CPU-PREPARATION-CLOSEOUT.md).

## Coordinator handoff

The [exact commands](../experiments/own-xpu-runtime/stage2/packet58c-onecard/WINDOW.md)
select card **0**, fresh output `evidence/card0-58c-a`, and order
**K1a → K1b → KD → W2m → WS → WS128x → WS128**. The existing queue has no
resume path, and its prerequisite checks require identical build-receipt
hashes. A wrapper change makes a new seal, so K1a/K1b must run again despite
unchanged binaries. Those rules were not weakened.

[CPU command plan](../experiments/own-xpu-runtime/stage2/packet58c-onecard/evidence/queue-plan.txt)
passes using 58b's recorded library path and old review timestamp solely as a
plan fixture. It creates no queue output. Before launch the coordinator must
review the retained 58b lineage latch and provide the actual review boundary;
the plan fixture is not that review. The original latch was neither removed
nor changed. Device fit, correctness and speed remain unmeasured for 58c.

## Workspace and storage

The requested first `git pull --rebase` refused because other agents had
unstaged edits. `git fetch origin main` then showed zero divergence, so there
was nothing to rebase and no other agent's work was stashed. This task changes
only the new packet, this note and the current-state pointer.

The generic 50 GiB storage check failed (about 28.95 GB available). For the
requested bounded copy, preparation used the packet's existing 8 GB storage
floor with a 180 MB write allowance; that check passed. This is a recorded
exception for this copy, not a claim that the generic floor passed or a change
to host settings. No evidence or other files were cleaned up to make space.
The runtime queue still checks its unchanged output allowances and 8 GB floor.

Large-artifact retention review: the copied `rope.bf16` is 4,194,304 bytes.
Keep it with the copied source because `main.cpp` uses this exact model
constant and fresh builds need it. Restore from frozen
`stage2/packet58b-onecard/rope.bf16` and verify SHA-256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
The new seal pins its bytes. The parent copy is retained too.
