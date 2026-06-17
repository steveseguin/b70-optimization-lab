# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-nospec-logprobs-eager-20260615g16b-completions.json`
- Candidate: `data/qwen36-oracle1-logprobs-eager-20260615g17-completions.json`
- Exact match all: `False`
- Mismatches: `1` / `2`

## Scheduler Summary

- Rows: `31`
- Requests: `2`
- Draft tokens: `31`
- Accepted: `31`
- Rejected: `0`
- Accept rate: `100.0`
- Full accept rows: `31`
- Full reject rows: `0`

## Case Diffs

### natural_latency_plan

- Status: `match`
- First diff: none

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `30`
- Accepted token: `17856` ` timing`
- Candidate token: `22188` ` verification`
- Accepted window: `. Preserve exact output while measuring multi token timing.`
- Candidate window: `. Preserve exact output while measuring multi token verification.`
- Replay mapping: `mapped`
  - Request: `cmpl-a5dd1236f8cd7ebd-0-ad3b7bd3`
  - Trace row: `31`
  - Position in row: `1`
  - Emission role: `verifier_bonus_after_full_accept`
  - Scheduled: `[3817]`
  - Generated: `[3817, 22188]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
