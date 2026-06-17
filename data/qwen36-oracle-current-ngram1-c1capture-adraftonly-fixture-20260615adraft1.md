# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-oracle-accepted-current-20260615oraclefresh1.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle-ngram1-c1capture-adraftonly-20260615adraft1.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `112`
- Requests: `2`
- Draft tokens: `112`
- Accepted: `43`
- Rejected: `69`
- Accept rate: `38.392857142857146`
- Full accept rows: `43`
- Full reject rows: `69`

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
- Replay mapping: `trace_emitted_sequence_not_found_in_candidate`

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
- Replay mapping: `trace_emitted_sequence_not_found_in_candidate`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
