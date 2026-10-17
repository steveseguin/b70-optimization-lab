# Coordinator commands

Run from `/home/steve/llm-optimizations`. No chain was launched during preparation.
Packet64's running chain and packet65's quick screens retain their coordinator.
Lane A's quick screens are scheduled after packet64 ends, about 18:45 UTC.

CPU selection and pre-check helper (waits for both screen lanes, never launches):

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/packet70-orchestration/orchestrate.py </dev/null
```

It reads packet65's `screen/quick/compare.py` output and validated receipts,
selects an expert only if all twelve screens are exact (13/13 each) and it
beats the mean of the two same-lane production controls on both lanes, then
runs the following CPU pre-checks. Missing or invalid candidate evidence cannot
select an expert. Incomplete live screens keep readiness pending. It writes
`ops/packet70-orchestration/ready.json` and prints the exact `systemd-run`
command; only the coordinator executes that printed command. The manual entry
refuses mock/stale readiness. No lane-B companion is launched or needed.

Manual CPU checks, with an example production reseal:

```bash
P=experiments/own-xpu-runtime/stage2/packet70-record-bundle
OUT=/home/steve/own-xpu-runtime-results/packet70-record-bundle/build/device-cards01-a
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/fast_reseal.py" --experts production </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/chain_seal.py" --verify </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/check_inputs.py" --output-root "$OUT" </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/storage_precheck.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/plan_gate.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_runner.py" --phase all --output-root "$OUT" --plan </dev/null
```

`--experts` accepts production, wide64, wg64, wg128 and prefetch64. Placement,
draft and miss defaults are fixed to `1`, `draft-hc`, `batch`. Resealing checks
all existing view sources/artifacts/gates, archives the old chain seal, copies
the selection, and refreshes the local chain/submission pins. It refuses once
any packet70 `device-cards01-*` chain exists. No recompile occurs.

The printed device command uses `device-entry.sh chain`, which retains the
approved environment file, fixed cores 0-3,16-19, nice 0, OMP=2, and the two
fresh packet56 head prerequisites. The registered chain is
K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs → WS128x → WS128.
All ten gaps are 90 seconds; all native drain and health gates still apply.
No retry, reboot, kill, power change or resident service restoration is added.
