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
