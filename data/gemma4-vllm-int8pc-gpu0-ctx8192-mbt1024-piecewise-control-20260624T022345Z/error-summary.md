# vLLM PIECEWISE graph startup failure

Label: `gemma4-vllm-int8pc-gpu0-ctx8192-mbt1024-piecewise-control-20260624T022345Z`

This run repeated the prior successful-shape control (`8192/1024`,
PIECEWISE graph, compile size `[1]`) against the current local vLLM/XPU stack.
It did not reach readiness or canaries and was stopped after the same
Triton/IGC compilation failure.

Server log:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-int8pc-gpu0-ctx8192-mbt1024-piecewise-control-20260624T022345Z.server.log`

Key identity:

- Gemma 4 26B A4B HF BF16 snapshot
- vLLM `0.20.2rc1.dev13+g9557d9108.d20260620`
- `QUANTIZATION=int8_per_channel_weight_only`
- `MAX_MODEL_LEN=8192`
- `MAX_NUM_BATCHED_TOKENS=1024`
- `XPU_GRAPH=1`
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`
- `COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}'`

Failure signature:

```text
RuntimeError: `ocloc` failed with error code 245
IGC: Internal Compiler Error: Floating point exception
Build failed with error code: -11
Command was: ocloc compile ... -spirv_input -device bmg
```
