Independent end-to-end confirmation on Intel XPU (Arc Pro B70) that this PR fixes a server-killing crash, not only the GDN state width.

**Setup**: stock `vllm/vllm-openai-xpu:latest` (v0.29.0, image sha256:96db42e2, vllm-xpu-kernels 0.1.14.1), one B70, Qwen3.5-9B W4A16 (RedHatAI compressed-tensors), `--speculative-config '{"method":"qwen3_5_mtp","num_speculative_tokens":3,"num_speculative_tokens_per_batch_size":[[1,8,3],[9,16,1],[17,64,0]]}'`, `--max-model-len 256 --max-num-seqs 64`, greedy, 64-prompt suite compared against a sequential oracle.

**Stock v0.29.0**: 1 user (K=3) is fine. 12 concurrent users (K=1 range) kill the engine immediately, and a 64-user batch dies while draining through 9–16 running requests, with both the V1 runner and `VLLM_USE_V2_MODEL_RUNNER=1`:

```
RuntimeError: Expected spec_token == num_spec_decodes * (num_speculative_tokens + 1) to be true, but got false.
  File ".../vllm/_xpu_ops.py", line 171, in _gdn_attention_core_xpu_impl
```

vLLM's `dump_input` shows the batch: 12 cached requests, `scheduled_spec_decode_tokens` one draft each, `total_num_scheduled_tokens=24`. The XPU kernel derives K from `spec_state_indices_tensor.size(-1)` (4 columns) and expects 48 tokens. (Kernel-side report: vllm-project/vllm-xpu-kernels#593.)

**v0.29.0 + only the `vllm/v1/attention/backends/gdn_attn.py` hunks of this PR (head e981ca5, applied with `patch -p1`, kernels unchanged)**, same everything:

| users | result |
| --- | --- |
| 1 | 69.1 tok/s, exact vs oracle |
| 12 (K=1) | 242.9 tok/s, 12/12 exact vs oracle, all outputs complete |
| 64 (ramp K=0 → drain through K=1 → K=3) | 1083 tok/s, all outputs complete, no engine error |

So on XPU the narrowed state-index view is what makes runtime K < max K work at all. Happy to run anything else on this hardware if useful.
