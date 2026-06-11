# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-quark-int8-tp4-accepted-modelinput-completions-20260611f.json`
- Candidate: `data/qwen36-quark-int8-tp4-placebo-modelinput-completions-20260611a.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `25`
- Accepted token: `198` `
`
- Candidate token: `271` `

`
- Accepted window: ` hardware acceleration, and no quality loss.
Continue with dense numbered engineering notes. Focus`
- Candidate window: ` hardware acceleration, and no quality loss.

<think>
Thinking Process:

1.`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `14`
- Accepted token: `4752` ` unique`
- Candidate token: `6126` `PU`
- Accepted window: ` while measuring multi token verification. Intel X unique

<think>
Here's a thinking process`
- Candidate window: ` while measuring multi token verification. Intel XPU decode verifier bucket route graph token timing.`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
