# Packet64 coordinator commands

Run from `/home/steve/llm-optimizations`. Preparation used only nice19 helper
cores, without devices or services. All device commands below are for the
coordinator. Outputs must be fresh; no automatic retries.

## Choose the final default, without compiling

Run before any packet64 chain starts. The four kernel choices and both
placements already have immutable screen seals. This only changes the active
chain selection and its bindings; it archives the previous chain seal.

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/fast_reseal.py" \
  --placement 1 --draft production --miss control
```

Use `--placement 1-split23`, `--draft draft-hc`, and/or `--miss batch` only for
those screen-selected alternatives. Default: `1-production-control`.
The command verifies source, fixture and executable hashes, refreshes submission
pins, and refuses once any external `device-cards01-*` output exists. The
measured reseal takes about 1.3 seconds, below the two-minute limit.

## Screen plans: all eight selections on both lanes

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
V=experiments/own-xpu-runtime/stage2/screen/v3-packet64
for placement in 1 1-split23; do
  for draft in production draft-hc; do
    for miss in control batch; do
      choice="$placement-$draft-$miss"
      for lane in A B; do
        nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/screen.py" \
          --profile tp2 --lane "$lane" --placement "$placement" \
          --lineage "$P/selections/$choice" \
          --seal "$P/selections/$choice/screen-seal.json" \
          --output "$V/evidence/packet64-$choice-$lane-a" --plan
      done
    done
  done
done
```

The same 16 plans pass with `V=experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes`.
Retained plans are `selections/<choice>/plan-{A,B}.json` and
`plan-lanes-{A,B}.json`. The original sealed v3 was not edited.

## Coordinator screen: lane A

Inside an admitted **nice0 `screen-*` systemd user unit** on the stated cores,
with `Restart=no`, `SendSIGKILL=no`, `KillMode=process`, `ExitType=cgroup`,
`TimeoutStopSec=infinity`, and the approved library path:

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
V=experiments/own-xpu-runtime/stage2/screen/v3-packet64
PLACEMENT=1
CHOICE="$PLACEMENT-production-control"
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane A --placement "$PLACEMENT" \
  --lineage "$P/selections/$CHOICE" --seal "$P/selections/$CHOICE/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet64-$CHOICE-A-a"
```

`FAULT_REVIEW` is the coordinator's fresh, boot-bound reviewed receipt. The
wrapper validates it and all normal memory, fault and isolation gates.

## Coordinator screen: lane B, including beside the packet64 chain

Use the lane-aware companion; it joins the chain's hold-lane-B protocol.
A whole-host chain window waits for B to finish and blocks new B launches.
Do not use the standalone wrapper beside the chain.

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
V=experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes
PLACEMENT=1
CHOICE="$PLACEMENT-production-control"
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane B --placement "$PLACEMENT" \
  --lineage "$P/selections/$CHOICE" --seal "$P/selections/$CHOICE/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet64-$CHOICE-B-a"
```

The same admitted unit properties apply. Change CHOICE and PLACEMENT together
for the other sealed views. The companion's device entry accepts B only;
its A plans exist for static coverage, not concurrent A screens.

## Full sealed chain: K0 through WS128

CPU preflight immediately before launch:

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
OUT=/home/steve/own-xpu-runtime-results/packet64-record-bundle/build/device-cards01-a
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/chain_seal.py" --verify
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/check_inputs.py" --output-root "$OUT"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/storage_precheck.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/plan_gate.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_runner.py" \
  --phase all --output-root "$OUT" --plan
```

Inside the coordinator's admitted nice0 user unit, cores `0-3,16-19`,
`OMP_NUM_THREADS=2`, and approved `LD_LIBRARY_PATH`:

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
PREFIX=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet64-record-bundle/build/device-cards01-a
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
  --prefix-windows "$PREFIX/evidence/head-k-a/window.json" "$PREFIX/evidence/head-k-b/window.json"
```

Order: K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs → WS128x → WS128.
The queue obtains rank/split from the sealed bundle. `target_split=0` is the
native spelling of balanced 24/24; `23` means 23/25. All windows use draft rank1.
Full speed/quality still require these fresh packet64 windows. The completed
packet49 oracle and the two current-boot packet56 prefix receipts are prerequisites.

## Explicit early-receipt resume

No parent receipts are interchangeable with this combined engine. Only a stopped
packet64 chain with passed K0..W0p, matching binary, topology, selection and boot
can be pinned. The source stays intact. This is an explicit coordinator action,
not a retry loop; first resolve the reason the original chain stopped.

```bash
P=experiments/own-xpu-runtime/stage2/packet64-record-bundle
BASE=/home/steve/own-xpu-runtime-results/packet64-record-bundle/build
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/prepare_resume.py" \
  --source "$BASE/device-cards01-a" --destination "$BASE/device-cards01-b"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/check_inputs.py" \
  --output-root "$BASE/device-cards01-b" --resume-from "$BASE/device-cards01-a"
```

Then, inside the same admitted coordinator unit conditions:

```bash
bash "$P/coordinator_windows.sh" --phase model --output-root "$BASE/device-cards01-b" \
  --resume-from "$BASE/device-cards01-a" --wait-oracle \
  --prefix-windows "$PREFIX/evidence/head-k-a/window.json" "$PREFIX/evidence/head-k-b/window.json"
```

The helper archives the old seal, binds every early file and admission sidecar,
registers the fresh output, reseals wrapper metadata, and prepares only the early
copies. KD..WS128 are always fresh. The original sidecar paths remain preserved
and hash-bound; changed or missing proof fails before a new lane reservation.
