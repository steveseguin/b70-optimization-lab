# Packet69 measurement handoff

CPU-only plan, from repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet69-rank1-head
V="$P/screen/attr"
S="$P/selections/1-production-control"
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/quick_seal.py" </dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/screen.py" \
  --profile tp2 --lane B --placement 1 --timing attribution \
  --lineage "$S" --seal "$S/screen-seal.json" \
  --output "$V/evidence/p69-attribution-B-a" --plan </dev/null
```

Coordinator only, inside an admitted nice0 `screen-*` systemd user unit,
cores `4-7,20-23`, `Restart=no`, `SendSIGKILL=no`, `KillMode=process`,
`ExitType=cgroup`, `TimeoutStopSec=infinity`; use current approved library
path and boot-bound fault-review receipt:

```bash
P=experiments/own-xpu-runtime/stage2/packet69-rank1-head
V="$P/screen/attr"
S="$P/selections/1-production-control"
taskset -c 4-7,20-23 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 \
  LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$V/screen.py" \
  --profile tp2 --lane B --placement 1 --timing attribution \
  --lineage "$S" --seal "$S/screen-seal.json" \
  --authorized-device-window --fault-review "$FAULT_REVIEW" \
  --output "$V/evidence/p69-attribution-B-a" </dev/null
```

One load, incident64, twelve control requests, twelve observed requests; all
128-token answers checked against packet49. Approximately seven minutes,
not a measured duration or timeout. No automatic retry. Whole-host timing
holds, isolation, memory floor and shared drain spacing stay enforced.

Report: `screen/attr/evidence/p69-attribution-B-a/run/attribution-summary.json`
and `.md`. Rebuild the CPU report after a reporting failure with `summarize.py
--run <run-dir> --output <run-dir>/attribution-summary.json` under the same
nice19/CPU affinity. No new GPU run is needed to repair a report.
