# Packet61 coordinator commands

No device command below was executed during preparation. The coordinator owns
fresh admission, the device window and its durable user unit. Never reuse an
output directory or retry a fault automatically.

## Screen v1: cards 0+1

From the repository root, inside the admitted screen unit with the approved
library path and actual reviewed fault boundary:

```bash
P=experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion
nice -n 19 taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B experiments/own-xpu-runtime/stage2/screen/screen.py \
  --profile tp2 --lineage "$P" --seal "$P/screen-seal.json" \
  --authorized-device-window --faults-reviewed-through "$REVIEWED_THROUGH" \
  --output experiments/own-xpu-runtime/stage2/screen/evidence/packet61-a
```

Append `--plan` for a CPU-only identity/command check. The retained plan uses
`1970-01-01T00:00:00Z` solely to satisfy that parser; it reviews no fault and
must not be used as an actual device admission boundary. Match the control's
placement, priority and wrapper identity when comparing speed.

## Screen v3

The v3 interface accepts packet61 without any changes to its shared folder.
Its CPU plan passed. Device use still waits for v3's own completed wrapper seal
and coordinator admission. Lane A maps physical cards 0+1 to native cards 0+1.
Inside its admitted nice-0 unit, with the lane's fixed CPU placement:

```bash
P=experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B experiments/own-xpu-runtime/stage2/screen/v3/screen.py \
  --profile tp2 --lane A --lineage "$P" --seal "$P/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output experiments/own-xpu-runtime/stage2/screen/v3/evidence/packet61-a
```

For its CPU plan, use `nice -n 19 taskset -c 8-15,24-31 python3 -B` with
`--plan`, omit `--fault-review` and keep the other arguments. A v1/v3 comparison
is a different test condition; use matched controls within one wrapper.

## Full chain: cards 0+1

First recheck storage and the seal on the helper cores:

```bash
P=experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/chain_seal.py" --verify
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/storage_precheck.py"
```

The preparation check passed, with 4,648,105,984 bytes above the required
15,446,804,480 free bytes. This is a snapshot; launch must pass again. The
8 GB floor and full chain reserve remain enforced.

Inside the coordinator's admitted nice-0 unit on cores **0–3,16–19**, with
`OMP_NUM_THREADS=2` and its approved `LD_LIBRARY_PATH`:

```bash
P=experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion
HEAD=experiments/own-xpu-runtime/stage2/packet56-draft-prefix
OUT=/home/steve/own-xpu-runtime-results/packet61-spin-hcfusion/build/device-cards01-b
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle \
  --prefix-windows "$HEAD/evidence/head-k-a/window.json" "$HEAD/evidence/head-k-b/window.json"
```

Order: **K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs → WS128x → WS128**.
The runner retains 90-second K gaps, 305-second W gaps, graceful teardown,
fault checks, exclusive host admission and no automatic retries.

The unchanged prefix reuses packet56's two head windows, verified for distinct
fresh owners, exact bytes and the current boot. The unchanged packet49 target
oracle is reused. All eleven chain windows are new packet61 outputs. Legacy
operator fixture binaries remain packet56; both full engines are packet61.
HC's integrated CPU gate is screen-bound, and full device model correctness
still requires the fresh chain's packet49 comparisons.

The chain output is external; binaries stay under this packet's local `build`
so the screen's repository path guard stays intact. `build/device-cards01-b`
is only a link to the registered external output. `prepare_chain.py` restores
verified parent fixture/input links and refuses changes after the chain starts.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/plan_gate.py"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_runner.py" \
  --phase all --output-root "$OUT" --plan
```

These last two commands are CPU-only and create no device window.

## October 17 input repair: required CPU preflight

Run this before handing the chain to the coordinator:

```bash
P=experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion
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
