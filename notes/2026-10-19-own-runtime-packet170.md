# Packet170 — one-card MTP complete-cycle review

**Closed without a build.** The layer micro passed, but the record-line
receipts do not contain the operation timings needed to turn its ratios into
a supported complete-cycle estimate. Cache loss, draft feedback and state
selection cannot be treated as free. The +3% decision gate is not met by the
available evidence.

At the requested 78.7% acceptance, the full cycle must finish within
**54.274 ms** to beat 31.966820 tok/s by 3%. A separately labeled charged
sensitivity costs **63.614 ms**, about **28.09 tok/s**. That is a conditional
calculation, not measured speed or a claim that every MTP design loses.
Acceptance at 70% and 85%, publication paid once per cycle, and a baseline
with that publication delay removed are all retained.

Memory fits the declared layout after reducing the target cache to **18.216
GB**. It needs **103.314 GB** available host memory, including margin and
reserve, and still fits after conservatively subtracting all five excluded
RAM blocks from the historical floor. The device keeps its **1.5 GB reserve**.
The shared-cache draft cannot have both free residency and no target pollution.

The requested roughly 0.5 ms/expert cost is measured CPU expert execution;
it is not the current GPU's host-memory miss latency. The packet keeps that
closed CPU alternative separate from the native cache-size measurement.
All 253 visible negative indexes were searched, with 305 matching lines
retained. Existing closed mechanisms remain closed.

[Full analysis and memory tables](../experiments/own-xpu-runtime/stage2/packet170-onecard-mtp-cycle/README.md)
· [Reproducer and source-bound values](../experiments/own-xpu-runtime/stage2/packet170-onecard-mtp-cycle/cycle.json)
· [Closeout](../experiments/own-xpu-runtime/stage2/packet170-onecard-mtp-cycle/CLOSEOUT.md)
· [Do not repeat](../experiments/own-xpu-runtime/stage2/packet170-onecard-mtp-cycle/DO-NOT-REPEAT.md).

CPU-only standard-library recomputation and source checks pass within a
2 GB limit, at nice19 on CPUs8–15/24–31. No GPU, compile, model read, service,
sudo, settings or live queue action was taken. Frozen packets and shared
operational files were untouched. There is no new speed or quality claim.
