# Exact two-command cycle guard: CPU replay

This prospective worker guard addresses one observed failure: the incomplete-depth task repeatedly alternated the same two Python replacements, each returning exit 0 and `patched`. Full command, return-code, and output records at actions 9–14 form three exact cycles.

The guard appends a **Repetition warning** after those six observed results. If the next command restarts the same cycle, it stops before that command executes. A different command clears the pending cycle. `FINISH` retains its acceptance checks. The existing single-command guard remains in place; `two_command_cycle_warnings` reports the new guard separately, while `repeated_command_warnings` remains the combined total.

Offline replay warns at action 14 and blocks action 15 on the failed trace. All **13 automatically acceptance-passing traces** replay without warnings or stops: three original task traces, three thinking traces, and seven corrected readable-observation traces. Automatic acceptance is distinct from independent review: the thinking zero-cost trace passed acceptance but was rejected in review.

`traces.json` retains every exact action and return-code/output observation used in replay, without truncation. It records original trajectory/result hashes. `report.json` records outcomes and binds all three frozen packet manifests and archives; `capture.json` hashes the compact receipts and records the guard/replay source identities at capture. Verification derives the compact records again from the existing frozen archives, without the original host or raw directories. Full original trajectories remain in those archives.

From the repository root:

```bash
python3 worker/replay_cycle_guard.py --verify --out experiments/local-coding-worker/data/2026-09-14-worker-hardening/cycle
```

To capture into a new directory from raw runs, use `--raw-root /path/to/bench-results --out /path/to/new-receipts`. `--packet-root` can relocate the directory containing the three frozen packets. Capture requires raw trajectory/result byte hashes to match those packets. Verification runs the current guard, reports its source hashes, and compares its outcomes against the historical capture; it does not execute historical Python or recorded commands.

CPU tests cover exact comparison, differing command/output/return-code values, recovery after a different command, warning then stopping before another execution, and unchanged FINISH/acceptance and single-command behavior. The new guard was added after the model campaigns ended.

This is a conservative repetition guard: identical outputs do not prove hidden workspace state made no progress. Model reactions to feedback were not measured. These receipts establish no latency, token-saving, quality, or acceptance improvement, and make no claim about unseen tasks.
