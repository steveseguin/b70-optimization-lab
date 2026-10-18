# Packet66 lane-B screen

Coordinator only. **No device window was run during preparation.** Use the
frozen lane-aware wrapper without modification. It handles chain timing holds,
device masks, process ownership, memory/fault checks, graceful stop and drain
spacing. It loads once, runs incident64, then all 12 fixed prompts with 128
generated tokens each and exact packet49 comparisons. d2 is discarded.

Expected active duration is **about four minutes**, including ordinary load
and teardown. The extra pass and backup copies may add time. Admission waits
for lane A's protected timing windows and shared drain spacing are additional
and unbounded by that estimate. The frozen inner watchdog is **3,600 seconds**,
15× the four-minute estimate, exceeding the required 4× margin. Do not wrap
the unit in a force-killing timeout or retry it automatically.

The coordinator exports its approved `P49_LDP` library path and sets
`FAULT_REVIEW` to its fresh, validated review receipt. From the repository root:

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe
systemd-run --user --unit=screen-packet66-B-01 \
  --property=Restart=no --property=Nice=0 \
  --property='CPUAffinity=4-7 20-23' \
  --property=KillMode=process --property=SendSIGKILL=no \
  --property=ExitType=cgroup --property=TimeoutStopSec=infinity \
  --working-directory=/home/steve/llm-optimizations \
  --setenv="P49_LDP=$P49_LDP" \
  /usr/bin/taskset -c 4-7,20-23 /usr/bin/bash \
  "$P/coordinator_screen.sh" "$FAULT_REVIEW"
```

The entry expands to this exact wrapper call inside that nice0 unit:

```bash
P=experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe
V=experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes
env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
  /usr/bin/python3 -B "$V/screen.py" --profile tp2 --lane B \
  --placement 1-split23 --lineage "$P" --seal "$P/screen-seal.json" \
  --binary "$P/build/device/own-rt-iq3" --dispatch "$P/dispatch-speed6.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet66-B-01" < /dev/null
```

Physical cards are **2+3**, PCI `0000:43:00.0` and `0000:47:00.0`; the masked
engine sees native card arguments 0+1. CPU cores are **4–7,20–23**. Output must
not exist. A refused or failed window is evidence; never delete it to retry.

After the window has passed, finish the CPU report:

```bash
P=experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe
V=experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/analyze.py" \
  --screen "$V/evidence/packet66-B-01" \
  --output "$P/evidence/device-acceptance.json" < /dev/null
```

This emits per-prompt/per-class a2, extra-pass wall/GPU time, measured-a2 ±0.05
conditional projections, and a ≥10% screening decision. The diagnostic screen
does not qualify a record or authorize a full chain.

CPU-only plan verification, safe before coordinator admission:

```bash
P=experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe
V=experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes
nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/screen.py" \
  --profile tp2 --lane B --placement 1-split23 --lineage "$P" \
  --seal "$P/screen-seal.json" --output "$V/evidence/packet66-B-01" \
  --plan < /dev/null
```
