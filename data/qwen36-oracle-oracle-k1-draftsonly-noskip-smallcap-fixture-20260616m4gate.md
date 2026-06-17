# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-nospec-smallcap-micro-candidate-20260616micro1.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-draftsonly-noskip-candidate-20260616m4.json`
- Exact match all: `True`
- Mismatches: `0` / `2`

## Scheduler Summary

- Rows: `32`
- Requests: `2`
- Draft tokens: `32`
- Accepted: `32`
- Rejected: `0`
- Accept rate: `100.0`
- Full accept rows: `32`
- Full reject rows: `0`

## Case Diffs

### natural_latency_plan

- Status: `match`
- First diff: none

### repetitive_kernel_notes

- Status: `match`
- First diff: none

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
