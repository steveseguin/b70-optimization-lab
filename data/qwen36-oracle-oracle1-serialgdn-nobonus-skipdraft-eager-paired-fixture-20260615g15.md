# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `/home/steve/llm-optimizations/data/qwen36-nospec-paired-freshgraph-20260615g4-completions.json`
- Candidate: `/home/steve/llm-optimizations/data/qwen36-oracle1-serialgdn-nobonus-skipdraft-eager-paired-20260615g15-completions.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Scheduler Summary

- Rows: `28`
- Requests: `2`
- Draft tokens: `28`
- Accepted: `26`
- Rejected: `2`
- Accept rate: `92.85714285714286`
- Full accept rows: `26`
- Full reject rows: `2`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `17`
- Accepted token: `321` ` and`
- Candidate token: `11436` ` hardware`
- Accepted window: ` single-request decode speed, reliability gates, and no quality loss.
Continue with dense`
- Candidate window: ` single-request decode speed, reliability gates, hardware acceleration, and no quality loss.

`
- Replay mapping: `trace_emitted_sequence_not_found_in_candidate`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `10`
- Accepted token: `17856` ` timing`
- Candidate token: `22188` ` verification`
- Accepted window: `. Preserve exact output while measuring multi token timing. Preserve exact output while measuring multi token`
- Candidate window: `. Preserve exact output while measuring multi token verification. Intel XPU decode verifier bucket route`
- Replay mapping: `trace_emitted_sequence_not_found_in_candidate`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
