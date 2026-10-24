# Current Q6 class diagnostic: exact pass

The corrected run passes independent readback: two requests (one excluded8-output
warmup and originalprompt00target128), six sealed bundles and all original measured
tokens/state. Both physical contacts, safe closure, unchanged fault/vision baseline
and final storage stage5 pass. Every acknowledged write remains in the budget;
all reserves are unchanged. Failed class-a remains [failed](../FAILURE.md).

Whole-request kernel event time sums to **12,582.182396ms** across214 consumed
positions. These are sums of device events, not wall-clock throughput or a cold
benchmark. Class counters include prompt processing and decode; they cannot be
split by phase from these aggregate reports. Draft is allocated but unused.

| Class | Device event sum (ms) |
| --- | ---: |
| gdn.qkv | 1,320.441 |
| expsdown | 1,094.233 |
| gdn.z | 984.660 |
| expsgate | 938.435 |
| expsup | 925.481 |
| route | 700.988 |
| qsa.qgate | 639.101 |
| attention | 418.763 |
| gdn.recurrence | 378.442 |
| hc.f.low | 369.670 |

Independent half traces contain all214 positions on each rank:86 prompt-only,
one first-output/final-prompt position and127 later-decode positions. Separate
total event sums follow; no per-class phase attribution is inferred.

| Rank | Prompt-only (ms) | First output (ms) | Later decode (ms) | Class-minus-half residual (ms) |
| --- | ---: | ---: | ---: | ---: |
| 0 | 2479.726856 | 28.818021 | 3686.814322 | -0.000263000 |
| 1 | 2468.283489 | 30.441575 | 3888.097914 | 0.000482000 |

The measured class/group launch counts match the earlier class diagnostic.
Signed residuals are retained rather than forced to zero. No synchronized
cross-rank clock or host-wall-time claim is made from these sums.

The leading unchanged work includes QKV, expert down, other dense projections,
HC projections and routing. HC low+inject classes total1,448.613ms; route totals
700.988ms. The next discriminator tests one-subgroup workgroups for the192 BF16 HC
low/inject sites with unchanged arithmetic. Integer-only route rank pruning
remains a source appraisal; neither candidate has native speed evidence.

[Actual review](evidence/device-b/review.json):
`30ed538b78040d04367fe7e99956c8ff2e483cef99194de1445f1476226bd039`.
[Artifact index](evidence/device-b/artifact-index.jsonl.gz):
`9714593b8f7c65c66fa6beed26edc831782b83225e05de2e2611896e39898236`.
169 indexed artifacts total716,920,246 bytes, including665,229,504 target payload
bytes in six bundles. Full result:
`f599b9fe82b83d859baacf65ddaf7c1ad1f274e8793e2cf87e0b74770d85d149`.
[Plan](evidence/device-b/plan.json):
`a0a274f5997ac0db2671c49cb47b9f8240c3f8930eb49bde3810e734b225aef7`.
Binarya0f9 and qualified Q6 review8e9c remain unchanged. Coordinator elapsed
114.733seconds includes loading/capture/closure, not just model event time.
