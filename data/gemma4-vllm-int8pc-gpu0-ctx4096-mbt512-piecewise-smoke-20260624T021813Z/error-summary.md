# vLLM PIECEWISE graph startup failure

Label: `gemma4-vllm-int8pc-gpu0-ctx4096-mbt512-piecewise-smoke-20260624T021813Z`

This run did not reach readiness or canaries. It was stopped after repeated
Triton/IGC compilation failure in the vLLM XPU stack.

Server log:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-int8pc-gpu0-ctx4096-mbt512-piecewise-smoke-20260624T021813Z.server.log`

Key identity:

- Gemma 4 26B A4B HF BF16 snapshot
- vLLM `0.20.2rc1.dev13+g9557d9108.d20260620`
- `QUANTIZATION=int8_per_channel_weight_only`
- `MAX_MODEL_LEN=4096`
- `MAX_NUM_BATCHED_TOKENS=512`
- `XPU_GRAPH=1`
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`
- `COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":2}'`

Failure signature:

```text
RuntimeError: `ocloc` failed with error code 245
IGC: Internal Compiler Error: Floating point exception
Build failed with error code: -11
Command was: ocloc compile ... -spirv_input -device bmg
```
