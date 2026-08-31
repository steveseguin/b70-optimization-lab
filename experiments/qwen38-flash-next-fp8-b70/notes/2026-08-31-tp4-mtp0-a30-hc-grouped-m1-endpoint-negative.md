# Qwen3.8 Flash-Next FP8 A30 grouped-HC endpoint result

Date: 2026-08-31
Status: bounded negative; no promotion

A30 completed one supervised TP4 full-model load on the fresh boot. The exact
hybrid stage, grouped-HC selector, and M1 eight-warp receipt were live. All 131
local-NVMe shards loaded in about 78 seconds, every rank reported the exact
11.92 GiB PLE-only placement, the endpoint became healthy, and the configured
cache exposed 4,747 tokens.

The short path retained the accepted quality boundary: recovery passed, six of
the seven inherited semantic cases passed with the same known code-case miss,
the long-context needle passed, all 16 repeats returned the protected digest,
and all three 256-token speed rows returned the protected short digest. Their
rates were `5.416309 / 5.415455 / 5.403828 tok/s`, median
`5.415455 tok/s`. That is 1.82% below the protected `5.515783 tok/s` median, so
the candidate fails the speed gate even before considering deeper-context
reliability.

The quality battery's 4K needle passed. Both exact-4K requests passed
transport and cache-zero gates at
`5.229220 / 5.044012 tok/s`, with TTFT `116.515 / 108.003 s`. Neither matched
the protected output authority. Row 1 returned `d3019c9c...` and first diverged
from authority at generated-token index 18. Row 2 returned `e82835cd...` and
first diverged at index 2; the two candidate rows also first differed at index
2. A30 therefore fails both exact-4K authority and same-boot repeatability.

The supervisor independently rejected postflight because the internal Samsung
NVMe logged two hardware-corrected physical-layer receive events while shards
were loading. There was no I/O error, controller reset, OOM, hung task, B70
fault, or GPU reset. Teardown was clean: no server/listener remained, all four
cards returned to about 43 MiB, host memory recovered, and swap was nearly
fully free. The corrected link events are not claimed as the cause of the model
result, but they violate A30's conservative evidence-acceptance gate.

This is a decisive endpoint negative. The large isolated grouped-HC component
win did not transfer to the full endpoint under this dispatch implementation;
the composite was slower and did not repair the already-known fresh-start 4K
variability. Do not spend two more full loads on the matched flag-off/flag-on
attribution sequence: the candidate failed the prerequisite speed and quality
gates. Keep the implementation default-off and preserve the qualified stage
for bounded source/mechanism work. Protected `5.515783 tok/s` MTP0 and
approximately `20.727 tok/s` MTP4 results remain unchanged.

Structured evidence and external artifact hashes are in
[`20260831-tp4-mtp0-a30-hc-grouped-m1-endpoint-negative.json`](../data/20260831-tp4-mtp0-a30-hc-grouped-m1-endpoint-negative.json).
