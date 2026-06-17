# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-nospec-graph-current-ref-candidate-20260615graphref2nolog.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-graph-currentref-candidate-20260615currentreforacle1.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `30`
- Requests: `2`
- Draft tokens: `30`
- Accepted: `29`
- Rejected: `1`
- Accept rate: `96.66666666666667`
- Full accept rows: `29`
- Full reject rows: `1`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `40`
- Accepted token: `29541` ` reliability`
- Candidate token: `4779` ` memory`
- Accepted window: `. Focus on single-request decode speed, reliability gates, memory management, and no quality`
- Candidate window: `. Focus on single-request decode speed, memory management, and no quality loss.
`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000000-0-bdb80d9a`
  - Trace row: `20`
  - Position in row: `1`
  - Emission role: `verifier_bonus_after_full_accept`
  - Scheduled: `[11]`
  - Generated: `[11, 4779]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `19`
- Accepted token: `271` `

`
- Candidate token: `4618` ` graph`
- Accepted window: `. Intel XPU decode verifier bucket route

<think>

</think>

Intel XPU decode`
- Candidate window: `. Intel XPU decode verifier bucket route graph token timing. Preserve exact output while measuring`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-graph-currentref-20260615a-000001-0-b2c2291b`
  - Trace row: `30`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[271]`
  - Generated: `[4618]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
