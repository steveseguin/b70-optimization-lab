# Packet201 streaming operational adapters — CPU preparation

These additive files connect the frozen CPU worker and contract. They have only
CPU mock validation; no operational admission, fault capture, model start or
service action is part of their preparation. The root coordinator alone writes
`../../stage2/packet201-streaming-serving/READY-FOR-DEVICE.json`.

That manifest keeps `packet201.execution-admission.v1`, `passed: true`,
`operational_launch_authorized: true`, the exact canonical CPU plan digest,
`storage_admission_mode: monitored-forecast`, and `storage_bound_proven: false`.
Its `source_sha256` closes the frozen worker/profile inputs and every file
returned by `run.py:required_sources()`. It additionally records `controller`
with fixed fresh `restore_suffix: 20261023-restore30`, absolute controller `evidence` directory,
`additional_write_bytes: 1048576` for the separate bounded client evidence,
`client_unit: packet201-client-a`, the fixed absolute `client_receipt` path
`packet201-streaming-serving/evidence/client-a/client-result.json`,
`qualification_requests: 16`, and the exact `staging_identity` returned by the frozen contract for
`packet201-streaming-serving/evidence/planned-a`. No file here creates that manifest.

`driver.py --check --restore-suffix SUFFIX --output EVIDENCE` is read-only and
refuses missing admission before host inspection. `--run` requires the same
admission before creating a lock or changing a latch. It records both PAUSE bytes,
requires empty queues and idle prior endpoints, stops each endpoint once,
passively verifies physical drain, then rechecks source, staging identity,
98,990,252,032 bytes host memory plus 1 GiB margin, and the full 768 MiB forecast plus the additional 1 MiB client evidence reserve
above the 27 GB root floor. The forecast is an operational reserve, not a quota
or proof that driver caches cannot exceed it. The frozen profile remains
`live_admission_ready: false`.

The read-only `run.py --verify-admission` checks the complete worker authorization
and root-admitted staging inode before host inspection. Public `--plan` stays
manifest-free and performs no operational admission. The gated
`run.py --capture-fault-review` captures the pinned exact-two-fault boot
review once at its fixed fresh path. `run.py --authorized-device-window` accepts
only the fixed planned-a children and `--activity-mode launch`; it delegates to
the unchanged worker exactly once. Native execution retains nice0/core0-3,16-19;
CPU planning and capture use nice19/helper cores. Launch-origin activity is
conservative and model loading consumes its initial idle budget.

After observing the fresh loopback listener, the controller starts exactly one
fixed CPU client unit, with nice19/helper cores and the same safe stop properties.
The client sends two GETs, one expected pre-RUN 400 refusal and sixteen fixed
valid turns. It performs no retry. Both worker and client units must exit with
success; restoration waits for the client's final response/oracle validation.
The joined proof requires sixteen worker requests and controls, sixteen client
turns, five original recorded-output matches, one resumed/fresh pair, all16 exact
p200 prompt/native/text/usage matches and1484 output tokens within the1728 cap,
seven complete SSE terminal sequences, nine ordinary replies, observed-delivery
timing only, and no speed/submission claim. Client admission metadata binds the exact
manifest, vectors, listener event bytes and address. This is a bounded serving
pilot qualification, not a general hosting or performance benchmark. The frozen
contract still labels zero turns lifecycle-only; this first pilot refuses zero
turns as qualification.

Normal closure requires successful inactive worker and client status, matching durable
pre-completion and final receipts, equal 0..16 request/control counts, one model
load, no pending disposition, diagnostics EOF/join, closed resources and an
independent physical drain. Only then may one guarded restoration use the fresh
suffix. The restore child binds the exact manifest bytes and pinned unchanged
p196 restore/validation sources. Its process-local `window` alias targets the
operational guard; the frozen p201 contract remains uniquely imported. Direct restore invocation independently rechecks worker/client terminal, unit and drain evidence and
creates an exclusive attempt marker. Each of the three exact validation argument
tuples also has a one-use marker; arbitrary validation targets and replay are
refused. Every restore/validation operation checks faults, STOP latches, original PAUSE bytes
and empty queues.

Incidents preserve external latch bytes, record STOP, and attempt at most one
main-process SIGTERM. No group kill, retry, reset, resume or second restoration
exists. A retained worker is left for review; restoration is refused. Source
changes, failed evidence or a failed unit cannot be turned into a clean result.

The additive worker plan includes a separate streaming source map/digest, checked
by this contract and the worker's full authorization. Its49-file streaming source
closure supplements the unchanged canonical profile. Adapter source admission
also requires the32 p200 HTTP/native baseline files, p200 vectors and new client
documentation/CPU receipt. `helper-pins.json` binds the actual frozen p200 window,
driver, restore adapter and tests in addition to the inherited safety helpers.
The Window state machine has an AST equality check against p200 after packet-name
substitution; ownership/incident/stop/restore ordering is unchanged.

No real staging directory, operational manifest or fresh production plan was
created for this CPU preparation. Fixtures intercept all services, queue, launch,
privileged drain and restoration operations. Root must independently establish
headroom before a real plan and review the complete new closure before a window.
