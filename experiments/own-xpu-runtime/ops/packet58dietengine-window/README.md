# One-card diet engine window

This driver runs one registered screen row, `packet58dietengine-one-card-v5-A`,
on lane A/card 0. It is a manual operation for the owner's continued optimization
window. It has no retry, automatic recovery, power/memory changes, reboot or
driver-reset path. Preparation of these files does not launch the window.

Read-only admission (requires the packet READY marker):

```sh
python3 -B experiments/own-xpu-runtime/ops/packet58dietengine-window/window.py \
  --check --restore-suffix 20261023-restore24 \
  --output experiments/own-xpu-runtime/ops/packet58dietengine-window/evidence/window-a
```

The coordinator may replace `--check` with `--run` after reviewing the packet and
the actual current host state. Use a fresh evidence directory and restoration
suffix; an interrupted operation is inspected, never retried under a new name
without reviewing the original failure.

The check reads FP8 `/metrics` and vision `/slots` to require no active or queued
requests. Missing metrics or slot status refuse. It also requires both queues
empty, both PAUSE files present, no STOP or ownership/inflight markers, unchanged
safe endpoint stop properties, the packet's READY/proposal hash, a fresh output,
27 GB root free, and the queue backend's reviewed boot/fault baseline. It creates
no file or lock and issues no generation request.

The run copies the previous queue and exact PAUSE bytes to its receipts before
publishing one row. The live plan must pass before endpoints stop. Stop requests
use their existing graceful process-mode wrappers, `SendSIGKILL=no`, no timeout
escalation and no restarts. The event cursor is captured before runner launch.
The runner has the same safe stop properties. A successful DONE must be followed
by inactive runner, no ownership/inflight markers or readable device clients,
both coordinator guards passing and an empty queue before restoration. The
owned STOP file is archived only after that proof and an inode/content check;
a foreign or replaced STOP refuses restoration and remains in place. PAUSE-A is restored byte for
byte, and PAUSE-B is never modified.

Any failure or new/unreadable fault evidence leaves PAUSE/STOP armed and never
starts the restoration helper. An active runner at the drain deadline is left
alone with STOP retained; there is no process kill. The queue runner and packet
supervisor remain responsible for graceful incident shutdown within an active
row. No new window or endpoint request is admitted by this driver afterward.

Restoration is once, only after a clean completed window, for the three endpoints
that were verified active before it. `restore.py` retains the original launcher
identities and settings; its source is recorded in `restore-provenance.json`.
It adds exact reviewed fault checks during startup and before each validation.
`validate.py` pins the existing validator and checks the kernel fault baseline
before every HTTP request. A failed validation prevents the next endpoint's
validation; a failed restore is recorded and never retried. Partial successfully
started endpoints are not automatically killed or rolled back.

Drain admission invokes the fixed `passive_device_holders.py` helper through
`sudo -S` with the existing outside-Git credential supplied only on stdin.
The helper reads sysfs vendor/device numbers and `/proc` descriptor metadata;
it never opens a device or runs compute. It requires all four Intel devices,
fails on any holder or unreadable ownership, and tolerates only vanished
processes/descriptors. Both existing coordinator guards are additionally
required. No privileged helper has been invoked during CPU preparation.
Idle HTTP checks are a
point-in-time check; the owner should avoid submitting new work during the
announced temporary application outage.

Mock-only tests:

```sh
cd experiments/own-xpu-runtime/ops/packet58dietengine-window
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest test_window -v
```
