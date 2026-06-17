# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-nospec-paired-freshgraph-20260615g4-completions.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-eager-paired-20260615g11-completions.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `16`
- Requests: `2`
- Draft tokens: `16`
- Accepted: `13`
- Rejected: `3`
- Accept rate: `81.25`
- Full accept rows: `13`
- Full reject rows: `3`

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
  - Request: `cmpl-b778328a79aacaf2-0-bc09d75b`
  - Trace row: `3`
  - Position in row: `1`
  - Emission role: `verifier_bonus_after_full_accept`
  - Scheduled: `[13]`
  - Generated: `[13, 271]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `3`
- Accepted token: `78503` ` Preserve`
- Candidate token: `271` `

`
- Accepted window: ` token timing. Preserve exact output while measuring multi token timing.`
- Candidate window: ` token timing.

<think>

</think>

Intel XPU decode`
- Replay mapping: `trace_emitted_sequence_not_found_in_candidate`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
