# Deploying MiniMax M2.7 INT4 on 4x Intel Arc Pro B70

This note is for a future user or agent starting with a fresh Ubuntu 24.04 machine. It explains what is being built, why the steps matter, and how to validate the result before using the endpoint.

## What You Are Building

You are building a local OpenAI-compatible text-generation server:

- `vLLM` provides the HTTP API and scheduling engine.
- `PyTorch XPU` provides Intel GPU support.
- `Level Zero` is the low-level Intel GPU runtime.
- `oneCCL/XCCL` provides multi-GPU communication.
- `vllm-xpu-kernels` provides native XPU kernels used by vLLM.
- `llm-scaler` provides custom Intel ESIMD kernels for the MiniMax INT4 MoE decode path.
- `Lasimeri/MiniMax-M2.7-int4-AutoRound` provides the model weights.

The endpoint is compatible with common OpenAI-style clients:

- `GET /v1/models`
- `POST /v1/completions`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /health`
- `GET /metrics`

The endpoint in this repro uses `--host 0.0.0.0`, so it is accessible on the LAN if the host firewall and network allow it.

The current serving default is a `24576`-token context window. The comparable
quality/speed gate still uses a `2048`-token context so new runs can be compared
against the original p512/n1536 benchmark.

## Hardware and OS Checklist

Before installing:

- Confirm all four B70 GPUs are installed.
- Use Ubuntu 24.04.x.
- Have at least 512 GB free SSD/NVMe space.
- Expect a long native build, especially on low-RAM systems.

After the Intel packages and reboot:

```bash
xpu-smi discovery
clinfo -l
lspci | grep -i intel
```

Expected:

- `xpu-smi discovery` lists four `Intel(R) Arc(TM) Pro B70 Graphics`.
- `clinfo -l` lists four Intel GPU devices.
- Topology may show `NODE` between GPUs; that was normal on the originating host.

## Why 16 GB RAM Is Still Possible

The model is too large to casually keep everything in RAM, but the runtime can work because weights live on the GPUs and the disk is used for model files and compile caches.

The build is the hard part. The `vllm-xpu-kernels` compile of `paged_decode_xe2.cpp` reached roughly 120+ GB RSS on the originating host. The repro script creates a temporary `160G` swap file to survive that compile on machines with only 16 GB RAM. This is slow but practical on SSD.

If the compiler is killed:

1. Keep or recreate the swap file.
2. Rerun `scripts/03-build-stack.sh`.
3. Use conservative parallelism: `VLLM_XPU_KERNELS_MAX_JOBS=4` or `8`.

## Recommended Directory Layout

The scripts default to:

```text
/mnt/fast-ai/
  llm-models/
  llm-cache/hf/
  bench-results/
  vllm-cache-exp/
  src/
```

The model path used by vLLM:

```text
/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround
```

## Install Flow

Use the new repro folder:

```bash
cd llm-optimizations/repro/minimax-m27-b70-110tps-ubuntu24-20260523
sudo bash scripts/00-install-system-deps.sh
sudo reboot
```

After reboot:

```bash
sudo bash scripts/01-prepare-storage.sh
bash scripts/02-download-model.sh
bash scripts/03-build-stack.sh
bash scripts/04-verify-runtime.sh
bash scripts/05-run-quality-and-benchmark.sh
bash scripts/06-serve-openai-compatible.sh
```

In another terminal:

```bash
bash scripts/07-smoke-test-endpoint.sh
```

## Build Order Matters

The successful order was:

1. Install Intel system packages and oneAPI.
2. Install PyTorch `2.11.0+xpu`.
3. Build `vllm-xpu-kernels` from source against that PyTorch.
4. Build `llm-scaler` custom MiniMax INT4 kernels against that PyTorch.
5. Install patched vLLM editable.
6. Run runtime import checks.
7. Run quality gates.
8. Run benchmarks.
9. Serve.

Do not install a prebuilt `vllm-xpu-kernels` wheel and assume it is ABI-compatible. It was not compatible during this bring-up.

## Critical Environment Choices

Use:

```bash
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
```

Avoid:

```bash
source /opt/intel/oneapi/setvars.sh
```

On the originating host, the umbrella `setvars.sh` selected oneAPI 2026 and caused SYCL build problems. The direct 2025.3 compiler environment built successfully.

Runtime flags are collected in:

```text
repro/minimax-m27-b70-110tps-ubuntu24-20260523/configs/runtime-env.sh
```

Notable flags:

- `ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3`
- `ZE_AFFINITY_MASK=0,1,2,3`
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`
- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`
- `VLLM_XPU_USE_LLM_SCALER_MOE=1`
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1`
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1`

Some flags show as "unknown vLLM environment variable" in vLLM's generic env scanner. They are still consumed by patched code paths or local integration logic. Do not remove them without rerunning the full quality gate.

## Quality Before Speed

The quality gate prevents false wins. It checks exact token hashes and semantic canaries. This matters because many low-level optimizations can produce fast but degraded, nondeterministic, or degenerate output.

Passed checks on 2026-05-23:

- `raw145-n64-exact`
- `raw145-n256-exact`
- `semantic-suite-n64-r2`
- `arithmetic-repeat-n64-r16`
- `extended-sixpack-n64-r2`

If any of these fail, stop and fix quality before benchmarking.

## Throughput Interpretation

vLLM benchmark output reports total tokens per second. For a 512 input / 1536 output request, total token throughput includes prompt processing and generation.

2026-05-23 result:

- Mean total/effective throughput: `110.90 tok/s`
- Mean output-only throughput: `83.17 tok/s`

The user's target was `>90 tok/s`; this setup clears that target using total/effective throughput. If comparing to earlier "89 tok/s" and "94 tok/s" notes, those were output-token-focused lanes and are not strictly the same headline number.

The served 24,576-token endpoint was also checked through the OpenAI-compatible
API:

- Short decode, prompt 512 / output 1536: `83.79 output tok/s`.
- Near-full-context request, prompt 24,400 / output 64: completed without OOM.
- Short decode after that long-context request: `83.78 output tok/s`.

This means the larger served context did not reduce the normal short-request
decode lane after warmup.

## Serving

Start:

```bash
bash scripts/06-serve-openai-compatible.sh
```

Default bind:

```text
0.0.0.0:8000
```

Default context settings:

```text
VLLM_MAX_MODEL_LEN=24576
VLLM_GPU_MEMORY_UTILIZATION=0.95
```

The script allows overrides for controlled retests:

```bash
VLLM_MAX_MODEL_LEN=16384 bash scripts/06-serve-openai-compatible.sh
```

Find LAN IP:

```bash
hostname -I
```

Test:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/models
```

Expected `/v1/models` includes:

```json
{
  "max_model_len": 24576
}
```

Example OpenAI-compatible client base URL:

```text
http://<server-ip>:8000/v1
```

## Known Failure Modes

### Hugging Face download hangs

Symptom: no progress, stale sockets, process appears wedged.

Workaround:

```bash
export HF_HUB_DISABLE_XET=1
bash scripts/02-download-model.sh
```

### PyTorch 2.13 XPU AOT failure

Symptom during quality gate:

```text
AssertionError: Handler already registered for <function current_stream ...>
```

Workaround: use `torch==2.11.0+xpu`.

### vllm-xpu-kernels ABI mismatch

Symptom:

```text
undefined symbol: _ZNR5torch7Library4_defEON3c1014FunctionSchema...
```

Workaround: build `vllm-xpu-kernels` from source after PyTorch is installed.

### Native build OOM

Symptom: compiler killed or system becomes unresponsive during `paged_decode_xe2.cpp`.

Workaround: use SSD swap and lower `VLLM_XPU_KERNELS_MAX_JOBS`.

### `--async-engine` rejected by vLLM serve

Symptom:

```text
vllm: error: unrecognized arguments: --async-engine
```

Workaround: remove `--async-engine`. This checkout enables async scheduling internally.

### Intel `ocloc` internal compiler error

Symptom during server compile:

```text
IGC: Internal Compiler Error: Floating point exception
```

Observed behavior: nonfatal in the final server start; vLLM continued compiling/capturing graphs and served successfully. If it becomes fatal, wipe the relevant compile cache, reduce concurrency, and rerun. Preserve logs for Intel.

### Context window does not fit

Symptom:

```text
ValueError: To serve at least one request with the models's max seq len ...
Try increasing `gpu_memory_utilization` or decreasing `max_model_len`
```

Observed limits on the originating 4x B70 host:

- `32768` failed; vLLM estimated the maximum around `25600`.
- `25600` failed by a narrow KV-cache margin; vLLM estimated `25344`.
- `24576` passed and is the documented default.

This is VRAM/KV-cache headroom, not system RAM overflow. vLLM preallocates KV
cache memory, so `xpu-smi` can show roughly `32651 MiB` used and `100%` memory
utilization even when the server is idle.

## What To Improve Next

Useful next experiments:

- Recover the earlier 89-94 output-token lane on this more recent package stack.
- Compare `VLLM_CACHE_ROOT` values and cache warmness; cold compile can distort throughput.
- Try to recover more context only if memory pressure changes; this repro serves
  `24576`, while `32768` and `25600` did not fit on the tested stack.
- Investigate why server startup using the older promoted cache root emitted `ocloc` ICEs.
- Package prebuilt ABI-matched `vllm-xpu-kernels` artifacts to avoid the >120 GB source build on low-RAM users' machines.
- Convert the local wrapper scripts into one idempotent installer with explicit version locks and artifact caching.
