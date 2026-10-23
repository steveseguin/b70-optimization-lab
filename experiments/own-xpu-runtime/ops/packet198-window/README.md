# Packet198 one-shot postreply checkpoint window

This controller admits one card0 native owner for eight sequential requests
and 1,408 generated tokens. Each reply is followed by one explicit protocol-v2
disposition: five saves and three releases. The last request must release its
pending state before the clean `stopped` event. This is a lifecycle and exactness
pilot, with no throughput or serving qualification.

The [worker](../../stage2/packet198-postreply-checkpoint/device_worker.py) saves
the full visible history. In particular, the resume save includes the original
prompt, its saved 256 generated tokens, and the new 128 generated tokens.
The worker gates every RUN, SAVE and RELEASE on the existing fault/stop/resource
checks. It owns the whole-host reservation and drain permit.

The controller is an explicit copy of the proven packet197 controller with fixed
packet198 paths, stronger postreply terminal checks, and an early planned-write
floor check. [helper-pins.json](helper-pins.json) binds the frozen packet197
implementation and the unchanged packet196 passive inventory/restoration helpers.
The worker separately binds its frozen packet197 parents. Parent files remain
unchanged; no import redirects affect another process.

Read-only admission, after readiness sealing and independent review:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/packet198-window/window.py --check \
  --restore-suffix 20261023-restore27 \
  --output experiments/own-xpu-runtime/ops/packet198-window/evidence/window-a
```

The owner coordinator alone may replace `--check` with `--run`. No device or
service operation occurs merely by preparing these files. All output paths must
be fresh; there is no retry or resume mode. The fixed worker unit is
`packet198-postreply-checkpoint-a`, and its result directory is
`stage2/packet198-postreply-checkpoint/evidence/device-p198-lifecycle-A-a`.

Admission requires both queues empty, both pause latches present, no stop latch,
unchanged reviewed fault history, no other owner, idle safely stoppable owner
endpoints, and the sealed worker plan. The 27 GB root floor plus the 800 MB write
reservation must fit before endpoints stop and again after passive drain.
The owner endpoints stop once using their existing graceful process semantics.
Only PAUSE-A is archived and removed; PAUSE-B is preserved. Root-owned passive
device-FD inventories prove both initial and final drain.

Restoration occurs once only after the complete eight-request/eight-control
proof, exactness checks, successful worker exit and passive drain. It uses the
inherited owner endpoint recipe and [restore_guard.py](restore_guard.py), which
checks packet198 output STOP, global STOP and faults before each new startup or
validation request. Any incident preserves external latch bytes, stops intake,
and may send one cooperative SIGTERM to the exact worker main process. No group
signal, forced kill, reboot, reset, restart chain or power/memory change exists.

[mock-tests.json](mock-tests.json) and [mock-tests.log](mock-tests.log) record
CPU-only tests with temporary directories and intercepted operations. They cover
fault/stop handling, external pause changes, unknown device owners, terminal
receipt races, restore boundaries, exact controls, and refusal of an incomplete
final release. The worker tests additionally check production launch interception,
resumed visible history, final release, and fault refusal between reply and SAVE.
