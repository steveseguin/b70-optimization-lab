# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-nospec-paired-freshgraph-20260615g4-completions.json`
- Candidate: `data/qwen36-oracle1-paired-freshgraph-20260615g5-completions.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `14`
- Requests: `2`
- Draft tokens: `14`
- Accepted: `13`
- Rejected: `1`
- Accept rate: `92.85714285714286`
- Full accept rows: `13`
- Full reject rows: `1`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `17`
- Accepted token: `321` ` and`
- Candidate token: `4779` ` memory`
- Accepted window: ` single-request decode speed, reliability gates, and no quality loss.
Continue with dense`
- Candidate window: ` single-request decode speed, reliability gates, memory management, and no quality loss.
`
- Replay mapping: `mapped`
  - Request: `cmpl-b96876a2f0994db7-0-a6a5a8f1`
  - Trace row: `9`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[321]`
  - Generated: `[4779]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `10`
- Accepted token: `17856` ` timing`
- Candidate token: `22188` ` verification`
- Accepted window: `. Preserve exact output while measuring multi token timing. Preserve exact output while measuring multi token`
- Candidate window: `. Preserve exact output while measuring multi token verification.

<think>

</think>

Intel X`
- Replay mapping: `mapped`
  - Request: `cmpl-9fe9fa7abd170bce-0-93fc9484`
  - Trace row: `14`
  - Position in row: `1`
  - Emission role: `verifier_bonus_after_full_accept`
  - Scheduled: `[3817]`
  - Generated: `[3817, 22188]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
