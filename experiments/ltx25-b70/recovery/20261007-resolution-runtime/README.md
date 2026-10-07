# 640×384 runtime — sampler accounting106 completed

Packet101 exposed a native FP32 inventory omission;101b corrected it and
produced six finite, exactly repeating native clips, then exposed a verifier
job-tag convention error. Both attempts stopped cleanly with healthy postflight.
The [101b closeout](../../notes/2026-10-07-resolution101b-verifier-refusal.md)
and [nonqualifying diagnostic](101b-offline-verifier-diagnostic.json) are retained.
Packet 101c then passed six native references, three candidate clips and ten timed
clips with exact four-tensor comparisons. Its short three-fixture serial-client
screen averaged 2.8702 s/clip (8.710 generated fps). The sealed proof reconstructed
after graceful shutdown; all four GPUs passed postflight.
[Measured closeout](../../data/resume-20261007/resolution101c-closeout/summary.json).
This is scoped workload qualification, not a speed record or endurance result.

Sealed102 passed its W2 screen: all six native executions and13 scored clips
matched exactly. Throughput rose41% to12.282 generated frames/s in the matched
three-fixture serial-client screen. The app was retained after successful completion; the unmodified verifier
reconstructed the proof. It later stopped cleanly for the controlled103 reload,
with healthy four-card postflight.
[102 closeout](../../data/resume-20261007/resolution102-closeout/summary.json).

The sealed103 runtime passed all ten original fixtures:20
native executions and50 scored optimized clips were exact. Initial throughput
was12.00FPS and thirty continuity clips averaged11.03FPS; late client delivery
drift has concurrent repository-work confounds. The unmodified proof reconstructed
after completion;103 later stopped cleanly for104.
[103 closeout](../../data/resume-20261007/resolution103-closeout/summary.json).

Sealed104 completed71 requests:20 native executions,10 candidate clips and both
ten-clip timing blocks passed exact four-tensor comparisons. The unchanged-ledger
policy measured12.786FPS versus12.040FPS, a6.20% gain in one quiet control-first
pair. It skipped724 redundant storage saves. Full proof reconstructed afterward,
and104 later stopped cleanly for105.
[104 result](../../notes/2026-10-07-client104-performance.md).

Sealed105 confirmed the client improvement in reverse order:12.617FPS versus
12.098FPS, a4.29% gain, with all ten native repeat pairs and thirty scored optimized
clips exact across all four tensors. Its full sealed proof reconstructed after
completion;105 later stopped cleanly for106 after its finite plan was consumed.
[105 result](../../notes/2026-10-07-client105-performance.md).
The client comparison lever is closed; keep the reduced-write policy.

Current author sources reconstruct106, one completed passive sampler diagnostic. The
[fixed plan](../20261007-sampler-accounting106-plan/README.md) preserves all ten
fixtures, model arithmetic, steps, precision, encoder window and W2/B1. It admits
20 native,14 candidate and14 reduced-write timing requests plus nine setup
requests:57 attempts and50 captures. Fresh runtime admission requires4GiB above
50GiB; source construction has a separate384MiB allowance.

The final `verify-fast-timed` action reconstructs native and candidate proofs and
opens the durable `fast_verified` barrier. There is no control timing block.
Checks, state durability and event fsyncs retain the qualified client policy.
A source-bound passive child reads the server's existing DRM fdinfo counters
before the timing block. It never opens devices or changes server settings.
It admits one child, a120-second observation,64 slots and128KiB output; kernel
read latency can overrun the wall deadline. Readiness is bounded at10seconds,
and normal finalization waits only to the original start plus130seconds.
There are no child signals or retries. A failed model request preserves its
original fault/lifecycle decision and any partial diagnostic without waiting.

Diagnostic validity is independent of model equality. Complete raw records do
not by themselves establish utilization or attribution inside the scored clips;
those require separate interval/engine/client analysis.106 completed57 requests,
withten exact native repeat pairs andtwenty exact optimized clips. The full proof
rebuilt independently. Its whole counter diagnostic remains invalid because two
scans lost an unclassified descriptor, including one inside the scored window.
Seven later complete interior pairs support only a posthoc exploratory raw-counter
subset. The application remains retained and idle; its finite plan is consumed.
This remains a repeated-workload diagnostic, not a public record or endurance claim.
[106 closeout](../../data/resume-20261007/sampler106-closeout/summary.json),
[scoped counter analysis](../../data/resume-20261007/sampler106-posthoc-counter-subset.json).

The owner has supplied replacement instructions preferring application reuse.
The runner now retains a successful application after verifying quiescence.
A failed campaign may attempt one bounded graceful incident stop; faults or
unresolved work remain for the coordinator. No automatic restart or request retry
is allowed. Retaining the application does not authorize bypassing its consumed
request plan; follow-up work needs its own registered admission.

105 is the reviewed predecessor; 99b remains the constructor source. Sealed
historical packets and plans are unchanged. New native references must precede
optimized capture. The accepted text encoder remains graph-sharded, so this is
not an all-eager oracle. The103 result is exact on the registered ten-fixture scope; it is not a public
record or a long endurance claim.

Implemented components:

- `geometry_overlay.py` transforms exactly seven hash-pinned source paths,
  retaining historical guards and adding an explicit phase-bound comparison
  mode. [Source contract](source-contract.md).
- `session.py` admits only exact registered graphs with new execution IDs,
  enforces ordered native/optimized phases, records barriers, and permanently
  halts after a failure. Completed pipeline tails may be released only after
  their identities are durably recorded; unfinished work cannot be cleared.
- `executor_guard.py` delays Comfy's success event until post-request checks
  and the authority's durable completion succeed. A refusal becomes a failed
  history entry. Halt-receipt write failure cannot kill the prompt worker.
- `runtime_observer.py` reads the actual registered node modules and pipeline
  jobs, including completed but uncollected tails. Importing a separate source
  mirror cannot stand in for the active node's ownership state.
- `reference_gate.py` rereads twenty native executions and all four tensor files,
  verifies distinct executions and exact repeat pairs, and exclusively writes
  a reference receipt. Reading the receipt reconstructs its proof from retained
  artifacts. [Reference contract](reference-gate-contract.md).
- `setup_gates.py` checks actual text-window, coverage, chain/freeze and decoder
  verdicts. A successfully completed setup prompt can still contain a negative
  result. Seeded native/replica decoder consistency remains distinct from real
  reference-clip equality; the old internal speed-only labels are preserved.

`native_safety.py` and its concrete `native_adapter.py` now check actual
registered node owners, unchanged resident tensor identities and fresh device
memory. The narrow loader wrapper protects loaded owners from eviction; ordinary
Comfy allocator bookkeeping is retained. `candidate_gate.py` verifies real
emissions against the ten native reference pairs and excludes fills. The complete
`request_client.py` accepts only the57 exact scheduled requests and reads fresh
server phase observations; `schedule.py` binds the nine setup graphs.

`integration.py` connects setup-result checks, native safety, source identity and
phase proofs. It also observes the separate preview writer queue, so unfinished
tail previews cannot cross phase boundaries. `runtime_packet.py` prepares a new
source packet only with an explicit reviewed input-inventory hash; its default
is read-only. `campaign.py` operates one already-owned application, submits each
request once, retains a successful application, and attempts a single incident
stop on failure only after actual quiescence.
It does not start or restart a server. The initial timing screen uses a serial
client feeding asynchronous pipeline stages, not a fully queued throughput run.

CPU suites are adjacent `test_*.py` scripts; validation results are recorded
before sealing. Required before device execution: source closure checks, fresh
actual host/storage admission, namespace collision checks, and actual resident
object/memory observations. A component test is not a launch admission.

The failure guard must prevent estimated/actual native VAE OOM from reaching
automatic tiled decoding or its cache-flush fallback. Pre-native physical free
thresholds6/6/2/7GiB include provisional allowances, not proven full-model peak
bounds. Capture 0 requires 6/6/2/7 GiB free; capture 1 requires 7/7/2/7 GiB.
The latter keeps a provisional 4 GiB transient allowance, 1 GiB rounded pool
allowance and 2 GiB floor on the sampler cards. Neither is a measured peak bound.
Both captures record fresh post-capture memory and enforce the 2 GiB floor.
Actual resident weights and encoder graphs must already be present.
Keep the50GiB disk reserve, fresh4GiB write allowance and50-capture bound.

Tests are adjacent `test_*.py` scripts, run with `python3 -B` individually.
Synthetic schema controls are labeled as such and are not model measurements.
CPU controls alone do not establish GPU performance or visual quality; measured
claims above are limited to their linked result evidence.
