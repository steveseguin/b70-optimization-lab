# Packet197 warm lifecycle window

One manual device-owner lifecycle with eight sequential requests. This is
application/checkpoint correctness work, not a cold performance submission.
The worker owns its native process, request intake, whole-host reservation and
drain permit. The controller owns one endpoint outage and conditional restore.

`helpers.py` reuses the proven packet196 safety and restoration helpers through
`helper-pins.json`. Those sources and packet196 evidence stay unchanged. This
directory adds no native build, generic chain machinery or resume policy.

After the worker's CPU plan is ready:

```sh
python3 -B experiments/own-xpu-runtime/ops/packet197-window/window.py \
  --check --restore-suffix 20261023-restore26 \
  --output experiments/own-xpu-runtime/ops/packet197-window/evidence/window-a
```

The check reads endpoint busy counters, current unit/queue/ownership state and
the CPU-only worker plan. It creates no files, invokes no privilege, and submits
no generation request. The coordinator may replace `--check` with `--run` after
review. All worker, fault-review, controller and restoration paths must be
fresh. The fixed unit is `packet197-warm-request-front-a`; safe process-mode
stop properties, Nice 0 and lane-A CPU placement are declared in the worker
plan and actual launch. An enclosing controller unit must use `window-*` with
`Restart=no`, `SendSIGKILL=no`, `TimeoutStopSec=infinity`, `KillMode=process` and
`ExitType=cgroup`.

Both lanes start paused with empty queues. The controller records their exact
pause bytes and the three active idle owner endpoints, requests each graceful
stop once, and requires the complete privileged passive DRM inventory. It
rechecks the worker plan/source, host/storage floors and fresh fault review
before temporarily removing PAUSE-A. PAUSE-B never changes; the live queues
are never written. Worker launch happens once.

Successful restoration requires a successful inactive unit and a final
`worker.json` proving one native process, one model load, exactly the eight
registered request IDs in order, all seven exactness checks, no live child,
safe exit and drained devices. PAUSE-A is re-armed, a fresh privileged passive
inventory and fault checks pass, and the prior endpoints are restored once.
The existing restoration validates each HTTP request against fault/STOP
guards. `restore_guard.py` executes the pinned parent sources with packet197's
guard bound at their existing operation boundaries and routes the validator
child through that same adapter, so packet197's own output/STOP is checked too.
An independent benchmark is not inferred from these lifecycle checks.

Any fault, external STOP or pause change, worker failure, incomplete receipt,
unknown ownership or deadline halts new work and withholds restoration.
Incident handling preserves existing latches, arms PAUSE-A/STOP-A and worker
output/STOP, and may signal only the worker's main process with one cooperative
SIGTERM. The worker forwards its stop to its own native child. There is no
group signal, hard kill, automatic retry, server restart loop, reboot, driver
reset or power/memory setting change. A retained owner remains for manual
review; no generic predevice resume mode exists.
Changed external PAUSE bytes are preserved and reported while incident STOP
and cooperative drain still proceed. A final pause refusal does not mask the
original failure receipt; it is recorded separately and cannot turn failure
into success.

CPU-only dry interception tests:

```sh
cd experiments/own-xpu-runtime/ops/packet197-window
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest test_window -v
```

The tests intercept service, HTTP, privileged and device operations and use
temporary files. Preparation does not run `--check` or `--run`.
