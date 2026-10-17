# Packet51 coordinator windows

Run only after `seal.json` exists and the coordinator admits physical card 0,
PCI `0000:23:00.0`; the device executable verifies that PCI identity.
No CPU preparation command runs a device. No full-model oracle is needed for
these synthetic full-layer comparisons. E1 and E2 must finish before T1/T2.
The launch wrapper verifies the seal, normal environment, free memory/storage,
visible device clients and kernel boundary. A failed attempt is not retried.

The coordinator sets `LIB` to its existing approved runtime library path and
`REVIEW` to its current approved fault-review boundary (the same values for
all four windows). These values are not invented by this runbook.

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet51-round2
OUT=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet51-round2/evidence
systemd-run --user --wait --unit=packet51-e1 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p51-a-e1"
```

After E1 finishes safely, run E2 once:

```bash
systemd-run --user --wait --unit=packet51-e2 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p51-a-e2"
```

After both exactness windows pass, run T1 then, after safe completion, T2:

```bash
systemd-run --user --wait --unit=packet51-t1 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p51-a-t1" \
  "$OUT/p51-a-e1/window.json" "$OUT/p51-a-e2/window.json"
systemd-run --user --wait --unit=packet51-t2 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p51-a-t2" \
  "$OUT/p51-a-e1/window.json" "$OUT/p51-a-e2/window.json"
```

The two timing commands above are sequential instructions, not parallel jobs.
Use the coordinator's existing gap policy and verify each finished receipt.
The exact/timing wrappers pin nice19, cores4–15,20–31, and two OpenMP threads,
matching packet46's microbenchmark conditions. They do not alter host settings.

Combine only the two successful fresh timing owners:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/summarize.py" \
  --windows "$OUT/p51-a-t1/window.json" "$OUT/p51-a-t2/window.json" \
  --output "$OUT/p51-a-summary.json"
```

The summary reports every class, full-layer savings and which primary classes
meet the fixed worthwhile-change threshold in both owners. No packet49 engine
switch or speed promotion occurs automatically. New layout allocation and
fresh full-model qualification are required before engine adoption.
