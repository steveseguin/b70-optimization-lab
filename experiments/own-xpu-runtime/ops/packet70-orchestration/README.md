# Packet70 preparation helper — no chain launch

Adapted from the lab's frozen `ops/packet64-orchestration`. This helper only
reads evidence and runs CPU preparation. It never starts a service, device
window or companion, and never clears markers, kills or retries work.

Packet65 quick lane A starts after the packet64 chain, about 18:45 UTC.
The helper waits for the chain and both quick-screen units to be terminal and
for the screen batches to finish. It records `screen/quick/compare.py` output
in `compare.log`, and `read_screens.py` uses that same module's validation:
sealed model identity, wrapper/receipt hashes, current boot, exact packet49
tokens, full 13-request coverage, zero caching and class-balanced interval
rates. Existing source and result files are read only.

A candidate must be strictly faster than the mean of the two production
controls **on each lane**, and all twelve screens must pass 13/13 exact checks.
Any invalid/inexact screen prevents an expert upgrade. Choose the largest
minimum gain across the two lanes, breaking ties by the fixed choice order;
otherwise keep production. This is diagnostic selection for a fresh chain,
not a speed or quality promotion. The packet64 preset stays fixed throughout.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/packet70-orchestration/orchestrate.py </dev/null
```

After selection it fast-reseals, verifies the chain seal, checks inputs and
storage, validates all window plans and runs the queue's `--plan`. Exactly two
known boot fault signatures must remain; new faults stop preparation.
It writes `ready.json` with selection evidence and seal hashes, and prints the
exact chain command. **The coordinator runs that command.** No companion is
needed. The manual `device-entry.sh` checks real readiness, boot and hashes
before the existing admitted queue entry. It rejects a mock or stale record.

Current `ready.json` is explicitly pending because both screen lanes have not
finished. CPU checks pass; production is selected. No live helper was left
waiting, and no service or model was started by this task.

Dry run (fully mocked; no subprocess or GPU calls inside orchestration):

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/packet70-orchestration/orchestrate.py \
  --dry-run experiments/own-xpu-runtime/ops/packet70-orchestration/dry-run.json </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops/packet70-orchestration -p test_orchestrate.py -v </dev/null
```

`dry-run-ready.json` is marked mock and cannot authorize device execution.
[Twelve tests](tests.log) cover both-lane selection, one-lane regressions,
equality, an inexact unrelated arm, missing controls, two-control averaging,
invalid rates, precheck failures, new faults and stale/mock readiness.
[Dry-run trace](dry-run.log), [current screen snapshot](screens-current.json),
[packet](../../stage2/packet70-record-bundle/README.md),
[task note](../../../../notes/2026-10-17-own-runtime-packet70.md).

October 17 K2 repair readiness is in `ready.json`; `ready-k2fail.json` preserves
the previous command/seal record. The new command uses the unused
`packet70-chain-k2fix` unit and `chain-k2fix.log`. It starts a fresh full chain
at the registered output, after the stopped chain was archived with STOP.
The repair has not launched it. `verify_ready.py` verifies the current boot,
command, selection, chain seal and orchestration source hashes.
