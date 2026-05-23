# Notes To Intel: Making 4x B70 vLLM/MiniMax Deployment Easier

This note summarizes pain points and requests found while deploying MiniMax M2.7 INT4 on 4x Intel Arc Pro B70 GPUs with Ubuntu 24.04, PyTorch XPU, vLLM, llm-scaler, and Level Zero.

The final setup worked and quality-gated successfully, but the path is still too fragile for ordinary users.

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

