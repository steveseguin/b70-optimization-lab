# Packet165c: restore idle I/O priority on one-card launches

Packet163's first one-card load refused with `ionice -c3 required for model
reads`. Its receipt records zero model bytes read and no compute started.
Packet165 shared the same omission. Each one-card worker now prefixes its
native command with `/usr/bin/ionice -c3`, matching packet58aj's chain.
The row format, closed environment, binary, arithmetic, KV, prompts, waits,
budgets and quality checks are unchanged. Only `worker.py` changes in each
existing seal. The previous workers, seals, readiness and proposals are retained
under `lineage/163` and `lineage/165`.

The four proposal names now contain `p165c`; output paths contain
`device-p165c-`. Each second fresh load references its corresponding new first
load. No live queue was edited and no load was launched.

`check_launch.py` reads the actual proposal, runs the real entry plan, imports
the device path under its closed native environment, and executes the real
worker through native exec interception. The replacement child runs through
the real ionice executable and asks Linux for its I/O class. All four report
class 3; removing the wrapper fails the assertion. Built `--help` accepts every
native flag. All 13 request paths, 26 stream checks per load and exact oracle
prefix checks run with synthetic outputs. The analyzer separately reproduces
the real retained parent's rate. Admission and GPU arithmetic are not tested.

`native_sensors.py` uses the existing CPU marker fixture, with only its order
assertion widened to accept packet163's cold order as well as packet165's warm
order. Its four runs exercise 56 real target resets and 224 sensor checks,
including the after-suite resets and poisoned-reset refusal. Landlock denies
model files and GPU devices. The test checks mutable samples, allocation
identities, cache-zero receipts and open native streams. These synthetic
transports are not model output or performance evidence. Device binaries were
not rebuilt; only the CPU test fixture was compiled through `ops/compile_turn.py`.
Exact fixture inputs and generated sources are retained; ignored build outputs
can be regenerated. Build size and observed RSS are in `evidence/native-sensors.json`.

`check_proposals.py` runs real lanequeue plans and shared report rehearsals on
temporary queue copies. All four plans and reports pass. Shared preparation
adapter warnings remain disclosed in the stderr logs. The initial stale READY
proposal-pin refusal is retained. Pending markers denied device launch while
pins were refreshed; `finalize.py` writes `ready_for_device=true` last, after
validating every new gate and the exact two-line production delta.
Each one-card READY pins exact local snapshots of the new gate receipts under
its own `lineage/packet165c/`. This preserves the queue guard's private packet
boundary; a direct pin into this repair packet is correctly refused. Final
pin admission and plans/rehearsals also pass with these local snapshots.

Run from the repository root, with stdin `/dev/null`, nice19 and assigned cores:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet165c-ionice/check_launch.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet165c-ionice/native_sensors.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet165c-ionice/check_proposals.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet165c-ionice/finalize.py </dev/null
```

CPU preparation stops below 27 GB free disk; build is below 300 MB and memory
below 4 GB. No GPU, services, sudo, host setting or model reads were used.
`iq3-p49-split32-v1` and existing quality limits remain: outputs after token128
are not independently oracle-certified. This fix adds no speed or lossless
output claim. The pre-existing dirty `CURRENT.md` and other workers' files
remain untouched.
