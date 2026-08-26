# Qwen3.8 official FP8 TP2 W8A16 MTP2-reuse screen preregistration

## Question

Can serially reusing Qwen3.8-27B-FP8's single publisher MTP layer for two
draft tokens improve fresh single-user decode over the selected MTP1 service
without weakening correctness?

This is **not** a native two-layer MTP checkpoint. The frozen model revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` declares
`text_config.mtp_num_hidden_layers=1`, and `mtp.safetensors` contains only
`mtp.layers.0`. vLLM warns that requesting more than one speculative token
reuses the same MTP layer and may reduce acceptance.

## Frozen identity

- model: `Qwen/Qwen3.8-27B-FP8` at
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image:
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122`, image ID
  `sha256:61bd8edb385c03b40cdadaba068608355b144a5011722597e7ca437f37346ecd`;
- vLLM `ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`;
- XPU kernels `1e90ffa672ba02f17a909da11838a4c55b199783`;
- block-W8A16 gate enabled, FP16 activations/KV, TP2, cache disabled, direct
  oneCCL P2P access;
- service: max model length 256, max 128 sequences, block size 64,
  `max_num_batched_tokens=512`;
- treatment: `qwen3_next_mtp` with `num_speculative_tokens=2`.

## One bounded screen

1. Start from a new vLLM cache directory and require `/health`.
2. Require the seven-case sequential semantic battery and eight-run repeat
   stability before performance is eligible.
3. Exclude one identical single-response conditioner, then measure one fresh
   cache-zero 40-prompt-token/128-output-token response with the same harness
   and seed as MTP1.
4. Only if single-user decode exceeds the MTP1 incumbent `61.699580 tok/s` by
   at least 1% may one output-audited c64 screen run. A later promotion would
   still require replicated performance and the concurrent semantic canary.

Any startup failure, semantic failure, incomplete output, nonzero cache use,
or sub-hurdle single-user result closes MTP2 reuse as a negative. No result is
interpolated or extrapolated, and no MTP2-reuse value may replace or be merged
with the native MTP1 profile.
