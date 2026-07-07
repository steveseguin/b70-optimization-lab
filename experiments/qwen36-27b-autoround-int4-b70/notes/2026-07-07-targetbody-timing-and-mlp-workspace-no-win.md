# 2026-07-07 - Qwen27 target-body timing and MLP workspace no-win

## Context

Current quality-confirmed Qwen3.6 27B INT4 AutoRound headline remains the
`webhie/Qwen3.6-27B-int4-AutoRound` ReplaySSM/MTP3 recipe at `68.236 tok/s`
strict fresh median, `cached_tokens=0`, repeat64 quality pass.

This pass tried to move beyond stale LM-head assumptions by measuring where the
decode step actually spends time, then screening one low-risk dense-MLP
workspace idea.

Important architecture correction: this model is dense `qwen3_5_text`, not MoE.
It has `64` layers: `48` linear-attention/GDN layers and `16`
full-attention layers. Each layer uses dense `Qwen2MoeMLP` as the MLP
implementation (`gate_up_proj`, SiLU/mul, `down_proj`), but there are no routed
experts in this checkpoint.

## Source state preserved before work

Pre-experiment snapshots:

- `patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-active-before-next-qwen27-optimization-20260707T035020Z.patch`
- `patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-xpu-kernels-active-before-next-qwen27-optimization-20260707T035020Z.patch`

The active source edit made during this experiment was reverted after it proved
no-win. The failed compile-guard patch is preserved at:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen2moe-act-workspace-compileguard-no-win-20260707.patch`

## Diagnostic 1: graph-none compiled target baseline

Run:

- label: `qwen27-targetbody-eager-nomtp-subtiming-20260707T035503Z`
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-targetbody-eager-nomtp-subtiming-20260707T035503Z-20260707T035503Z`
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-targetbody-eager-nomtp-subtiming-20260707T035503Z-candidate-summary-20260707T035503Z.json`
- config: no MTP, `COMPILATION_CONFIG={"cudagraph_mode":"NONE"}`, target INT8
  LM-head enabled, quality skipped.

Strict fresh mechanics passed (`cached_tokens=0`, each prompt once), but this
is diagnostic only because it disables the current headline recipe.

Result:

- median `22.703 tok/s`, mean `22.696`, p10 `22.503`;
- TTFT median `200.377 ms`;
- timing summary:
  - `gpu_model_runner.model_forward`: `39.971 ms/token`;
  - `gpu_model_runner.compute_logits`: `2.755 ms/token`;
  - `logits.local_argmax_lm_head`: `2.672 ms/token`;
  - `lm_head_int8.gemm_w8a8`: `2.519 ms/token`;
  - `lm_head_int8.per_token_quant`: `0.055 ms/token`.

Interpretation: runtime INT8 LM-head is no longer the obvious primary waste in
the current code path. It is still real cost, but the target model body is much
larger.

## Diagnostic 2: enforce-eager one-request layer split

Run:

- label: `qwen27-targetbody-enforceeager-single-subtiming-20260707T040257Z`
- run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-targetbody-enforceeager-single-subtiming-20260707T040257Z`
- config: no MTP, `--enforce-eager`, no graph/compile, one local request,
  quality skipped.

This is not a throughput benchmark. It exists only because normal torch.compile
suppresses inner `timed_region` hooks.

Key timing over the request after `skip_first=4`:

- `gpu_model_runner.model_forward`: `155.898 ms/token` under enforce-eager;
- `qwen3_next.layer_type.linear_attention`: `17.402 s` total over `7436`
  layer calls;
- `qwen3_next.layer.linear_attention`: `8.403 s`;
- `qwen3_next.layer_type.full_attention`: `7.088 s` total over `2476` calls;
- `qwen3_next.layer.full_attention`: `4.142 s`;
- `qwen3_next.layer.mlp`: `5.685 s`;
- input/post-attention RMSNorm together: `4.475 s`;
- `qwen3_next.gdn.core_op`: `2.776 s`;
- dense MLP internals:
  - `qwen2_moe.shared.gate_up_proj`: `2.349 s`;
  - `qwen2_moe.shared.down_proj`: `1.374 s`;
  - `qwen2_moe.shared.silu_and_mul`: `0.620 s`;
- full-attention internals:
  - rotary: `1.292 s`;
  - qk norm: `0.947 s`;
  - attention: `0.438 s`;
  - qkv projection: `0.317 s`;
  - o projection: `0.267 s`;
  - output gate: `0.144 s`.

Interpretation: under visible eager timing, the largest body-level buckets are
linear-attention/GDN layers, full-attention layers, dense MLP, and norms. This
does not directly transfer to graph-captured endpoint timing, but it rules out
MoE-specific work for this dense model and supports focusing on real target-body
kernel work or accepted-token depth rather than more wrapper-level LM-head
plumbing.

## Screen: `VLLM_XPU_SHARED_EXPERT_ACT_WORKSPACE=1`

Reason tried: the dense MLP uses `Qwen2MoeMLP`; the existing
`VLLM_XPU_SHARED_EXPERT_ACT_WORKSPACE=1` path reuses the SiLU/mul output buffer
and is not actually limited to routed shared experts.

Same-window control:

- label: `qwen27-current-control-samewindow-20260707T040539Z`
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-control-samewindow-20260707T040539Z-candidate-summary-20260707T040539Z.json`
- result: median `67.321 tok/s`, mean `67.401`, p10 `62.366`, strict
  fresh/cached-zero pass, quality skipped.

Workspace attempt 1:

- label: `qwen27-mlp-act-workspace-samewindow-20260707T040539Z`
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mlp-act-workspace-samewindow-20260707T040539Z-candidate-summary-20260707T040539Z.json`
- failed before readiness.
- root cause: `torch._dynamo.exc.Unsupported`, `ContextVar.get()` from
  `current_xpu_cudagraph_scratch_key()` in the workspace key path during
  fullgraph compile.

Workspace attempt 2:

- patch applied locally:
  `vllm-qwen2moe-act-workspace-compileguard-no-win-20260707.patch`
- label: `qwen27-mlp-act-workspace-compileguard-samewindow-20260707T040807Z`
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mlp-act-workspace-compileguard-samewindow-20260707T040807Z-candidate-summary-20260707T040807Z.json`
- failed before readiness again.
- root cause after guard: vLLM graph splitting failed with
  `RuntimeError: Tried to erase Node size but it still had 2 users in the graph:
  {core_attn_out: None, setitem: None}!`

Decision: close this flag for Qwen27 endpoint work. It is a small allocation
reuse idea, not worth deeper graph-split surgery, especially because older
Qwen35 PIECEWISE work also rejected this env family. The active source edit was
reverted; the patch and logs are preserved for reference.

## Next credible work

1. Do not pursue MoE-specific layerlets for this Qwen27 checkpoint; it is dense.
2. Do not keep sweeping wrapper/config flags unless they target a measured
   bucket and can pass compile/graph without invasive fixes.
3. Best remaining Qwen27 lanes:
   - real GDN/linear-attention kernel or exact state-transaction work;
   - real full-attention/norm fusion only if microbench-backed;
   - a stronger drafter that first clears the offline accepted-depth threshold;
   - accepted-prefix/branch-regenerate work only if it improves tokens per
     expensive target step enough to overcome overhead.

