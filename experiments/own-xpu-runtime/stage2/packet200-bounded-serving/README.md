# Bounded interactive owner — CPU preparation

## Question and identity

Packet200 connects the unchanged p198 binary to the frozen bounded profile,
chat/session composition, checkpoint store and stderr drainer. It proposes one
owner, at most sixteen sequential loopback requests, context4096, full BF16
state and the21,552,729,600-byte baseline cache. It does not use the later
max23/diet benchmark identity. No device window is queued or launched.

## CPU plan and execution seam

`cpu_plan(staging_parent, activity_mode='launch')` verifies the historical and
new component profile and describes fresh `output`/`checkpoints` children of an
existing trusted private local parent. It never creates those children. The
only CLI is `--plan --staging-parent PATH`, optionally selecting the registered
`mapped-cold-start` activity mode. There is no live CLI or service installer.

`execute(plan, fault_review=..., manifest=...)` is a future coordinator function.
It refuses without packet200's separately authored execution manifest, exact
plan digest/source closure and explicit operational authorization. The manifest
schema is `packet200.execution-admission.v1`. Root owns its construction and
review. Successful execution returns0; safely completed failures raise a
bounded `WorkerFailure` retaining the original exception as `.original`.
Uncertain ownership remains in an explicitly retained worker instead of
returning or retrying. The CPU plan is not operational authorization.

The native launch uses the exact profile argv, with only the three admitted
p199 value changes: owner output, checkpoint root and request count16. Native
main stays nice0 on cores0-3,16-19 with unlimited AS. The diagnostics-start
trampoline and passive monitor set only their own threads to nice19/helper
cores8-15,24-31. Diagnostic capture/reader threads inherit that helper placement.

## Ownership and startup

Pinned p199/p198 safety factories supply the whole-host reservation, drain
permit, journal/fault review, memory and passive device checks. Their historical
execution wrappers are not reused. `OwnedRun` explicitly retains the child,
front, store, diagnostic readers/writers, helper threads and admission objects.

Exactly one `Popen` uses stdin/stdout/stderr pipes. Diagnostic startup immediately
follows, before readiness waits or device-registration scans. The original
stderr reader closes only after successful duplicate-reader startup. Any
ambiguous spawn or reader startup keeps the endpoints/resources; one incident
SIGTERM is an attempt, never proof that the owner exited. There is no forced
kill, restart, checkpoint cleanup or resource-limit change.

The default initial activity is the conservative timestamp before Popen. The
optional source-proven mode prepares fresh-output provenance before Popen and
checks actual mapping/cold-start provenance after READY. A contradiction fails;
it never silently falls back to launch mode. Absolute origin stays unchanged.
If soft admission already expired before attachment, the owner closes normally
without opening a listener or constructing the checkpoint store. Zero-request
clean sessions are valid. A received READY never resets activity.

## Storage and closeout

Admission is explicitly `storage_admission_mode='monitored-forecast'`,
`storage_bound_proven=false`. The768MiB forecast and27GB root floor are checked
before and immediately preceding launch; passive and operation guards continue
checking available space. Frozen profile readiness remains false.512MiB parking
and256MiB SAVE reservations are unchanged. Unbounded driver/native filesystem
writers and inter-poll growth remain uncertainty, not a proven quota.

Routed evidence uses separate bounded instances:8MiB stderr,7MiB control/kernel,
1MiB terminal. A blocked stderr writer cannot hold the terminal writer's lock.
Fault journal bytes are appended before the fault refusal, with a bounded fault
excerpt/cursor retained even if the evidence append itself fails.

Normal close requires matching0..16 request/control counts, one load, no pending
or discarded descriptor, valid stopped reason, owner exit0, diagnostics EOF and
finished threads, native shutdown proof and passive physical drain. Session
lifecycle closes the front exactly once. Retained owner/pipe/thread/startup state
keeps resources and coordination markers; no ordinary context-manager unwind
runs on a timeout.

Closeout has two durable phases. `output/terminal/pre-completion.json` is written
before permit/lease completion while the control writer remains open for final
guards. Only then may coordination complete, control evidence close, and
`output/terminal/worker.json` acknowledge success. The final unit exit0 is also
required: `writers_closed` describes stderr/control closure, while exit proves
the terminal descriptor finished. A pre-completion evidence failure prevents
coordination completion. A final acknowledgment failure after physical and
coordination completion is a failed evidence result, explicitly distinguished
from retained ownership; it cannot yield a successful controller verdict.

## Verification and remaining work

Twenty-six CPU checks pass. Tests intercept the sole Popen, exercise real historical CPU plan/import
closure, use synthetic owner/front/session objects, and include one real
`os.pipe`/PipeDiagnostics/BoundedEvidence join. No native executable, model,
service or device is run. Failed and retained cases test uncertainty, original
error retention, single signalling, partial admission, fault evidence,
provenance contradiction and both closeout failure phases.

The initial eleven-test passing checkpoint is retained under
`lineage/before-root-closeout-review`; root review found closeout-order and
receipt gaps before any native use. A later preflight-error test exposed a
unittest teardown fixture mistake; its exact candidate is preserved under
`lineage/preflight-test-teardown-failure`. The corrected suite passes. CPU
evidence is retained in `evidence/worker-cpu-tests.json` and its linked log. Actual arbitrary chat has no prerecorded output oracle; this is neither
a serving qualification nor a benchmark claim. A future root-owned manifest,
controller admission and explicit operational window remain separate work.
