# Independent promoted rolling launcher review

The frozen promoted planner/transport/lifecycle integration has no identified
launch blocker. `rolling-provider-independent-review.json` binds the reviewed
controller receipt and its complete source closure. This was CPU-only work;
no GPU owner, model execution, full build or service action was performed.

All 19 promoted tests passed independently. The promoted transport also passed
21 additional three-byte socket send/receive cases across 2/4/6 owners, including
cancellation before any bytes of an already-reserved ROW, ACCEPT or provider
command were sent. A mocked lifecycle failure propagated its exception and
retained the failed result, error/return codes and raw lifecycle/plan hashes.

An actual CPU-only plan regenerated successfully against native binary
`8e03d3cd67fc99c7db4408cb9c2e6abb158806f142df16292ece37083e706231`, the
retained adapter and model authority, and the independently retained trusted
draft manifest SHA. All runtime pins matched. The generated launch contained
no oracle/reference-token inputs or reference-file pins. The native draft
loader separately checks each consumed tensor's authenticated file identity
and raw content hash; the controller does not replace that validation.

The planner reuses full native source/binary validation, target placement/auth,
explicit draft manifest trust, EOS/arithmetic configuration and owned fresh
output paths. Its runtime source closure includes the new package initializer,
arbiter, coordinator, transport and wrapper plus the existing strict codecs and
observer/lifecycle dependencies. It refuses disabled diagnostic controls,
scripted/reference inputs and more than 32 generated tokens for this first gate.

The wrapper retains the existing named-unit ownership check, Restart=no,
KillMode=process, SendSIGKILL=no, niceness, bounded lifetime and cooperative
stop pipes. Every spawned child remains tracked before identity/evidence capture
can fail. The passive observer closes admission on faults, ambiguous holders or
resource-floor failure. No restart, forced kill, driver reset, power or memory
setting change is introduced.

The wrapper does not expose the prototype's optional cancellation callback.
Signals and guard failures enter the existing cooperative exception/shutdown
path before normal DUMP/FINISH, avoiding a false completed-request attestation
for an intentionally incomplete provider prefix. The result sidecar preserves
the underlying success/failure instead of converting controller completion into
numerical proof. V6 provenance replay, exact target/canonical draft comparison
and native survival checks remain required after the parent-owned model gate.
Diagnostic timings remain ineligible for throughput claims.
