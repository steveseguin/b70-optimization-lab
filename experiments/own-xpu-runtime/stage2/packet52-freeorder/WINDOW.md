# Packet52 coordinator windows

Preparation runs no GPU. Run these commands only after the final seal passes
and the coordinator releases physical card0, PCI `0000:23:00.0`. Do not overlap
packet49c or its WS128 record window. Passive admission refuses other Xe
clients. The packet49 oracle and packet49c units are never stopped here.

Set `LIB` to the coordinator's approved runtime library path and `REVIEW` to
its approved UTC fault-review boundary. Use the same values for all four
windows. These commands intentionally do not invent either value. Execute
one command at a time, verify safe completion, and follow the coordinator's
existing gap policy. No failed launch is automatically retried.

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet52-freeorder
OUT="$P/evidence"
systemd-run --user --wait --unit=packet52-e1 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p52-a-e1"
```

After E1 safely passes, run a fresh E2 owner:

```bash
systemd-run --user --wait --unit=packet52-e2 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p52-a-e2"
```

After both E receipts pass, T1 and then T2:

```bash
systemd-run --user --wait --unit=packet52-t1 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p52-a-t1" \
  "$OUT/p52-a-e1/window.json" "$OUT/p52-a-e2/window.json"
```

```bash
systemd-run --user --wait --unit=packet52-t2 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p52-a-t2" \
  "$OUT/p52-a-e1/window.json" "$OUT/p52-a-e2/window.json"
```

Only after all four complete, calculate the fixed decision:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/summarize.py" \
  --windows "$OUT/p52-a-t1/window.json" "$OUT/p52-a-t2/window.json" \
  --output "$OUT/p52-a-summary.json"
```

The wrappers use script files, nice19, cores4–15,20–31 and a closed environment.
They hash-check CPU gates, source closure, binaries, native E captures and
fresh owner identity. Both timing runs use the same E companions. They pass
the zombie-tolerant memory sensor explicitly, check the kernel journal during
execution, request a cooperative SIGTERM on a stop, and retain an undrained
owner for the coordinator. No hard kill, reboot, driver reset, power setting
or cache change is made. Do not treat an incomplete window as a failed speed
candidate or start a retry loop.

## Duration estimate

The fixed timing window watchdog is 1,140 seconds; cooperative drain and
postflight are bounded separately. A kernel stuck beyond drain is retained,
so safe device recovery takes precedence over a wall-clock promise. The
intended T1/T2 duration is below 20 minutes each. Final case counts and the
CPU-preparation-informed estimate are recorded in the preparation note before
sealing. These estimates are planning numbers, not measurements of a device.

Timing excludes CPU reference work, transfers and readback, and includes all
compute stages and epilogues of each class. This is a production-shaped
operator ceiling probe, not a model throughput benchmark. A passing summary
permits the v3 design decision; it launches no oracle or packet53 job.

The frozen five-variant matrix contains252 E comparisons per owner
(`7 classes × 6 orders including control × 2 fixtures × 3 token rows`).
T contains44,100 class-arm records and72,450 compute events per owner
(`630 token-row iterations × 115 events`). There are200 measured and10 warmup
iterations for each M value. HC includes all four low/gate sites; split4
includes its finish stage. The event count is lower than packet51's95,760
full-layer events, whose retained T owners took377–378 seconds, although
packet52 has more individual class resets. That comparison is scheduling
context, not a speed prediction.

**Plan for E1/E2:2–5 minutes each; T1/T2:6–12 minutes each**, plus the
coordinator's gap between windows. These are conservative planning ranges,
not measured packet52 durations. Four input snapshots are cached once;
between arms only that group's operands, outputs and controls are restored.
The16MiB operator scratch/workspace is not recopied for every arm. A bounded
full-shape CPU rehearsal checks the same reset/binding logic. Do not enlarge
the fixed watchdog or trim the matrix based on observed device speed.
