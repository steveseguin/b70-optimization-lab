# Route and phase diagnostics for the next two-card run

This is an independently authored, CPU-testable C++20 adapter and wire schema.
**It is not installed in packet45, and no device collection has run.** It is
ready for a future unsealed two-card owner to attach the hooks below. Packet46's
single-card layer timing window does not need or enable this diagnostic.

`trace.hpp` has no device, model, math or routing implementation dependency.
It observes original ordered route IDs and existing event timestamps. It never
computes an expert, reorders a route, sums outputs, changes a state update or
chooses a token. The callback used for route reads can introduce synchronization;
therefore `Mode::diagnostic` is required and every header and validation result
says `diagnostic_only=true`, `speed_claim_eligible=false`. Flags with off or
speed-claim mode throw before callbacks or output. Default-off calls invoke no
read, event-query, copy or wait callback. The future owner's CLI must derive
`Mode` from its purpose, never silently turn a speed run into a diagnostic.

## Wire schema v1

Canonical schema: `ownrt.packet46.diagnostics.v1`, JSONL, one file per rank.
Each collector has one issuing-thread writer; it is not a shared worker logger.
`validate.py` defines the exact allowed fields and validates field types,
geometry, identity consistency, unique routes/events, intervals, final command
resolution and a complete footer. No third-party validator is required.

Every row carries `schema`, `kind`, consecutive zero-based `record`, `rank`
(0/1) and physical card. The header additionally carries:

- `run_id`, immutable `model_identity` and `runtime_identity` (use checkpoint,
  oracle and dispatch/seal SHA256s, not mutable labels); `prompt_sha256` binds the
  ordered prompt-input manifest; `dataset_role`: calibration, evaluation or mock.
- `routes`, `phases`, `target_experts_per_layer=512`, `target_top_k=10`, and the
  two diagnostic/speed-claim booleans described above.

Each routes/phase/resolution row has a command key `(request_id,
command_sequence)` plus `position`, input `token_id`, `occupied_context`,
`stage` (prefill/decode), `attempt` (ordinary/speculative/corrected/draft).
The same key must always have identical metadata. Preserve the input token of
rejected speculation: a position alone is not a unique execution. Context is
the number of preceding occupied positions at entry, not allocated capacity.
Request IDs are assigned by the coordinator and shared across both ranks;
command sequences retain the existing wire request's sequence and are unique
within a request/rank, including corrected work and draft commands.

| Kind | Additional fields and meaning |
| --- | --- |
| `routes` | `layer` 0–47; `expert_ids`: ten distinct IDs 0–511 in **original routing slot order**, never sorted. Target routes only in v1. |
| `phase` | `layer` (-1 boundary, 0–47 target, 48 draft); `phase`; `clock`; `event_id`; `start_ns`, `end_ns`, `duration_ns=end-start`. |
| `resolution` | `outcome`: accepted, rejected, cancelled, error or draft_proposal. Exactly one final resolution per command, after its observations. |
| `footer` | `complete=true`; absent on an interrupted/failed collector. Unresolved commands cannot close successfully. |

GPU `clock=gpu_event` rows contain one original profiled event each and a
positive ID. Sum `end-start` within a named phase to reproduce the packet45
per-class GPU-busy measure. `clock=host_steady` rows have `event_id=null` and
explicit enclosing host spans. Their epoch is process-local. GPU epochs are
device-local. **Never subtract timestamps across these clocks/ranks, add host
and GPU durations, or add overlapping phases as a wall-time budget.** Host
enqueue/wait/command intervals can nest. Label them as enclosing intervals.
Handoff copy events and mailbox waits are separate; mailbox time is not PCIe
transfer time. CPU mock intervals establish schema behavior only.

Allowed phases are `prepare`, `enqueue`, `wait`, `dense`, `routing`,
`expert_gate_up`, `expert_down`, `shared_expert`, `attention`, `gdn`, `hc`,
`sampler_head`, `snapshot_capture`, `snapshot_restore`, `draft`, `handoff_copy`,
`handoff_mailbox`, `lookup_copy`, `command`, `accept`, `diagnostic_route_copy`.
Choose exactly one GPU phase per event. More detailed site labels can be added
under a new schema version; they must not double-count the same event.

## Hook plan for a future unsealed engine

1. Parse purpose and optional route/phase flags before queue construction.
   Reject either flag for a speed claim. Construct one `Trace` per rank with a
   bounded record budget and an exclusive new output path. Request profiled
   queue events only for enabled phase collection, using the existing backend.
   Do not add a second timing execution of a command.
2. In the equivalents of packet45 `rank.hpp::half_step` and the draft/rollback
   handlers, construct `Command` from the actual pipeline request. Attach host
   spans at preparation, enqueue, waits, capture/restore, draft, handoff and
   complete-command boundaries. Layer/class events are identified at
   `main.cpp::issue_site`/`finish`; do not replace existing cancellation hooks
   `Device::before_compute` or `after_compute`.
3. Immediately after each completed route producer and **before any reuse of
   that layer's route allocation**, call `capture_routes(command, layer,
   callback)`. The callback waits for the producer and reads the first route
   output (ten IDs), or ten `iq3::Route::expert_id` members of its descriptors,
   into an `std::array<uint32_t,10>`. Read the allocation's actual scalar type;
   do not reinterpret float/BF16 ID arrays as uint32. The route42 descriptor
   layout is `{expert_id,row_begin,row_count}`. Use the original selected IDs,
   never layer-streaming's remapped compact 0–9 slots. No route weights are
   needed for cache modeling. Sticky errors/cancelled producers emit no stale
   route row. Record readback cost as `diagnostic_route_copy` if phases are on.
4. In the equivalent of `Engine::drain`, **after event completion but before
   `retire_completed_events()`**, call `gpu_events` with the actual event IDs
   and `dev(0).timing(id)` callback. Existing `Launch` groups give first, last
   and passes; check their contiguity as packet45 does. Record copy events too,
   without relabeling them as compute kernels. Host wait duration remains a
   separate span. Disabled callbacks submit nothing.
5. Hold resolution until ACCEPT/ROLLBACK/cancellation/error is known; mark
   speculative accepted only after the target verifier confirms it. Corrected
   target work has its own sequence. Mark draft commands `draft_proposal`.
   Finish all rows, resolve commands, call `close()`, and run `validate.py`.
   A budget/write/schema failure invalidates the diagnostic attempt; never
   silently drop rows and report a complete census.

Use accepted target decode rows for token-popularity estimates, and separately
report prefill. Use **all** executed rows, including rejected work, for work and
cache-traffic modeling. Cancelled commands can contain only a layer prefix;
report coverage and never impute missing layers. Header dataset roles keep
independent cache calibration apart from benchmark evaluation. No hit rate is
measured until actual IQ3 routes exist. Freeze placements from independent
calibration; never train cache choices on benchmark prompts. Retain ordered
records and their hashes, then derive counters offline. A future diagnostic
window must also compare tokens and states against the same uninstrumented
owner; observation-only source design does not replace that device check.

## CPU checks (compile only after 2026-10-17 02:55 UTC)

From the repository root; these commands do not access a GPU or weights:

```sh
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet46-specialized/diagnostics/run_cpu.py --output experiments/own-xpu-runtime/stage2/packet46-specialized/diagnostics/evidence/cpu-gate
```

The runner enforces the cutoff/CPU/storage rules and shared preparation lock,
compiles once, executes fresh processes twice, checks schema tests, and records
source/binary/trace hashes with timestamps. For an isolated manual reproduction
after the cutoff (serialize against other packet46 CPU work):

```sh
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet46-specialized/diagnostics/test_validate.py
nice -n 19 taskset -c 4-15,20-31 c++ -std=c++20 -O0 -Wall -Wextra -Werror experiments/own-xpu-runtime/stage2/packet46-specialized/diagnostics/mock_test.cpp -o /tmp/packet46-diagnostic-mock
nice -n 19 taskset -c 4-15,20-31 /tmp/packet46-diagnostic-mock > /tmp/packet46-diagnostic-mock.jsonl
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet46-specialized/diagnostics/validate.py /tmp/packet46-diagnostic-mock.jsonl
```

The mock checks disabled callbacks, explicit speed-run refusal, invalid routes,
changed inputs, rejected/corrected identities and timestamp serialization.
Python tests reject altered IDs, duplicate observations, unresolved commands,
invalid times, scope leakage and ambiguous command identities. These are
diagnostic contract tests, not model quality or performance evidence.

`cache_report.py --cache-budget ../cache-budget.json rank0.jsonl rank1.jsonl`
validates the traces and evaluates that frozen placement offline. It reports
all-executed and per-outcome packed bytes, per-layer miss counts and empirical
tails, accepted-route popularity, and explicit observed layer coverage. Prefill
and decode remain separate. It accepts an explicitly partial one-rank trace
and labels the ranks present; missing layers are never filled in. It neither
trains a placement nor infers a tokens/s result. CPU mocks test the report but
are not IQ3 hit-rate evidence. Keep evaluation data out of cache training.
