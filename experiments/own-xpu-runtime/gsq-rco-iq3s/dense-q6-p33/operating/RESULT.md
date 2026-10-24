# Nineteen-site Q6 extension: full exactness pass

All26 requests completed in one persistent pair. All24 measured arms across the
original12 prompts matched every token and full logical target-state byte against
the original baseline. Independent readback verified54 sealed bundles and946
artifacts (6,343,845,363 bytes), final repeated DUMP and post-close stamps. Both
physical contacts and clean owner/descriptor drain pass; fault/vision baseline
is unchanged. No retries, signals, model or precision changes occurred.

| Order group | Target-only tokens/s | MTP tokens/s |
| --- | ---: | ---: |
| All12 prompts | 16.169987 | 23.436774 |
| Target first,6 prompts | 16.168386 | 23.357786 |
| MTP first,6 prompts | 16.171588 | 23.516297 |

Each mode emitted1536 tokens; rates use1524 N−1 decode intervals, retaining all
samples. Decode wall totals are94,248.687ms target and65,026.015ms MTP. Prompt
wall sums are26,229.340ms and27,681.365ms, including the first output; they are
not a512-input prefill benchmark. MTP acceptance remains1160 hits/364 misses.
Two disjoint8-output warmups are excluded by the original fixed schedule.

These are cap128 resident-screen descriptions. The prior973489 binary measured
15.732355/23.303290 in a separate run. The MTP difference is small and does not
establish a meaningful causal improvement. Retain this as a qualified candidate
for current bottleneck diagnosis, not a new public record or broad quality claim.
The512-output/2084-input [coverage](../../coverage/RESULT.md) belongs to the prior
binary and is not silently transferred here.

Actual device allocations are30,994,676,618 and29,966,053,268 bytes, exactly the
forecast. The19 additional dense expansions cost188,743,680 bytes total:
47,185,920 on rank0 and141,557,760 on rank1. Full BF16 KV, context4096, full draft
vocabulary and unchanged target verification remain. Existing p33 variant6/Split1
arithmetic and39 compiled objects are reused; CPU selector proof passed309 checks.

[Actual review](evidence/device-a/review.json):
`8e9c69ae212a45f1bf2491dd25a75743b01a19395064d52b06d713497f686d14`.
[Artifact index](evidence/device-a/artifact-index.jsonl.gz):
`ac8a034fa32ed06b01d847c61e7a14184983631c8548d1f65878df20af034ad6`.
Binary `a0f9ffc58de704a276b237cbeec2b338ee873c0872bcae2da2214286aa5cce50`;
full result `f2bcf806d89c15689c7e12d8f917a7ad761e7c127c4a6484d8485f3482a15546`.
[Plan](evidence/device-a/plan.json):
`a173939f134f6b71e9f43f29e32dc77652a4c9a9b2332140234ab9d9e460e507`.
Coordinator elapsed459.492s; this includes loading, capture and teardown and is
not the reported decode timing denominator.

Next: reuse the same binary's class diagnostic on original prompt00, preserving
exact state/closure and separating total prompt, first-output and later-decode
event sums. Class counters remain whole-request totals. No additional build is
needed. Original evidence is retained. Four duplicate prompt00 bundles now use verified
[canonical restore mappings](../../storage/dense-prompt00-canonical/RESULT.md);
all other captures and sibling metadata remain at their original paths.
