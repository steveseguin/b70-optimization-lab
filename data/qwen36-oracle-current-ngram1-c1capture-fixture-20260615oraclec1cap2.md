# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-oracle-accepted-current-20260615oraclefresh1.json`
- Candidate: `data/qwen36-oracle-ngram1-c1capture-20260615oraclec1cap2.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `34`
- Requests: `1`
- Draft tokens: `34`
- Accepted: `31`
- Rejected: `3`
- Accept rate: `91.17647058823529`
- Full accept rows: `31`
- Full reject rows: `3`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `17`
- Accepted token: `11436` ` hardware`
- Candidate token: `321` ` and`
- Accepted window: ` single-request decode speed, reliability gates, hardware acceleration, and no quality loss.

`
- Candidate window: ` single-request decode speed, reliability gates, and no quality loss.

<think>

</think>`
- Replay mapping: `trace_emitted_sequence_not_found_in_candidate`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `0`
- Accepted token: `3817` ` token`
- Candidate token: `220` ` `
- Accepted window: ` token timing. Preserve exact output while measuring multi`
- Candidate window: ` ���<|im_end|>`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
