# Packet81 coordinator screens

Preparation runs no GPU and does not enqueue work. Proposed lines are
[ops/lane-queue/proposed-p81-A.txt](../../ops/lane-queue/proposed-p81-A.txt) and
[proposed-p81-B.txt](../../ops/lane-queue/proposed-p81-B.txt).
Their plans use a temporary queue directory; live queues remain unchanged.

Lane A runs production, gate-input-packed, down-input-packed, input-packed,
production, each once with a 90-second gap. Lane B runs production, the exact
improving A winner, production, each once. All A rows must pass all thirteen
exact requests; the winner must beat both A controls. B refuses missing,
inexact, reordered or non-improving A evidence. A plan validates every possible
B winner but cannot authorize or select it. Shared v4 owns admission, device
masking, teardown, fault checks and lease release before reporting.

CPU-only commands from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet81-experts3/final_check.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet81-experts3/queue_plan.py </dev/null
```

Coordinator execution uses the proposed queue lines with its current reviewed
fault boundary. Do not bypass the shared wrapper, copy its files or reuse an
old output directory. Screens are diagnostic 128-token comparisons, not a
512-token realistic final gate or record. An exact both-lane win still needs
integration and a fresh full record chain under its final binary identity.
