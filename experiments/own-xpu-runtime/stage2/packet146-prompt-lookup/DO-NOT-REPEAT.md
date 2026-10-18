# Packet146 — do not repeat

| Date | Closed arm | Evidence and reason | Revisit condition |
| --- | --- | --- | --- |
| 2026-10-18 | Within-request prompt/generated-token suffix lookup (lengths 2–6) as a second exact speculative guess or MTP arbiter for a headline | [Policy analysis and closeout](ANALYSIS.md): AGENTS.md and LocalMaxxing rules disable n-gram/history acceleration. Narrower repeated-history wording and `freshResponseNgramValidated` do not expressly authorize request-local lookup. The brief requires stopping on ambiguity; no acceptance study, design or runtime work was done. | Explicit policy revision or owner ruling resolving this exact request-local case, followed by independent held-out acceptance of at least +1.5 points and the usual quality/performance gates. Do not work around the rule with labels, boolean flags or `--allow-non-headline`. |

This closes the policy-gated arm, not the optimization lane. Acceptance and
speed remain unmeasured; no failed performance result is implied.
