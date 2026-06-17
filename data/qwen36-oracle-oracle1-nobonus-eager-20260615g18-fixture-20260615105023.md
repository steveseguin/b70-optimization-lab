# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-nospec-logprobs-eager-20260615g16b-completions.json`
- Candidate: `data/qwen36-oracle1-nobonus-eager-20260615g18-completions.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `22`
- Requests: `2`
- Draft tokens: `22`
- Accepted: `22`
- Rejected: `0`
- Accept rate: `100.0`
- Full accept rows: `22`
- Full reject rows: `0`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `14`
- Accepted token: `29541` ` reliability`
- Candidate token: `4779` ` memory`
- Accepted window: `. Focus on single-request decode speed, reliability gates, Arc Pro B70 hardware`
- Candidate window: `. Focus on single-request decode speed, memory management, and no quality loss.
`
- Replay mapping: `trace_emitted_sequence_not_found_in_candidate`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `30`
- Accepted token: `17856` ` timing`
- Candidate token: `22188` ` verification`
- Accepted window: `. Preserve exact output while measuring multi token timing.`
- Candidate window: `. Preserve exact output while measuring multi token verification.`
- Replay mapping: `trace_emitted_sequence_not_found_in_candidate`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
