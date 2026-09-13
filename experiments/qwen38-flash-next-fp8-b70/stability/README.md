# Flash-Next single-session stability candidate

Prepared locally; **execution disabled, not launched or device-qualified**. The user requires stable
operation without repeated server restarts or AI changes to power settings.
This is a new operating configuration, not a replacement speed record.

`serve-single-session.sh` keeps A394's exact model/runtime configuration and
identity preflights: FP8 revision bcd9f01, vLLM 6d872457, exact GDN stage bbae3c5,
TP4/EP4, MTP1, 33,280-token capacity, one sequence, 64-token prefill batches,
1,341,530,112-byte KV allocation and A315 expert placement. It holds the host
and four device locks through the server lifetime. See `provenance.json` and
`a394-to-single-session.patch` for the derivation.

## Operating changes

- One foreground server lifetime; no benchmark driver, timed server stop,
  automatic restart, retry loop, or fresh-server chain.
- No root wrapper; no power/ASPM, swap, cache-drop or sysctl changes. Existing
  power and swap state is recorded, never altered or restored.
- Model and stage can remain on the read-only USB mount. New run evidence and
  caches use internal `/mnt/fast-ai` ext4 paths; RPC/compile data remains local.
- Preserve caches and logs after exit. A deliberate signal requests graceful
  shutdown of the owned group once, with a 60-second bound. If processes remain,
  record failure; no forced kill, driver reset, reboot or automatic restart.
- Saved GPU telemetry is never substituted for current preflight. The original
  bounded discovery/stats and collective checks remain before the sole launch.
  There is no post-stop GPU polling; shutdown health remains unverified.
- Stage boundaries are flushed to persistent logs. HTTP health queries have
  bounded timeouts. Failed external client requests do not stop/restart the server.

## Before first use

Keep the current launch hold during source review. Retained preflight includes
one bounded four-card discovery/stats pass and an XCCL probe; those have NOT run
for this candidate. Do not invoke the old host-controlled launcher to satisfy
its swap/ASPM requirements. The new path has no such host-setting prerequisites.
Do not infer current health from A146/A394 cached receipts.

After the launch blockers below are resolved, use a new numeric `ATTEMPT` and the explicit acknowledgement
printed when running the script without arguments. That no-argument path is
CPU-only and exits before filesystem setup, runtime import or device discovery.
The full execute path starts real GPU work and has not been validated here.

The first use should be one continuous session with bounded, spaced requests
and passive host/error observation. Preserve the process after successful
requests; use the same endpoint for later work. On an incident, stop new requests
and capture evidence. Do not cycle the server to see whether the problem recurs.
No throughput claim is made for leaving swap enabled and host settings untouched.

## Verification boundary

Shell syntax and no-argument refusal are checked; source-level checks cover the
single launch, runtime selectors, locks, prohibited host mutations and absent
restart/forced-kill/cache-deletion paths. These are preparation checks, not GPU
health, model correctness, sustained stability or successful shutdown evidence.

Historical packets are unchanged. Their 231 existing literal-pin drift findings
remain separate; this candidate's original dependency preflight must succeed
before launch, and a mismatch must not be silently repinned.

## Remaining launch blockers

The execute path currently refuses before any preflight or device call, with no
environment override. Resolve the fresh-device-health approach given telemetry
concerns, add startup journal fast-fail detection, and retain lock/descendant
ownership if graceful cleanup times out before enabling it. The retained
discovery calls are inherited A394 startup checks, not its cached postflight;
that distinction does not independently establish their safety today.

The user has authorized stability work. This disablement is a technical safeguard
while implementation is incomplete, not a new request for permission. No server
restart or power-setting adjustment is needed to finish the source work.
