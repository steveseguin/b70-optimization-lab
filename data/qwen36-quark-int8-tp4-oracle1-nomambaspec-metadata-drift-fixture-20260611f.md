# Qwen3.6 Oracle k=1 Drift Fixture

- Accepted: `data/qwen36-quark-int8-tp4-accepted-noasync-metadata-p512o128-20260611f.json`
- Candidate: `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-p512o128-20260611f.json`
- Exact match all: `False`
- Mismatches: `2` / `2`

## Case Diffs

### natural_latency_plan

- Status: `mismatch`
- First diff index: `3`
- Accepted token: `47193` `None`
- Candidate token: `148368` `None`
- Accepted window: `None`
- Candidate window: `None`

### repetitive_kernel_notes

- Status: `mismatch`
- First diff index: `3`
- Accepted token: `78503` `None`
- Candidate token: `220` `None`
- Accepted window: `None`
- Candidate window: `None`

## Next Actions

- Use this fixture as the token-parity gate for any speculative scheduler/KV patch.
- First repair k=1 oracle parity before enabling DFlash, MTP, n-gram, or learned proposers.
- If a patch passes this fixture, rerun full r8 quality through the paused-local public frontdoor.
