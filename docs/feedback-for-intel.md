# Feedback For Intel

This is a discussion entry point. The detailed technical note is [Notes To Intel: Making 4x B70 vLLM/MiniMax Deployment Easier](intel-b70-minimax-feedback-20260523.md).

## Short Version

The B70 hardware is promising for local AI because 32 GB of VRAM below workstation-GPU pricing opens models that are awkward on 16 GB and 24 GB cards. The main problem is not the card. The main problem is that the software path is still too fragile for normal users.

The other practical constraint is coverage. This repo is maintained by Steve
Seguin (`@xyster`) on a four-B70 host, so Intel/XPU feedback is currently
bounded by `4 x 32 GB = 128 GB` of VRAM and by the fact that long optimization
passes occupy the same cards needed for everyday inference. More Intel VRAM
per device would make this a much better proving ground for the larger models
that driver, compiler, and vLLM teams increasingly need to see in the wild.
There is spare EPYC 9015 platform capacity with up to ten PCIe 5.0 x16 slots;
the bottleneck is access to larger Intel GPUs and the time needed to cycle each
serious model lane through quality-gated optimization.

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
11. Where possible, make higher-VRAM Intel/XPU development hardware available
    to community repro labs. B70 is enough to expose many bugs, but
    Crescent Island-class `160-480 GB` hardware would let the same recipes cover
    GLM 5.2, DeepSeek Flash-class, and other larger-model lanes without turning
    every experiment into a capacity workaround.

## Community Angle

The B70 can become useful community hardware if users can share recipes, not just screenshots. A good Intel-supported path would make it easy to publish:

- exact install recipe
- model and quantization
- benchmark shape
- quality check
- logs and artifacts
- known driver/runtime versions

This repository is structured around that idea: `docs/` for humans, `repro/` for install recipes, `notes/` and `data/` for detailed lab evidence.

## Community Seeding And Mindshare

Intel's open driver/runtime posture is a real advantage for community research:
bugs can be described, reproduced, and often worked around in public. The part
that still needs help is hardware presence. Community mindshare comes from
people seeing current models run on hardware they can name, discuss, benchmark,
and eventually buy.

The B70 is already getting that kind of exposure through this repo, Steve
Seguin's `@xyster` posts, and LocalMaxxing submissions. Those artifacts make the
card easier to discover, easier to compare, and easier for future users or AI
agents to optimize against. Larger Intel devices should get the same treatment
early, before the public recipe surface is shaped mostly by enterprise-only
deployments.

For upcoming high-memory Intel GPUs, the most useful community enablement would
be loaner, eval, grant, or sponsored access that is compelling alongside small
CUDA dev boxes. In practice, the interesting
community threshold is not one more 32 GB card; it is enough Intel VRAM to make
large open models feel newly possible at home, roughly the `400-1000 GB`
aggregate range across high-memory devices.

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
