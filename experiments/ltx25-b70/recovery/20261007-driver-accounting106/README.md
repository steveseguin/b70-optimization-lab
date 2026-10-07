# Bounded raw DRM accounting prototype

CPU-tested proposal only. No live observation has been run with this collector.
The coordinator owns the admission contract and operational scheduling. Do not
attach it to the sealed 105 comparison.

`collector.py` reads existing proc metadata. It never opens a GPU node, imports
Torch, calls an endpoint, submits work, signals a process, or changes settings.
Fixed limits remain: two seconds between actual sample starts, 120 seconds,
64 schedule slots, 128 KiB output, 4,096 descriptors, 512 tasks, 32 render descriptors per scan, and 16 KiB per proc-file read. Source files are capped at
2 MiB each; mapping evidence admits at most eight source files. Each snapshot
has two bounded descriptor/task scans, with render-client identity and child
coverage rechecks. The output cap may end collection before the time cap.
Filesystem/proc latency can overrun a deadline; these limits bound calls and
bytes, not kernel scheduling latency.

## Contract and mapping evidence

Supply a reviewed contract using `--contract`, its whole-file
`--contract-sha256`, and a fresh absolute `--output` path. No live contract is
included. Required contract fields are:

- `schema`: `ltx.raw-drm-accounting.v1`;
- `pid`, `start_ticks` (decimal string), `boot_id`, `collector_sha256`;
- `runtime_manifest_sha256`, semantic `plan_sha256`, and `qualification_id`;
- `render_nodes`: exact render-device path to PCI BDF mapping;
- `ordered_xpu_mapping`: entries described below;
- `fault_paths`: at most eight absolute marker paths, including the bound run's
  `FAULT.json`, `resolution-halt.json`, and its parent root's `FAULT.json`;
- `bindings`: exactly `plan`, `server_identity`, `runtime_manifest`, and
  `mapping_evidence`, each containing absolute `path` and whole-file `sha256`.

`plan` means the server's candidate-plan envelope. Its path must be
`identity.source_packet_path/resolution/candidate-plan.json`; the runtime
manifest must be beside that packet's sources. The envelope's semantic digest,
qualification identity, manifest's `resolution101.plan_sha256`, and manifest's
whole-file plan digest must agree. The manifest digest must equal the actual
server identity's `source_packet_manifest_sha256`. PID/start ticks/boot must
also agree. Source, identity, plan, mapping, and fault checks run before and
after every snapshot, including checking the collector's own source digest.
Duplicate JSON keys and nonfinite JSON values are rejected.

The bound mapping document must have:

- `schema`: `ltx.reviewed-render-xpu-map.v1`;
- `review_method`: `reviewed-existing-evidence`;
- `server_identity_sha256`, `runtime_manifest_sha256`, `plan_sha256`;
- exactly the contract's `render_nodes` and `ordered_xpu_mapping` values;
- `evidence_sources`: one to eight distinct `{path, sha256}` records. These
  source files are hash checked with every binding check.

Each ordered mapping row has exactly `ordinal`, `render_node`, `pci`, and
`properties_sha256`. All devices in the bound identity must appear in ordinal
order, with distinct admitted render nodes. `properties_sha256` hashes the
UTF-8 bytes of that device's exact `identity.devices[ordinal].properties`
string. This ties the reviewed mapping to the actual XPU enumeration without
implementing a speculative UUID decoder inside the collector. It does not prove
the mapping merely because someone supplied a matching hash: the coordinator
must review the linked physical/source evidence before admitting the contract.
This is an agent review step, not a new user-approval requirement.

The coordinator's existing
[driver mapping review](../../data/resume-20261007/driver106-mapping-source-review.json)
records the matching compute-runtime tag and UUID layout checks against all
four physical PCI devices. A future application identity needs its own binding
and mapping revalidation; this prototype does not assume that a historical
ordinal remains correct. Output retains PCI identities and the reviewed mapping,
without deriving utilization or independently decoding installed-runtime UUIDs.

## Counter and coverage semantics

Deduplicate `(PCI, client ID)` without adding duplicate-FD counters. Retain the
selected descriptor, duplicate raw observations, and each render descriptor's
client identity. Conflicting duplicate capacity metadata or regressing duplicate
counters mark a snapshot incomplete. Recheck targets and render-client IDs so
reusing the same descriptor number during a scan is detectable. These bounded
checks are not an atomic kernel snapshot and cannot detect a change that appears
and disappears entirely between reads.

Both task scans inspect children. Any observed child means process coverage is
incomplete; task, render-descriptor, target, client, and child changes are reported.
Known nonrender descriptor churn is recorded in `nonrender_fd_churn` without
invalidating DRM coverage. Every descriptor is re-enumerated on the second scan,
so newly opened render handles cannot hide among unrelated descriptor changes.
A descriptor vanishing before its target can be classified remains conservatively
incomplete, since its render/nonrender role is unknown.
Only the admitted process's descriptors are read. Missing admitted render nodes,
missing counters, changed clients/capacities, and nonincreasing totals also mark
observations incomplete. Exited/zombie process states, identity/source drift,
fault markers, malformed input, and bounds violations stop observation.

CCS/BCS busy and total counters remain raw values. Missing counters are `null`;
missing capacity defaults to 1 and is explicitly labeled. Busy and total
high-water marks survive regressions, missing values, and temporary client
absence. Below-watermark observations remain incomplete until catchup; there is
no silent reset or wrap repair. Duplicates can advance a watermark even when the
selected descriptor's counter is missing. No utilization, busy seconds, compute
plus copy sum, idle estimate, or throughput ceiling is calculated.

The coordinator previously checked the
[generic DRM statistics specification](https://docs.kernel.org/gpu/drm-usage-stats.html)
and [Xe statistics documentation](https://docs.kernel.org/gpu/xe/xe-drm-usage-stats.html).
Upstream documentation does not itself prove the installed kernel's exact
counter behavior. Interpretation still requires reviewed engine/capacity
normalization and coverage treatment.

## Bounded output and failure handling

The exclusive JSONL header records source bindings, collector/contract digests,
process identity, ordered mapping, and limits. Header and parent directory are
fsynced before sampling. Short writes are completed explicitly; zero writes or
write/fsync failures raise instead of returning success. Every nonterminal
record reserves space for the terminal record, including skipped schedule slots.
Terminal counts reflect emitted samples, not the schedule-slot index.

Late starts push the next sample far enough out to preserve two-second spacing;
missed slots are reported rather than producing catchup bursts. Duration, slot,
and output caps are normal bounded terminations. Expected observation failures
write `observation-stopped` and the CLI exits nonzero. Other Python exceptions,
including `KeyboardInterrupt`, attempt an `observer-failed` terminal and are
re-raised. A `finally` block fsyncs the output and its parent on every Python
exit path. Failed writes preserve partial bytes without appending misleading
completion data. Disk errors or abrupt process/system termination can still
leave incomplete evidence: require a successful process exit and valid terminal
record before treating collection as complete. No retry or cleanup removes it.

## Synthetic validation

Run `PYTHONDONTWRITEBYTECODE=1 python test_collector.py` when CPU work is allowed.
All tests use temporary fake proc trees or mocked clocks/collectors. The 24
controls cover source/manifest/plan/mapping linkage, nonfinite JSON, dead-process
states, duplicate clients and conflicting metadata, missing/regressed counters,
FD reuse, nonrender churn, new render handles, child coverage, late wakeups, cap termination after skipped slots,
short/zero writes, fsync failure, and interruption evidence. No live proc, GPU,
endpoint, application control, or production contract was exercised.
