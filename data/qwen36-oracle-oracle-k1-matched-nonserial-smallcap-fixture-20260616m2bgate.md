# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-nospec-smallcap-micro-candidate-20260616micro1.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle-k1-matched-nonserial-candidate-20260616m2b.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `15`
- Requests: `2`
- Draft tokens: `15`
- Accepted: `14`
- Rejected: `1`
- Accept rate: `93.33333333333333`
- Full accept rows: `14`
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
Continue with dense`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-matched-nonserial-20260616m2b-000000-0-bc403edd`
  - Trace row: `9`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[11436]`
  - Generated: `[321]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `12`
- Accepted token: `15153` ` Intel`
- Candidate token: `271` `

`
- Accepted window: ` exact output while measuring multi token verification. Intel XPU decode verifier bucket route

<think>`
- Candidate window: ` exact output while measuring multi token verification.

<think>

</think>

Intel XPU decode`
- Replay mapping: `mapped`
  - Request: `cmpl-qwen36-oracle-k1-matched-nonserial-20260616m2b-000001-0-8d1a1a16`
  - Trace row: `15`
  - Position in row: `1`
  - Emission role: `verifier_bonus_after_full_accept`
  - Scheduled: `[13]`
  - Generated: `[13, 271]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
