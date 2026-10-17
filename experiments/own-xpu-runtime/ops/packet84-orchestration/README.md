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
