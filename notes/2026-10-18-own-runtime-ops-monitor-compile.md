# Device-time accounting and compiler admission — October 18

Hourly review 24b counted packet124c's waiting chain as busy. Its W2m hold
started around 13:37 UTC while lane B still owned its window; A's native
children started around 14:03. Those 26 minutes are idle admission waiting,
not device work. The frozen packet94 compiler gate also treated that pending
hold as a running whole-host window and unnecessarily stopped CPU preparation.

The ops review now uses device evidence instead of service lifetimes. It reads
current-boot window/request receipts, rank identities and device-isolation
observations, plus live `own-rt-iq3` children from device builds. Queue events
and the user journal retain attribution. Rank pairs and duplicate receipts are
unioned. B receives whole-host hold credit only over evidenced device work.
`idle_admission_wait` is reported separately per lane and remains idle. The
CLI and existing report headings remain available.

Historical wrappers do not always save exact device exit times. Their last
proven request or device observation is a conservative endpoint; service exit,
drain completion and file modification times are never substitutes. Missing
clocks are disclosed. Consequently these totals can undercount old work; a
gap without evidence is not a claim that all cards were physically idle.
This change makes no GPU performance claim.

The new [ops compiler turn](../experiments/own-xpu-runtime/ops/compile_turn.py)
allows a compile while B's active marker remains and the whole-host owner has
no device child. It blocks when B releases its marker or the owner has a native
device descendant. It retains the compiler flock, foreign compiler detection,
ten-second polling, one-hour blocker deadline and `build_engine.limits()`.
Malformed coordination stays conservative. This is observation-based admission;
it does not interrupt compilers or atomically coordinate a later device launch.
Packet94 and all other frozen compile gates are unchanged. Future briefs use
the ops copy as documented in [LATCH-POLICY.md](../experiments/own-xpu-runtime/ops/lane-queue/LATCH-POLICY.md).

## Evidence and checks

The [minimal fixture](../experiments/own-xpu-runtime/ops/fixtures/admission-wait/README.md)
replays a chain service from 13:10 to 14:09, its 13:37–14:03 admission wait,
native start at 14:03, last proven work at 14:05 and drain at 14:07. It expects
26 minutes `idle_admission_wait` and two minutes evidenced device occupancy,
including the corresponding B hold. These are synthetic regression times,
not benchmark measurements. The local packet124c evidence consulted was
`stage2/packet124c-record-bundle/build/device-cards01-a/W2m-lane-admission.json`
and its `W2m/run/receipt.json` under `experiments/own-xpu-runtime/`.

All **27 CPU tests pass**. They cover the fixture through the CLI, per-lane and combined unions,
requesting-lane idle subtraction, screen receipts, live children, PID reuse,
CPU mocks, zombies, old boots, absent/invalid clocks, clipping, pending holds,
release-before-device admission, foreign compilers, serialization, exceptions,
timeouts and safety-limit failures. Run from the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/ops -p 'test_*.py' -v < /dev/null
```

The read-only live review also identifies the 13:37–14:03 interval as
`idle_admission_wait`. No GPU workload, service, sudo operation, host setting,
live queue or marker was changed. Pull initially refused unrelated dirty files;
fetch confirmed HEAD equaled origin/main. Those files remain untouched.
