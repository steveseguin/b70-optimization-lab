# Notes To Intel: Making 4x B70 vLLM/MiniMax Deployment Easier

This note summarizes pain points and requests found while deploying MiniMax M2.7 INT4 on 4x Intel Arc Pro B70 GPUs with Ubuntu 24.04, PyTorch XPU, vLLM, llm-scaler, and Level Zero.

The final setup worked and quality-gated successfully, but the path is still too fragile for ordinary users.

Hardware-scope caveat: all measurements here come from a community lab with
four Arc Pro B70 32 GB cards. That `128 GB` aggregate footprint is enough for
MiniMax, Qwen, and Gemma work, but it leaves little room to test larger
frontier-adjacent open models while keeping a usable inference endpoint alive.
Additional high-VRAM Intel evaluation hardware would make the same
quality-gated workflow much more useful to vLLM/XPU, driver, compiler, and
business-unit teams looking for evidence on models beyond the current B70
capacity envelope.

## What Worked

- Four B70s were visible through `xpu-smi`, `clinfo`, PyTorch XPU, and vLLM.
- Level Zero/XPU with vLLM tensor parallel 4 successfully served MiniMax M2.7 AutoRound INT4.
- `torch==2.11.0+xpu` plus oneAPI compiler 2025.3 was stable enough to pass strict quality gates.
- llm-scaler ESIMD INT4 MiniMax MoE kernels worked across all 62 MoE layers.
- vLLM's OpenAI-compatible API served on `0.0.0.0:8000`.
- Effective benchmark throughput reached about `110.90 total tok/s` for p512/n1536.

## Main Friction Points

### 1. Native XPU kernel builds are extremely memory hungry

Building `vllm-xpu-kernels` from source required one compiler process around 120+ GB RSS for `paged_decode_xe2.cpp`.

Impact:

- Users with 16-64 GB host RAM can fail unless they provision huge SSD swap.
- Build time is long and failure recovery is unclear.
- It is hard for agents to distinguish "slow but healthy compile" from a hang.

Requests:

- Publish ABI-compatible `vllm-xpu-kernels` wheels for the supported PyTorch XPU versions.
- Split or reduce the highest-memory generated source files.
- Document expected peak memory per build target.
- Provide a supported low-RAM build mode, even if slower.

### 2. Version compatibility is too implicit

The successful stack required:

- PyTorch `2.11.0+xpu`
- oneAPI compiler 2025.3
- matching source build of `vllm-xpu-kernels`
- patched vLLM commit
- patched llm-scaler commit

An attempted newer PyTorch XPU nightly loaded the model but failed during vLLM torch.compile/AOT with a duplicate handler assertion.

Requests:

- Publish a tested compatibility matrix for:
  - PyTorch XPU
  - oneAPI compiler
  - Intel compute runtime
  - `vllm-xpu-kernels`
  - vLLM version/commit
  - oneCCL/XCCL
- Add a single "known-good for B70 vLLM" installation page.
- Expose a diagnostic script that checks all versions and explains mismatches.

### 3. `ocloc`/IGC internal compiler errors need better handling

During server startup, Triton/Inductor compilation emitted:

```text
IGC: Internal Compiler Error: Floating point exception
Build failed with error code: -11
```

The process eventually continued and the server started, but this is scary and ambiguous.

Requests:

- Fix the IGC crash for the emitted Triton reduction kernel.
- Include the failing SPIR-V and options in a durable repro directory by default.
- Return actionable diagnostics: driver/runtime/compiler versions, target device, and known workaround hints.
- Make transient/fallback behavior explicit in the logs.

### 4. oneAPI environment selection is easy to get wrong

Using `/opt/intel/oneapi/setvars.sh` selected a newer compiler stack that caused build trouble. Directly sourcing `/opt/intel/oneapi/compiler/2025.3/env/vars.sh` worked.

Requests:

- Document exact compiler env selection for PyTorch XPU/vLLM builds.
- Provide a "pin compiler version" helper.
- Warn when headers/libraries from mixed oneAPI versions are detected.

### 5. The "unknown vLLM environment variable" warnings hide useful integration flags

Patched/local vLLM paths used several `VLLM_*` flags, while vLLM's generic environment scanner warned they were unknown.

Impact:

- Operators may remove important flags because logs imply they are mistakes.

Requests:

- Upstream or register the Intel/XPU/MiniMax env vars.
- Include owner/module metadata in env-var warnings.
- Add a way for extension packages to register accepted runtime flags.

### 6. Quality validation needs to be first-class

Performance work on MoE, graph capture, custom allreduce, and logits paths can silently change output quality.

Requests:

- Ship small deterministic quality canaries with vLLM XPU examples.
- Publish expected token hashes for known model/config pairs.
- Include "speed is invalid unless quality passed" guidance in optimization docs.

### 7. CPU KV offload is CUDA-shaped and needs an XPU path

The native vLLM CPU KV offload path rejected XPU before a local prototype was
added:

```text
CPU Offloading is currently only supported on CUDA-alike GPUs
```

A local XPU worker prototype showed that pinned host RAM, XPU streams/events,
and multi-GB KV movement can work on this stack. It moved CPU-to-GPU KV around
`14-16 GB/s` in session-cache tests. The remaining limitation is that XPU
FlashAttention still needs the active request's working KV blocks resident in
live GPU KV memory.

Requests:

- Provide an official XPU CPU KV offload worker.
- Document whether pinned host memory should use PyTorch XPU, SYCL USM, or
  Level Zero allocation APIs.
- Add XPU test coverage for prefix cache reloads and long-context attention.
- Make it clear in docs whether CPU KV offload means "session parking" or true
  active-context overflow.

### 8. Session-cache reload can hit Level Zero device loss

In c4 session-cache service testing, vLLM started with `34304` GPU KV tokens and
`8.0 GiB` CPU KV budget per tensor-parallel worker. A later operational smoke
hit a Level Zero device-lost error while copying vLLM block-table state back to
GPU:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

The stack was:

```text
gpu_model_runner.py:_prepare_inputs
block_table.py:commit_block_table
vllm/v1/utils.py:copy_to_gpu
```

Requests:

- Investigate device-loss behavior during non-blocking CPU-to-XPU metadata and
  KV reload copies under high scheduler pressure.
- Add recovery diagnostics that identify the specific XPU device, queue, and
  copy size involved.
- Provide guidance for safe `max_num_seqs`, KV offload size, and batched-token
  settings on B70.

### 9. TurboQuant on XPU needs workspace and quality guidance

TurboQuant is promising for KV capacity, but the first B70/XPU run failed with
a locked-workspace allocation error:

```text
Workspace is locked but allocation from turboquant_attn.py:_decode_attention
requires 0.19 MB, current size is 0.00 MB.
```

A local fallback patch allowed forward progress by allocating temporary buffers
when the shared workspace was locked. After that, `turboquant_k8v4` could start
at 32K and report about `80128` GPU KV tokens, but sustained decode was much
slower than the normal FP16-family KV lane.

Requests:

- Pre-size or grow TurboQuant workspaces correctly before they are locked.
- Provide XPU-specific TurboQuant examples and known-good settings.
- Publish quality guidance for FP8 KV versus TurboQuant modes on long-context
  reasoning and retrieval tasks.
- Make the failure mode actionable instead of a generic HTTP 500 from the
  OpenAI API path.

### 10. Long-context logprobs exposed NaN JSON serialization

Small OpenAI-compatible logprob requests worked, but long-context logprob
checks failed because NaN values escaped into JSON:

```text
Out of range float values are not JSON compliant: nan
```

Requests:

- Prevent NaN logprobs from escaping through the OpenAI JSON response path.
- Include the token index, model layer/backend context, and sampled logits
  shape when this happens.
- Provide a deterministic long-context token/logprob canary for XPU serving
  examples.

## Suggestions For A Streamlined Intel-Supported Path

An ideal user path would be:

```bash
sudo apt install intel-gpu-ai-runtime-b70-vllm
python -m venv .venv
. .venv/bin/activate
pip install torch-xpu-b70 vllm-xpu-b70 llm-scaler-minimax-kernels
intel-ai doctor --model minimax-m27-int4 --gpus 4
intel-ai serve-minimax --model /models/minimax --host 0.0.0.0 --port 8000
```

The `intel-ai doctor` command should verify:

- kernel driver
- Level Zero loader and devices
- XPU runtime
- PyTorch XPU availability
- oneCCL/XCCL
- vLLM XPU platform detection
- native extension ABI compatibility
- compiler cache directory writability
- expected B70 topology

It should also explain how much disk, RAM, and swap are needed.

## Concrete Bugs To Investigate

- PyTorch XPU nightly `2.13.0.dev20260520+xpu` duplicate handler assertion during vLLM torch.compile/AOT:
  - `AssertionError: Handler already registered for <function current_stream ...>`
- `vllm-xpu-kernels` prebuilt wheel ABI mismatch against the active PyTorch stack:
  - undefined torch `Library::_def` symbol.
- IGC/ocloc floating point exception compiling Triton reduction kernels:
  - command shape: `ocloc compile -spirv_input -device bmg`.
- Excessive memory use compiling `paged_decode_xe2.cpp`.
- Ambiguous/nonfatal `ocloc` failures during server warmup.
- CPU KV offload rejects XPU as non-CUDA-alike even though XPU streams/events
  and pinned host transfers are available.
- c4 session-cache reload can hit Level Zero `UR_RESULT_ERROR_DEVICE_LOST` in
  vLLM block-table `copy_to_gpu`.
- TurboQuant/XPU can hit locked-workspace allocation failures in
  `turboquant_attn.py`.
- Long-context OpenAI logprob responses can contain NaN values that break JSON
  serialization.

## What To Preserve For Repro Reports

When reporting issues, capture:

- `xpu-smi discovery`
- `clinfo -l`
- `dpkg-query -W 'intel-*' 'libze*' 'xpu-smi'`
- `python -c 'import torch; print(torch.__version__, torch.xpu.is_available(), torch.xpu.device_count())'`
- vLLM commit and local patch
- llm-scaler commit and local patch
- `vllm-xpu-kernels` commit
- full `ocloc` command and SPIR-V file if available
- vLLM compile cache path
- exact model path and benchmark shape
