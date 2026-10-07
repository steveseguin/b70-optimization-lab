# One-shot durable pilot on the two-card host

`durable_host_runner.py` coordinates the already frozen
[pilot](durable/README.md). It lives outside the model-facing source directory,
so adding host supervision does not change that experiment's source identity.

Preparation reads the protected supervisor identity, qualified server profile,
task files, reference outputs and dependencies. It hashes them into `queue.json`.
It performs no device work. Execution refuses changed dependencies or a new boot.

The coordinator waits for the exact protected supervisor to exit, its units and
Harbor clients to finish, and its server stop receipts to confirm release. It
also checks GPU ownership before touching the devices. A port gap between the
old supervisor's retries is not a release. The legacy wrapper's `plan complete`
marker is used only for handoff; its skipped task setup is separately recorded
and is not counted as a completed model trial.

After release, the coordinator runs the existing bounded health probe under the
GPU stage lock. It starts one server with the pinned Plan-E image/profile and
the existing 1.6 GiB host-memory guard. The strict quality/standing-reference gate
must pass, followed by both fixed development extraction gates. Only then can
the eighteen held-out trials begin. Failures stop the sequence. There is no
server retry, driver reset, reboot, power change or process-pattern kill.

The server is stopped through its own STOP receipt on success, failure or
graceful cancellation. Cleanup failures are recorded for manual inspection;
the runner does not forcibly kill an unresponsive GPU owner.

## Commands

Run from the lab root. Use a new output directory for each attempted execution.
The protected supervisor PID must still identify the expected process at
preparation time; the default is specific to the current campaign.

```bash
RUNNER=experiments/qwen38-27b-b70/scripts/context/durable_host_runner.py
OUT=/mnt/fast-ai/bench-results/context-durable-v1-20261007
python3 "$RUNNER" --prepare --out "$OUT" --supervisor-pid 1430254
systemd-run --user --unit=ctx-durable-pilot-v1 --collect \
  -p WorkingDirectory=/home/steve/b70-optimization-lab \
  -p Restart=no -p KillMode=process -p SendSIGKILL=no -p TimeoutStopSec=600 \
  -p "StandardOutput=append:$OUT/coordinator.log" -p StandardError=inherit \
  /usr/bin/python3 /home/steve/b70-optimization-lab/"$RUNNER" \
  --execute --out "$OUT"
```

Do not repeat these commands while that unit or an owned server remains active.
CPU regression tests use mocks and temporary files:

```bash
python3 -m unittest discover \
  -s experiments/qwen38-27b-b70/scripts/context -p 'test_durable_host_runner.py'
```

## Status and results

`status.json` records the current phase; `lifecycle.jsonl` retains its history.
`queue.json` preserves the launch/dependency identity. After model work,
`strict-comparison.json`, `extraction-{report,dispatch}/result.json`, and
`pilot/summary.json` contain the gates and results. `server-stop.json` records
cleanup. A waiting/prepared state is not a started model trial, and completion
does not imply the pilot's correctness or speed gate passed.

```bash
systemctl --user status ctx-durable-pilot-v1.service
cat /mnt/fast-ai/bench-results/context-durable-v1-20261007/status.json
```

To cancel this coordinator, stop its exact systemd unit. Its handler cancels
only owned CPU clients and asks its own server to stop; it does not cancel the
protected campaign it was waiting for.
