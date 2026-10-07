# Lossless 640×384 follow-up choices — October 7, 2026

Status: source-only hypotheses after packet 101's bounded qualification attempt.
No 101 outcome, new throughput improvement or W2 quality result is assumed here.
No code, runtime, model, endpoint or device change was made for this review.

Keep the current B1/BF16 arithmetic, 25 frames, original 8+3 steps, accepted window
encoder and all-four-tensor same-size reference requirement. The marginal small
shape 20/28 result and closed W3 screen do not justify another layout sweep.
B2/B4 outputs remain outside the unchanged-output requirement.

## 1. Overlap two B1 sampler jobs at the useful resolution

If 101 establishes exact 640×384 native/candidate outputs, consider one separately
admitted W2/B1 comparison against its W1 control. One W1 sampler job traverses
both 23/25-card segments serially; a second independent clip could overlap the
segments without batching arithmetic or combining conditioning. The existing
worker-specific pipeline path (`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/scripts/pipeline_sampler_node.py:933`)
and per-worker chain check (`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/scripts/ltx_graph_capture.py:631`)
already provide mechanisms and exact eager/replay/repeat checks. Their earlier
small-shape qualification is not qualification of this new geometry/worker arm.

The sampler-only ideal ceiling is below 2× the W1 throughput; actual gains may be
much smaller from memory bandwidth, shared-pool behavior, decode service and
host delivery. Additional per-worker graph memory needs fresh measured admission,
not a renamed 101 manifest or an inherited 256² pool estimate. A successor would
also need its own fixed graph depths, fill accounting, worker coverage and
same-size reference comparisons. The current 101 W1 gates deliberately reject W2.

**Decision after 101:** use actual emitted sampler service/phase receipts versus
completed-clip intervals and decoder wait/service times. Prefer this screen only
if sampling remains the limiting service and measured memory leaves the required
reserve for a second worker's graphs. Do not infer a card-occupancy measurement
from the old decoder-only cost estimate, or add speculative instrumentation to
the current live run.

## 2. Remove duplicate host copies in output delivery

The normal VAE output device is CPU unless `gpu_only` is selected
(device policy (`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/comfy/model_management.py:1267`)).
In the nonchunked B1 replica path, a freshly copied decoder output is copied again
into `pixel_samples`
(replica wrapper (`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/scripts/ltx_decode_replica.py:330`)).
The preview queue then makes a private CPU copy
(submit (`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/scripts/pipeline_decode_node.py:175`));
raw capture separately makes contiguous tensors, allocates bytes for hashing,
scans statistics and writes safetensors ([capture implementation](../scripts/capture_node.py#L44)).

A 640×384×25 F32 image tensor alone is 73,728,000 bytes. A narrow ownership design
could avoid the extra nonchunked B1 destination copy when an already-owned output
has exactly the required contiguous layout, then share one immutable per-clip CPU
snapshot between preview and raw evidence consumers. Keep the existing numeric
operations, full hashes/finite checks and raw output comparisons. Preserve object
lifetime until both consumers finish; refuse unsupported layouts or mutation,
rather than trading the current isolation for unsafe aliases. This is proposed
per-output ownership, not reuse of generated outputs across clips.

**Decision after 101:** inspect preview `enqueue_s`, writer `queued_s/save_s`,
node 414 time from request events, and gaps between decoder completion and emitting
request success. `enqueue_s` starts after the private CPU copies, so it measures
queue insertion, not copying; those existing receipts cannot isolate copy cost. Pursue only if those observed host costs materially delay clip
completion or backpressure decoding. The upper bound is the affected measured
copy/scan/serialization time; this cannot remove the decoder's 1.66-second eager
video computation from the historical probe. If the handoff cost is small,
close the idea rather than build a general caching framework.

## Evidence to use after the run closes

The fixed server run is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-resolution-reference-101-two-way-w1-b1-p1-dxpu2-s640x384`.
Read only its completed, archived outcome before selecting a follow-up:

- Verified native/candidate/timed receipts, exact server/source identities,
  health/fault outcome and refusal reasons. A failure leaves no qualified speed
  baseline; diagnose it before interpreting service times as an optimization win.
- `pipeline-sampler-NAME.json`: emitted index, `emitted_phases`, per-request
  timing and any wait evidence. Do not confuse prompt-thread enqueue time with
  full background sampler service.
- `pipeline-decode-NAME.json`: emitted `decode_split.wait_s`, `vae_s`,
  `enqueue_s` and preview-writer records; plus sample/decode/save done markers.
  Completed but un-emitted tail work must stay separate from scored clips.
- Request events and `same-size-timed.json`: nine completion intervals for ten
  emitted clips cycling three fixtures. That is preliminary three-fixture
  coverage, not ten unique scenes or an endurance result. Report generated
  frames per wall second separately from 24 fps playback.

No third low-level bet is justified by this source review. In particular, do not
reopen the retired decoder graph-capture/host-table-cache path, generic QKV fusion,
or context-transfer machinery without evidence of material transfer cost.
The [dated cost-note clarification](2026-10-06-resolution-cost-probe.md#implementation-clarification--october-7-2026)
separates the measured decoder cost from the inaccurate earlier claim that decoder
graph capture was already enabled.
