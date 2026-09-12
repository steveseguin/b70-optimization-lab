End-to-end follow-up (same B70, no lab patches): on stock `vllm/vllm-openai-xpu:latest` (v0.29.0, kernels 0.1.14.1) a dynamic schedule `[[1,8,3],[9,16,1],[17,64,0]]` with Qwen3.5-9B W4A16 reaches this assertion in ordinary serving — 12 concurrent users (K=1, 24 tokens with a 4-column state-index tensor) kill the engine at once, and a 64-user batch dies while draining through 9–16 running requests, with both model runners:

```
RuntimeError: Expected spec_token == num_spec_decodes * (num_speculative_tokens + 1) to be true, but got false.
```

Applying only the `gdn_attn.py` hunks of vllm-project/vllm#53542 (which narrows `spec_state_indices_tensor` to the active width on the vLLM side) on top of v0.29.0, kernels unchanged, removes the crash: 12 users run 12/12 exact against a sequential oracle and the 64-user ladder completes. So the contract can be satisfied from the vLLM side; the kernel-side change discussed above is not required for correctness once #53542 lands. Details posted on that PR.
