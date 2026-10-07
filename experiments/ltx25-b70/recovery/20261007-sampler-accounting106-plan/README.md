# 106 sampler accounting: standalone CPU plan, runtime pending

This is a bounded passive driver-accounting diagnostic, not another client-policy
comparison. The ledger change is adopted for the sole timing block after 104/105
confirmed its benefit in both orders. No application request, runtime integration,
namespace reservation, build or reload was performed by these plan constructors.
The consumed 105 plan is immutable and cannot admit this schedule.

The same numerical workload is preserved: original ten prompts/seeds in order,
accepted window 64, native BF16 sampling/decode, 640×384 output, 25 frames, 8+3
steps, W2/B1, 23/25 transformer placement, sampler depth two and decoder depth two.
The independently pinned 99b constructor manifest remains
`f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
The qualification basis binds the successful 105 predecessor manifest
`1ff7bd5ab281dad1a19f8d01aaf8899505168f0606689ba43ccb23cc05311fad`, without using
its candidate sampler/decode as the native oracle.

[plan_reference.py](plan_reference.py) builds [candidate-plan.json](candidate-plan.json):

1. Twenty independent native executions, two passes of all ten fixtures.
2. Fourteen candidate-check requests: four unscored fills, ten exact emissions.
3. Fourteen `timed-fast` requests: four unscored fills, ten exact emissions with
   `storage-change-only` checkpoints and bounded passive accounting.

There are **48 model-plan requests plus nine setup requests: 57 total**. There is
no `timed` control block and no further client confirmation. Native/setup/candidate
requests retain `always` policy. All explicit changed-state saves, attempt and
completion durability, event fsyncs, source/process/fault checks and fresh storage
checks remain required. Source-bound per-request policy readouts remain required.

Namespace: `resolution-sampler-accounting-20261007`. Native indices are
99906000–99906019; setup captures are 99906030/99906041; candidate indices are
99906100–99906113; diagnostic indices are 99906200–99906213. Prior sealed
101/101b/101c/102/103/104/105 names and indices do not collide in CPU checks.
Actual request/output namespace reservation is still a runtime obligation.

[schedule.py](schedule.py) builds [setup-schedule.json](setup-schedule.json) from
pinned setup graphs. Preserve all nine setup operations, both worker-specific
capture admissions and completed-tail retirements, full chain/replica qualification
and freeze. Native verification precedes optimized preparation; candidate
verification precedes timing. The final `barrier:fast_verified` depends on all
fourteen diagnostic requests; its final verification action is
`verify-fast-timed`. No control receipt/barrier is involved. Scored timing scope
is `sampler-driver-accounting`; the four fills remain `unscored-fill`.

Storage remains finite: **50 raw capture requests, cap 50, 4 GiB write allowance
above a 50 GiB reserve**. The count includes twenty native, twenty-eight optimized
requests including their fills, and two setup captures. Charging all fifty at the
full four-tensor size costs 3,731,033,600 bytes before other outputs, below 4 GiB;
actual disk admission and cumulative-write enforcement remain mandatory. No
retry, extra fill or automatic extension is included. Preserve exact images,
video/audio latents and waveform comparisons; a passive accounting failure must
never silently weaken those gates.

The accounting contract is pending independent collector review and admission
in the separate `../20261007-driver-accounting106/` folder. This plan binds the
intended scope, not an unfinished collector hash: existing render-node proc
fdinfo only, raw CCS/BCS counters, two-second cadence, 120 seconds, 64 samples and
128 KiB maximum output. A future contract must bind the reviewed collector,
plan, server identity, PID/start ticks/boot, exact render/PCI mapping evidence and
bounded descriptor/task/read coverage. Deduplicate duplicate DRM clients, retain
separate clients and each engine's counters, mark incomplete coverage explicitly,
and preserve the prior busy watermark during transient counter regression.
No GPU instrumentation, device opens, signals, endpoint calls, UUID-layout
assumptions, aggregate utilization/idle estimates or performance headlines are
part of this diagnostic. Do not add the collector to an existing 105 run.

Both generated envelopes remain explicitly CPU-only and not runtime qualified.
Independent immutable-source closure, exact-count author-runtime integration,
source-bound accounting admission, fresh memory/disk checks, original ten-fixture
oracle proof and final quiescence/tail proof are pending. Successful execution
should preserve the application; faults halt requests, without retries or
restart chains. This short repeated workload is not cold-start, endurance,
general visual quality or public record evidence.

CPU validation: **18 plan tests and 13 schedule tests passed**. They compare all
corresponding numerical graphs with 105, preserve independent native graph
construction, test four-fill/ten-fixture mapping, reject coherently rehashed
geometry/policy/accounting-budget changes, missing tensors, candidate-as-oracle,
missing final barriers and extra control requests. Source hashes and exact
plan/schedule identities are in [cpu-validation.json](cpu-validation.json).
