# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-quark-int8-tp4-accepted-noasync-oraclelane-p512o128-20260611b.json`
- Candidate: `data/qwen36-quark-int8-tp4-oracle1-noasynclane-p512o128-20260611b.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `14`
- Requests: `2`
- Draft tokens: `14`
- Accepted: `14`
- Rejected: `0`
- Accept rate: `100.0`
- Full accept rows: `14`
- Full reject rows: `0`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `14`
- Accepted token: `29541` ` reliability`
- Candidate token: `4779` ` memory`
- Accepted window: `. Focus on single-request decode speed, reliability gates, hardware acceleration, and no quality`
- Candidate window: `. Focus on single-request decode speed, memory management, and no quality loss.

`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `14`
- Accepted token: `4752` ` unique`
- Candidate token: `6126` `PU`
- Accepted window: ` while measuring multi token verification. Intel X unique

<think>
Here's a thinking process`
- Candidate window: ` while measuring multi token verification. Intel XPU decode verifier bucket route graph token timing.`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
