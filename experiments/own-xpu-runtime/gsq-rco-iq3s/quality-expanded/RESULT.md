# Expanded exactness passes; task quality remains limited

Independent closed readback verifies all26 requests, all24 original128-token
prefixes, all12 complete target/MTP token-and-state pairs and all54 state bundles.
Both owners had positive physical GPU contact, exited and drained safely, with
unchanged fault baseline and protected vision. No weights, precision, fullBF16KV,
vocabulary, verifier or device allocation changed.

Root read every unique answer in full against the preregistered rubric, then
joined every reviewed output hash to the closed independent artifact index.
Eleven answers are incomplete at the fixed512-token cap. The customer-email
draft reaches EOS at316tokens and covers the requested structure, with factual
assumptions to verify before real use. Overall quality_qualified stays false.
This is an AI readback, not external human evaluation or an independent-model
oracle. No output was repaired, discarded or retried.

| Task | Output per mode | Ending | Full-text assessment |
|---|---:|---|---|
| incident-retrospective | 512 | cap | incomplete cap with unsupported details |
| code-review | 512 | cap | incomplete cap with technical cautions |
| customer-email | 316 | eos | complete draft with assumptions to verify |
| sql-debugging | 512 | cap | incomplete cap |
| release-plan | 512 | cap | incomplete cap with unverified project assumptions |
| benchmark-analysis | 512 | cap | incomplete cap with metric confusion |
| architecture-tradeoff | 512 | cap | incomplete cap with parallelism errors |
| bug-report-synthesis | 512 | cap | incomplete cap |
| technical-guide | 512 | cap | incomplete cap with unqualified repository conventions |
| risk-register | 512 | cap | incomplete cap with identity caution |
| performance-hypotheses | 512 | cap | incomplete cap with route reuse caution |
| decision-memo | 512 | cap | incomplete cap with fabricated decision evidence |

The [complete rubric record](evidence/manual-readback.json) preserves coverage
and cautions. These include invented incident/decision metrics, overly broad
database-retry advice, confusing prefill-cache savings with decode speed, and
incorrect limits on tensor-parallel batching. Missing sections and safeguards
remain missing; no favorable ungenerated continuation is assumed. These are
observations about the shared target output, not evidence that the optimization
changed it. The original128 prefix and all512 pair states are separate exactness
evidence. An independent same-weight reference remains under concrete source
investigation; older2084-token coverage belongs to binary973489, not this one.

## Retained timing, without performance promotion

Both modes emit5948 tokens across12 cases, giving5936 measured decode intervals.
Target-only uses318,933.904407ms, or18.612007 tokens/s; MTP uses235,474.974945ms,
or25.208624 tokens/s. These are descriptive longer-answer results, not a new
public benchmark or a comparison with the shorter28.14 screen. Prompt processing
totals21,434.329337ms target-only and22,902.582340ms MTP, measured separately.
No512-token-input prefill result is inferred from these short prompts.

MTP records4534 accepted and1402 rejected proposals, plus one unscored proposal
at EOS (5937 guesses). The terminal boundary is retained instead of inventing
an acceptance denominator. Warmups remain excluded; all caps and EOS stay in
the evidence. The one persistent owner pair ran14min15.094s including setup and
evidence work; that unit runtime is not decode throughput.

## Evidence and next work

- [Independent review](evidence/device-a/review.json):
  `c70ee06dc9f51e8f3e5506b73fba7b442217421d3e986096d23e3230ccd70ead`.
- [Artifact index](evidence/device-a/artifact-index.jsonl.gz):
  `44d9cd43bf4a36e7c6a7cb49e8856aa7f42bc89ef04059623a5c31aecce3b406`.
- Plan: `e95aba2d48f73b40ae4ef077cb8d2182da09e06bea61184697806c550a006169`.
- Full result: `662297ea420f085f6dc81aaa3b93875fff8cf4a94d6d4aaf94b7cc97d529175d`.
- Native binary: `5aef74d5f803b33758711db352ee5e1a393a364e6c33aa9f8a4cdb4478f5fe6a`.

The970 artifacts total6,438,697,690bytes. Raw root is
`/mnt/usb-models/own-xpu-runtime-results/gsq-quality-expanded-a`.
Admission retained all reserves and added384MiB initial cumulative-metadata
headroom; successful52-event capture accounting ends at zero remaining payload.

Continue exact acceleration using a current-binary cost diagnostic, while
resolving the concrete independent-reference gap. Preserve duplicate paired
evidence through verified canonical mappings before further device work.
Do not silently extend caps or relabel this failed completeness assessment.

The1,915,069-byte independent review JSON is retained in Git because it contains
all per-request token arrays, timing arithmetic, state checks and closure evidence.
The result summary, manual-readback join and future audits consume it. It is
unique structured evidence, restored by Git; do not discard it as a duplicate
of raw bundles or replace it with a summary.
