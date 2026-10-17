# Packet61x coordinator commands

CPU preparation runs only on nice19 helper cores. The device commands below
are for the coordinator, inside separately admitted nice0 user units with the
approved library path. No device command was executed during preparation.
Use a fresh reviewed fault receipt; never reuse an output or retry a fault.

## Screen v3, lane A (physical cards 0+1)

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
V=experiments/own-xpu-runtime/stage2/screen/v3
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane A \
  --lineage "$P" --seal "$P/screen-seal.json" \
  --binary "$P/build/device/own-rt-iq3" --dispatch "$P/dispatch-speed6.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet61x-A-01"
```

## Screen v3, lane B (physical cards 2+3)

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
V=experiments/own-xpu-runtime/stage2/screen/v3
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane B \
  --lineage "$P" --seal "$P/screen-seal.json" \
  --binary "$P/build/device/own-rt-iq3" --dispatch "$P/dispatch-speed6.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet61x-B-01"
```

Each lane belongs in its own coordinator-owned `screen-*` unit with the v3
required properties. V3 supplies the lane's device masks and validates fdinfo.
Both lanes address their masked devices as native 0+1. Compare with matched
controls within v3; prior v1 numbers are motivation, not a v3 baseline.
For CPU plans replace the placement prefix with
`nice -n 19 taskset -c 8-15,24-31 python3 -B`, add `--plan`, and omit
`--fault-review` and `--authorized-device-window`.

## Full chain, cards 0+1

CPU checks immediately before launch:

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/chain_seal.py" --verify
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/storage_precheck.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/plan_gate.py"
```

Inside the coordinator's admitted nice0 unit on cores 0–3,16–19, with
`OMP_NUM_THREADS=2` and the approved `LD_LIBRARY_PATH`:

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
HEAD=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build/device-cards01-a
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
  --prefix-windows "$HEAD/evidence/head-k-a/window.json" "$HEAD/evidence/head-k-b/window.json"
```

Order: K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs → WS128x → WS128.
The runner preserves packet61's admission, cooldowns, graceful teardown,
fault supervision and no retries. All eleven chain outputs must be fresh.
Packet56's unchanged prefix windows and packet49 oracle remain prerequisites.
Legacy operator fixtures remain packet56; both full engines are packet61x.
The screen and chain use the same device executable bytes. No full-chain
quality or performance claim is possible from a screen alone.

CPU-only queue command preview:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_runner.py" \
  --phase all --output-root "$OUT" --plan
```

## October 17 input repair: required CPU preflight

Run this before handing the chain to the coordinator:

```bash
P=experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/check_inputs.py"
```

`queue_runner.py --plan` now runs this check, and execution checks all static
inputs before creating the output directory. Every window also rechecks its
inputs and requires its earlier windows' generated receipts and dispatch before
launch. The complete oracle must therefore already be available, even when
planning the early phase. A plan never creates device outputs.

K1 and K2 now receive an explicit packet-local `--fixtures` path. The 72
fixtures, `cases.txt` and original fixture manifest were restored from the
hash-verified archive of packet56's shared input directory. No parent path or
binary was changed. `prepare_inputs.py` restores these exact bytes or hardlinks
an already verified local copy; it refuses changes after this registered chain
starts. The chain seal binds every fixture hash. Storage admission counts the
local build and external chain outputs, preserving its reserve.

See [input repair closeout](INPUT-REPAIR-CLOSEOUT.md) for the exact scope,
checks, preserved evidence and current storage snapshot. Device admission,
boot/fault review, environment and correctness gates remain required.
