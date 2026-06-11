# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-quark-int8-tp4-perfectdraft-k4-accepted-p512o256-20260611.json`
- Candidate: `data/qwen36-quark-int8-tp4-perfectdraft-k4-candidate-p512o256-20260611a.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `5`
- Requests: `2`
- Draft tokens: `20`
- Accepted: `17`
- Rejected: `3`
- Accept rate: `85.0`
- Full accept rows: `4`
- Full reject rows: `0`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `17`
- Accepted token: `321` ` and`
- Candidate token: `11436` ` hardware`
- Accepted window: ` single-request decode speed, reliability gates, and no quality loss.
Continue with dense`
- Candidate window: ` single-request decode speed, reliability gates, hardware, and no quality loss.

<think>`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `5`
- Accepted token: `2468` ` output`
- Candidate token: `1879` ` input`
- Accepted window: ` token timing. Preserve exact output while measuring multi token verification. Intel X`
- Candidate window: ` token timing. Preserve exact input

<think>

</think>

Intel XPU`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
