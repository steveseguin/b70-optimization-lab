# Packet149 — measure the exchange bill inside the correction path

Prepared on steve-b70s, October 18, on main. Pull refused unrelated dirty files;
fetch confirmed HEAD matched origin/main at
`6a86eb7c508856ab39e81204cfb1648fc941bb62`. Other workers' changes are preserved.
This work is CPU-only: no GPU launch, service, sudo, host-setting change or live
queue write. The packet148 CPU study and all earlier packets stay untouched.

[Packet149](../experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/README.md)
vendors the packet136 source and the later one-load harness. All 182 original
symlink objects are preserved as provenance; active code uses the closed local
source tree, immutable parent ELF inputs and the unchanged packet49 oracle
binding. It keeps banked rollback, exact target arithmetic `iq3-p49-split32-v1`,
BF16 state/KV, the corrected drain wait, native getrlimit checks and the vendored
`ops/launch_env.py` environment. New loader module names are packet149-specific.

The proposed shared work is the large attention projections and routed expert
projections. Four coalesced exchanges per layer use actual BF16 shapes, selected
expert IDs and error flags. The 24-layer correction adds 96 round trips:
849,792 bytes out and 1,362,048 bytes back. Small projections, HC, PLE, shared
experts and state updates remain local. This is an explicit design scope, not
a claim that four exchanges suffice for every possible shared runtime.

The on/off switch only enables exchanges during a confirmed miss correction.
The peer responder is an explicit miss-only command. Saving the draft publication
sequence separately prevents this command from being mistaken for a new draft.
Private scratch has its own strict non-aliasing snapshot exclusion; the p105
head scratch rule is unchanged. Actual received bytes are discarded. All native
copy/event operations use the existing compute-queue path; peer copies contend
with any outstanding draft. The native census requires 96 exchanges per miss.

The report reader now consumes the views that v5 actually retains. It no longer
requires per-request p105 head-transfer logs. Corrected halves are matched to
miss positions, with per-view correction time, miss count and throughput.
The real failed packet145 router bracket is replayed read-only, redirecting only
report output to scratch. Its original evidence hashes remain unchanged.
The old bracket's times are regression checks, not new probe measurements.

The device proposal is lane B: first one xchg 12 × 64 smoke, then one load with
five 12 × 128 views, off/xchg/off/xchg/off. Each view also runs the existing
incident64 check after reset. Every generated token must match the unchanged
oracle. The bracket checks per-prompt draft proposals and acceptance counts,
loaded allocation identity, complete request resets and cold-cache status.
No proposal is queued by this preparation. Device quality and timings are pending.

## How to use the eventual measured cost

Let `C_off` be mean corrected-half time per miss in the control views, and
`C_xchg` the corresponding time in a probe view. The report gives
`E = C_xchg − C_off` in milliseconds per miss, retaining every view and the
control drift. Also inspect per-prompt corrections, native command clocks,
exchange counts and full token throughput. A negative difference within drift
is not evidence of free communication.

Let `G` be the gross compute time that a real cooperative row split saves in the
selected projections, and `A` its additional assembly, scheduling, weight-access
and draft-interference cost beyond this surrogate. Then:

`C_real = C_off − G + E + A`

`net correction reduction = G − E − A`

To obtain the packet147 target of **2–3 ms net per miss**, a real implementation
therefore needs **at least E + A + 2–3 ms gross compute saving**. No value for G
or A is measured here. The old correction time of about 11.819 ms is a baseline
budget, not a promise that all of it can be split. The 2.6–3.9% target is the
previous interval-replay sensitivity, not a packet149 prediction.

For a throughput estimate, use the saved per-interval critical-path model:
`max(D, R + C) + max(B, A_half + speculative_offset) + control_gaps`.
Replace only C on actual miss intervals with the proposed net reduction and
recompute each prompt's 99-interval rate and the median across class medians.
Do not subtract an average miss penalty from reciprocal aggregate tok/s: draft
and corrected halves overlap, and some savings are hidden by the draft.
The probe's measured throughput remains separate from that later projection.

The probe deliberately leaves all original rank-0 compute in place and performs
serialized transfers. It omits peer matrix work and duplicate weights. Its E
measures this concrete schedule under the engine; it is neither a universal
communication lower bound nor a proven upper bound for a finished shared design.
Any later overlap or different grouping must earn new in-engine evidence.

## Validation and handoff

GNU and Intel builds and two fresh runs per compiler check the controller and
actual transport methods on CPU mocks. Hit/miss/mixed/native-draft cases preserve
tokens, proposals, acceptance and final state. Transport checks 96 exchanges,
all payload extents, waited copy events, peer-abort and odd-row refusal, and
unchanged model buffers. These are mock proofs, not a full-model quality pass.

The payload/source checks, real retained report regression, drain and limit
checks, real entry/worker/report tests, temporary queue plans, report rehearsal
and pin guard are retained under the packet's `v5/evidence/`. The final marker
binds their successful receipts and both exact proposals. Source and note commit
is pushed first; the final marker is then the last workspace write and is
committed and pushed separately with that source commit in its body.

The 58.798108759182306 record is unchanged. Root stayed above the 25-GB reserve;
new build material is capped at 300 MB, and CPU work stays below 4 GiB. Compilers
use the shared arbiter and honor its timing-window holds. No full-model payload
or full-shape startup read is part of the validation. Inherited unused synthetic
fixture copies were excluded; their original packet trees remain intact.

Final native build receipt: 68,045,191 bytes of build material; peak compiler child RSS 736,644 KiB. Four real entry combinations, eight limit probes, all 78 worker requests, both proposal plans and both report rehearsals pass. The pin guard passes on both proposals. The transport test confirms the actual native probe methods preserve every mock model buffer.

Git whitespace checking reports inherited whitespace in the vendored source/history. Those retained bytes are preserved; this is not a clean-whitespace claim.
