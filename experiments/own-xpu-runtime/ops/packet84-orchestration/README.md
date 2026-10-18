# Packet84 one-shot CPU preparation

Run from the repository root:

    nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/ops/packet84-orchestration/orchestrate.py </dev/null

The helper reads packets81/82/83 through their own compare and best logic in
isolated interpreters. Every selected candidate must be13/13 exact and beat both
same-lane controls on both lanes. Packet83 supports A-grid/B-confirm and
B-grid/A-confirm; disagreeing valid choices refuse. Missing/failed evidence
keeps that dimension at production and readiness pending.

The baseline is the coordinator's pinned packet80 selection in baseline-pins.json.
--pin key=value can retain the evidence choice or revert only to its production
default (wide64 for experts,1 for placement). It cannot invent a candidate.
The helper fast-reseals, checks the cached CPU proof, imports the real wrapper,
checks lane admission, selection consumers, every window plan, inputs and storage,
then writes ready.json. It never executes the chain command or submits anything.
verify_ready.py must pass immediately before the coordinator launches manually.

Large source-screen snapshots retain source and receipt hashes for audit. These
are live evidence references; changing receipts invalidates readiness. CPU proof
is separately cached and never hashes this directory.

The saved preparation passed; readiness remains false while packet81 and
packet82 confirmations are pending. Packet83's completed direction reports no
winner. The baseline has been restored after eight reselection rehearsals and
a real coordinator pin-reversion check. Cached proof was unchanged throughout.
See ready.json for the exact snapshot and the lab note for evidence links.
Resolved no-winner screens retain the baseline; only pending/conflicting screens
block readiness after all prechecks pass.

The initial failure log is retained byte-for-byte as safety-tests.log.gz with
a hash manifest; its original stays local. final-tests.log records the passing
regression verdict.
