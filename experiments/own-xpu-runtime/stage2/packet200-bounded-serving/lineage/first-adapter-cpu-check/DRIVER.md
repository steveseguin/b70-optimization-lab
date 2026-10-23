# Packet200 operational adapters

These additive files connect the frozen CPU worker and contract. They have only
CPU mock validation; no operational admission, fault capture, model start or
service action is part of their preparation. The root coordinator alone writes
`../../stage2/packet200-bounded-serving/READY-FOR-DEVICE.json`.

That manifest keeps `packet200.execution-admission.v1`, `passed: true`,
`operational_launch_authorized: true`, the exact canonical CPU plan digest,
`storage_admission_mode: monitored-forecast`, and `storage_bound_proven: false`.
Its `source_sha256` closes the frozen worker/profile inputs and every file
returned by `run.py:required_sources()`. It additionally records `controller`
with the chosen fresh `restore_suffix`, absolute controller `evidence` directory,
and the exact `staging_identity` returned by the frozen contract for
`packet200-bounded-serving/evidence/planned-a`. No file here creates that manifest.

`driver.py --check --restore-suffix SUFFIX --output EVIDENCE` is read-only and
refuses missing admission before host inspection. `--run` requires the same
admission before creating a lock or changing a latch. It records both PAUSE bytes,
requires empty queues and idle prior endpoints, stops each endpoint once,
passively verifies physical drain, then rechecks source, staging identity,
98,990,252,032 bytes host memory plus 1 GiB margin, and the full 768 MiB forecast
above the 27 GB root floor. The forecast is an operational reserve, not a quota
or proof that driver caches cannot exceed it. The frozen profile remains
`live_admission_ready: false`.

The gated `run.py --capture-fault-review` captures the pinned exact-two-fault boot
review once at its fixed fresh path. `run.py --authorized-device-window` accepts
only the fixed planned-a children and `--activity-mode launch`; it delegates to
the unchanged worker exactly once. Native execution retains nice0/core0-3,16-19;
CPU planning and capture use nice19/helper cores. Launch-origin activity is
conservative and model loading consumes its initial idle budget.

The controller announces an observed loopback listener without sending requests.
Clients and any serving qualification belong to a separately reviewed coordinator.
Zero completed requests are explicitly `lifecycle_only`; positive counts alone
are not a user-serving qualification or performance benchmark.

Normal closure requires successful inactive worker status, matching durable
pre-completion and final receipts, equal 0..16 request/control counts, one model
load, no pending disposition, diagnostics EOF/join, closed resources and an
independent physical drain. Only then may one guarded restoration use the fresh
suffix. The restore child binds the exact manifest bytes and pinned unchanged
p196 restore/validation sources. Its process-local `window` alias targets the
operational guard; the frozen p200 contract remains uniquely imported. Every
restore/validation operation checks faults, STOP latches, original PAUSE bytes
and empty queues.

Incidents preserve external latch bytes, record STOP, and attempt at most one
main-process SIGTERM. No group kill, retry, reset, resume or second restoration
exists. A retained worker is left for review; restoration is refused. Source
changes, failed evidence or a failed unit cannot be turned into a clean result.
