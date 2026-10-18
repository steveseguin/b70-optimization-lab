# Packet 71b: depth-two screen repair and remaining cheap M2 coverage

CPU-only screen preparation, copied from frozen packet71. Packet49 remains the
oracle; target arithmetic is `iq3-p49-split32-v1`, with full BF16 KV/state.
No device, service or CPU model ran during this preparation.

The worker no longer imports a chain registration just to run a screen. Chain
storage admission refuses explicitly in this screen-only copy. The worker and
placement check recognize this packet's name, so the candidate actually enables
depth two. Every plan imports the same worker and deferred runtime modules in
the queue's closed environment, with its lane mask. The import audit prohibits
device opens, subprocesses, network connects and writes, and records imported
sources and read dependencies. Wrapper seals are checked for control plans too.

Three production paths gain a second row's independent accumulators:

| Classes | Preserved production implementation |
| --- | --- |
| `hc.a.gate`, `hc.f.gate` | p60 gate-plus-mix, 256 threads, two output columns and four streams per group; p49c vector loads; BF16 gates before the ordered mixture |
| `router` | standalone F32 constant-split4, 128 threads, four global partials per output, unchanged adjacent reduction and BF16 write |
| `route` | selected p49d exp32/rank4, four passes; separate maxima, exponentials, rounded probabilities, ranks and route outputs |

The shared-up epilogue prevents the router's historical small-FFN tuple in this
production dispatch. An unexpected tuple refuses instead of silently timing a
serial router. Existing packet68c dense/expert choices stay in place. Causal
recurrence and unsupported expert formats remain serial. The all-M1 view uses
the same binary and independent seal.

GNU and Intel each pass **2,728 byte checks**, including full route scratch,
outputs and controls, independent inactive/failed rows, ties, nonfinite input,
router partials, and HC mixture bytes. Expected and actual streams also agree
across compilers. Host and device compilation pass. Eleven wrapper/import tests
pass. These are operator and packaging gates, not full-model qualification.
The copied packet71 transaction-fixture receipts remain historical evidence;
no new CPU model or transaction-fixture run is claimed.

## Coordinator handoff

The four JSON job lines are in
[proposed-p71b-B.txt](../../ops/lane-queue/proposed-p71b-B.txt). They are proposed
only; no queue file or live job was changed. Order: smoke, control, candidate,
control repeat. Expected durations are about **3/4/4/4 minutes**, unmeasured;
each watchdog is **3,600 seconds**, at least four times the estimate. No retries.

From the repository root, CPU planning:

```bash
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet71b-depth2-engine/run_job.py smoke-B --plan </dev/null
```

The coordinator supplies its valid review and admitted lane-B unit for execution:

```bash
taskset -c 4-7,20-23 python3 -B experiments/own-xpu-runtime/stage2/packet71b-depth2-engine/run_job.py smoke-B --fault-review "$FAULT_REVIEW" </dev/null
```

After smoke passes, use `control-B`, `candidate-B`, then `control-repeat-B`.
The quick screen checks the separate 64-token incident request and all twelve
128-token packet49 streams. Controls use packet64's sealed `1-draft-hc-batch`
view. `serial-smoke-B` is an optional all-M1 diagnostic, not one of the four
proposed jobs. All paths and arguments are in [screen/jobs.json](screen/jobs.json).

Both [seals](screen-seal.json), five direct plans and all four queue plans pass.
[Import audit](evidence/worker-import-check.json),
[operator gate](fixture/m2-receipt.json),
[metadata gate](evidence/metadata-gate.json),
[build](build-device-receipt.json),
[queue plans](evidence/lanequeue-plan.jsonl),
[closeout](CPU-PREPARATION-CLOSEOUT.md).

Device row/state identity and speed remain unmeasured for packet71b. Packet68c's
consecutive-position result makes depth two marginal; this packet supplies the
requested cheap screen, not a speed claim or a long qualification campaign.

## Rebuild

In a fresh unsealed copy, run `build_engine.py`, `batch_cpu_gate.py`,
`metadata_gate.py` (save JSON to `evidence/metadata-gate.json`), then
`seal_and_plan.py`, each with `OMP_NUM_THREADS=2 nice -n 19 taskset -c
8-15,24-31 python3 -B` and stdin `/dev/null`. One compiler runs at a time,
with an 8 GiB address-space bound. Parent packet64 objects must be present and
hash-correct. This is an originating-host experiment, not a public recipe.
See [retention](RETENTION.md) for copied history and binary fixture restoration.
