# Passive sampler accounting106 runtime integration

105 remains healthy and idle. Its finite71-request plan is consumed. Keep the
reduced-write client policy and close its comparison lever;106 investigates
sampler activity without changing model arithmetic or quality requirements.

The author runtime now admits57 requests and50 captures:20 native,14 candidate,
14 reduced-write timing and9 setup. Final fast verification reconstructs the
native and candidate proofs. There is no control timing block. The unchanged
99b constructor is stopped;105 is the reviewed predecessor. Build and runtime
allowances are384MiB and4GiB separately above the50GiB reserve.

The frozen passive collector is copied unchanged into the sealed-component
inventory, alongside a client-only adapter. Neither enters server runtime imports.
The adapter starts one child only after start-timing and requires a bound header
plus a complete sample within10seconds, before any timed request. Normal finish
waits only until the original child start plus130seconds. No child signals or
retries exist. On a model/fault failure, the original lifecycle is preserved;
partial accounting is marked unfinalized and is not awaited. Accounting-only
refusal retains a proven-idle healthy application. A valid model proof cannot
turn invalid accounting into a utilization claim.

All253 synthetic CPU tests passed in37.072seconds. Focused agent tests also
passed, and independent campaign/integration/builder review found no blocker.
The initial root integration test caught obsolete105 setup prefixes; all were
corrected before the complete suite. Source-bound validation and the actual
460007-entry filename reservation scan are in `data/resume-20261007/` as
`sampler106-cpu-validation.json` and `sampler106-reservation.json`.
No106 model request has been made. Independent passive-runner review found no
blocker. Source tests alone do not admit GPU execution.

Raw counter integrity is only the first gate. Analyze complete intervals lying
inside the delivery window for the ten scored outputs, separately per DRM
client, PCI and engine with its own total/capacity. Asynchronous lookahead and
tails overlap this window; it is not exclusive GPU service for those clips. Engine activity is not EU occupancy; do not add compute and
copy fractions or treat sampler A/B stage times as separate GPU utilization.
The diagnostic is not a public speed record or endurance measurement.

## Sealed source and controlled reload

Author commit `5e5e95248` is pushed to main. Input inventory
`cf28822dfe066892a8e0c638a717ca83b0d20f28ddf8154fa826a9034cd1cee3`
built the new packet with its own fresh384MiB admission above50GiB. Sealed
manifest `59765f873aa553104691053c43f0964725353ddb25df471f806b039e1aa4c6e2`
passed full source closure. Qualified99b constructor PID3129897 was absent;
105 remained untouched during construction.

105 then received one SIGINT only after two empty-queue/tail/preview observations
five seconds apart, exact PID/start/boot/identity checks and a clean kernel
journal. Its stop intent and completion receipts are in `client105-closeout/`.
All four render nodes were unowned afterward. The single four-card postflight
passed at20:13:55UTC with zero prior or new kernel fault lines. No host restart,
power/memory change, retry or forced kill occurred. Full duplicate-retirement
proof reconstruction follows before any raw archive removal or106 launch.

## Timestamp analysis admission

Independent source/receipt review identifies scored timed-fast rows04–13,
emitted indices0–9, physical clip IDs99906200–99906209. The standard delivery
window runs from row04 success_ms through row13 success_ms (nine intervals).
A separate full request window can use row00 start_ms through row13 success_ms.
Neither identifies exclusive per-clip service: sampler work begins during the
fill requests and later lookahead overlaps the scored delivery window.

Each collector sample exports monotonic_start_ns, unix_start_ns and
monotonic_end_ns. The offset bracket is [Ustart−Mend,Ustart−Mstart]. Check
cross-sample consistency, report widths and explicitly assume local clock
stability; the records cannot rule out every intervening wall-clock step.
Allow the server's sub-millisecond timestamp quantization, reject uncertain
edges, and retain only full snapshot pairs inside the conservative inner window.
Require complete samples with stable client sets, capacities and default flags,
positive same-engine total deltas, no busy regression or intervening coverage
gap. Counter reads are not simultaneous; scan widths remain uncertainty bounds.
If no admissible pair remains, report incomplete attribution without inferring
zero work or launching a repeat automatically.

## Live admission

Launch check passed after fresh4GiB/50GiB storage admission. The single server
launch began20:19:53UTC. Actual PID3348053, start ticks27822505,
boot`10192010-9700-4915-ac6c-980d6b74afa0` owns manifest
`59765f873aa553104691053c43f0964725353ddb25df471f806b039e1aa4c6e2`.
Server identity SHA`e292b16b347bf2673e3c7657aa17f85ebac70d58c00560c1c6d18ce1b53e9dda`.

The installed library hash and actual process mapping match the reviewed105
library. All four106 ordinal property hashes/UUIDs match the reviewed PCI layout;
current sysfs vendor/device/revision and physical paths matched again. The
run-local mapping observation, mapping evidence and observer contract bind106's
own identity. Sealed Client and observer check() passed without launching the
observer. Client contract SHA`2f6046c602fb19a74321211932ebad4ac51e62f231969ff8498b64860438b53f`;
observer contract SHA`7d4f3bcfb78afa3d6c266d6a57d9c6fb5c2249be910892acd02a3b919c8e231f`.

FD observation and the57-request campaign launched once at2026-10-07T20:23:28.201696+00:00.
Native qualification proceeds first. No106 quality or accounting verdict exists
yet. Preserve one application, no request retries and no unrelated work during
the timed block. Registered command arrays and admission receipts are tracked in
`data/resume-20261007/sampler106-*`.

## Conditional next lever: boundary activation transport

A bounded read-only source audit, independently checked by root, found one
specific copy candidate in sealed106 `source/scripts/ltx_graph_capture.py`:
`staged_move` lines822–840 allocates a fresh destination tensor and copies the
pinned host payload into it; `DeviceGroup.fill` lines455–473 then copies that
activation into the captured graph's static input. Frozen replay uses this fill
immediately before unchanged graph replay at1253–1255. Source SHA-256:
`3a9a99954cb4877829c4407eb74306f6b409864002dfcccf3562fd0c98380400`.
No implementation or numerical change has been made.

A possible successor could carry a pending pinned payload through the routing
step and write H2D directly into the exact existing img slot at its original fill
position. This would remove the transient destination allocation and redundant
D2D activation copy. It must retain source-stream D2H, the existing host wait,
argument-transfer ordering, the destination worker stream and unchanged graph
replay. Writing static buffers early in staged_move is not an equivalent recipe.

Prerequisites: frozen existing entry and exact worker-thread/device/signature/
component ownership; matching shape, dtype, stride and expanded-core layout;
no source/target alias or cross-worker static/pinned sharing; pinned lifetime
through destination consumption; no escaping output-buffer or cross-forward
argument-cache reuse. Every fresh arrival must copy, even if a Python object is
reused: existing fill skips when slot.sources[i] is value, so a generic mutable
buffer cache could silently replay stale activations. Unknown signatures must
refuse, never recapture after freeze. No added global/device synchronization.

Pursue only if admitted copy-engine deltas make copying material while sampler
compute engines have available service capacity. Counters still cannot identify
this particular copy or prove critical-path benefit. Negligible copy activity or
heavy sustained compute would lower its priority. Low/ambiguous activity needs
one sparse attributed boundary trace first. Do not turn this proposal into a
speculative implementation or claim an unmeasured speedup.

## Completed106 and next decision

The57-request campaign completed20:37:00UTC. All20 native executions formten
exact repeat pairs; allten candidate andten timed clips are exact across video
latent, audio latent, images and waveform. The unmodified sealed final verifier
rebuilt the full proof at20:39:25UTC. The application remains healthy and idle,
with its finite plan consumed. No stop/restart or extra request followed success.
Closeout preserves1237 file bindings and25 small raw receipts/counter artifacts.

Timing intervals were1.807,1.991,2.109,2.549,1.526,2.194,1.540,2.519,1.700s,
mean1.99277778s and12.5453 generated FPS. These are instrumented repeated-workload
observations, not a speed record or matched improvement over105.

The observer ended normally at its output cap:128164bytes,27 snapshots,25 complete,
2 incomplete, no missed cadence slots. Global diagnostic_valid staysfalse.
The unclassified descriptor disappearance at20:35:37.603–37.656UTC was during
fills; the second at20:35:43.603–43.653UTC was INSIDE the scored completion window
20:35:43.401–20:36:01.336. Matching surviving render maps do not clear either
unknown disappearance. No fault occurred, and the observer child exited normally.

Independent reviews agree that eight later complete snapshots (zero-based5–12,
JSONLrows6–13) provide seven stable interior pairs. They span approximately
20:35:45.610–20:35:59.670UTC including scan widths, with all source, client,
capacity and counter checks intact. Any analysis of this subset is posthoc and
exploratory; it cannot turn the whole diagnostic valid. Sampler-card copy counters
advance materially, but cannot identify a costly transfer or critical path.

Decision: preserve this result, do not rerun accounting merely to obtain green,
and design ONE sparse attributed transport/fill trace before implementing the
conditional buffer change. Prefer placing sparse traces in the existing candidate
phase and retaining a later uninstrumented timing block if attribution and exact
quality gates permit; this is still a proposal, not a registered107 runtime.
Sampler transfer timing must distinguish the existing host wait from actual
copy intervals and retain lifetime/order guarantees. Small hypothetical savings
are not a reason to build a long optimization campaign.

## Durable retrospective counter analysis

`recovery/20261007-accounting106-analysis/analyze.py` binds13 fixed evidence
inputs, including the independently rebuilt quality proof and collector source.
Root reviewed it and reran21 synthetic controls successfully in0.018seconds.
The actual exclusive output is `data/resume-20261007/sampler106-posthoc-counter-subset.json`.
It derives seven eligible adjacent pairs rather than preselecting their indexes;
records all rejected-pair reasons,65.758ms observed clock-offset envelope, scan
uncertainty and edge exclusions; and retains global diagnostic_valid=false.
Only per-client/per-engine raw cycle deltas are emitted. No utilization estimate,
busy seconds, cross-client aggregate, speed claim or per-clip GPU attribution.

## Next storage admission hypothesis

The retained106 outputs remain protected. A bounded read-only audit hashed only
the ten106 native-p1 archives and ten already-protected105 native-p1 anchors
(20 archives,1,492,420,320bytes). Every same-fixture whole-file hash and size matched,
with distinct inodes and nlink1. Stored proof hashes for all40 scored106 archives
map to those same ten105 anchors, so a future necessary controlled reload could
retire all40 duplicates with direct restoration maps, preserving106 metadata and
avoiding another permanent set of identical raw anchors. No106 deletion occurred.

Potential allocated reclaim is2,985,103,360bytes (2.7801GiB). At20:44:27UTC,
56,096,702,464bytes free plus that conditional reclaim would admit4GiB runtime
and384MiB source above50GiB with697,094,144bytes spare;5GiB runtime would still
fall short. All40 candidate files still need fresh full proof, hashes/stats,
exact stopped-owner evidence and durable per-file receipts before retirement.
Runtime/source admission must then be checked afresh. This is a hypothesis only.
Stopped104/105 and live106 inductor caches are empty. Older compiler caches carry
negative-result source evidence and are protected. Pip cache is only36KiB and uv
cache is absent, so package-cache deletion provides no meaningful headroom.

## 107 standalone preparation

The standalone `recovery/20261007-sparse-transport107-plan/` passes32 CPU controls,
including numerical equivalence to106 and namespace/index collision checks.
Plan SHA`b4590ffc14a7a4a2c0c3e59d6785cfbfc85df1d3080687f05bfd12ffd390002d`,
qualification`1979c71925283fd715e9983baba81f7d0c2cd7dc4534a1514c016ededa4e4923`,
schedule`b8d7176691e7c3a7a8470b4ec8b046c27db20f4f623b3fc1034930edbf58506b`.
Root caught an initial descriptor error selecting only one worker globally;
it now selects at most one eligible actual job on EACH worker0/1, maximumtwo
jobs, with actual index/thread ownership and incomplete status if either is
missing. No substitute requests. Descriptor SHA
`6247dc126c073a8d7691cf28edd5cc399a56e21b6e6042906703c2f229b48efa`.
Eligible physicalcandidate IDs99907104–99907109 emit via requests08–13.
All14 timed-fast requests explicitly disable tracing. The injection contract,
event budget, runtime and actual filename reservation remain unimplemented.

The proposed fixed40-file retirement helper in `recovery/20261007-post106-retirement/`
passes17 root synthetic tests in5.667seconds and independent source review.
It requires stopped106 plus full fresh sealed proof, exact keeper provenance and
direct ordinary restoration copies. No actual106 plan/apply/restore occurred.
Helper SHA`f84c78426081e503656e0a0faba124e5106829fec1aceeb68bd886b5823ed215`.
It is not a filesystem-wide atomic transaction: coordinator-exclusive ownership
must continue throughout every future operation.

Historical contiguous capture and native multiblock compiler results were reviewed
before proceeding. `notes/contiguous-capture-retired.md` closed whole-shard
chaining based on the older small-shape service measurements; compiler screen01
found no speed win and an all48 regression. Those are separate historical
workloads, but provide no reason for a blind new chaining sweep. Keep that lever
closed unless the sparse current-shape trace provides materially new evidence.
