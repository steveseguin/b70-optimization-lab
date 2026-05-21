# MiniMax Router+WS Custom-Op Patch Notes - Rejected

Date: 2026-05-21

This records the quality-clean but speed-negative router+WS experiment. It is
not a promoted patch.

## llm-scaler Change

Workspace:

`/mnt/fast-ai/src/llm-scaler-router-ws-20260521T094408Z/vllm/custom-esimd-kernels-vllm`

Base copied from:

`/mnt/fast-ai/src/llm-scaler-promoted-rebuild-20260520T120230Z/vllm/custom-esimd-kernels-vllm`

Added C++/SYCL entry point:

```cpp
torch::Tensor moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_router_ws(
    torch::Tensor x,
    torch::Tensor gate_weight,
    torch::Tensor e_score_bias,
    torch::Tensor w13_qweight_u4,
    torch::Tensor w13_scales,
    torch::Tensor w2_qweight_u4,
    torch::Tensor w2_scales,
    int64_t top_k,
    bool norm) {

    TORCH_CHECK(x.dim() == 2 && x.size(0) >= 1 && x.size(0) <= 4 && x.is_contiguous());
    TORCH_CHECK(x.scalar_type() == torch::kHalf || x.scalar_type() == torch::kBFloat16);
    TORCH_CHECK(gate_weight.dim() == 2 && gate_weight.is_contiguous());
    TORCH_CHECK(gate_weight.scalar_type() == torch::kFloat,
                "MiniMax M2 router gate_weight must be fp32");
    TORCH_CHECK(e_score_bias.dim() == 1 && e_score_bias.is_contiguous());
    TORCH_CHECK(e_score_bias.scalar_type() == torch::kFloat,
                "MiniMax M2 e_score_bias must be fp32");

    const int hidden_size = (int)x.size(1);
    const int num_experts = (int)gate_weight.size(0);
    TORCH_CHECK(gate_weight.size(1) == hidden_size,
                "MiniMax M2 gate_weight hidden size mismatch");
    TORCH_CHECK(num_experts == 256,
                "MiniMax M2 dense router path currently expects 256 routed experts");
    TORCH_CHECK(e_score_bias.size(0) == num_experts,
                "MiniMax M2 e_score_bias expert count mismatch");
    TORCH_CHECK(top_k == 8,
                "MiniMax M2 dense router path currently expects top_k=8");

    auto router_input = x.to(torch::kFloat);
    auto router_logits = torch::matmul(router_input, gate_weight.t()).contiguous();

    return moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws(
        x, w13_qweight_u4, w13_scales, w2_qweight_u4, w2_scales,
        router_logits, e_score_bias, top_k, norm);
}
```

Also added:

- TORCH_LIBRARY schema for
  `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_router_ws`
- XPU implementation binding
- pybind export
- Python wrapper/export in:
  - `python/custom_esimd_kernels_vllm/ops.py`
  - `python/custom_esimd_kernels_vllm/__init__.py`

Build command used:

```bash
cd /mnt/fast-ai/src/llm-scaler-router-ws-20260521T094408Z/vllm/custom-esimd-kernels-vllm
source /home/steve/.venvs/vllm-xpu/bin/activate
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
export MAX_JOBS=4
rm -rf build python/custom_esimd_kernels_vllm/moe_int4_ops.cpython-312-x86_64-linux-gnu.so
python setup_moe_int4_only.py build_ext --inplace
```

## vLLM Hook

Files patched:

- `/home/steve/src/vllm/vllm/model_executor/models/minimax_m2.py`
- `/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/vllm/model_executor/models/minimax_m2.py`

The hook is default-off:

```bash
export VLLM_MINIMAX_MOE_ROUTER_CUSTOM_OP=1
export VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1
```

The hook calls `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_router_ws`
when the existing llm-scaler U4 decode state is present. A Python debug-print
path was removed after it caused a TorchDynamo graph break in compiled mode.

## Outcome

Strict quality passed, but p512/n1536 warm throughput regressed:

- Candidate: `92.27838026827611` output tok/s.
- Matched control: `92.415143036347` output tok/s.
- Delta: `-0.14798740074135464%`.

Decision: reject, do not promote, do not submit to LocalMaxxing.
