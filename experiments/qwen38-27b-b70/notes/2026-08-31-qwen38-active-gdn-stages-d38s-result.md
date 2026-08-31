# Qwen3.8 active packaged GDN exception capture D38s result

D38s successfully preserved the exception. The server imported
`/opt/venv/lib/python3.12/site-packages/vllm/.../qwen_gdn_linear_attn.py`; that
module had no `_use_deterministic_xpu_quantized_prefill` because r2 patched only
`/workspace/vllm`. The hook raised `AttributeError` at the first M=71 prefill
request. This is a decisive import-path finding, not a model failure.

A neutral-directory import check shows r1 has the helper in the actual runtime
module and r2 does not. D39 returns to r1 with the non-invasive forward wrapper.
