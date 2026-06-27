# Gemma4 Router Post-Scale Screen Loss

Date: 2026-06-27

Owner/agent: Codex

Source worktree:

```text
/home/steve/src/llama.cpp-gemma-record-stack
```

## Hypothesis

The Gemma4 MoE router path scales the RMS-normalized router input by
`1 / sqrt(n_embd)` before `ffn_gate_inp`:

```text
attn_out -> RMS -> scale -> ffn_gate_inp_s -> router matmul -> selected softmax
```

Because Gemma4 has no router bias in this path and the following router matmul
is linear, the scalar can be moved after the router matmul:

```text
attn_out -> RMS -> ffn_gate_inp_s -> router matmul -> scale -> selected softmax
```

The goal was to remove a wide `[n_embd, tokens]` scale node and replace it with
a narrow `[n_expert, tokens]` scale node. The patch was gated behind:

```text
LLAMA_GEMMA4_MOE_ROUTER_POST_SCALE=1
```

This was tested on top of the current record stack, including
`LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`.

## Validity Notes

This was treated as a semantic-risk patch until full canary validation. A
subagent audit found it conditionally safe only if the post-scale happens
immediately after `ffn_gate_inp` and before `cb(logits)` / `build_moe_ffn`.
That is how the patch was implemented.

The full validation passed quality, but did not beat the current fresh-response
record. Therefore this is a valid negative result, not a LocalMaxxing
submission.

## Screen Runs

All screen runs used `CANARY_REPEATS=64`, `BENCH_REPEATS=1`,
`BENCH_PROMPT_MODE=filled-long`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`, and
`cached_tokens=0`.

| Label | GPU | UBatch | RMS reuse | Router post-scale | Fresh row0 tok/s | Canary |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-routerpost-control-ub768-screen-20260627T0752Z` | 0 | 768 | 1 | 0 | 102.42188151299553 | 256/256 |
| `gemma4-q8-gpu1-routerpost-rms-ub768-screen-20260627T0752Z` | 1 | 768 | 1 | 1 | 103.46173086223892 | 256/256 |
| `gemma4-q8-gpu2-routerpost-rms-ub832-screen-20260627T0752Z` | 2 | 832 | 1 | 1 | 104.81345372517579 | 256/256 |
| `gemma4-q8-gpu3-routerpost-normbase-ub768-screen-20260627T0752Z` | 3 | 768 | 0 | 1 | 104.11943111754168 | 256/256 |
| `gemma4-q8-gpu0-routerpost-rms-ub704-screen-20260627T0800Z` | 0 | 704 | 1 | 1 | 102.343722946888 | 256/256 |
| `gemma4-q8-gpu1-routerpost-rms-ub896-screen-20260627T0800Z` | 1 | 896 | 1 | 1 | 101.9003323723304 | 256/256 |
| `gemma4-q8-gpu3-routerpost-rms-ub832-pmin012-screen-20260627T0800Z` | 3 | 832 | 1 | 1 | 102.31730512832657 | 256/256 |

The only screen above the existing `104.30919255569083 tok/s` record was
`gpu2/routerpost/rms/ub832`, so that one received full validation.

## Full Validation

Label:

```text
gemma4-q8-gpu2-routerpost-rms-ub832-fullrepeat-20260627T0758Z
```

Artifacts:

- `data/gemma4-q8-gpu2-routerpost-rms-ub832-fullrepeat-20260627T0758Z/summary.json`
- `data/gemma4-q8-gpu2-routerpost-rms-ub832-fullrepeat-20260627T0758Z/chat-canary.json`
- `data/gemma4-q8-gpu2-routerpost-rms-ub832-fullrepeat-20260627T0758Z/p512o512.json`
- server log outside Git:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu2-routerpost-rms-ub832-fullrepeat-20260627T0758Z.server.log`

Identity:

- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- target/verifier quality lane: Q8 target
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- GPU: 2
- context: 8192
- batch / ubatch: `1024 / 832`
- prompt / output: `588 / 512` tokens reported by API usage
- repeats: `CANARY_REPEATS=1536`, `BENCH_REPEATS=8`
- strict headline policy: row 0 only, repeated benchmark rows support-only
- `cached_tokens`: all rows reported `0`

Result:

- chat canary: `6144/6144` rows passed
- fresh-response headline row0: `104.19915421673585 tok/s` after TTFT
- row0 wall throughput: `90.8629049012444 tok/s`
- support repeated-prompt mean after TTFT: `103.95041920238755 tok/s`
- support repeated-prompt wall mean: `95.41905783684088 tok/s`

## Decision

Loss. Do not submit to LocalMaxxing.

The full validation is slower than the current valid fresh-response record:

```text
current record: 104.30919255569083 tok/s
router post-scale full: 104.19915421673585 tok/s
delta: -0.11003833895498 tok/s
```

The screen-only `104.81345372517579 tok/s` result was variance and should not
be referenced as a valid record.

## Follow-Up

This result reinforces that the current Gemma4 Q8 stack is at a micro-variance
frontier for graph-level scalar/node cleanups. The next high-ROI work should
move away from another ubatch/pmin/router-scale sweep and toward one of:

- verifier/output matmul reduction;
- MoE expert matmul/kernel reduction around `MUL_MAT_ID:ffn_moe_gate_up-*`;
- a larger MTP verifier/draft design that increases fresh-response tokens per
  target forward without relying on repeated-output history.

