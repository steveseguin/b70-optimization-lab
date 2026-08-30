# Qwen3.8 Flash-Next FP8 TP4 MTP0 A12 score-path result

Date: 2026-08-30
Status: mechanism-positive diagnostic; no performance credit

A12 completed the corrected API-logprob retry on the unchanged A10 server
identity. All four byte-identical p4096/o128 requests passed exact usage,
cache-zero, length-stop, 128-token, and 128-decision gates. Across all 512
decisions, the selected token was the API-reported top-one token. This rules
out a post-selection sampler substitution as the reason identical greedy
requests produce different outputs.

The four returned token hashes were all different. Only row 3 matched the
retained authority. Rows 1 versus 2/3/4 first differed at generated token 7;
the other pairwise first differences were token 36 for rows 2-3 and token 11
for rows 2-4 and 3-4.

The stronger finding is that the score vectors already differ at generated
position 0, while all four rows still select token ID 763. Both the reported
top-eight ordering and logprob values vary across the four repeats. At token
7, row 1 reports an exact score tie between IDs 1 and 487 at
`-1.410357714` and selects ID 1. Rows 2-4 rank ID 487 above ID 1 by `0.375`,
`0.750`, and `0.625` logprob respectively and select ID 487. Output variation
therefore begins in the repeated forward/score path and is exposed by a
near-boundary greedy decision; the sampler is following the scores it receives.

This result does not prove PLE placement or QSA causality. A7 observed the same
exact-4K repeat failure under the older selective placement. The A12 server log
does show six QSA Triton kernels first compiling when the exact-4K diagnostic
begins: group compression, row storage, paged MQA, index expansion, sparse
paged GQA split-K, and split-K merge. That makes the long-context QSA route the
next bounded source locality to audit, not a concluded cause.

The diagnostic elapsed times were `219.47`, `148.45`, `135.26`, and
`131.89 s`. They receive no speed credit because requesting logprobs changes
instrumentation and the preregistration explicitly forbids it. A9 remains
Grade C, the protected short and exact-4K speeds remain unchanged, and no
reliable/lossless MTP0 base has yet been established.

The next GPU arm must be a separately frozen deterministic treatment of the
exact-4K attention/indexing route. It must first pass repeated byte-identical
output and retained-authority parity. Only after that may its ordinary no-logprob
short/4K speed be compared against protected floors.

Structured receipt:
[`../data/20260830-tp4-mtp0-4352-ple-only-a12-logprob-mechanism-positive.json`](../data/20260830-tp4-mtp0-4352-ple-only-a12-logprob-mechanism-positive.json).
