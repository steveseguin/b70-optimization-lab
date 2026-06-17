# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-nospec-paired-freshgraph-20260615g4-completions.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle1-nomambaspec-paired-20260615g7-completions.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `4`
- Requests: `2`
- Draft tokens: `4`
- Accepted: `2`
- Rejected: `2`
- Accept rate: `50.0`
- Full accept rows: `2`
- Full reject rows: `2`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `3`
- Accepted token: `47193` ` numbered`
- Candidate token: `16` `1`
- Accepted window: `Continue with dense numbered engineering notes. Focus on single-request decode`
- Candidate window: `Continue with dense1. **Tensor Parallelism (TP)`
- Replay mapping: `mapped`
  - Request: `cmpl-b5993198d5c98610-0-a5eee754`
  - Trace row: `2`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[47193]`
  - Generated: `[16]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `3`
- Accepted token: `78503` ` Preserve`
- Candidate token: `220` ` `
- Accepted window: ` token timing. Preserve exact output while measuring multi token timing.`
- Candidate window: ` token timing. 

<think>
Here's a thinking process`
- Replay mapping: `mapped`
  - Request: `cmpl-9a26e7b6c9fd7504-0-8ef1c32a`
  - Trace row: `4`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[78503]`
  - Generated: `[220]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
