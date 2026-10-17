# Packet53b coordinator windows

Preparation runs no GPU. Run these commands only after the final seal passes
and the coordinator releases physical card0, PCI `0000:23:00.0`. Do not overlap
packet49c or its WS128 record window. Passive admission refuses other Xe
clients. The packet49 oracle and packet49c units are never stopped here.

Set `LIB` to the coordinator's approved runtime library path and `REVIEW` to
its approved **past UTC fault-review boundary** (for example, an actual reviewed
time formatted `2026-10-17T09:00:00Z`, only if that is the coordinator’s reviewed
boundary). Missing boundaries and any future timestamp are refused before launch.
Do not use the scheduled end of the window as the review boundary. Use the same values for all four
windows. These commands intentionally do not invent either value. Execute
one command at a time, verify safe completion, and follow the coordinator's
existing gap policy. No failed launch is automatically retried.

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet53b-virtual
OUT="$P/evidence"
systemd-run --user --wait --unit=packet53b-e1 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p53b-a-e1"
```

After E1 safely passes, run a fresh E2 owner:

```bash
systemd-run --user --wait --unit=packet53b-e2 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p53b-a-e2"
```

After both E receipts pass, T1 and then T2:

```bash
systemd-run --user --wait --unit=packet53b-t1 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p53b-a-t1" \
  "$OUT/p53b-a-e1/window.json" "$OUT/p53b-a-e2/window.json"
```

```bash
systemd-run --user --wait --unit=packet53b-t2 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p53b-a-t2" \
  "$OUT/p53b-a-e1/window.json" "$OUT/p53b-a-e2/window.json"
```

Only after all four complete, calculate the fixed decision:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/summarize.py" \
  --windows "$OUT/p53b-a-t1/window.json" "$OUT/p53b-a-t2/window.json" \
  --output "$OUT/p53b-a-summary.json"
```

The wrappers use script files, nice19, cores4–15,20–31 and a closed environment.
They hash-check CPU gates, source closure, binaries, native E captures and
fresh owner identity. Both timing runs use the same E companions. They pass
the PF_EXITING-tolerant packet52 memory sensor explicitly (fix `b9745a557`), check the kernel journal during
execution, request a cooperative SIGTERM on a stop, and retain an undrained
owner for the coordinator. No hard kill, reboot, driver reset, power setting
or cache change is made. Do not treat an incomplete window as a failed speed
candidate or start a retry loop.

## Duration estimate and fixed decision

Allow 1–3 minutes per E/T window plus coordinator gaps. Packet53's windows
lasted seconds; this is a planning allocation, not a measured duration. Keep
the inherited conservative 2880-second watchdog and 2820-second native
cooperative deadline. A stuck owner is retained, never hard-killed.

Each E window contains 90 comparisons: 15 class arms including controls,
two fixtures, and all three token rows across M1/M2. Each T has 13,860
class-arm records and 25,200 compute events: 11 candidates paired with
production, 630 token-row iterations, HC contributing four events per arm.
There are 10 excluded warmups and 200 measured pairs per M value. Every
K split, HC epilogue, tuple member and local-memory fill stays in timing;
reference evaluation, restoration copies and readback stay outside.

Choose one V for each of the four classes by its minimum paired median M1
saving across both owners (control is allowed). Sum those same choices in
each owner: both totals must reach 35 µs against packet49c production.
V4 is remeasured as a candidate, never substituted for the production control.
M2 and regressions remain reported and cannot rescue M1. A passing result
goes to packet49d in the next brief; this packet does not change the engine.
