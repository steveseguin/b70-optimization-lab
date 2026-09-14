# How the dual-R9700 Qwen3.8 result reaches 894.9 tok/s

Reviewed September 14, 2026. **Community-reported; not reproduced on AMD or B70.**
The submitted record was created September 11. Read [STATUS.md](STATUS.md) for
provenance, review scope and recognition. The useful conclusion is an aggressive
batch-throughput demonstration with several transferable ideas, rather than an
895-token/s single-user, unchanged-FP8 result.

## What the public records say

[LocalMaxxing's API snapshot](reported/localmaxxing-leaderboard.json) contains ten
runs by the same contributor. Selected rows:

| Workload and mode | Concurrent requests | Reported output tok/s | Run ID |
| --- | ---: | ---: | --- |
| Filler, reasoning enabled, no speculation | 1 | 45.197 | cmtx6ay860ai3ps011oye4gtx |
| Filler, reasoning enabled, MTP | 1 | 73.738 | cmtx6mmco0ai9ps013oxxrj18 |
| Filler, reasoning enabled, DFlash2 | 1 | 102.623 | cmtx6wu6j0ailps01t0k36dhs |
| Code, thinking disabled, DFlash2 | 1 | 235.290 | cmtx76g6u0aixps018qt65nd4 |
| Code, thinking disabled, DFlash2 | 8 | 894.946 | cmtx76rb70aj0ps014d8a37v9 |

The last value is consistent with aggregate throughput: dividing by eight gives
111.868 tok/s per simultaneous stream as an accounting equivalent, not a measured
per-request latency distribution. The code c1 record reports 40 input/512 output
tokens; c8 reports368/4096. Thus 4096 appears to be eight 512-token responses
combined, and 368 appears to sum eight 46-token requests with the disclosed ID
suffixes. The actual benchmark client and per-request receipts are missing.
Do not describe this as 4096 output tokens per request or as a 32K-input test:
32768 is configured context capacity. The reported depth 0 does not mean no input.

The headline prefill value 2226.5 equals 368 / 0.16528 to reported precision. Other
rows similarly divide prompt counts by HTTP first-token wait. This supports
a TTFT-derived proxy interpretation, with aggregate prompt accounting at c8;
raw server prefill timers are absent. It is not directly comparable to the
lab's fixed 512-token, one-user server-prefill measurement. The 975.351 total
rate likewise numerically equals 894.946 × (4096 + 368) / 4096.

The site marks the record unverified/experimental: missing prompt hash, output
sample and raw engine timing, plus batch/concurrency 8 outside its single-user
verification rule. Draft acceptance counters and exact engine commit are absent.
The nearly identical code prompts, greedy decoding and disabled thinking favor
draft agreement and shared batch behavior. Prefix caching defaults on in the
reviewed Compose source, but the submitted command omits its override and has
no cache-hit receipts; no cache contribution is established.

## Implementation and actual precision

The observed 1.0.16 registry manifest resolves to digest
`sha256:83a9dc02a8f8e75aabe81366d36ebaa2e35fcbe181cacf8e8e0a4cef4ebccbcc`;
its OCI revision label points to
[`f295b9ef51ad413a68e4192371e0377741a354ce`](https://github.com/magiccodingman/vllm-radiance/tree/f295b9ef51ad413a68e4192371e0377741a354ce).
This pins the image inspected now; the submitted run itself reports only the
mutable tag and cannot prove its exact local image bytes.

- Packed group-32 MXFP4 target weights reduce weight traffic. Radiance's W4A8
  path quantizes activations to FP8 and uses hand-written RDNA4 FP8-WMMA
  kernels, instead of the checkpoint's generic W4A4 route. This is a different
  arithmetic/quality profile from our official FP8-weight/FP16-activation lane.
- WPERM stores weights in the order kernel fragments consume them. Decode-NT
  uses non-temporal loads. Separate small-row decode and larger prefill kernels,
  fused split-K reduction, merged GDN input projections and fused speculative
  state updates reduce data movement and launches.
- DFlash2 proposes seven tokens in a parallel draft pass; the target normally
  verifies the block. Local convolutions and a candidate selector make the
  proposed sequence coherent. This can preserve the target's output when target
  verification and state handling remain exact. Speculation alone is not proof
  of reduced quality.
- FAST_DRAFT further compresses eligible draft linears to W4 and uses an INT2
  vocabulary shortlist with original-weight reranking. Draft-only approximation
  is compatible with exact target verification; a weaker proposal mainly costs
  acceptance. Dynamic verification width reduces wasted work at higher loads.

Primary explanations: [MXFP4 implementation](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/docs/MXFP4_W4A8_R9700.md),
[RX3 mechanisms](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/docs/MXFP4_RX3_CONTINUATION.md),
[DFlash2 architecture](https://docs.vllm.ai/projects/speculators/en/latest/user_guide/algorithms/dflash2/).

## The stronger exactness concern

The [independent pinned-source audit](validation/radiance-1.0.16-source-audit.md)
retains OCI manifest/config receipts and source hashes.

The image/Compose defaults enable `RADIANCE_VERIFY_HEAD=1`. With fast drafting
active, eligible target-logit steps can reuse an INT2 coarse shortlist, rerank
64 candidates using original BF16 weights, and set every other target logit to
negative infinity. The greedy gate accepts this based on empirical candidate
recall; it has no full-vocabulary bound proving an excluded token cannot win.
Exact scores within a shortlist do not establish an exact global argmax. Some
request types fall back, but the submitted greedy workload is eligible. Missing
server logs prevent asserting which path actually fired in this run.

The source also defaults to rotated six-bit compressed all-reduce for eligible
large target messages, above a 128 KiB threshold. That changes target arithmetic,
not just draft quality. Actual use depends on shapes, availability and overrides.
These are mechanisms to isolate, not to silently port into our lossless default.

The exact source's README explicitly keeps DFlash experimental because strict
speculative/non-spec greedy equivalence has not passed. Its stable subset has
meaningful-output and tool-test evidence; those are different checks. The broader
RX5 bundle failed structured-tool tests and stays disabled. We have not proved
that this particular code response is wrong or that either shortcut caused the
reported cross-mode mismatches.

Sources: [target head](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_verifyhead.py),
[shortlist implementation](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_drafthead.py),
[collectives](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_allreduce.py),
[qualification boundary](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/README.md).

## Current transfer decision: retain FP8 and native MTP

The user now excludes DFlash. The [MTP-only follow-up review](validation/2026-09-14-mtp-fp8-transfer-review.md)
compares other Radiance mechanisms with the actual restored B70 source and
existing negative tests. It prepares a small inactive metadata cleanup and
retains exact native two-card communication as a larger design lead. No new
runtime optimization or speed gain is established. Convolution channel tiling
is a useful native-kernel reference, not an applicable Triton flag on this XPU
path. Existing lossless output, target precision and cache rules remain intact.

The [earlier transfer test](../../experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-results.md)
found exact-but-neutral projection dispatch and a combined newer-runtime/V2/
DFlash startup freeze before inference. The user rebooted; the original MTP
service was restored and verified. That attempt supplies no DFlash quality or
performance result. It is closed, and the MTP-only review supersedes the old
DFlash feasibility priority.

The runtime's broader [RX5 report](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/docs/MXFP4_RX5_FP8KV_CONTINUATION.md)
reports 183.1 weighted single-stream tok/s and 523.5 c8 aggregate on its broader
suite, with 5–6% gains from the narrow layout/load change. Those are contributor
measurements on different prompts and settings, not independent validation of
this run or a B70 forecast. Our [current FP8 package](../../packages/qwen38-27b-fp8-tp2-b70/README.md)
and [prefill profiling](../../experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md)
remain the local sources of truth.
