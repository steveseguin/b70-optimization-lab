# 2026-05-31 Initial Brief

## Decision

Use `Intel/DeepSeek-V4-Flash-W4A16-AutoRound` as the primary AutoRound target
because no STEP 3.7 AutoRound INT4 checkpoint is currently available.

## Model Facts Captured

- HF id: `Intel/DeepSeek-V4-Flash-W4A16-AutoRound`
- HF revision observed via API: `d8ac6c04e22da23f68f797884471dae5cb129ee0`
- Created: `2026-04-27`
- Last modified: `2026-05-06`
- Architecture: `DeepseekV4ForCausalLM`
- Model type: `deepseek_v4`
- Quantization: AutoRound W4A16, `auto_round:auto_gptq`, `bits=4`,
  `group_size=128`, `sym=true`
- Direct safetensors size from HF repo tree: about `153.0 GB` decimal /
  `142.4 GiB` across 46 shards
- HF model API `usedStorage`: `303.7 GB` decimal / `282.9 GiB`; treat this as
  repository/backend storage accounting, not the expected local download size
- Tensor count/shape summary reported by HF: about `39.9B` stored tensor
  elements, mostly `I32` packed weights plus BF16/F16/F32 side tensors.

Key config values:

- `hidden_size=4096`
- `num_hidden_layers=43`
- `num_attention_heads=64`
- `head_dim=512`
- `qk_rope_head_dim=64`
- `q_lora_rank=1024`
- `o_lora_rank=1024`
- `n_routed_experts=256`
- `num_experts_per_tok=6`
- `moe_intermediate_size=2048`
- `n_shared_experts=1`
- `num_hash_layers=3`
- `sliding_window=128`
- `index_topk=512`
- `hc_mult=4`
- `max_position_embeddings=1048576`
- `compress_ratios=[0,0,4,128,...,4,0]`

## Why This Is Harder Than MiniMax

MiniMax M2.7 required a W4A16 MoE fit patch and then a long optimization loop.
DeepSeek V4 likely needs that plus XPU bring-up for architecture-specific code:

- The local vLLM `DeepseekV4Model` creates `torch.cuda.Stream()` aux streams
  unconditionally.
- `DeepseekV4MLAAttention` creates `torch.cuda.Event()` objects and asserts
  FlashMLA sparse attention.
- DeepSeek V4 attention requires an fp8-style KV cache and mutates
  `cache_config.cache_dtype` to `fp8_ds_mla`.
- `DeepseekV4MegaMoEExperts` is explicitly CUDA/SM100 only. Avoid
  `--kernel-config moe_backend=deep_gemm_mega_moe` on B70; start with regular
  `FusedMoE`.
- The official inference folder is not a vLLM path. It uses conversion,
  `torchrun`, TileLang kernels, and GPTQModel/Marlin-style W4A16 helpers.

## Initial Hypothesis

The first viable vLLM/XPU path should use:

- `FusedMoE`, not DeepGEMM MegaMoE;
- vLLM `inc` W4A16 for dense and MoE linear weights;
- small `max_model_len` for bring-up, likely `2048`;
- `--kv-cache-dtype fp8` or `fp8_ds_mla` if accepted by CLI/config;
- `--tensor-parallel-size 4`;
- no speculative decoding;
- no prefix caching during bring-up;
- no LocalMaxxing submission until quality gates exist.

## Immediate Patch Targets

1. Replace or guard unconditional CUDA stream/event creation in the DeepSeek V4
   model and attention code.
2. Determine whether the sparse MLA backend can run on XPU. If not, add a
   correctness-first XPU fallback before optimizing.
3. Confirm `INCConfig` maps the checkpoint's AutoRound config and handles
   `extra_config` for `head` and `embed` without quantizing the wrong tensors.
4. Verify W4A16 `FusedMoE` parameter names for DeepSeek V4 experts match vLLM's
   `FusedMoE.make_expert_params_mapping` path.
5. Add DeepSeek V4 quality canaries once the model produces text.

## First Commands To Try

```bash
cd /home/steve/llm-optimizations/experiments/deepseek-v4-flash-autoround-vllm
bash scripts/download-model.sh

INPUT_LEN=64 OUTPUT_LEN=16 MAX_MODEL_LEN=2048 RUN_TIMEOUT=30m \
  bash scripts/bench-vllm-deepseek-v4-flash-autoround-xpu.sh
```

Expected result before patches: failure during config/model construction or
attention backend setup. Capture the exact log in `results/experiment-ledger.md`
before changing vLLM.
