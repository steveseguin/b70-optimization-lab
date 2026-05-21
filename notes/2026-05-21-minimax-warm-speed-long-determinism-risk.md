# 2026-05-21 MiniMax M2.7 Warm Speed And Long Determinism Risk

## Summary

The promoted 4x B70 MiniMax M2.7 AutoRound W4A16 runtime is still quality-clean on the strict short-horizon gate, but the newest warm persistent-engine probe exposed a repeatability caution for longer greedy generations.

This means the 93+ tok/s warm speed is plausible as steady-state throughput, but it should not be treated as a new shareable quality-certified result until the long-output determinism issue is understood.

## Accepted Control

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Runtime: vLLM XPU, TP4, fp16, context 2048, max batched tokens 512, max seqs 1, block size 256
- Quality gate: passed
- Bench prompt/output: p512/n1536
- Cold-per-process repeat outputs:
  - 87.925232 tok/s output, 117.233643 tok/s total
  - 88.021334 tok/s output, 117.361779 tok/s total
  - 89.070379 tok/s output, 118.760505 tok/s total
- Mean: 88.338982 tok/s output, 117.785309 tok/s total
- Quality artifacts:
  - raw145 n64 exact hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
  - raw145 n256 exact hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
  - semantic suite hash: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
  - arithmetic repeat r8 hash: `261779104d5abf1642713bfc560ca8d2d6c0f16edbcc929c8b0819b5a760dd7c`

Artifact: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-promoted-path-repeat-control-strict-tp4-ctx2048-mbt512-bs256-20260521T191253Z-summary.json`

## Warm Throughput Probe

Warm persistent-engine p512/n1536, after one warmup run:

- 93.502939 tok/s output, 124.670585 tok/s total
- 93.449131 tok/s output, 124.598841 tok/s total
- 93.431856 tok/s output, 124.575807 tok/s total
- 93.479189 tok/s output, 124.638919 tok/s total
- Mean: 93.465779 tok/s output, 124.621038 tok/s total
- Stdev output tok/s: 0.031563

Artifact: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-promoted-path-warm-repeat-p512n1536-20260521T193211Z.json`

The token hashes differed across warm repeats. Since this harness was throughput-focused, it does not yet prove semantic or exact-repeat quality for warm runs.

## Long Exact-Repeat Risk

I then ran a longer raw145 exact-repeat check with `max_tokens=1536`, two greedy repeats, same promoted runtime.

Result: failed exact determinism, but did not show the previous corruption signature.

- `passed`: false
- Failure: `nondeterministic lstrip_text`
- Combined token hash: `6b50fa7d8119aca3a1504a2dc0b59cfc5bf6597aae90f7466c2a35b28107272f`
- Total generated tokens checked: 3072
- Distinct generated token count: 41
- NUL token count: 0
- Control non-space chars: 0
- Degenerate output: false
- First differing token index: 13
- Run 0 token at first difference: 16793
- Run 1 token at first difference: 10

Artifact: `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/minimax-promoted-path-raw145-n1536-r2-20260521T193639Z.json`

This looks different from the rejected custom collective/trace failures. Those produced obvious NUL/control output. This one produced normal text but diverged early on a repetitive Greek-token prompt, which could be either benign near-tie drift or a real reproducibility issue.

## Decision

Do not submit a new LocalMaxxing result from the warm 93.47 tok/s probe yet.

The existing accepted 93.443623 tok/s result remains useful as a prior warm-speed result, but the current next quality bar is stricter: warm-speed runs should be paired with either exact deterministic long-output proof or a stronger semantic long-output suite.

## Next Diagnostics

1. Run raw145 exact-repeat at intermediate lengths, especially n512 and n1024, to locate whether the failure is length-related or prompt-related.
2. Run long semantic prompts at n512/n1536, not just the repetitive raw145 prompt, and require task-specific correctness.
3. Compare graph vs eager for the long raw145 repeat. If eager passes and graph fails, the issue is likely graph/collective numerical order.
4. Keep `VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=0`; the custom-op collective path has already produced NUL/control corruption.
5. Do not promote or publish performance changes unless they pass the strict gate and the new long-output quality checks.
