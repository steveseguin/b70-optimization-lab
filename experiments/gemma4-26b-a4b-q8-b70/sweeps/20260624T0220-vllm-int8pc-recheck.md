# 2026-06-24T0220: vLLM INT8 per-channel recheck

Goal: recheck the vLLM/XPU INT8-per-channel lane after the fresh-response
validity correction, using one complete Gemma 4 26B A4B replica on one B70 and
no prefix-cache reuse. This is a quality-compatible INT8-or-better lane, but it
must beat the llama.cpp Q8 draft-MTP fresh record to matter.

Current valid llama.cpp comparison:

- `data/gemma4-q8-gpu0-mtp-n7-c926-fastargmax-cpucleanup-vmm0-ub512-poll100-full-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T222838Z/`
- fresh headline: `92.397 tok/s` for the first measured request after TTFT
- supporting repeat mean: `92.767 tok/s`
- canary: `384/384`
- all measured benchmark rows had `cached_tokens=0`

## Graph-off smoke

Run directory:

- `data/gemma4-vllm-int8pc-gpu0-ctx4096-mbt512-smoke-20260624T021537Z/`

Server log:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-int8pc-gpu0-ctx4096-mbt512-smoke-20260624T021537Z.server.log`

Identity:

- model: `/mnt/fast-ai/llm-cache/hf/models--google--gemma-4-26B-A4B-it/snapshots/20da991ab4afab98e8f910c4a2e8f4fbefc404ad`
- runtime: vLLM `0.20.2rc1.dev13+g9557d9108.d20260620`, XPU
- quantization: `int8_per_channel_weight_only`
- dtype: `bfloat16`
- TP/PP/DP: `1/1/1`
- `MAX_MODEL_LEN=4096`, `MAX_NUM_BATCHED_TOKENS=512`, `MAX_NUM_SEQS=1`
- `--no-enable-prefix-caching`, `--language-model-only`, `--generation-config vllm`
- `ONEAPI_DEVICE_SELECTOR=level_zero:*`, `ZE_AFFINITY_MASK=0`
- graph disabled: `XPU_GRAPH=0`, `VLLM_XPU_ENABLE_XPU_GRAPH=0`

Result:

- canary: `32/32` pass
- fresh first request after TTFT: `25.913 tok/s`
- wall throughput: `25.168 tok/s`
- TTFT: `0.585 s`
- prompt/completion: `588 / 512`
- `cached_tokens` was not reported by vLLM for this response, but prefix
  caching was disabled and only one benchmark request was measured.

Decision: valid but far below the llama.cpp Q8 draft-MTP lane. Do not promote.

## PIECEWISE graph smoke

Label:

- `gemma4-vllm-int8pc-gpu0-ctx4096-mbt512-piecewise-smoke-20260624T021813Z`

Server log:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-int8pc-gpu0-ctx4096-mbt512-piecewise-smoke-20260624T021813Z.server.log`

Additional graph config:

```bash
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":2}'
```

Outcome: rejected at startup. The run did not reach canaries. Torch/Inductor
tried to compile a Triton kernel for B70 and `ocloc` failed with an IGC internal
compiler error:

```text
RuntimeError: `ocloc` failed with error code 245
IGC: Internal Compiler Error: Floating point exception
Build failed with error code: -11
Command was: ocloc compile ... -spirv_input -device bmg
```

The server was stopped manually after the compiler failure repeated and no
benchmark artifacts were produced.

## PIECEWISE graph control at prior shape

Label:

- `gemma4-vllm-int8pc-gpu0-ctx8192-mbt1024-piecewise-control-20260624T022345Z`

Server log:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-vllm-int8pc/servers/gemma4-vllm-int8pc-gpu0-ctx8192-mbt1024-piecewise-control-20260624T022345Z.server.log`

Additional graph config:

```bash
MAX_MODEL_LEN=8192
MAX_NUM_BATCHED_TOKENS=1024
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}'
```

Outcome: rejected at startup with the same current-stack compiler failure as the
smaller PIECEWISE smoke. The server did not become ready, and only an empty
readiness artifact was produced under:

- `data/gemma4-vllm-int8pc-gpu0-ctx8192-mbt1024-piecewise-control-20260624T022345Z/models.json`

The failure signature again was:

```text
RuntimeError: `ocloc` failed with error code 245
IGC: Internal Compiler Error: Floating point exception
Build failed with error code: -11
Command was: ocloc compile ... -spirv_input -device bmg
```

## Interpretation

This confirms the prior vLLM screening:

- vLLM INT8-per-channel is mechanically useful as a compatibility reference,
  but graph-off decode is much slower than llama.cpp Q8 MTP.
- On the current local vLLM/XPU source and compiler stack, the PIECEWISE graph
  lane that previously reached about `35 tok/s` no longer reaches readiness; it
  fails in Triton/IGC compilation.
- The current online quantization logs say only MoE expert weights are
  quantized; dense linear layers remain BF16, which likely explains much of the
  speed gap.
- PIECEWISE graph remains fragile on this B70/XPU/Triton/IGC stack for Gemma 4
  26B A4B and is not an immediate path to `>150 tok/s`.

Do not spend LocalMaxxing or promotion-depth validation budget here unless the
XPU compiler stack or vLLM Gemma quantization path changes substantially.
