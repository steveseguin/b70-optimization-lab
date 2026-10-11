# Independent buffer-alias and lifetime review

Reviewed by the independent `alias_review` subagent on 2026-10-11. CPU-only
source inspection; no device binary, discovery, device node, parked process or
host setting was touched. The reviewer did not implement the runtime fusion.
It did implement the prepared window wrapper and its tests, so the window
observations below are an audit, not a claim of independent wrapper authorship.

## Reviewed identities

| Source | SHA256 |
| --- | --- |
| `main.cpp` | `4235b087d95d04fc9579dc83a4433404c12871bdaec77d9d721b9ab9a8cace29` |
| `gemv_batch.hpp` | `4b963550897488c6c4edf41925000814282e7bfde6f35210ad036217b7b5bbf6` |
| `gemv_batch.cpp` | `500bceed93571cc1e2604ec9f26dcc4b3e14552815f2c0249957897f4d6391bc` |
| `adapter.cpp` | `13b9eb6e6ce46d9de7848c1ff2dcbcaa73811cf89dabf5f51066f11143b560f9` |
| `instrument21.hpp` | `b834aac76930b619f807dc7457fbb7489d3428ad3f8b5544cb85778217d1909d` |
| `window.py` | `eff7115a05eb14766dc1dc9dd313ec12346203ed17d76cca8dc8b1473ecf74a8` |
| `WINDOW.md` | `50df28a189765cf51bc0ab874ceabdd33b598e4925fdb7e07ffc4e6b0b9047ba` |
| `DEADLINES.md` | `3002ed2d24ee7688ed565dc17f563f221196d92e67fbe2763a5c8575f0b73e05` |
| `gemv_fixture.cpp` | `5b82e9aca2069a4c5bbb2c6209d00314b8690aa644f043f7e735d851fa3a640b` |
| `nongemv_fixture.cpp` | `df13ab1624931efea830448c6e4b2aadd93b87d181f9ba8498750190357646f5` |
| `adapter_fixture.cpp` | `2e847ae1d3e4f59b234a0fdeade409393940287bf1e3fdcc54025ba90e91fc83` |
| `adapter_fixture.hpp` | `58908c5f54b49c0ae5eedee461b29a5af478ff43c0936ec69a0e81dd4f8fb1fa` |

Changes to these bytes require checking whether the argument below still applies.
This review does not replace fixture/oracle/sanitizer receipts or device gates.

## Finding fixed

The first GEMV-batch implementation required `peer.status == matrix.status`.
Packet18's expert gate and up projections own distinct status allocations, so
that requirement rejected the intended integration. Simply discarding the peer
status would also leave the subsequent peer-status check without its original
producer. The current implementation binds both status allocations and writes
both from the same row-zero group, using the identical guarded route validity.
If a caller deliberately shares status storage, the descriptor uses the same
binding and its writes remain sequenced in the same work-item. The original two
status-check sites remain after the producer launch. This finding is fixed in
the source identity above.

## GEMV batches and folded pointwise work

The descriptor table and every referenced weight, activation, output, route,
status and materialized-input allocation are bound to `Device::compute`.
Consequently owner leases and the dependency checker can see their lifetime;
pointed-to storage is not hidden behind the table pointer. `validate_aliases`
rejects any ordinary writable binding that aliases another read or write in
the batch. Read-only sibling inputs may share storage.

Each output row owns its work-group. The paired gate/up epilogue performs both
row reductions in that group, preserves each BF16 projection store, then forms
the activation output. It never reads another work-group's gate/up output.
Split reductions use group-local storage with a barrier before combination;
sibling matrices do not reuse a concurrently live global partial workspace.

HC SiLU/div4 and four-stream mixing are recomputed from completed input buffers
into local storage. A designated row-zero/slot-zero group materializes each
retained intermediate for later launches. Other siblings recompute their own
input and do not read that concurrent materialization. Different input rows
have disjoint materialized offsets. The main schedule chooses only one such
materialization per shared input within each batch.

For the attention residual epilogue, a group producing output row r updates
exactly stream indexes `r`, `rows+r`, `2*rows+r`, and `3*rows+r`. These sets are
disjoint between groups. Its GEMV input and four injection factors are separate
read-only allocations. Streams are represented as one explicit read/write
binding; the GEMV never reads another stream location that a sibling overwrites.
The next HC normalization remains a separate launch, so its full-row reduction
cannot observe a partly updated stream.

The route-ranking launch has four groups, each owning disjoint candidate IDs.
Ranking ties use the original lower-ID rule; consequently every selected slot
has a unique writer. Probability normalization runs in an extra group of the
following expert batch. Expert arithmetic does not consume probabilities;
MoE combine runs after the entire batch, so there is no same-launch dependency
on the probability group's stores. Route and status indices remain guarded.

## Sequential non-GEMV chains and changed schedule

Every integrated multi-site chain has exactly ONE work-group. Global/local
barriers separate each original group and each producer/consumer phase. This
makes the inter-phase completion proof local to one group; increasing its group
count without a new synchronization design would invalidate the review.
GDN output reductions finish reading each old state row before its state commit.
Convolution retains the old history reads before replacement. Attention scores
and probabilities remain distinct allocations and retain their ordered phases.

The later PLE additions were reviewed explicitly:

- `ple.key` and `ple.value` share the completed host-lookup activation, with
  distinct output allocations; neither overwrites that activation.
- The chain orders key norm, old-stream query norm, gating, gated-input norm,
  convolution, then residual addition. Its final stream write occurs after
  every old-stream reader. In-place convolution history stays in the same
  sequential single-group chain.
- No host lookup, layer snapshot, card handoff or weight-release boundary is
  crossed by this PLE chain.

Initial broadcast plus layer-zero HC norm is also safe in the inspected model
schedule. Broadcast first fills all four streams, then the same work-group's
barrier precedes normalization. There is no intervening PLE update on layer zero
in this fixed schedule. This condition must be revisited if model geometry or
PLE placement changes; the current grouping helper does not prove it generally.
Layer-zero norm weights loaded when binding this initial chain remain alive
through its event; subsequent layer staging drains before releasing allocations.

Layer snapshots still occur at the original `ffn.combine` boundary after its
fused producer event. Streamed descriptor tables and their referenced weights
are cleared only after a drain. Card changes and peer copies retain host fences;
this review found no new cross-card event dependency introduced by fusion.

## Sanitizer interpretation and limits

The fused operation contracts compose ordered internal phases without treating
a write in the SAME phase as satisfying an earlier read. Read/modify/write
inputs, index reads and external WAR/WAW edges remain visible. This supports the
randomized dependency-order execution gate, but that gate operates between
submissions. It cannot by itself detect work-group races inside one submission;
the ownership and barrier arguments above address that separate question.

The coordinator reports passing 13 integration cases and 16 randomized mini
runs at this revision. Those are coordinator-run evidence, not additional runs
performed by this reviewer. This reviewer ran the CPU-only window test suite:
54 tests passed, including host-byte/hash binding, distinct fixture owners,
missing-component rejection, exact oracle admission and watchdog margins.

No unresolved intra-launch WAR/WAW hazard was found in the reviewed source.
This is not device qualification. Compiler lowering, local-memory pressure,
full-model shapes and kernel duration still require the prepared K1/W1 gates.

## Window duration audit

`WINDOW.md` and `DEADLINES.md` correctly separate reported expected duration,
per-submission budgets and watchdogs. Each watchdog is at least four times its
stated estimate including the approximately 17-second first-run JIT proxy, and
none is below 300 seconds. The K1 estimate includes both components and their
extra startup allowance; its watchdog spans both children.

The slowest known reference is explicitly the single-work-item core row at
approximately 1.05 seconds. Historical parallel kernels below 20 ms are not
presented as a bound on the new fused chains. New fused maxima are unknown.
K1's completed-submission budget is below 4 seconds versus the driver's 5-second
job timeout. W0 preserves its below-100-ms canary budget and original defaults.
W1/W2/W3 describe 4 seconds as a planning budget and retain timing evidence;
the wrapper does not claim to enforce an unmeasured per-kernel maximum there.
Reported expected duration never signals or fails a run. The larger watchdog
is the only total-duration stop threshold; no device window ran in this review.

The final wrapper audit additionally requires the sealed `fault_halt_boot_id`
and rejects that exact boot before loader inspection or child creation in all
five window kinds. CPU fake-child tests exercise each refusal. A different boot
is necessary, not authorization by itself. K1's revised conservative work
estimate is 1,800 seconds plus 17 seconds startup allowance; its default watchdog
is 10,800 seconds and minimum 7,300 seconds (above the 7,268-second four-times
floor). Retained `build/fusion-fixtures` inputs are explicitly not scratch.

## Final actual-adapter fixture ownership review

The non-GEMV fixture now shuts down its prototype Device owner before creating
the actual runtime-adapter fixture's owner, on the same selected card. Both
actual shutdown receipts are retained. The prototype's 16-slot Args types and
the runtime's 19-slot Args types occupy separate namespaces and translation
units, preventing accidental ABI/ODR sharing through similarly named inline
functions. The adapter helper reads the actual runtime `adapter.hpp` and calls
`submit_chain` and `submit_rank`; it is not another copy of the prototype.

Reference and candidate allocations are disjoint. In-place recurrent history
and state aliases occur only within their own sequential chain. All inputs and
outputs appear in owner bindings. Upload/control copies finish before the
fixture continues; allocated pinned staging remains owned until shutdown.
Every retained output is compared against host Core bytes and an independently
submitted Core path on the same card. Raw and normalized route probabilities,
route descriptors and sticky error are retained/compared. The original Core
expert gather produces the route-descriptor reference. The fixture now sets
`packed_heads=true`, matching real-model adapter binding; the prior default
false would have missed that real-model GDN mapping and was corrected during
review. None of this has been executed on a device.

The K1 receipt checker keeps model `safe_teardown` unchanged. Its fixture-only
check requires the expected integer `sequential_owners`, exact teardown-array
length and safe/zero-live/zero-in-flight status for EVERY owner. GEMV expects
one owner; non-GEMV expects two. The component window receipt also binds this
count. Two K1 invocations therefore prove six owner teardowns across four fresh
processes. CPU tests reject a missing second owner, an unsafe owner, remaining
live bytes, remaining in-flight work, and a changed sealed component count.

Final fixture-only allocator correction: each of the three fixture allocators
now assigns a unique monotonic allocation label. This preserves distinct owner
arena entries throughout the fixture and its teardown; no runtime source changed.
The source hashes above include that correction. The coordinator reports the
GNU fixture gates passing (553 GEMV checks and non-GEMV 72 fixtures, 6 chains,
8 controls plus 16 actual-adapter checks) with zero live bytes at teardown.
This is reported coordinator evidence; the reviewer performed no new execution.

## Retained-child systemd unit correction

A final prepared-command audit found a lifecycle hazard: default
`ExitType=main` considers the service stopped when the Python watcher exits;
default `KillMode=control-group` and `SendSIGKILL=yes` can then terminate a native
child which the watcher's 60-second cooperative drain deliberately retained.
That contradicts the promised ownership handback.

The installed executable reports systemd 255 (255.4-1ubuntu8.17). Local manual
`/usr/share/man/man5/systemd.service.5.gz` documents `ExitType=cgroup` (introduced
in version 250): the service remains running while at least one cgroup process
remains. `/usr/share/man/man5/systemd.kill.5.gz` documents that `KillMode=process`
limits stop signals to the main process and `SendSIGKILL=no` disables final kill
escalation. These settings intentionally depart from the usual service cleanup
policy because the GPU owner must survive watcher handback.

All six prepared commands now explicitly set `Type=exec`, `ExitType=cgroup`,
`KillMode=process`, `SendSIGKILL=no`, and `Restart=no`. They remain ordinary
transient services, not scopes. A new static command test parsed all six commands
and passed: every required property is present, with no external RuntimeMaxSec.
Only that new static test ran for this edit; the previously reported 54 tests
remain prior evidence. No service was created, started, stopped, or modified;
no systemd manager setting, runtime source or binary changed.

The final timing clarification was reviewed: GEMV-category device time includes
folded pointwise work, so category subtotals have changed scope. Total device
and wall time retain the comparable definitions. This wording makes no measured
speed claim and changes no prepared command or safety setting. The WINDOW hash
above includes the clarification; no further tests or builds were run.

## Final GEMV-batch source reconciliation

The final seal audit found the previous GEMV-batch review hash stale. The
current source `500bceed93571cc1e2604ec9f26dcc4b3e14552815f2c0249957897f4d6391bc`
was independently reread in full for this correction. Its CPU-only operation
now computes each pure BF16 input prologue once per distinct input into a
submission-local vector before the OpenMP output-row loop. That vector is
read-only during the loop and lives until all loop workers finish. It is not
persistent state or a cross-submission cache.

The batch-wide alias validator still forbids any writable allocation from
aliasing a sibling input. Thus hoisting the transform cannot observe a source
that a sibling changes. Materialized prologue output is also forbidden from
aliasing a batch input. The existing admission guard permits materialization
only for shared input or count=1; under either condition the first
`input_rows * columns` prepared entries are exactly the distinct rows copied
to that output. Device work-groups continue to compute their own local prologue;
its row-zero/slot-zero materialization has the previously reviewed unique writer.
No new WAR/WAW or temporary-lifetime hazard was found.

The final peer-matrix checks also reject incompatible quantization block
alignment, row span, and route/status presence before descriptor construction.
They strengthen admission without introducing an alias or moving a write.
Distinct expert status outputs and the existing explicit HC residual
read/write binding remain intact.

All 12 source hashes listed in this review were checked against current bytes.
The other 11 already matched; only the GEMV-batch hash required correction.
This reconciliation changes only this review document. No tests, builds, runtime
changes, or device execution were performed.
