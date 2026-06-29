# 2026-06-29 BF16 routed gate/up + GEGLU direct fused lane: negative

Purpose: test whether the second-hot verifier node after the Q8 LM head,
`MUL_MAT_ID:ffn_moe_gate_up-29`, could be reduced by routing BF16 Gemma 4 MoE
gate/up through a direct fused gate-up + GEGLU backend op.

## Context

Current valid record to preserve:

- result: `data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/`
- LocalMaxxing: `cmqyrpox4021dqk01co5o4fcw`
- primary metric: `115.8466634928202 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT;
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: Q4_0 Gemma MTP draft, with accepted tokens verified by the Q8 target.

The post-top1 node profile made dense/shared FFN fusion low priority, but it
did show final-layer routed BF16 gate/up as the next visible target after the
LM head. This experiment tried the faster-to-code direct routed BF16 path,
rather than the larger "preserve existing BF16 matmul route and only fuse
post-GEMM GEGLU" design.

## Patch

Source worktree:
`/home/steve/src/llama.cpp-gemma-record-repro-c926` at upstream `c926ad098`
with the existing dirty Gemma record stack.

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260629-bf16-gateup-geglu-direct-experiment-current.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260629-bf16-gateup-geglu-direct-experiment-current.diffstat`

Main source changes:

- `src/llama-graph.cpp`: added
  `LLAMA_GEMMA4_MOE_GATEUP_GEGLU_BF16=1` as an opt-in for the existing Gemma 4
  routed gate/up+GEGLU graph path when `gate_up_exps` is BF16.
- `ggml/src/ggml.c`: allowed `ggml_moe_q8_0_gateup_geglu` to accept Q8_0 or
  BF16 `gate_up_exps`.
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: added a direct BF16 fused routed
  gate/up+GEGLU kernel, and extended the SYCL op support validator for BF16.

Build/checks:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
git diff --check -- src/llama-graph.cpp ggml/src/ggml.c ggml/src/ggml-sycl/ggml-sycl.cpp
source /opt/intel/oneapi/setvars.sh --force >/tmp/oneapi-setvars.log 2>&1 || true
ninja -C build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 llama-server
```

The build completed. The flag is recorded in new run summaries as
`launcher_identity.llama_gemma4_moe_gateup_geglu_bf16`.

## Four-GPU strict128 screen

All rows used the fixed realistic cold suite, each prompt once,
`cached_tokens=0`, Q8 target/verifier, Q4_0 MTP draft, `MAX_TOKENS=128`, and
`CANARY_REPEATS=64` (`256` canary rows). All rows passed the realistic final
gate and the chat canary.

| GPU | Label | BF16 gateup flag | median tok/s 1-100 | p10 | mean | full after TTFT | wall full | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | `gemma4-q8-gpu0-bf16gateup-control-strict128-20260629Tscreen` | unset | `115.413375` | `102.883754` | `115.212683` | `114.609253` | `99.279333` | `179.388016` |
| 1 | `gemma4-q8-gpu1-bf16gateup-on-strict128-20260629Tscreen` | `1` | `114.467121` | `101.482810` | `113.188548` | `111.528468` | `96.311544` | `179.602764` |
| 2 | `gemma4-q8-gpu2-bf16gateup-control-strict128-20260629Tscreen` | unset | `112.422293` | `102.404963` | `113.532033` | `112.448887` | `96.278471` | `181.571202` |
| 3 | `gemma4-q8-gpu3-bf16gateup-on-strict128-20260629Tscreen` | `1` | `110.829693` | `98.439078` | `110.467957` | `111.574130` | `94.481284` | `181.650772` |

Evidence:

- `data/gemma4-q8-gpu0-bf16gateup-control-strict128-20260629Tscreen/summary.json`
- `data/gemma4-q8-gpu1-bf16gateup-on-strict128-20260629Tscreen/summary.json`
- `data/gemma4-q8-gpu2-bf16gateup-control-strict128-20260629Tscreen/summary.json`
- `data/gemma4-q8-gpu3-bf16gateup-on-strict128-20260629Tscreen/summary.json`

## Decision

Closed negative. The flag-enabled rows passed quality but were slower than
their paired controls:

- GPU1 flag-on vs GPU0 control: `114.467` vs `115.413` tok/s primary, with a
  larger full-output and wall-rate loss.
- GPU3 flag-on vs GPU2 control: `110.830` vs `112.422` tok/s primary.

No full512 confirmation and no LocalMaxxing submission should be run for this
direct fused BF16 variant.

Likely reason: the direct BF16 kernel gives up enough performance versus the
existing BF16 matmul route that eliminating separate gate/up/GEGLU handling does
not compensate. This is consistent with the older broad
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT=1` loss.

The more surgical design remains a separate possible future lane: preserve the
existing BF16 matmul route and fuse only the post-GEMM GEGLU/scatter, ideally
after a microbench or profile proves that standalone GEGLU/materialization is a
meaningful cost. Do not retry this direct routed BF16 dot-kernel variant without
new lower-level evidence.
