# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-eager-serialrecur-candidate-20260615serialrecur1.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `16`
- Requests: `2`
- Draft tokens: `16`
- Accepted: `15`
- Rejected: `1`
- Accept rate: `93.75`
- Full accept rows: `15`
- Full reject rows: `1`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `17`
- Accepted token: `11436` ` hardware`
- Candidate token: `321` ` and`
- Accepted window: ` single-request decode speed, reliability gates, hardware acceleration, and no quality loss.
`
- Candidate window: ` single-request decode speed, reliability gates, and no quality loss.

<think>
Thinking`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-eager-serialrecur-20260615a-000000-0-9fe1d289`
  - Trace row: `9`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[11436]`
  - Generated: `[321]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `14`
- Accepted token: `4752` ` unique`
- Candidate token: `6126` `PU`
- Accepted window: ` while measuring multi token verification. Intel X unique

<think>
Here's a thinking process`
- Candidate window: ` while measuring multi token verification. Intel XPU decode verifier bucket route graph token timing.`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-eager-serialrecur-20260615a-000001-0-addc295d`
  - Trace row: `16`
  - Position in row: `1`
  - Emission role: `verifier_bonus_after_full_accept`
  - Scheduled: `[1543]`
  - Generated: `[1543, 6126]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
