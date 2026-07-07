# 2026-07-07: GDN fused norm/gate + INT4 out-proj plan

## Classification

Implementation plan only. No code has been promoted, no endpoint benchmark was
run, and this is not a LocalMaxxing result.

## Why this lane exists

Current Qwen27 strict fresh best is still the target-INT8 / draft-INT4
ReplaySSM MTP3 recipe at `68.236 tok/s`. Accepted-depth work is ongoing, but
if stronger draft screens do not produce enough accepted tokens, the next
credible non-config route is reducing target-body step cost.

Prior standalone GDN `RMSNormGated` native work was a no-win at endpoint scale.
Do not repeat that route. The only plausible target-body variant is a
producer-integrated path that removes the Python/module boundary between:

```text
gdn_attention_core_xpu -> RMSNormGated(core_attn_out, z) -> INT4 out_proj
```

## Current Python path

Source:

```text
/home/steve/src/vllm/vllm/model_executor/layers/mamba/gdn_linear_attn.py
```

For `GatedDeltaNetAttention.forward_xpu`, the post-core path is:

```python
core_attn_out: [T, local_v_heads, 128], bf16
z:             [T, local_v_heads, 128], bf16

core_attn_out = core_attn_out.reshape(-1, 128)
z = z.reshape(-1, 128)
core_attn_out = self.norm(core_attn_out, z)
core_attn_out = core_attn_out.reshape(T, local_v_heads, 128)
core_attn_out = rearrange(core_attn_out, "... h d -> ... (h d)")
output[:num_tokens], _ = self.out_proj(core_attn_out)
```

For the local Qwen3.6 27B AutoRound config:

- `hidden_size=5120`
- `linear_num_value_heads=48`
- `linear_value_head_dim=128`
- full GDN `value_dim=6144`
- TP1 out-proj input: `[T, 6144]`
- TP4 local out-proj input: `[T, 1536]`
- model activations: BF16
- INT4 AutoRound/GPTQ group size: `128`

`RMSNormGated` semantics for this path are:

```text
out = rmsnorm(x, weight, eps) * silu(z)
```

The norm reduction is over the per-head dimension `128`, not over the flattened
`value_dim`.

## Current kernel surface

Relevant files:

```text
/home/steve/src/vllm-xpu-kernels/csrc/xpu/torch_bindings.cpp
/home/steve/src/vllm-xpu-kernels/csrc/xpu/ops.h
/home/steve/src/vllm-xpu-kernels/csrc/xpu/onednn/onednn_matmul.cpp
/home/steve/src/vllm-xpu-kernels/csrc/xpu/onednn/int4_gemm_w4a16.h
/home/steve/src/vllm/vllm/_xpu_ops.py
/home/steve/src/vllm/vllm/model_executor/kernels/linear/mixed_precision/xpu.py
/home/steve/src/vllm/vllm/model_executor/layers/quantization/inc.py
```

Existing schema:

```text
int4_gemm_w4a16(Tensor A, Tensor B, Tensor? bias, Tensor B_scale,
                Tensor B_zp, int group_size, Tensor? g_idx) -> Tensor
```

Weight layout constraints:

- activation `A`: FP16/BF16, flattened to GEMM `[M, K]`;
- packed INT4 `B`: int32, logical `[K / 8, N]`;
- `B` must be oneDNN NT layout (`B.stride(0) == 1`);
- scales: `[K / group_size, N]`;
- symmetric zero point may be scalar-style `[8]`; per-group/per-channel zero
  points are packed logically like `[K / group_size, N / 8]`;
- existing `g_idx` support is outside oneDNN through activation gather.

## Proposed default-off prototype

Do not change `int4_gemm_w4a16` in place. Add a new experimental op, e.g.:

```text
qwen_gdn_out_proj_int4_w4a16(
    core_attn_out,   # [T, local_v_heads, 128]
    z,               # same
    norm_weight,     # [128]
    qweight,
    bias,
    scales,
    qzeros,
    group_size,
    eps,
    g_idx
) -> Tensor
```

A graph-friendlier `_out` form is preferable if the first prototype shows any
promise:

```text
qwen_gdn_out_proj_int4_w4a16_out(
    core_attn_out,
    z,
    norm_weight,
    qweight,
    scales,
    qzeros,
    workspace,   # [T, local_v_heads * 128]
    output,      # [T, hidden_partition]
    group_size,
    eps
) -> Tensor
```

Initial restrictions:

- XPU only;
- TP1 only first, unless RowParallel all-reduce is explicitly preserved;
- `head_v_dim == 128`;
- `norm_before_gate=True`;
- activation is `silu` / `swish`;
- `bias is None`;
- `g_idx is None`;
- contiguous BF16/FP16 inputs;
- default-off env such as `VLLM_XPU_GDN_FUSED_OUT_PROJ_INT4=1`.

Implementation sketch:

1. Add a SYCL prologue kernel that reads `[T, H, 128]` `core_attn_out` and `z`.
2. For each `(token, head)`, compute FP32 RMS over the `128` value dimension.
3. Multiply by `norm_weight[d]`, multiply by `silu(z)`, and cast to the same
   BF16/FP16 boundary the current path materializes before linear quantization.
4. Write flattened workspace `[T, H * 128]` in the same order as
   `"... h d -> ... (h d)"`.
5. Feed the workspace into existing oneDNN INT4 GEMM.
6. Add fake/meta registration in `vllm/_xpu_ops.py`.
7. Add an env-gated branch in `GatedDeltaNetAttention.forward_xpu`.

## Exactness risks

The main risk is silently changing the BF16 materialization boundary. Current
code returns BF16 from `RMSNormGated` before the INT4/INT8 activation quant path
sees it. A fused prologue that quantizes directly from FP32 normalized values
can change token choices.

Other risks:

- SiLU precision/order must match current FLA/native semantics.
- The RMS reduction must stay per `128`-wide value head.
- Flattening order must match the current `rearrange`.
- RowParallel all-reduce semantics must not be skipped for TP>1.
- Existing oneDNN helper may still allocate scratchpad, hiding the expected
  launch/materialization win.

## Expected payoff

This is plausible as a contained experiment, not a guaranteed record path. The
first prototype is likely a separate SYCL prologue plus existing oneDNN GEMM,
so it still materializes a full `[T, value_dim]` workspace. Without a true
oneDNN fused prologue, expected gain may be sub-ms to low-ms per MTP step.

Run it only if:

1. the active stronger-drafter screens fail to produce enough accepted-depth;
2. timing confirms the GDN norm/out-proj boundary is still material at the
   current recipe;
3. parity against the unfused output is exact on real model weights before any
   endpoint benchmark.
