# MiniMax M2.7 N-major Prefill64 Candidate

Date: 2026-05-21

## Question

Can the existing llm-scaler N-major INT4 MoE path, which accepts up to 64 tokens, be used for small prefill chunks without changing MiniMax routing quality?

## Candidate

Patch the vLLM `MoeWNA16Method.apply` fast-path gate from a hard-coded decode-only `x.shape[0] <= 4` to an opt-in environment limit:

```bash
VLLM_XPU_LLM_SCALER_MOE_APPLY_MAX_TOKENS=64
MAX_BATCHED_TOKENS=64
```

The default remains `4`, so the promoted path is unchanged unless the experiment is explicitly enabled.

## Quality

Passed all strict gates:

- raw145 n64 exact token hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact token hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic suite n64 r2
- arithmetic repeat n64 r8
- extended sixpack n64 r2

This confirms the path preserves MiniMax's existing router output, including sigmoid plus `e_score_correction_bias` and renormalized top-k weights. It does not use the llm-scaler all-in-one prefill softmax router, which is not MiniMax-correct.

## Throughput

Strict p512/n1536 repeats:

| Repeat | Output tok/s | Total tok/s |
| --- | ---: | ---: |
| 1 | 85.247 | 113.663 |
| 2 | 86.865 | 115.821 |
| 3 | 85.923 | 114.564 |
| 4 | 86.420 | 115.227 |

Mean output tok/s: `86.114`

Mean total tok/s: `114.819`

Promoted strict result: `89.314` output tok/s.

Delta: `-3.58%`.

## Outcome

Reject for promotion. The candidate is quality-safe, but it is slower on the decode-heavy p512/n1536 benchmark. The likely reason is that the benchmark does not gain enough from the smaller prefill chunks to offset extra scheduling/kernel overhead, while decode remains the dominant cost.

Keep this as an opt-in investigative knob. It may still be useful for future prefill-heavy or short-output throughput sweeps, but it should not replace the promoted 89 tok/s reproducible path.

## Reliability Note

The run repeatedly hit recoverable Intel/Triton graph-capture compile warnings:

```text
ocloc failed with error code 245
IGC: Internal Compiler Error: Floating point exception
```

vLLM recovered and all exact/semantic quality gates passed, but this remains a driver/compiler reliability caveat for PIECEWISE graph capture on this stack.
