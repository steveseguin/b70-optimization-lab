# Packet131: preserve recurrent rollback state by rotating buffers

CPU preparation in a new symlink-preserving copy of packet124c. The frozen
parent, existing packet trees, screen wrappers and live queues are unchanged.
`git pull --rebase` refused the unrelated dirty index/worktree; `git fetch`
confirmed HEAD and origin/main at `c7b59d9429e3c2b1c6c351f523203e36ec1327fa`.
Work is on main, on steve-b70s. No GPU, service or host setting is touched.

The measured question is capture on **every** speculative cycle, about
0.523 ms in packet128b. This differs from packet121's restore-on-miss question.
Packet124c already submits one descriptor upload and one flat copy kernel;
the hundreds of copy extents are not hundreds of device submissions.

The new candidate admits the existing, dormant `banks-batch` path against
bundle7. This mechanism originated locally in packet62. It is requalified here
because packet128b now measures the per-cycle capture cost on the changed
bundle. The old packet62 rank1 bottleneck diagnosis is not reused as evidence
about this configuration. No new arithmetic, quantization, KV precision,
target verifier, draft prefix or controller scheduling is introduced.

Committed A and previous spare B are observable. Speculation reads A and
writes private C. A hit commits C/A; a miss restores A/B by rotating bindings.
All six ordered physical pairs have prepared commands. Only full-overwrite
GDN and convolution destinations qualify. Historical tails in scratch,
nonbank outputs and QSA/KV rows continue through the existing guarded batched
snapshot. This removes recurrent capture copying; it does not claim to remove
the entire snapshot or its entire measured time.

The first host and device-target build passes, without device execution. The
production 24/24 census and forced state tests are being prepared. Compilation
waits for packet94's lock and the coordinator's whole-host reservation. The
candidate is **not ready for device admission** at this milestone.

Planned CPU gates: production allocation/descriptor census, actual snapshot
and miniature target state under GNU and Intel, every logical committed/spare
byte after hit/miss/cancel/fallback sequences, boundary retirement, reset bug
regression, full-window startup arguments, native exec limits, drain and error
teardown, seals, and real queue planning/execution on temporary copies.
GNU/Intel compile the changed Engine/snapshot test code; unchanged arithmetic
dependencies remain pinned inherited objects. This is not full-model device
equality.

The candidate changes bank allocations and prepared-pair ownership, so it is
not a runtime switch in the existing one-load wrapper. Preregister a lane-B
12 × 64 exact smoke, then a v4 fresh-load control/candidate/control/candidate/
control grid. Smoke: 4–6 minutes, 1,800-second watchdog. Each grid load: 6–8
minutes, 3,600-second watchdog. The grid requires the exact sealed smoke first.
Both candidates must match every oracle token and acceptance count and beat
both adjoining controls; a single lucky load cannot establish a speed verdict.
All device gates remain pending until the coordinator admits the proposals.

Work tree: [packet131-snapshot-banks](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/README.md).
