# Current-upstream quality rejection — October 7, 2026

Packet 99 started successfully, passed encoder/capture/decode consistency and
memory checks, then failed accepted-reference parity on both initial self-check
clips. The runner skipped probe/timed arms, proved quiescence and sent one SIGINT;
PID 3123108 was gone at 13:34:41 UTC. All four cards passed postflight with zero
kernel GPU fault lines. No host reset or setting change occurred.

Manifest `e7b268d2e54e9010e88e325681a5d7af43052d7affdf803ca9b6c7ee54ed8736`
remains preserved at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99`.
The run used current source `b00c6e95279053474955540ba4f551646722b9aa`, the
reviewed accepted overlay, explicit file limits, progress-lock cleanup and the
isolated current application dependency closure. This candidate is **not adopted**
and has no timed throughput result. All failed raw clips and receipts remain.

[Closeout and exact comparisons](../data/resume-20261007/closeout-99.json),
[runner summary](../data/upstream-99/two-way-w2-b1-p1-dxpu2-s256x256/summary.json),
[postflight](../data/resume-20261007/postflight-99.json).
The local selfcheck.json reports clean resource/state invariants; it does not
report reference quality. The arm's failed parity correctly overrides it.

## First observed divergence

Both boat and marble differ in all four output tensors, with matching shapes and
dtypes. Boat maximum absolute differences: video latent5.5605, audio latent0.2287,
images0.7168, waveform0.00189. These are quality-gate failures, not a tolerable
speed tradeoff. The magnitude does not identify the first cause.

Independent request audit found the same text, seeds, sigma schedule, CFG1,
initial latent hashes and pipeline ancestry as the accepted control. Actual
normalized request graphs and source pipeline helpers match. Beware comparing
reference request payloads without following pipeline ancestry: the request
that emits a boat clip can itself carry a later fixture's input.

The saved boat sampler receipt already has a different conditioning fingerprint
and connector context before diffusion: accepted conditioning ca4e9178… vs
4525b1eb…, context b318cf6b… vs1032e454…. Initial video/audio latent hashes and
seeds42/42 match. All six encoder handoffs have unchanged text hashes, real-token
counts and window64 but different conditioning fingerprints. This narrows the
first observed failure to encoder/conditioning, not decoder or emission routing.

## Concrete compatibility lead and next test

Gemma4's active encoder forward calls comfy-kitchen's split-half positional
encoding helper. The dependency upgrade0.2.33→0.2.37 changed its eager
`apply_rope_split_half1`: separate products followed by addition became a product
followed by in-place `addcmul_`. That can change rounding. The actual XPU path
has no CUDA backend and Triton is disabled by default. Gemma4 forward itself,
RMSNorm and relevant cast functions are unchanged. This is a strong causal
candidate, still requiring a controlled full-clip test.

Prepare a new immutable packet99b that retains all current source/dependency
bytes and installs only a source-bound process-local compatibility function.
Preserve the original separate-operation arithmetic. CPU tests must demonstrate
the numerical distinction and exact recovery, check routing/loaded code identity
and reject unsupported/repeated installation. Then run one separately registered
23/25 control against w93c with the same failure gates. Do not silently downgrade
the entire dependency or overwrite failed99.

The planned20/28 packet100 CPU preparation is retained but cannot build/launch
from failed99. It must be rebound to a qualified current-upstream control before
use. The [batch arithmetic audit](2026-10-07-exact-batch-arithmetic-review.md)
remains a later hypothesis, not the response to this failure.

Lesson: source/API compatibility and matching package versions do not establish
numerical compatibility. Audit actually-used dependency operators when porting;
the exact-output gate is mandatory even when graph replay is internally exact.
The original accepted runtime and references remain available unchanged.
