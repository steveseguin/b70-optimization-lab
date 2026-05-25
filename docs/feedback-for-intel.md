# Feedback For Intel

This is a discussion entry point. The detailed technical note is [Notes To Intel: Making 4x B70 vLLM/MiniMax Deployment Easier](intel-b70-minimax-feedback-20260523.md).

## Short Version

The B70 hardware is promising for local AI because 32 GB of VRAM below workstation-GPU pricing opens models that are awkward on 16 GB and 24 GB cards. The main problem is not the card. The main problem is that the software path is still too fragile for normal users.

The working MiniMax M2.7 INT4 deployment required a narrow combination of:

- Intel compute runtime packages.
- oneAPI compiler 2025.3, selected directly.
- PyTorch `2.11.0+xpu`.
- source-built `vllm-xpu-kernels`.
- patched vLLM.
- patched llm-scaler MiniMax kernels.
- large temporary SSD swap for a native compile.
- strict quality checks to reject fast-but-wrong optimization paths.

That is reasonable for a lab. It is not reasonable for a broad community install story.

## What Would Help Most

1. Publish a tested B70 vLLM compatibility matrix.
2. Publish ABI-matched `vllm-xpu-kernels` wheels for supported PyTorch XPU releases.
3. Provide a single "B70 local LLM doctor" command that checks drivers, Level Zero, PyTorch XPU, oneCCL, vLLM, native extension ABI, and cache permissions.
4. Make oneAPI compiler version selection explicit and warn on mixed header/library stacks.
5. Fix or make actionable the `ocloc`/IGC internal compiler error seen during Triton/Inductor compilation.
6. Upstream or register Intel/XPU/MiniMax vLLM environment flags so logs do not call important flags "unknown."
7. Ship small deterministic quality canaries for XPU examples so optimization work does not silently corrupt output.
8. Make CPU KV offload and paged attention XPU-aware, not CUDA-only.
9. Fix TurboQuant/XPU workspace allocation failures and document supported compressed-KV quality tradeoffs.
10. Investigate Level Zero `UR_RESULT_ERROR_DEVICE_LOST` during high-pressure vLLM session-cache reloads.

## Community Angle

The B70 can become useful community hardware if users can share recipes, not just screenshots. A good Intel-supported path would make it easy to publish:

- exact install recipe
- model and quantization
- benchmark shape
- quality check
- logs and artifacts
- known driver/runtime versions

This repository is structured around that idea: `docs/` for humans, `repro/` for install recipes, `notes/` and `data/` for detailed lab evidence.

## Messaging That Would Land Better

Community users are trying to run current models, not only old reference demos. Intel examples and launch content should include modern local-AI targets that enthusiasts actually care about, such as current Qwen, MiniMax, Kimi-class, GLM-class, and other frontier-adjacent open-weight models where licensing allows.

Useful public examples would include:

- one single-card recipe for a smaller model
- one two-card recipe for a 27B-class model
- one four-card recipe for a larger MoE model
- an OpenAI-compatible serving example
- a concurrency example
- a quality-validation example
- a long-context example that clearly distinguishes "parked sessions in RAM"
  from one large active-context request

The community conversation is not only "what is the top tok/s?" It is also:

- can it serve real tools?
- can it handle multiple users?
- can it fit the model I want?
- can an ordinary Linux user reproduce it?
- can Intel fix the install path before people give up?
