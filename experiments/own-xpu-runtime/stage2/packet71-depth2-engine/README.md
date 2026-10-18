# Packet 71 dependent depth-two engine

CPU-only preparation. The coordinator owns device execution. Packet64 sources
are copied; frozen trees are unchanged. Target arithmetic is
`iq3-p49-split32-v1`, with BF16 KV/state and packet49 as output oracle.

The engine runs dependent two-row tiles on both cards. In steady operation,
rank1 verifies the current tile while rank0 computes the next proposed tile in
separate storage. A first-token miss discards that proposed tile before rank1
uses it. A second-token miss selects prefix 1 and discards the entire future
tile. Only target-verified tokens are emitted.

`kernel-table.tsv` selects production-derived M2 or production M1 per class.
Routed IQ2 gate/up and IQ4 down have priority, followed by supported dense and
attention projections. The target also contains IQ3 expert formats; these and
all unsupported shapes keep serial M1. The row log records actual class modes when plans are captured, including
mixed classes. No generic paired loop is called a production
batched kernel. The `serial-screen-seal.json` view selects M1 for every class.

The feedback draft pass uses confirmed target hidden state. Two recursive
passes propose the next tile from private draft hidden state, then restore all
mutable draft allocations. Accepted inputs subsequently advance the draft
with the corresponding confirmed target hidden state. This costs three draft
passes per tile; the cost model explicitly reserves the extra pass.

All 1,428 operator byte checks pass under GNU and Intel. Three tiny synthetic
fixtures exercise all acceptance prefixes, full plan/spare-state comparisons,
and the QSA extent boundary. Full-model device identity and speed remain
pending. Cloning/copies, a second-input repair bubble and draft synchronization
are real costs; the ideal projected rate is not a measured engine speed.

[Design](DESIGN.md), [CPU gate](fixture/receipt.json),
[build](build-device-receipt.json), [screen seal](screen-seal.json).

From the repository root, the coordinator runs each job once inside its admitted
`screen-*` user unit, using its approved library environment and a fresh fault
review. No service is created by this packet. Lane B requires nice0 and exact
cores 4–7,20–23. The wrapper retains masking, lane leases, memory/fault checks,
graceful drain and release-before-report behavior from packet70's private copy.

```bash
taskset -c 4-7,20-23 python3 -B experiments/own-xpu-runtime/stage2/packet71-depth2-engine/run_job.py smoke-B --fault-review "$FAULT_REVIEW" </dev/null
```

After the 1-prompt x32 smoke passes, run these three commands in order, once per
fresh process pair, supplying the coordinator's currently valid review:

```bash
taskset -c 4-7,20-23 python3 -B experiments/own-xpu-runtime/stage2/packet71-depth2-engine/run_job.py control-B --fault-review "$FAULT_REVIEW" </dev/null
taskset -c 4-7,20-23 python3 -B experiments/own-xpu-runtime/stage2/packet71-depth2-engine/run_job.py candidate-B --fault-review "$FAULT_REVIEW" </dev/null
taskset -c 4-7,20-23 python3 -B experiments/own-xpu-runtime/stage2/packet71-depth2-engine/run_job.py control-repeat-B --fault-review "$FAULT_REVIEW" </dev/null
```

For an all-M1 smoke of the same binary, substitute `serial-smoke-B` for
`smoke-B`. Both views have separate sealed settings and fresh output paths.

Exact argv and output directories: [jobs.json](screen/jobs.json). The quick
screen retains incident64 plus all twelve prompts x128, compared token-for-token
against packet49. Smoke is one separate 32-token request. Planned durations are
about 3 and 4 minutes, unmeasured; each watchdog is 3,600 seconds (>4x). No retry.
Quick evidence is diagnostic and cannot become a headline or submission.

CPU preparation: `OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B`
for `build_engine.py`, `cpu_gate.py`, `batch_cpu_gate.py`,
`metadata_gate.py` (save its JSON under `evidence/metadata-gate.json`), then
`seal_and_plan.py`, each with stdin
`/dev/null`. Build only a fresh unsealed copy; one compiler at a time. The build
limits address space to 8 GiB, requires 12 GiB disk free and remains under 1 GB.
No long CPU model runs. Parent build objects must be present and hash-correct.
This is an originating-host screen packet, not a portable public release.

The first serial milestone is commit `5c22d7374`. Its historical build/seal
receipts are retained under `milestones/serial/`; those receipts describe the
old drained schedule and are not launch seals for the current source tree.
The current seals cover the pipelined engine with either M2 or all-M1 dispatch.
