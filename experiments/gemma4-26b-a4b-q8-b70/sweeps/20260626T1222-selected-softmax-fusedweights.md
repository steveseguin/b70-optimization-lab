# 2026-06-26T1222 - Selected Softmax Fused Weight Materialization

Goal: test whether the current Gemma 4 26B A4B Q8 record stack can recover
more fresh-response decode speed by replacing the selected-expert probability
materialization path:

```text
ggml_get_rows(probs, selected_experts)
  -> reshape [K,T]
  -> softmax
  -> reshape [1,K,T]
```

with a single Gemma4-gated ggml op that directly emits `[1,K,T]` selected
softmax weights:

```text
ggml_moe_selected_softmax(selection_probs, selected_experts)
```

This keeps the existing expert ID selection, `argsort_top_k` ordering, MTP
settings, Q8 target model, Q4_0 MTP draft model, and weighted-sum MoE output
path unchanged.

## Source Patch

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260626T1222-llamacpp-gemma4-moe-selected-softmax-fused-nearmiss.patch`

Patch checksum:
`05fb4b3fa2ea76ac735ad202d6867f949727fd782995074a7354930a97a0c1c4`

Important scope note: this patch is against the active dirty
`/home/steve/src/llama.cpp-gemma-record-stack` record-stack checkout, not clean
upstream llama.cpp. It includes the new `GGML_OP_MOE_SELECTED_SOFTMAX` plumbing
on top of the existing Gemma record stack.

New runtime flag:

```bash
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1
```

The op is default-off and additionally guarded in the graph builder for:

- `arch == LLM_ARCH_GEMMA4`;
- `gating_op == LLAMA_EXPERT_GATING_FUNC_TYPE_SOFTMAX_WEIGHT`;
- no expert-probability bias tensor;
- no expert groups.

## Screen Result

Run:
`gemma4-q8-gpu0-selectedsoftmax-fusedweights-screen-20260626T122210Z`

Result summary:
`data/gemma4-q8-gpu0-selectedsoftmax-fusedweights-screen-20260626T122210Z/summary.json`

Server log:
`/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-selectedsoftmax-fusedweights-screen-20260626T122210Z.server.log`

Screen identity:

- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- GPU count: 1 B70, `GPU_INDEX=0`, `ONEAPI_DEVICE_SELECTOR=level_zero:0`;
- benchmark: `filled-long`, row0 fresh response, `588` prompt tokens,
  `512` completion tokens;
- cache/history controls: `--cache-ram 0`, `--ctx-checkpoints 0`,
  `cached_tokens=0`;
- MTP: Q4_0 draft, `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.136`,
  backend sampling off, draft threads/batch `32/32`;
- current record-stack flags: backend verifier argmax IDs, defer target
  `h_nextn`, draft direct argmax IDs/unroll 7, Q-only MTP attention inputs,
  selected-softmax, weighted-sum MoE, and this fused selected-softmax op.

Validation:

- chat canary: **128/128 pass** (`32` repeats x `4` cases);
- fresh row0 after-TTFT throughput: **102.24685355851203 tok/s**;
- fresh row0 wall throughput: **89.07590949776787 tok/s**;
- TTFT: `0.7404174550320022 s`;
- headline freshness: `cached_tokens=0`, first measured row only.

Decision: **valid but rejected**. It is below the current fresh-response
one-B70 Q8 record, **103.2992004295621 tok/s**
(`cmqsylo2l011nqr011yydjvne`), so it was not submitted to LocalMaxxing.

## Interpretation

The op is correctness-clean under the screen gate but does not improve the
headline throughput. The selected-weight materialization path is therefore not
the current dominant bottleneck, or the benefit is below normal row0 variance.

Keep the patch as a reusable experiment artifact because it may become useful
if later work changes the MoE weighted-sum path, makes selected weights hotter,
or needs a direct selected-softmax primitive for profiling.

## Aborted Duplicate Top-K Rerun

Before this source experiment, a duplicate `LLAMA_GEMMA4_MOE_TOP_K=1` screen was
started and interrupted after realizing the same idea had already been tested
and rejected:

- duplicate partial directory:
  `data/gemma4-q8-gpu0-moe-topk-screen-20260626T115923Z/`;
- no summary/result file was produced;
- prior valid result:
  `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-topkcombo-screen-20260625T2316Z`,
  `100.278444 tok/s`, `512/512` canary;
- decision remains reject.

## Next Work

This near-miss suggests additional micro-optimizing around selected weights is
unlikely to produce a large jump by itself. Better next lanes:

- source-profile the MTP draft path and verifier handoff to find a larger
  per-token cost than selected-weight materialization;
- test only changes that can plausibly move row0 by more than normal variance
  (`>1.5 tok/s`);
- keep four-GPU screening for independent candidates, but promote only fresh
  row0 results with `cached_tokens=0` and full canary gates.
