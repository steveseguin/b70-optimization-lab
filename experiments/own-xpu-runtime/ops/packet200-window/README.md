# Packet200 outer-window scaffold

This directory prepares CPU contract checks for one bounded interactive owner.
It has no operational CLI, service/queue action, fault capture or worker launch.
The worker's future gates and `READY-FOR-DEVICE.json` must precede an operational
controller. Existing packet199/packet196 sources remain unchanged and are bound
by [helper-pins.json](helper-pins.json).

## Minimal topology to reuse

1. Admit the source/worker plan and independently reviewed storage forecast.
   Verify both queues empty and paused, no STOP or other owner, unchanged boot
   faults, idle daily endpoints and their graceful-stop properties.
2. Record endpoint identities and exact pause bytes. Stop the three existing
   daily applications once; wait for passive privileged drain without hard kill.
3. Recheck source closure, memory and storage. Require a fresh fault review.
   Under the queue edit lock, verify both empty queues and unchanged pause bytes,
   then remove only PAUSE-A. Preserve PAUSE-B.
4. Start one worker unit with `Restart=no`, `SendSIGKILL=no`,
   `TimeoutStopSec=infinity`, `KillMode=process`, `ExitType=cgroup`. The owner
   uses card0 and the admitted lane-A affinity/nice. No retry/resume path exists.
5. Watch fault/STOP/pause state and worker completion. A new incident halts
   intake; at most one cooperative main-process SIGTERM belongs to the outer
   controller. No group signal, restart, reset or forced close is allowed.
6. Restore PAUSE-A's original bytes. Only complete runtime **and evidence**
   success, successful worker exit and passive whole-host drain permit one
   restoration of the prior three applications. Guard every restored start and
   validation request. External STOP or latch changes block restoration.

The eventual restored suffix must be supplied explicitly and proven fresh;
restore29 is a candidate name, not a reservation or action performed here.

## Interactive completion differs from packet199

Packet199 required six named requests, five SAVE controls, one RELEASE and fixed
reference comparisons. Packet200 permits zero through sixteen completed turns;
the request/control counts must agree and no reply may remain pending or be
discarded. Normal idle/deadline/requested closure with zero turns can establish
safe lifecycle completion, but does not establish model correctness or serving
use. There is no fixed-output exactness or throughput qualification claim.

Success requires two matching durable records. `pre-completion.json` proves
runtime/resource drain before coordination completion while the control writer
is still open. Final `worker.json` acknowledges coordination completion and
closed stderr/control writers. A successful worker-unit exit additionally proves
the terminal writer finished closing. Missing/mismatched pre-completion evidence
or a post-completion evidence failure blocks restoration even if device drain
already succeeded.

A native exit alone is insufficient. The terminal contract must separately
prove runtime success, evidence success, exit0, stderr EOF, ended diagnostic
reader/capture threads, closed/inactive store and evidence writer, no retained
resources and physical device drain. Incident-induced signal/EOF shutdown must
not be relabeled as a normal successful interactive session.

## Private staging and source identity

The CPU worker plan takes an already-existing private0700 staging parent with
fixed sibling `output` and `checkpoints` children. The worker terminal receipt is
`output/terminal/worker.json`. The parent is an explicitly prepared staging
artifact; read-only planning must not create it. Its local filesystem, owner,
mode and identity must be retained and rechecked before mutation. Children must
be fresh, including no dangling symlink or foreign prior work.

Future worker argv is a reviewed contract, not currently an available live CLI:

```text
PYTHON -B device_worker.py --authorized-device-window
  --staging-parent PRIVATE_PARENT --activity-mode EXACT_PLAN_MODE
  --fault-review REVIEW --output PRIVATE_PARENT/output
```

Worker source, integration closure, plan, private staging identity and fault
review must be bound by the future packet200 seal. Closure changes during the
endpoint stop/drain interval require refusal before launch.

## Storage observations only

The proposed768MiB forecast retains the27GB floor and remains separate from a
proven bound on all native/driver writers. The new pipe drainer covers routed
stderr only. Neither this scaffold nor a successful CPU plan admits live work.

Metadata-only inspection found two surviving p199 checkpoint directories:
147,009,584 binary bytes (147,737,106 bytes including small metadata), occupying
148,070,400 allocated file bytes. Selected older local build traces from
packets181/184/195/196/197/198 contained1,591 ignored JSONL/log/text files totaling
64,102,987 logical and66,449,408 allocated bytes. Ignored status does not mean
disposable: those traces may be unique or referenced by sealed evidence.

The p199 states offer more headroom per reviewed archive. Any archival and later
pruning requires its own assigned, verified preservation operation. No archive,
copy, deletion, external-tree scan or live action occurred in this preparation.
