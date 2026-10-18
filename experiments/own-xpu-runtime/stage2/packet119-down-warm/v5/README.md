# Packet119 conditional one-load bracket

The frozen packet118 bundle supplies the runtime source and inherited objects.
The fixed 80,128-row draft prefix, target verifier, BF16 KV, split target head,
other fusion, expert half cache and tile16 down layout stay in use. The only
runtime switch is `down_warm=production|p119`.

The five views are production, candidate, production, candidate, production
with one loaded rank pair. Every switch drains and resets all mutable state,
preserves allocation and immutable-weight identities, and rebuilds captures.
Every prompt starts after reset and checks each token against
`iq3-p49-split32-v1`. Per-prompt acceptance remains separate for each arm.

The coordinator may queue the proposal only after two fresh micro processes
pass byte identity and combined gate/up plus down time is at most 0.85 of
production in both orders. The job rereads that evidence and the CPU seal
before any launch. A pending plan is explicitly ineligible to launch.
Expected duration is 15 minutes, with a 60-minute watchdog.

CPU preparation compiles GNU-host and Intel device binaries without opening
a device. Real-shape startup and switching checks exercise only the two views
and both ranks that the bracket will use. Separate miniature reset and IPC
checks disable warming and project expert/head layout to supported miniature
shapes; those checks prove state and transport behavior, not warming arithmetic.
The independent GNU/Intel byte gate and full-shape capture checks supply that
coverage. Native exec guards reject inherited address-space caps or changed
resource limits. Teardown clamps its final sleep to a nonnegative duration.

Use `nice -n 19 taskset -c 8-15,24-31 python3 -B` with stdin from `/dev/null`.
Only CPU CLI entry points install resource caps. Builds use packet94's serial
compile lock. Frozen packet trees and live queues remain read-only. This
bracket is diagnostic and cannot publish a model speed record.

From this directory, run the following CPU preparation commands after the root
packet's operator byte and micro prerequisites exist. Each command starts a
fresh Python process; the exec-limit gate must inherit unlimited address space
from the shell.

```bash
for script in prepare_sources.py build_engine.py full_shape.py reset_gate.py protocol_gate.py exec_gate.py test_v5.py; do
  nice -n 19 taskset -c 8-15,24-31 python3 -B "$script" </dev/null || exit
done
nice -n 19 taskset -c 8-15,24-31 python3 -B cpu_seal.py --operator-evidence ../evidence/cpu-byte-identity.json </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B queue_plan.py </dev/null
```

The resulting proposal is `ops/lane-queue/proposed-p119-v5-B.txt`. Its temporary
queue plan does not modify a live queue. The separate coordinator launch still
requires the two-process micro qualification and exact sealed inputs.
