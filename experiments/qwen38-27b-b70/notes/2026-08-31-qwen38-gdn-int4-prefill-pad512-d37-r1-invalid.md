# Qwen3.8 GDN INT4 prefill pad D37 r1 image receipt

The r1 image is **invalid before model execution**. Its Docker layer patched
`/opt/venv/lib/python3.12/site-packages/vllm`, but Python resolves this image's
editable vLLM checkout from `/workspace/vllm`. An import smoke test found the
new constants absent from the loaded module. No model request or benchmark was
run with r1.

The r2 build targets `/workspace/vllm`, binds source head
`ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`, compiles the active file, and must
pass an import-path receipt before model execution.
