# Packet69 quick token screens

Seven immutable views share one binary: production, target-wide64,
target-wide128, draft-head-wide64, draft-attention, draft-hc and combined.
Production is first and last on both lanes. Lane B reverses the six candidates.
The default stays production. All device output, speed and draft acceptance
results are pending the coordinator.

The wrapper is copied from packet65's `screen/quick/`, with packet70's corrected
post-drain release sequence. It saves checked request inputs before FINISH,
confirms process exit, isolation and postflight, releases the cooperative and
legacy lane locks, then aggregates on CPU. Report failure leaves raw data and
`report-failure.json`; it cannot leave an active lane marker or device-fault
latch. Drain, worker or postflight failure retains the marker. Fifteen mocked
CPU checks cover both paths, full request flow, all job orders, stop-on-failure,
mask isolation and class-balanced timing. All sixteen plans pass.

Each screen loads once, checks incident64 plus all twelve 128-token prompts
against packet49, then drains gracefully. Full BF16 KV, original target weights,
91,392-row draft prefix, 97 GiB admission floor, 8 GiB host reserve, anonymous
memory guard, fault review, shared drain spacing and timing holds remain.
No retries or services are started by the job runner. Eight fresh screens per
lane with seven 90-second gaps take an estimated 39 minutes plus admission and
drain contention. The 3,600-second watchdog is per screen, not per lane job.

CPU-only validation:

```bash
P=experiments/own-xpu-runtime/stage2/packet69-rank1-head
Q="$P/screen/quick"
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$Q/quick_seal.py" </dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$Q/run.py" --lane A --jobs "$Q/jobs-A.txt" --plan </dev/null
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$Q/run.py" --lane B --jobs "$Q/jobs-B.txt" --plan </dev/null
```

Coordinator commands, from repository root with current approved library path
and boot-bound `FAULT_REVIEW`. These are instructions only; preparation did
not execute them. Both units may run on their admitted lanes:

```bash
Q=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet69-rank1-head/screen/quick
: "${FAULT_REVIEW:?Current reviewed fault receipt required}"
: "${P49_LDP:?Coordinator-approved library path required}"
systemd-run --user --unit=screen-p69-quick-A \
  --property=Restart=no --property=SendSIGKILL=no --property=KillMode=process \
  --property=ExitType=cgroup --property=TimeoutStopSec=infinity --property=Nice=0 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/taskset -c 0-3,16-19 /usr/bin/env -i PATH=/usr/bin:/bin \
  OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" /usr/bin/python3 -B "$Q/run.py" \
  --lane A --jobs "$Q/jobs-A.txt" --fault-review "$FAULT_REVIEW" --authorized-device-window </dev/null
systemd-run --user --unit=screen-p69-quick-B \
  --property=Restart=no --property=SendSIGKILL=no --property=KillMode=process \
  --property=ExitType=cgroup --property=TimeoutStopSec=infinity --property=Nice=0 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/taskset -c 4-7,20-23 /usr/bin/env -i PATH=/usr/bin:/bin \
  OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" /usr/bin/python3 -B "$Q/run.py" \
  --lane B --jobs "$Q/jobs-B.txt" --fault-review "$FAULT_REVIEW" --authorized-device-window </dev/null
```

After both jobs finish:

```bash
OMP_NUM_THREADS=2 nice -n 19 taskset -c 8-15,24-31 python3 -B "$Q/compare.py" </dev/null
```

The comparison rechecks all thirteen token streams and sealed identities,
computes 99 intervals between token timestamps 1 and 100, takes the median
within each prompt class and then across classes, and compares against the
mean of that lane's two fresh controls. It prints draft acceptance for every
view. Draft arithmetic changes are judged by target exactness and end-to-end
speed together with acceptance. No guessed saving is a measured result.
Lane-parallel rates are diagnostics; a winner still needs fresh isolated
measurement and the full sealed qualification chain before promotion.
