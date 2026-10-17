# Packet54 coordinator windows

Preparation runs no GPU. Run these commands only after the final seal passes
and the coordinator releases physical card 0, PCI `0000:23:00.0`. Do not overlap
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
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet54-compute
OUT="$P/evidence"
systemd-run --user --wait --unit=packet54-e1 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p54-a-e1"
```

After E1 safely passes, run a fresh E2 owner:

```bash
systemd-run --user --wait --unit=packet54-e2 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p54-a-e2"
```

After both E receipts pass, T1 and then T2:

```bash
systemd-run --user --wait --unit=packet54-t1 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p54-a-t1" \
  "$OUT/p54-a-e1/window.json" "$OUT/p54-a-e2/window.json"
```

```bash
systemd-run --user --wait --unit=packet54-t2 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p54-a-t2" \
  "$OUT/p54-a-e1/window.json" "$OUT/p54-a-e2/window.json"
```

Only after all four complete, calculate the fixed decision:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/summarize.py" \
  --windows "$OUT/p54-a-t1/window.json" "$OUT/p54-a-t2/window.json" \
  --output "$OUT/p54-a-summary.json"
```

The wrappers use script files, nice 19, cores 4–15,20–31 and a closed environment.
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

Each E window contains54 ordinary comparisons:9 arms including controls, two fixtures,
and all three token rows across M1/M2, plus one exceptional mix comparison
against compiled production. Each T has 6300 class-arm records and
25200 compute events: five eligible candidates paired with production over 630 token
rows; route has4 events, recurrence1, HC10 per row. FFN combine remains control-only and has no paired timing arm.
Every class member remains in timing. CPU references, restoration and output
readback stay outside event intervals; timing pairs are also byte-checked.

Choose one common candidate per class by its minimum paired-median M1 saving
across both owners (control allowed). Packet54 independently needs 25 µs in
both owners. Separately add the exact banked 23.4385/23.4375 µs; both combined
totals ≥40 µs trigger packet49d preparation. M2 and all regressions remain
reported and cannot rescue M1. The combined number is an integration budget,
not an already measured integrated speedup. See PREREGISTRATION.md.
