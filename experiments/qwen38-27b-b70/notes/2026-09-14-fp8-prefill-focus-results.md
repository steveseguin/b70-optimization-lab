# Official 27B FP8: final prefill measurements and profiling

The preferred official Qwen3.8 27B FP8 model now has measured reading speeds
at 512 and 2,048 input tokens on two B70s, fixed MTP1, one user. The bounded
source review and profiler pass found no justified inexpensive optimization.
**Keep the serving defaults and close this prefill campaign.** No runtime patch,
new decode record or optimization speedup is promoted.

## Reading speed and first-token wait

| Input tokens | Server prefill | Reading speed | HTTP first-token wait |
| ---: | ---: | ---: | ---: |
| 512 | 179.21 ms | 2,856.96 input tokens/s | 182.18 ms |
| 2,048 | 556.64 ms | 3,679.25 input tokens/s | 567.90 ms |

Prefill measures how fast the model reads the prompt before producing its first
token. The longer prompt processes more tokens per second but takes longer to
finish. HTTP first-token wait includes additional serving/network time and is
recorded separately. Neither metric is isolated GPU kernel throughput.

These points use **4,096-token capacity and batch budget**, fixed MTP1 with a
full-vocabulary INT4 draft head, one active sequence, native FP16 KV, FP16
activations, no saved prompt cache and the unchanged public R304 image.
The [earlier 2,885-token/s homepage result](2026-09-13-short-prefill-results.md)
used a 1,024-token capacity/batch budget and different prompt material; it remains
unchanged. This new profile does not establish an improvement over that test.
The published higher-draft decode records also retain their original identities.

Each length has 18 measurements: three repetitions of prose, Python and setup
documentation in each of two control arms. Each arm takes a median within each
class, then the median across classes. The table averages the two arm aggregates.
The inputs are unrepeated contiguous excerpts truncated to exact numeric token
counts, with 128 forced output tokens. Warmups and profiling are excluded.
Maximum control drift was 0.02% at 512 and 0.70% at 2,048 tokens.

## Quality and decode

All 36 measured requests were cache-zero and their complete output token arrays
repeated exactly across both control arms. The separate full 12-prompt realistic
suite used natural stopping with a 512-token cap; all objective canaries passed
and all 12 complete outputs matched the qualified R304 reference.

Strict class-balanced decode was **54.747 tokens/s**, versus the historical
reference's **54.818 tokens/s** (−0.13%). This is a support check with no meaningful
regression observed, not a matched optimization comparison. One continuously
loaded server was used; no independent-process speed confirmation is claimed.

## What profiling showed

One diagnostic 512-input/one-output request matched the unprofiled first token.
The profiler was stopped before the final timing controls. Summed device times
below include profiler overhead; ranks overlap and collective durations include
waiting, so these are not request latency or additive potential savings.

| Traced device work | Rank 0 | Rank 1 |
| --- | ---: | ---: |
| FP8-weight/FP16-activation matrix operations | 106.970 ms | 111.861 ms |
| GDN, directly attributed | 21.751 ms | 22.848 ms |
| Allreduce | 27.222 ms | 20.498 ms |
| FP16 rowchunk plus descendants | 3.784 ms | 3.776 ms |

The FP8 matrix operations account for 61–64% of each rank's summed kernel time.
Their largest shape is `[512,5120] × [5120,17408]`, called 65 times per rank.
The small FP16 rowchunk path accounts for only about 2.15%; the earlier 4B
profiling lead does not justify applying its optimization direction here.

The source audit checked the actual R304 installed `scaled_mm/xpu.py` route and
matching `csrc/xpu/onednn/fp8_gemm_w8a16.h` source. Activation quantization is
already skipped for this path, scales are prepared once, weight transposes are
views, and oneDNN primitives are cached. There is no newly discovered repeated
weight copy or uncached primitive setup to remove.

The earlier direct-output allocation screen was neutral on FP8 and was not
rerun. Scratchpad rings, descriptor and geometry variants have closed negative
records in the [do-not-repeat index](../DO-NOT-REPEAT.md). CLASSPAD and larger
batched GEMMs require new arithmetic qualification. A competitive kernel change
would be substantial work beyond this final bounded pass. No candidate was
implemented or benchmarked, and no reliable quick win is claimed.

The fixed-K W8A16 hook covers 1–512 scheduled rows. Larger calls use the natural
oneDNN catalog; the 2,048-input point is not described as an all-fixed-K path.
This trace covers 512 inputs only and does not profile or extrapolate the longer
point's operator breakdown.

## Evidence and reproduction

- [Preregistration and exact run command](2026-09-14-fp8-prefill-focus-prereg.md)
- [Measured summary and setup identity](../data/2026-09-14-fp8-prefill-focus/summary.json)
- [Original receipts and trace archive manifest](../data/2026-09-14-fp8-prefill-focus/evidence/manifest.json)
- [Offline replay receipt](../data/2026-09-14-fp8-prefill-focus/verification.json)
- [Trace analysis, shapes, methodology and source hashes](../data/2026-09-14-fp8-prefill-trace-analysis.json)
- [FP8 setup guide](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)

The packet preserves raw requests, numeric inputs/outputs, SSE timings, metric
histograms, complete reference outputs, model/runtime contracts, logs and
original compressed worker traces. Recompute the aggregates, output parity and
trace attribution offline, checking all archive/member/source hashes:

```bash
python3 experiments/qwen38-27b-b70/scripts/verify-fp8-prefill-evidence.py
```

The [collector](../scripts/summarize-fp8-prefill-focus.py),
[trace analyzer](../scripts/analyze-fp8-prefill-trace.py),
[single-stage controller](../scripts/run-fp8-prefill-focus.py) and
[corpus](../data/2026-09-14-fp8-prefill-corpus.json) preserve this measurement
without modifying the earlier frozen campaigns.

All GPU work is complete. The owned server is stopped; both-card compute/XCCL
and journal postflights passed. No power, swap, page-cache, reset, reboot or
restart-chain changes. Other model and draft settings are deliberately deferred.
LocalMaxxing disposition: withheld; these prefill points and profiling evidence
are not a new qualified decode submission.

The existing hash-pin audit still finds 231 historical Flash-Next references
that drifted across two unrelated verifier files, with no missing targets. They
were preserved. This packet's own source, archive and raw-replay checks pass.

## Publication validation

Offline raw/trace replay, profile extraction, package/catalog and recipe checks,
renderer and guide tests, repository links and manifest paths pass. Desktop and
mobile inspection covered the preserved homepage value, separate capacity
labels, graph/tooltips, exact values, evidence links and copy control; reading
also works without JavaScript. [Browser receipt](../data/2026-09-14-fp8-prefill-focus/browser-check.json).
