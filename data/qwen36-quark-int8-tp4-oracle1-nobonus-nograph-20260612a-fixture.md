# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json`
- Candidate: `data/qwen36-quark-int8-tp4-oracle1-nobonus-nograph-20260612a-completions.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `16`
- Requests: `2`
- Draft tokens: `16`
- Accepted: `7`
- Rejected: `9`
- Accept rate: `43.75`
- Full accept rows: `7`
- Full reject rows: `9`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `9`
- Accepted token: `3074` `None`
- Candidate token: `383` `None`
- Accepted window: `None`
- Candidate window: `None`
- Replay mapping: `mapped`
  - Request: `cmpl-90583939dcf68be9-0-8b7d15a2`
  - Trace row: `9`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[3074]`
  - Generated: `[383]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `7`
- Accepted token: `28043` `None`
- Candidate token: `1345` `None`
- Accepted window: `None`
- Candidate window: `None`
- Replay mapping: `mapped`
  - Request: `cmpl-bcef8a4a7367bcb8-0-84e2b9a7`
  - Trace row: `16`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[28043]`
  - Generated: `[1345]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
