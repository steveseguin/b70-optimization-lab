# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json`
- Candidate: `data/qwen36-quark-int8-tp4-oracle1-workertrace-completions-20260611a.json`
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
- First diff index: `14`
- Accepted token: `29541` `None`
- Candidate token: `4779` `None`
- Accepted window: `None`
- Candidate window: `None`
- Replay mapping: `mapped`
  - Request: `cmpl-a036bf49c31e1bd7-0-910cd43a`
  - Trace row: `7`
  - Position in row: `1`
  - Emission role: `verifier_bonus_after_full_accept`
  - Scheduled: `[11]`
  - Generated: `[11, 4779]`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `15`
- Accepted token: `11436` `None`
- Candidate token: `16401` `None`
- Accepted window: `None`
- Candidate window: `None`
- Replay mapping: `mapped`
  - Request: `cmpl-84f7445f48f11315-0-b01312e5`
  - Trace row: `15`
  - Position in row: `0`
  - Emission role: `replacement_after_reject`
  - Scheduled: `[11436]`
  - Generated: `[16401]`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
