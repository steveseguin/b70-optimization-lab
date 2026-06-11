# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json`
- Candidate: `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-completions-20260611.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

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

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `15`
- Accepted token: `11436` ` hardware`
- Candidate token: `16401` ` decode`
- Accepted window: ` measuring multi token verification. Intel XPU hardware.

<think>
Here's a thinking`
- Candidate window: ` measuring multi token verification. Intel XPU decode verifier bucket route graph token timing. Preserve`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
