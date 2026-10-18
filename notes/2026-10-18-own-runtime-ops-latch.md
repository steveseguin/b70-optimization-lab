# Own-runtime queue latch isolation — 2026-10-18

The task brief records a lane-A `p103-…-composite-A-0-control` software failure
at 08:02 UTC (`mmap failed`) while the boot's kernel fault count stayed at two.
Its lane-A v3 latch stopped lane B at the queue guard. Hourly review 19 requested
lane-local queue admission when the reviewed kernel fault count is unchanged.

The operational change is confined to
[`lanequeue.py`](../experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py).
The existing global kernel check still runs first, using the authoritative
window driver's FAULT/DELETED expressions. It requires the reviewed boot
prefix `2cba7160` and count two, now also explicitly requiring an integer.
A wrapper-shaped, reviewed-boot latch for A blocks A only; B is symmetric.
Unknown names, lane-less names and other-boot names remain global. No restart
can rebaseline a third fault line. The existing recorded job-start comparison
also remains intact.

No owner-marker, teardown, PAUSE/STOP, inflight, cooldown or failed-job rule
was changed. The tests use temporary latch/marker files and fake fault counts;
none touches the live coordination state.

The [policy](../experiments/own-xpu-runtime/ops/lane-queue/LATCH-POLICY.md)
documents an important remaining boundary: the frozen v4 wrapper's own
`screen_main()` still checks all current-boot v3 latches. This task fixes the
queue-driver rejection only. It does not certify that a frozen screen can run
while the other lane's latch remains. Wrappers and their review helpers were
read but left unchanged; recovery and driver restarts remain coordinator work.

Validation on `steve-b70s`, all at nice 19, cores `8-15,24-31`, Python `-B`,
with stdin `/dev/null`:

- `python3 -B -m unittest discover -s experiments/own-xpu-runtime/ops/lane-queue -v`:
  **58 tests passed** (49 existing, nine added). New cases cover A/B symmetry,
  third-fault refusal including a fresh backend, changed count without a latch,
  lane-less/ambiguous/other-boot latches, both lane latches, unreadable counters,
  retained latch bytes and a dead owner. Existing teardown and PAUSE tests pass.
- `python3 -B experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py plan --lane A`:
  exit 0 before and after; the live A queue had no pending job output.
- The same read-only plan with `--lane B`: exit 0 before and after, identical
  three passing rows: `packet106b-B-grid-1`, `packet106b-B-grid-2`, and
  `packet106b-B-grid-3`, each with `seal: checked by packet plan/wrapper`.
  Plans check queue inputs and seals; they do not exercise live kernel/latch
  admission or launch devices. The unit tests establish the guard behavior.
- `git diff --check` passed.

`git pull --rebase` refused the unrelated dirty orchestration files. `git fetch`
then confirmed HEAD and origin/main both at
`ace4fadda79d9440859e7d1ee85687540924c843` before editing. Work stayed on main;
the focused commit uses `git commit --only -- <paths>` and is pushed immediately.
No GPU work, service action, sudo, settings change, or live queue/event/inflight/
PAUSE/coordination/latch mutation was performed. Existing dirty work is retained.
