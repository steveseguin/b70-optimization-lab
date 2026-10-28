Dedicated persistent all-owner reset overlay — review candidate, NOT applied

Candidate.patch and overlay/ contain explicit opt-in native + controller wiring.
No canonical file, model process, GPU or commit was changed. Native full build
and model A -> B -> A gate remain unrun. status.json binds current source bases.
The main/rank diff against current canonical was inspected: only reset hunks.

Native composition
Startup retains twelve immutable prompt mappings plus model auth identity.
Policy v2 derives F32, check policy, capacity, depth, rows, slots and the actual
0/1 OWNRT_REFERENCE_ROUTE_TIE_SORT environment; changed/invalid policy refuses.
Targets retain Suite lifetime, use existing ring/reset/state-zero primitives,
replace prompt only after engine reset, and invalidate their entire publication
and bulk maps. Provider uses actual Owner reset, private-byte zero readback,
existing sealed native cold-baseline verifier, allocation identity, prompt/header
publication and trace rotation. Final provider receipt precedes ACK and follows
bulk flags reopening. Legacy branches and default refusals remain unchanged.

Controller composition
The suite planner extends the existing dedicated planner (no expected tokens).
It registers exactly twelve prompts, writes immutable authority files, binds
suite/policy into request identity, pins sources/files, and checks all-owner route
policy. Existing dedicated lifecycle launches once, loops twelve requests, and
FINISHes once. Optional registered order [0,1,0] is the bounded reuse gate; it
retains and byte-compares complete first/last A target AND provider source maps/bundles and actual emitted
output IDs. The provider comparison requires all73 sources.
Every transition uses existing OP11 sequencing/receipts, all-owner quiescence,
actual full sealed target/provider DUMPs and exact cold payload comparison.
Only after all ACKs + cold proof does it republish the actual retained prefill
geometry header. The first OP15 admission consumes one-shot epoch/request/prompt
readiness and verifies actual provider Header and full bulk geometry/tail bytes.
All owners receive one common request plan. Partial failure poisons the lifetime;
there is no retry, restart or further request after a failed barrier.

Cold proof and retention
All 2,065 canonical target sources and 73 provider sources are required, including
inactive banks; every physical owner copy is authenticated and byte-compared.
Host inventory remains exact except the two source-proven prepared launch-cache
extent fields, separately checked for bounded multiples of32. No complete-host-
identity claim is made. Duplicate cold payloads are unlinked only after real full
reader verification, exact bytes/source maps and a durable alias receipt to the
retained startup payload. All metadata remains. No baseline bytes are removed.
Forecast is three complete per-owner payload sets (four for the retained first-A
reuse gate) + the native provider sealed
baseline +64MiB metadata allowance, checked above the unchanged evidence floor.
The actual provider payload at262K is at least638,509,378 bytes; actual startup
cold extents must fit registered per-owner bounds before request0. Native device
allocation/runtime floors and startup96GiB admission are not lowered.

CPU evidence
Actual provider run_loop/Owner/Prompt/Suite/v2 descriptor/header/trace and sealed
cold-reader refusal fixture passed, with synthetic73-source engine (r3). Route
policy mismatch and invalid environment refuse. First r1 fixture name-collision
failure is preserved. Six controller tests pass: actual full sealed reader and
cold byte/source proof, inventory adverse cases, actual reset_all ordering with
mocked wire-owner ACKs, cold failure poison/no publication, and first OP15
admission/header/one-shot readiness. The request-loop test verifies twelve drives
and eleven barriers reuse the same owner objects with fresh epochs/plan bindings;
its transport/model/cold operations are mocked, not a native lifetime proof. Three fragmented provider transport tests
also pass. These are not native Engine/GPU or model lifecycle proof.

Review/build/launch sequence
1. Review isolated patch + exact current base hashes; apply only reviewed hunks.
2. Actual native full build with new headers pinned; no arithmetic change.
3. Prepare authority once with dedicated_provider_suite_plan.py --prepare-authority
   --config CONFIG. Then use --config CONFIG --plan PLAN for pure, read-only plan
   generation. make_plan defaults to validating existing authority, never writes.
   Use an ordinary dedicated config
   augmented with dedicated_reset_protocol, dedicated_request_suite (existing
   runtime-only suite schema), fresh dedicated_suite_authority directory,
   dedicated_reset_payload_bounds and dedicated_reset_evidence_bytes. Optional
   dedicated_request_indices=[0,1,0] selects first reuse gate; omit for full12.
4. After existing admission/guard approval, --run --plan PLAN --admission ADMISSION
   --unit UNIT validates the admission plan SHA, all source pins and pure regenerated
   identity before invoking the existing lifecycle. Existing launch authority executes the planned owner
   lifetime; do not bypass startup/runtime/evidence floors. No GPU run is done.
5. Require actual cold/allocation/sequence/first-OP15 and repeated-A fullstate
   proof before the realistic12 timing. Host-wall per-request timing is valid;
   provider native counters remain cumulative and are not per-request metrics.

R2/R3/R4 CPU closure (2026-10-28)
Suite planner pins actual reader.py, persistent_live_suite and rolling_ring_driver
module paths; preparation and regeneration enforce native prompt bounds3..context-512.
Four new CPU tests cover immutable authority regeneration, unexpected inventory,
boundary refusal before directory creation, dependency pins, admission SHA/pin/
regenerated-plan refusal, and CLI validation before lifecycle execution. Combined
13 controller/planner/transport tests pass. Planner/lifecycle in entry tests are
mocked: no native admission, model or GPU execution claim. The preserved guard
requires bulk prefill; measured check policy is independent of transport mode.

Apply-path correction and resource review (2026-10-28)
Run git apply --check candidate.patch from experiments/own-xpu-runtime/engine;
the default -p1 strips the leading engine/ component in patch paths. Dry apply
from that exact directory passed; no canonical mutation was performed.

At context262144 the registered conservative A-B-A forecast is four complete
physical-owner sets plus one provider payload plus64MiB, ABOVE the unchanged
evidence floor. This is not affordable with roughly16GB/set and currently
50,251,800,576 bytes available on /dev/shm (17,206,480,896 already used).
The root filesystem currently has27,268,268,032 available bytes, also insufficient
for that full forecast by itself. These are observations, not admission authority.
Do not reduce bounds/floors to launch. Existing lifecycle explicitly checks
/dev/shm; merely putting evidence on disk does not satisfy that guard. A separate
reviewed evidence-location authority would need actual owner output relocation,
pinned plan/path identity and per-filesystem capacity checks. Smaller-context
qualification is the existing safe option if its real native layout, planner
runtime/startup/evidence floors and model geometry all pass unchanged.

Repeated-A metadata review: reader includes state.json in its complete source map.
Target state_dump JSON has history0/history1, buffer hashes, fp32_cache_valid and
fp32_extent. Provider live_dump JSON has buffer/layout inventories and host
position/context_extent/disabled/async_pending/pending_head/pending_confirmed/
reverse_hidden_present/queued_probe/queued_confirmed/depth_probe. Neither JSON
contains request hash, epoch, command sequence or output path. Ring attestation
with epoch/request is a separate sibling file, outside the sealed bundle reader.
Therefore new request identity alone cannot cause the repeated-A map comparison
to fail. Actual fp32/context/host-state differences remain meaningful failures.

Cold-count correction: rank0 banks are allocated before READY and persist through
reset. Canonical2065 excludes alternate-* ONLY from that count. All alternate
sources remain in full map and payload comparison; exact inactive inventory
matches native stage metadata and extents match active and launch-plan bytes.
Proof separately records inactive_bank_sources. Sealed alternate-only mutation
CPU refusal passes; all13 CPU tests pass. Python canonical and overlay synchronized.
