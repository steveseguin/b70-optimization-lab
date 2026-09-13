# Qwen 27B upstream correctness review — 2026-09-12

Follow-up: [deeper CPU and native B70 validation](VALIDATION.md) completed after
the initial report. The upstream prefill delta passes 22/22 same-base CPU cases;
the width candidate passes isolated FP16/BF16 native operator tests. Production
and full-model/graph qualification remain separate.

Afternoon follow-up: [runtime reproductions on stock images](runtime-repro/README.md), evidence posted on PR #53542 and #593. The width defect (#593)
reproduces end-to-end on stock v0.29.0 and today's nightly (any dynamic schedule reaching K=1 kills the server);
vLLM PR #53542's `gdn_attn.py` hunks alone fix it on unchanged kernels, so no kernels PR. The 08-25 mixed-batch
crash (#53928) is gone on v0.29.0. Phantom not reproduced on v0.29.0 compiled arms. Draft comments held in
`runtime-repro/drafts/`.

Initial review scope: historical evidence audit, current upstream source comparison, CPU
regressions, and public release availability. That initial review performed no GPU execution, model downloads,
runtime edits, service changes, or production promotion. The historical FP8
model path is absent on this four-card host. User authorized review and deciding
whether to publish upstream findings.

## Decisions

| Finding | Evidence | Decision |
| --- | --- | --- |
| Fresh one-token GDN prefill treated as decode | Current-source CPU routing reproduction; separate September 9 matched-image B70 evidence | Add evidence to existing vLLM issue #51562; support existing PR #51565. Do not submit a duplicate or promote our narrower patch. |
| Reduced active speculative width with maximum-capacity cache columns | Current-source compiled CPU host-contract reproducer | File a kernels issue. Candidate patch needs current XPU numerical/state-transition validation before promotion. |
| Historical anomalous first token | Stock September 3 output discrepancy; instrumented lab traces contradict the original insertion explanation | Correct and hold the old draft. Current reproduction and root cause remain unconfirmed. |

The [phase packet](phase/README.md) records three harmful fresh-request routing
cases, two other partition differences that are not additional bugs, and an
extra trailing-padding case that **fails with our local candidate**. PR
[51565](https://github.com/vllm-project/vllm/pull/51565) handles resumed state,
padding, and graph metadata more carefully. Today's CPU test is not GPU
validation of that PR. The contributor's multi-hour incident remains
`community-reported`; bounded historical local phase testing remains
`B70-tested` and does not prove that incident resolved.

The [width packet](width/README.md) confirms the current host assertion rejects
N=2, four active tokens, three cache columns; both native launch selectors also
choose the wrong active width for that contract. The candidate passes isolated
host checks, but does not prove per-request uniformity, current sliding
convolution-state correctness, or graph safety. No performance claim is made.

The [independent phantom audit](phantom/REVIEW.md) and
[corrected draft](../../../drafts/2026-09-03-vllm-issue-piecewise-mtp2-phantom.md)
retain the observation without the disproven claim that the sampler never
generated the token. R170 sampled token60 and R171 selected the correct logit
row. Another run selected token220. Scalar signatures and failure-suppressing
instrumentation do not establish complete tensor comparisons or a faulting layer.

## Downstream disposition

The historical R35 width fix is available in the public FP8 release and its
reproduction chain. This review downloaded the small release patch and matched
its SHA256 to the tracked source; see [receipt](downstream-release-check.json).
Existing INT4 source chains also include R35, but the current R293 recipe
manifest is still draft/pending publication. Do not equate a local image or
recipe manifest with a published release, or availability with user adoption.

The local one-token phase guard remains a candidate, not a promoted universal
fix. This review found its padding gap and recommends the broader upstream
approach after validation. The published R187 `splitting_ops=[]` configuration
is a scoped workaround for the historical first-token anomaly, not a root-cause
fix. No new candidate was deployed to users in this review.

## Provenance and verification

- Pinned vLLM: `22f6e4eccb674b534f62810c66838317169b6b98`.
- Pinned kernels: `efc85bc8a0eb3076c861b2e6cb1e1731a93905d5`.
- Retained upstream source headers and hashes identify third-party code.
  CPU harnesses, review, and candidate adaptation are lab follow-up with AI
  assistance. Existing upstream authors retain credit for #51562/#51565.
- The separate uniform-decode classifier contribution in upstream #53051/
  #53059 and dominick253's lab submission is not the phase or width fix.
- Primary review independently reran both CPU harnesses; phase output matched
  `phase/results.json`, including the candidate padding failure. System Python
  lacks torch; use the documented existing vllm-xpu Python for that test.
  Width compiles extracted real host blocks with shape stubs, not XPU kernels.
- Phase source hashes verified. Claims validator passed (11 claims); guide
  validator passed (38 guides). No recipe behavior changed.
- GitHub searches found no exact active-column-width report; related issues
  and limitations are recorded in the width packet. Search absence is bounded.

Prepared report bodies: [phase comment](phase/upstream-comment.md),
[width issue](width/upstream-issue.md). Published and read back successfully:

- [Evidence comment on vLLM #51562](https://github.com/vllm-project/vllm/issues/51562#issuecomment-5647033118), supporting the existing open PR #51565.
- [New kernels issue #593](https://github.com/vllm-project/vllm-xpu-kernels/issues/593), reporting the active-width contract failure.
- Exact transmitted bodies and immutable evidence commit are in
  `phase-comment-receipt.json` and `width-issue-receipt.json`.

No code PR was submitted: phase has an existing upstream proposal; width needs
current device/state validation before claiming a complete fix. The historical
phantom report remains held. Review decisions and authorized upstream reporting
are complete; outstanding GPU validation is explicitly outside this review's
execution evidence.

Diff whitespace checks report only blank context lines inside the two retained
unified patch files. Those leading context markers are required patch syntax;
source hashes and the width harness verify the preserved patches.
