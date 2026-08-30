# Qwen3.8 Flash-Next FP8 A16 late-prefill trace result

Date: 2026-08-30
Status: trace captured; battery failed closed at exact-4K repeat

A16 captured the planned rank-0 trace at positions 3968–4031. The artifact has
51 ordered boundary records and 149 exact tensor digests: positions, model
input, the delayed-hyperconnection tuple after each of 48 decoder layers, and
the final model outputs. The report-only path completed without a model fault.

The unchanged battery retained the established short output in all three rows,
passed the 16-repeat and 4K needle cases, and had only the inherited
`code_execution=30` semantic miss. Exact-4K row 1 matched retained authority;
row 2 did not. The two 128-token rows first differ at token 62 and differ in 66
positions. The client therefore returned 1 and the supervisor tore down the
server cleanly. No trace timing receives performance credit.

A16 alone cannot identify a differing layer because it has no fresh-start
peer. The next and only preregistered action is A17: identical head, trace,
request order, and selectors, with fresh run/cache/process paths. Compare all
149 digests in label order and report the first differing tensor. Do not
propose an arithmetic treatment before that comparison.

Structured receipt:
[`../data/20260830-tp4-mtp0-4352-ple-only-a16-late-prefill-trace.json`](../data/20260830-tp4-mtp0-4352-ple-only-a16-late-prefill-trace.json).
