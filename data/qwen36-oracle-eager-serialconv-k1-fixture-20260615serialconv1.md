# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-eager-serialconv-candidate-20260615serialconv1.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `6`
- Requests: `2`
- Draft tokens: `6`
- Accepted: `4`
- Rejected: `2`
- Accept rate: `66.66666666666667`
- Full accept rows: `4`
- Full reject rows: `2`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `7`
- Accepted token: `24985` ` Focus`
- Candidate token: `271` `

`
- Accepted window: `Continue with dense numbered engineering notes. Focus on single-request decode speed, reliability gates`
- Candidate window: `Continue with dense numbered engineering notes.

<think>
Thinking Process:

1.`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-eager-serialconv-20260615a-000000-0-b2490ce8`
  - Trace row: `4`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[24985]`
  - Generated: `[271]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `3`
- Accepted token: `78503` ` Preserve`
- Candidate token: `271` `

`
- Accepted window: ` token timing. Preserve exact output while measuring multi token verification.`
- Candidate window: ` token timing.

<think>

</think>

Intel XPU decode`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-eager-serialconv-20260615a-000001-0-9e990a57`
  - Trace row: `6`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[78503]`
  - Generated: `[271]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
