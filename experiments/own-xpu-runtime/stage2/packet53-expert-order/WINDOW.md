# Packet53 coordinator windows

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
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet53-expert-order
OUT="$P/evidence"
systemd-run --user --wait --unit=packet53-e1 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p53-a-e1"
```

After E1 safely passes, run a fresh E2 owner:

```bash
systemd-run --user --wait --unit=packet53-e2 --property=KillMode=none \
  bash "$P/coordinator-exact.sh" "$LIB" "$REVIEW" "$OUT/p53-a-e2"
```

After both E receipts pass, T1 and then T2:

```bash
systemd-run --user --wait --unit=packet53-t1 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p53-a-t1" \
  "$OUT/p53-a-e1/window.json" "$OUT/p53-a-e2/window.json"
```

```bash
systemd-run --user --wait --unit=packet53-t2 --property=KillMode=none \
  bash "$P/coordinator-timing.sh" "$LIB" "$REVIEW" "$OUT/p53-a-t2" \
  "$OUT/p53-a-e1/window.json" "$OUT/p53-a-e2/window.json"
```

Only after all four complete, calculate the fixed decision:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/summarize.py" \
  --windows "$OUT/p53-a-t1/window.json" "$OUT/p53-a-t2/window.json" \
  --output "$OUT/p53-a-summary.json"
```

The wrappers use script files, nice19, cores4–15,20–31 and a closed environment.
They hash-check CPU gates, source closure, binaries, native E captures and
fresh owner identity. Both timing runs use the same E companions. They pass
the PF_EXITING-tolerant packet52 memory sensor explicitly (fix `b9745a557`), check the kernel journal during
execution, request a cooperative SIGTERM on a stop, and retain an undrained
owner for the coordinator. No hard kill, reboot, driver reset, power setting
or cache change is made. Do not treat an incomplete window as a failed speed
candidate or start a retry loop.

## Duration estimate

Plan E1/E2 at **2–5 minutes each** and T1/T2 at **6–12 minutes each**, plus
coordinator gaps. These are conservative allocations, not measured durations.
Packet52's completed windows took about 34s E and 30s T. Packet53 has fewer
cases and may be similarly short, but its persistent candidates are unmeasured.
The fixed cooperative watchdog is2880s (48min), at least4× the upper12min
estimate; native deadline2820s leaves60s before the wrapper stop request.
Cooperative drain/postflight are separate, and a stuck owner is retained.

Each E window has60 comparisons: two fixtures, three token rows across M1/M2,
and ten class arms including controls. Each T has10080 class-arm records and
compute events:630 token-row iterations × eight candidate/control pairs ×2.
There are200 measured and10 excluded warmup iterations for each M value.
Timing includes the SLM codebook fill and all persistent loop work. It excludes
host reference evaluation, restoration copies and readback. M2 sums both
serial rows. Report all regressions; no representative arm is dropped.

The common expert selection must save at least30us per ordinary M1 layer in
**both** fresh owners. A pass is an operator-screen result only; it does not
integrate kernels, rerun an oracle or claim a model throughput improvement.
