# Ornith 1.5 35B-A3B: recurrent convolution + SiLU fusion

Date: 2026-08-22 EDT

Status: **accepted package increment; +2.10% matched serving**

## Accepted scope

The one-token graph has 30 recurrent layers. Each layer launched `SSM_CONV`
over `[4,8192]` FP32 input and then a sole full-width SiLU consumer. The
default-off candidate preserves the stock convolution loop and SiLU expression,
writes the existing SiLU tensor directly, and skips only the raw convolution
materialization and separate SiLU launch. Exact names, types, shapes, strides,
single-consumer ownership, and one-token dimensions are required.

Runtime door:

```bash
export GGML_SYCL_FUSED_ORNITH_CONV_SILU=1
```

Warmup plus one measured token produced 60 hits, or 30/30 recurrent layers in
each graph. The patch removes 30 launches per generated token.

## Matched performance

One B70, directly verified local GGUF, F16 KV, flash attention, target-only,
and the accepted ordered-MoE reduction enabled in both arms.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7` | `107.480637`, `107.453365` | `108.695561`, `108.785273` | **+1.1849%** |
| fresh 12-prompt server suite | `103.289809`, `102.734504` | `105.688482`, `104.653313` | **+2.0956%** |

All four server suites used each unique prompt once, generated up to 512
tokens, reported `cached_tokens=0` for every row, and passed the realistic
fresh-response gate. The primary server metric is the median rate over tokens
1-100 after TTFT.

## Correctness

- Same-binary door-off/on forced 400-token greedy response was byte-identical;
  both response payloads hash to
  `5cb5ad6254e0560e624e4ee9712658b341dcc462030789d17e1e7a3143326f0e`.
- Candidate 8x repeat stability, arithmetic, exact copy, and JSON schema
  canaries passed.
- A poison build path visibly diverged and reported 930 fused hits, proving the
  tested path reached the new arithmetic.

## Rejected wider candidate

The first candidate also bypassed `GET_ROWS`, `CONCAT`, persistent-state `CPY`,
and Q/K L2 work. It fired on all 30 recurrent layers and showed a promising
short-run speed signal, but deterministic CLI output diverged after the first
few generated tokens. It is archived as
`../patches/llamacpp-ornith15-direct-state-conv-silu-negative-20260822.patch`
and must not be enabled or described as a performance result.

Structured summary and raw engine/server JSON are under `../data/`.
