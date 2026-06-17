# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-nospec-smallcap-micro-candidate-20260616micro1.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-serialfixed-smallcap-candidate-20260616fix1.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `32`
- Requests: `2`
- Draft tokens: `32`
- Accepted: `30`
- Rejected: `2`
- Accept rate: `93.75`
- Full accept rows: `30`
- Full reject rows: `2`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `17`
- Accepted token: `11436` ` hardware`
- Candidate token: `321` ` and`
- Accepted window: ` single-request decode speed, reliability gates, hardware acceleration, and no quality loss.

`
- Candidate window: ` single-request decode speed, reliability gates, and no quality loss.
Continue with dense`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000000-0-b4ffb650`
  - Trace row: `8`
  - Position in row: `1`
  - Emission role: `verifier_bonus_after_full_accept`
  - Scheduled: `[11]`
  - Generated: `[11, 321]`

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
  - Request: `cmpl-qwen36-oracle-k1-serialfixed-smallcap-20260616fix1-000001-0-9f62fab5`
  - Trace row: `26`
  - Position in row: `0`
  - Emission role: `accepted_draft`
  - Scheduled: `[4618]`
  - Generated: `[4618, 3817]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
