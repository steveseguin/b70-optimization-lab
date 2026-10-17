# Coordinator handoff

Run from `/home/steve/llm-optimizations`. These commands do not change packet64
or packet61x. No device command was run during preparation.

CPU-only validation of lane B (cards 2+3):

```bash
P=experiments/own-xpu-runtime/stage2/packet64-attribution
V=experiments/own-xpu-runtime/stage2/screen/v3-attr
S="$P/selections/1-production-control"
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/cpu_seal.py" --verify < /dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/screen.py" \
  --profile tp2 --lane B --placement 1 --timing attribution \
  --lineage "$S" --seal "$S/screen-seal.json" \
  --output "$V/evidence/packet64-attribution-B-a" --plan < /dev/null
```

The following is for the coordinator **inside an admitted nice0 `screen-*`
systemd user unit** with cores `4-7,20-23`, `Restart=no`, `SendSIGKILL=no`,
`KillMode=process`, `ExitType=cgroup`, and `TimeoutStopSec=infinity`. Use the
coordinator's current approved library path and fresh reviewed fault receipt:

```bash
P=experiments/own-xpu-runtime/stage2/packet64-attribution
V=experiments/own-xpu-runtime/stage2/screen/v3-attr
S="$P/selections/1-production-control"
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --profile tp2 --lane B --placement 1 \
  --timing attribution --lineage "$S" --seal "$S/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/packet64-attribution-B-a" < /dev/null
```

A fresh output is required. The wrapper keeps lane B's lease through the whole
load, both arms, graceful drain and postflight. Packet64's whole-host speed
windows wait for that lease; a pre-existing hold blocks the new screen. Use it
beside only a chain that implements the same lane protocol. Normal physical
card masks, PID/fd ownership, memory floors, boot-fault review and shared drain
spacing remain. Admission can refuse even when cards 2+3 are empty.

The report is produced automatically after successful teardown:

- `evidence/packet64-attribution-B-a/run/attribution-summary.json`
- `evidence/packet64-attribution-B-a/run/attribution-summary.md`
- `run/{control,attribution}/<prompt>/rank{0,1}/sites.jsonl`
- `run/{control,attribution}/<prompt>/receipt.json` and `timings.jsonl` per rank

To regenerate the report using CPU only:

```bash
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/summarize.py" \
  --run "$V/evidence/packet64-attribution-B-a/run" \
  --output "$V/evidence/packet64-attribution-B-a/run/attribution-summary.json" < /dev/null
```

Missing events, duplicate events, invalid durations, missing layer/draft classes,
control-arm instrumentation, mismatched answers or acceptance, missing cancellation
receipts, and incomplete paired suites refuse the report. A failed report leaves
all raw evidence intact. No automatic rerun, server restart or record submission.
