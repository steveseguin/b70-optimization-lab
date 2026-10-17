# Packet 71 dependent depth-two engine

CPU-only preparation. The coordinator owns device execution. Packet64 sources
are copied; frozen trees are unchanged. Target arithmetic is
`iq3-p49-split32-v1`, with BF16 KV/state and packet49 as output oracle.

The serial fallback is a working two-row dependent transaction. It overlaps
rank0's proposed pair with rank1's preceding single row, then drains before
rank1 verifies the pair. All three acceptance prefixes are explicit. This first
schedule has extra drain and copy costs; the optimistic two-token pipeline
projection is not a performance prediction for this implementation.

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

Exact argv and output directories: [jobs.json](screen/jobs.json). The quick
screen retains incident64 plus all twelve prompts x128, compared token-for-token
against packet49. Smoke is one separate 32-token request. Planned durations are
about 3 and 4 minutes, unmeasured; each watchdog is 3,600 seconds (>4x). No retry.
Quick evidence is diagnostic and cannot become a headline or submission.

CPU preparation: `OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B`
for `build_engine.py`, `cpu_gate.py`, then `seal_and_plan.py`, each with stdin
`/dev/null`. Build only a fresh unsealed copy; one compiler at a time. The build
limits address space to 8 GiB, requires 12 GiB disk free and remains under 1 GB.
No long CPU model runs. Parent build objects must be present and hash-correct.
This is an originating-host screen packet, not a portable public release.
