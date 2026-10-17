# Packet63 coordinator screens

Set `FAULT_REVIEW` to the coordinator's fresh reviewed receipt. Run each
command inside its separately admitted nice0 `screen-*` user unit, with the
v3-required properties and approved `LD_LIBRARY_PATH`. These are device
commands for the coordinator; CPU preparation executed only `--plan`.
Do not schedule lane A while packet61x's record chain owns cards 0+1. Use new
output paths for later attempts; never overwrite or automatically retry.

```bash
P=experiments/own-xpu-runtime/stage2/packet63-balance
V=experiments/own-xpu-runtime/stage2/screen/v3
```

**control, lane A, physical cards 0+1:**

```bash
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane A \
  --lineage "$P/selections/control" \
  --seal "$P/selections/control/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet63-control-A"
```

**control, lane B, physical cards 2+3:**

```bash
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane B \
  --lineage "$P/selections/control" \
  --seal "$P/selections/control/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet63-control-B"
```

**draft-hc, lane A, physical cards 0+1:**

```bash
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane A \
  --lineage "$P/selections/draft-hc" \
  --seal "$P/selections/draft-hc/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet63-draft-hc-A"
```

**draft-hc, lane B, physical cards 2+3:**

```bash
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane B \
  --lineage "$P/selections/draft-hc" \
  --seal "$P/selections/draft-hc/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet63-draft-hc-B"
```

The lineage seal selects the binary and dispatch; both selections use the same
executable bytes. V3 applies lane masks; both native ranks address masked cards
0 and 1. The current 23/25 placement and default `token` timing are retained.
Require all 13 exact checks. Screens are nonqualifying; no result here replaces
the full chain or the unchanged packet49 oracle.

For a CPU-only plan, replace the entire `taskset ... env ...` prefix with
`nice -n 19 taskset -c 8-15,24-31 python3 -B`, retain the script and selection/lane
arguments, add `--plan`, and omit `--authorized-device-window --fault-review ...`.
The four retained plans live in each selection's `plan-A.json` / `plan-B.json`.
