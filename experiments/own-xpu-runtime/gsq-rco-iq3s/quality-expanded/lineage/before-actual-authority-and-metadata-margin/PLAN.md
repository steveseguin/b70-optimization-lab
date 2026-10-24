# Expanded correctness and task readback

Planned after the dense packed block engine passes its original 24-arm gate.
No inference has run for this plan. Bind the actual successful binary and review
before preparing an operational launch.

Use all twelve original fixed realistic prompts, unchanged in text, token IDs
and order. Raise the actual RPC response cap from 128 to 512, retaining the
qualified native startup bound of 128. Each prompt gets target-only and MTP
with full RESET, alternating the original six orders each way. Reuse the two
disjoint excluded eight-token warmups. All measured first 128 tokens must match
the original SC117 baseline; all complete target/MTP outputs and final target
state must match exactly. Early EOS stays in the results. No prompt tuning,
output repair, discarded cases, precision change or verifier change is allowed.

This is 26 requests and 27 capture groups, so the raw capture forecast stays
6,248,947,500 bytes until exact arithmetic is bound in preparation.
Full BF16 KV and context 4096 are unchanged. Source preparation must use the
reviewed acknowledged-capture accounting correction, with unchanged root and
external reserves. Closed prior captures may be mapped to independently
verified existing canonical archives before this run; no archival during
measured inference.

Retain decoded full output and all per-token timestamps for every arm. Read all
twelve unique answers in full against the original request and the
[preregistered rubrics](rubrics.json), recording task
coverage, contradictions, malformed structures, natural EOS and truncation.
A capped incomplete answer is not a complete-task pass. Record prompt reading
time separately from decode, with its exact timing definition. This remains
a correctness/coverage screen: repeated cross-mode prompts and same-target
equality do not establish an independent model oracle or a public performance
claim. Do not transfer the older binary's 2084-token factual-retrieval result
to this binary. That case needs separately bound coverage.

After this screen, choose the next lossless acceleration from measured costs.
The strongest remaining candidates include exact packed expert arithmetic,
MTP rejection/rollback work, and prompt processing. Avoid small launch-only
fusions whose theoretical ceiling cannot justify their implementation cost.
