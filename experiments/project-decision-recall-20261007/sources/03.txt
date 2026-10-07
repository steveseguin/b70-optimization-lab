# Durable revision 4: cold primary trials correct; summary hits reasoning cap

The [prospective r4 plan](2026-10-07-durable-context-r4-plan.md) ran on a fresh
server with prefix caching explicitly disabled. The emitted launch flags were
verified before requests. Standing reference qualification passed 12/12, and both
fixed extraction diagnostics passed with zero reported cache reuse on every call.

The planned 12-trial development matrix ended with **five completed trials, one
failed trial and six not started**. The second summary trial generated 8192
reasoning tokens, reached the fixed output cap and returned no answer content.
The harness recorded the failure and stopped its server without continuation or
retry. The gate stayed closed; none of the held-out seeds was used.

| Seed 17 trial | Archive | Quoted | Summary |
| --- | ---: | ---: | ---: |
| Report | 24/24 | 24/24 | 24/24 |
| Dispatch | 24/24 | 24/24 | No submission; output cap |

Seed 29's six trials did not start. All four completed primary trials were exact
and independently verified uncached. Their 192 structured-table checkpoints were
exact. All 288 source batches in the six started stores were byte-exact. Quoted
was slower than archive in both completed pairs; the incomplete matrix provides
no qualifying speed signal or verdict. The two styles are representations of the
same seed's underlying events, not independent arithmetic streams.

The failed summary's final call reported 3615 input tokens, 8192 output tokens
(all reported as reasoning), zero cached tokens, `finish_reason=length`, and no
submitted answers. This is a measured bounded-model failure, not a transport or
GPU failure. Its partial reasoning and usage are preserved; no partial output is
presented as a successful answer. CPU validation passed 102 harness tests and 33
host-runner tests before the run.

## Next work

Keep r4 frozen and failed. Do not raise its cap or silently relabel the incomplete
matrix. A future evaluator should distinguish an expected bounded-model failure
from an infrastructure failure: a secondary method's failure should remain a
visible outcome without hiding other planned trials. Such a change needs a new
protocol and tests; it does not complete this run retrospectively.

The next useful reliability test is the separate
[semantic development packet](2026-10-07-context-semantic-development-plan.md):
short manually authored stress/control pairs for cancellations, corrections,
reversals, aliases, distracting numbers and time-specific ownership references.
Two separate assistant annotations agreed on all 84 answers and 48 batch states;
six alias quote-span differences are preserved and adjudicated separately from
semantic event meaning. This is development diagnosis, not external validation.
An adapter must honor explicit answer types and grade intermediate events/states
so a later reset cannot hide an earlier mistake.

After semantic diagnosis, larger sparse state tables are a more meaningful
performance lever than small tuning of an eight-counter task. Quoting adds output
cost here; no speed advantage is assumed. Retain zero-cache evidence and fresh
server replication requirements for any future performance claim.

## Evidence and cleanup

[Audited native evidence](../data/2026-10-07-durable-r4-result/audit.json) contains
all completed native results, failed-call evidence, raw-call hashes, cache checks,
partial campaign status, strict/extraction receipts and cleanup confirmation.
Full output: `/mnt/fast-ai/bench-results/context-durable-r4-20261007`.
GPU release was confirmed at **04:45:14 UTC**. No r4 server remains running.
The previous public 480K comparison now explicitly states its matching
cache-enabled profiles and one-task scope; its native 10/10 scores are unchanged.
