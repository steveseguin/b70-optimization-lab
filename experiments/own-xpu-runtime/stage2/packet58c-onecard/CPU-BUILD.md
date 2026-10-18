# Packet58c wrapper-only preparation

The four binaries are exact copies of packet58b's sealed artifacts. No compile
was needed. The two build receipts retain parent build commands/timestamps and
add parent receipt pins; their source maps relocate byte-identical native files.
`seal.py` verifies both the original source map and its exact relocation.
The original binary still resolves its compiled-in RoPE path in frozen 58b;
that file remains bound by the inherited source closure.

Inherited cache, expert, copy-queue and reset checks are historical 58b results.
Fresh 58c CPU checks exercise the sensor, replay retained snapshots, verify
census credit, and require true-shadow and combined-budget overflows to stop.
The current submission ledger was re-read: all matching IQ3 entries still use
two cards, so the new copy refreshes its ledger hash with no one-card threshold.

From the repository root, use nice 19, affinity 8-15,24-31 and stdin /dev/null:

```bash
P=experiments/own-xpu-runtime/stage2/packet58c-onecard
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/python_gates.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
```

The coordinator command and CPU plan are in WINDOW.md and evidence/queue-plan.txt.
