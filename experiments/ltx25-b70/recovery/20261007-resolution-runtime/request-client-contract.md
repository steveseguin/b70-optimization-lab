# Finite request client (CPU-tested; live integration pending)

`request_client.py` implements serial requests from the reviewed plan, semantic SHA
`3281a1eb45d210ac75f2a07c415cf2f99b2b9308651456587aa483e2596d65e2`.
It has not contacted an endpoint or run a model. Tests use a stub transport and
stub passive process/filesystem probes. This component neither launches nor
stops a service, sends a process signal, modifies settings, or retries a POST.

The public interfaces are:

```python
client = Client(contract_path, independently_expected_contract_sha256)
await client.execute(exact_registered_request_name)
await execute_native_sequence(client)  # all six, serial; stops at first failure
```

The CLI performs exactly one named request. It is not a campaign launcher:

```text
python request_client.py --contract /absolute/client-contract.json \
  --contract-sha256 EXPECTED_SHA256 --request EXACT_REGISTERED_REQUEST_NAME
```

Do not execute this command until the sealed runtime, phase authority, native
safety guards and coordinator admissions are ready. A native-only contract
accepts the first six plan requests. A complete-schedule contract accepts exactly
32 ordered requests: two native setup, six native, five optimized setup, six
candidate, and thirteen timed. The coordinator owns phase transitions and
receipt barriers; this client never advances a phase. It does not implement
concurrent queue batching or service lifecycle operations.

## Independently bound contract

The coordinator supplies an immutable `ltx.resolution-request-client.v1`
object and its expected SHA-256, containing:

- Exact `plan_sha256` above and qualified `parent_manifest_sha256` 99b
  `f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
- Absolute `root`, `server_run`, `client_dir`, `plan_path`; `client_dir` must
  initially be unused, its parent already present, and `root/requests` present.
  Runtime and client evidence must use the same admitted filesystem.
- `server_identity_sha256`, `runtime_manifest_sha256`, and `source_bindings`
  mapping absolute regular source paths to SHA-256. Bind the actual loaded
  `request_client.py`, sibling `reference_gate.py`, and the sealed session
  authority at `capture_guard_path` (also an entry in `source_bindings`). The
  launcher must validate that this really is the reviewed capture authority;
  merely naming an arbitrary hash-bound file is not source qualification.
- `min_free_bytes=53687091200`, `planned_write_bytes=4294967296`,
  `max_captures=32`, and integer `request_timeout_seconds` from 1 through 1800.

For the complete schedule, also supply `setup_schedule_path` pointing to the
sealed `resolution/setup-schedule.json` envelope, `setup_schedule_sha256` equal
to `9f79ee01c507d46c106f9e0037eda772a20a717a49d3de03a2aca06785517441`, and
`phase_observation_path` pointing to the bound run's
`resolution-client-phase.json`. This digest is SHA-256 of the canonical inner
`schedule` object, matching the envelope's `schedule_sha256`; it is not the
envelope file's byte hash. The client separately retains and rechecks the exact
envelope bytes. Include sibling `schedule.py` in `source_bindings`; its validator
reconstructs the exact setup graphs from pinned parent sources and the plan.
Unknown, changed, reordered or repeated requests refuse before submission.

The trusted server status handler writes an atomic observation under the phase
authority lock after checking actual queue state. Immediately before every
client request, the coordinator refreshes it through `/ltx-resolution/status`.
Its schema is `ltx.resolution-client-phase.v1`, with `plan_sha256`,
`qualification_id`, `runtime_manifest_sha256`, `server_identity_sha256`,
`phase`, `active_request=null`, `fault=false`, and integer `observed_at_ms`.
The client requires an observation no more than 30 seconds old, both before
starting an attempt and immediately before POST. Native/setup rows require
`native_reference`; optimized setup/candidate rows require
`optimized_preparation` and `reference_receipt_sha256`; timing requires
`timing` plus both reference and `candidate_receipt_sha256`. These fresh status
observations are not immutable qualification proofs; the server authority
independently verifies the actual receipts before phase changes. The client
saves the observation bytes' hash and contents with each request and cannot
create an observation or advance authority itself.

The server identity must match the pinned successor and original model receipt
`273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f`.
Its PID, string proc start ticks, boot ID and server-args hash are checked.
Before submission and at every wait/checkpoint, the client rereads the fixed
identity, bound sources, root `FAULT.json`, run `resolution-halt.json`, and
passive procfs identity. Reused/dead/zombie PID, changed source or fault/halt
prevents further work. No GPU health probe is performed by this client.

## One attempt and durable evidence

The exclusive client directory contains a locked durable ledger. Each attempted
name is recorded before the one possible `/prompt` POST. A failed or uncertain
POST, disconnect, timeout, status error, cached node, malformed history, storage
refusal or any other exception permanently halts this client ledger. Reinvoking
it does not retry the failed request. Existing request directories refuse and
are never modified.

The exact pinned graph is sent unchanged: no seed, name, clip index, run_name,
comparison mode, graph edge or preview-prefix rewrite. Each new request gets
exclusive `prompt.json`, `identity.json`, `submission.json`, `events.jsonl`,
`history.json`, and `result.json` compatible with the existing profiler/reference
gate schemas. Errors retain partial evidence and `client-failure.json` where
possible. File and directory fsyncs make completed writes durable; ENOSPC or
other write failure cannot promise that an additional failure receipt will fit.

The client checks an empty queue, opens a fresh WebSocket, rechecks identity and
budget, and checks the queue again before submitting. Server authority must
still own admission: those observations do not lock out another client.
Messages for other prompt IDs cannot complete the request. Its fresh prompt ID
must have a current execution_start and matching execution_success; cached nodes
and error/interruption terminals refuse. History must match the submitted graph,
submission number/ID, current start/success messages and successful status.
Only after a matching success may history be polled, at most 20 times with
100-ms waits. All transport calls and receive waits share the request deadline.
There is no HTTP retry on an error and no submission retry under any condition.

Timeout closes only the client connection. It leaves the potentially executing
job and server untouched for the coordinator's bounded diagnosis and graceful
shutdown policy. The server guard separately halts on its own numerical/safety
failures; the client does not manufacture a server halt receipt.

## Disk and capture accounting

Before initial evidence creation, available space must cover the 50-GiB reserve
plus the 4-GiB allowance. The persistent ledger then charges every observed
positive availability decrease across checkpoints, including client evidence
and concurrent filesystem writes. It never resets the 4-GiB charge between
requests or credits later frees. Each checkpoint requires the remaining allowance
plus the 50-GiB reserve; exhausted allowance stops new work. Observations between
checkpoints are not a filesystem quota or reservation and may miss offsetting
allocations/frees. The coordinator must exclude unrelated writers and retain
the server's own storage/admission guard. The bound includes setup and later
tails only when the complete driver uses this same ledger from campaign start;
the legacy six-request API does not account for earlier setup writes.

The client conservatively caps attempts at 32; the complete schedule has 32
requests and 26 planned captures. **Actual captures**, including setup, pipeline fills/tails and other
phases, remain counted by the hash-bound server session authority. Its cap is
not inferred from successful output count or from this client-only attempt list.
Neither cap proves that 4 GiB will suffice for the unmeasured workload.

CPU controls:

```bash
python3 -B experiments/ltx25-b70/recovery/20261007-resolution-runtime/test_request_client.py
```

The tests exercise real pinned graph names/payloads, compatible evidence schemas,
serial six-request ordering, one-attempt failure latching, stale/cached/foreign
events, bounded history polling, passive identity refusal, source drift,
cumulative storage charge, timeout and refusal without touching prior evidence.
Complete-schedule controls exercise all 32 registered rows, coherent setup
tampering, stale status, the reference phase barrier and the candidate receipt
requirement before timing. All observations/transports are synthetic; these
controls establish no live memory, correctness or performance qualification.
