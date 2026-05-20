# MiniMax M2.7 Current-High MBT640 Scheduling Screen

Date: 2026-05-20

## Summary

Retested the current promoted MiniMax M2.7 AutoRound INT4 stack with `MAX_BATCHED_TOKENS=640` instead of the promoted `512`.

Decision: reject as a speed candidate and do not submit to LocalMaxxing. The candidate is quality-clean, but the mean speed is below the promoted current-high result.

## Result

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM `0.20.1-local`, XPU TP4
- Shape: p512/n1536, ctx2048, batch 1, block size 256
- Candidate change: `MAX_BATCHED_TOKENS=640`
- Mean output: `88.835750` tok/s
- Mean total: `118.447666` tok/s
- Output repeats: `[88.399707, 88.428179, 89.290248, 89.224864]`
- Total repeats: `[117.866276, 117.904239, 119.053664, 118.966485]`
- Promoted baseline: `89.314195` output tok/s / `119.085594` total tok/s
- Delta vs promoted: `-0.478446` output tok/s / `-0.637928` total tok/s

## Quality

All strict gates passed before benchmarking:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

Matched promoted hashes:

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic repeat: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

## Artifacts

- Summary: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-currenthigh-mbt640-20260520-strict-tp4-ctx2048-mbt640-bs256-20260520T045740Z-summary.json`
- Runtime marker: `/home/steve/bench-results/minimax-m2.7-strict-candidates/minimax-minimax-currenthigh-mbt640-20260520-strict-tp4-ctx2048-mbt640-bs256-20260520T045740Z-runtime.json`

## Lesson

Changing only the chunked-prefill scheduling boundary from 512 to 640 is quality-preserving, but it does not improve the steady-state single-session decode rate on the current high stack. Keep `MAX_BATCHED_TOKENS=512` for promoted MiniMax p512/n1536 runs and move effort back to lower-level source work.
