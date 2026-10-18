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
24/24 production constructor census copies 48,627,432 bytes over 1,021 extents
for control, and 19,025,640 bytes over 984 extents for the candidate: 29,601,792
bytes avoided on every cycle. The third bank costs exactly that amount, and
backup capacity shrinks by the same amount. Total device allocation is
unchanged: 28,144,182,388 bytes on rank0 and 31,425,985,242 on rank1. These are
CPU allocation-ledger results, not a driver-residency measurement. Evidence:
`evidence/census131.json` in the packet. Both retain two submissions.

Two fresh miniature runs per choice match frozen packet124c target tokens,
96 retained layer outputs and draft state/proposals. Ten Python tests pass,
covering the drain deadline race, graceful teardown on error, full smoke/grid
suite control flow and rejection of a one-load speed win. The real eleven-
window queue loop passes for both selections, with failure at each position,
changed receipt fields and repeat refusal. Operational admissions and child
results are synthetic in these CPU queue tests, not a device qualification.

The forced-state and production bank-binding checks are prepared. Compilation
waits for packet94's lock and the coordinator's whole-host reservation. One
owned sleeping census process was interrupted to consolidate the final serial
build/check sequence; no device process was signalled. The candidate is
**not ready for device admission** at this milestone.

The final build and production census now pass, including the captured pointer
and source/destination checks across every ordered bank pair and QSA context
transition. [Complete census](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/CENSUS.md)
and [individual extents](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/capture-extents.csv)
are generated from the new receipt. The full inherited eleven-window Python
gate, K2 replay, original K2/oracle failures and real queue validators also pass.
Its disposable queue uses packet131's actual build/storage census: counting
the frozen parent's live chain as retained scratch exceeded that parent's
budget. The original refusal remains in `evidence/inherited-queue-parent-storage-refusal.log`;
the parent and actual device storage policy were not edited. Packet131's own
real pre-LATE oracle subprocess passes without root redirection.

The full-state test's observed peak was about 865 MiB. Four independently
capped 1.5-GiB CPU workers run at once; an interrupted sequential attempt is
retained as incomplete. The Intel CPU fixture needed its own linker and an
explicit non-PIE link. A separate production recurrence test passes raw
bank-versus-reference equality under both compilers, but an additional
cross-compiler comparison found different reference transcripts. Localization
found only the deliberately supplied NaN case: GNU and Intel produce different
NaN payloads in their unchanged references. All 72 production bank cases pass
raw candidate/reference equality within each compiler, twice. A diagnostic
normalization of copied output confirms that all other cross-compiler bytes
agree; it is not used to accept candidate/reference differences. Runtime bytes
and arithmetic remain unchanged.

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
