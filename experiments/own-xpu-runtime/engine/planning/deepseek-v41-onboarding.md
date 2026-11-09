# DeepSeek V4.1 Flash: native engine onboarding handoff

Read-only audit findings, 2026-11-08. This packet supports development on
another computer. The owner targets **Unsloth Dynamic 3.0 GGUF of DeepSeek
V4.1 Flash used with llama.cpp**. Hardware, exact filenames, quant variant and
revision remain unconfirmed; do not silently choose 1017 or today's latest files.
**DeepSeek support is not implemented or qualified in the native engine.**

## Source baseline and boundaries

Start from the [canonical engine](../README.md), its
[onboarding audit](reusable-onboarding-audit.md), and the
[engine objective](../../../../docs/own-xpu-runtime-objective.md).
Implement our own native architecture adapter; external runtimes are reference
material, not the code base of our engine. Preserve existing SC117 kernels and
admission checks. No training is authorized.

The current profile admits SC117 `qwen4exp`, F32 activations and native context
4096. Other model geometry, formats and state layouts require an explicit new
capability path. Metadata planning alone does not supply native support.
The broader goal is reusable model and per-tensor quant interfaces that make
later onboarding and optimization quicker; no hours/days completion guarantee
follows from that goal. llama.cpp supplies a reference graph, GGUF semantics and
comparison execution; our native engine remains our own implementation.

## GGUF target takes priority

Unsloth's [model card](https://huggingface.co/unsloth/DeepSeek-V4.1-Flash-1017-GGUF/blob/2688c0c3c2c3b052ec4f6d10a8417b0ef7ee4eba/README.md)
and [local guide](https://unsloth.ai/docs/models/deepseek-v4.1-flash) confirm a
GGUF release for llama.cpp. Metadata-only inspection returned repository SHA
`2688c0c3c2c3b052ec4f6d10a8417b0ef7ee4eba`; its filenames include distinct
`UD-IQ3_S`, `UD-IQ3_XXS` and `UD-Q3_K_XL` shard sets, among other variants.
This is an observed candidate repository, not the owner's selected artifact.
The guide now advertises Dynamic V3.1, so latest `main` does not identify the
requested Dynamic 3.0 generation. **Dynamic 3.0 is a quantization generation,
not a declaration that every tensor is 3-bit.** Do not infer a filename from it.

Prioritize actual GGUF architecture metadata, per-tensor quant types, shapes,
block layouts/scales and any separate Engram/vision artifacts. Pin the matching
llama.cpp revision and supported graph semantics. The official FP8/FP4 config
below is architecture reference, not the chosen GGUF's storage contract;
implementing its native FP4 loader would not establish GGUF support.

## Verified official inputs

Metadata and source were inspected without downloading weights. HF API model
metadata returned these revisions on 2026-11-08:

| Candidate | Revision |
| --- | --- |
| DeepSeek-V4.1-Flash | `314113f8a7dadb388215396ba5fbee2c610a04d6` |
| DeepSeek-V4.1-Flash-1017 | `1bae0e1088993b9b82de08f59de5be5a34e42170` |

Pinned official configuration sources:

- [Flash config](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/314113f8a7dadb388215396ba5fbee2c610a04d6/config.json)
- [1017 config](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/blob/1bae0e1088993b9b82de08f59de5be5a34e42170/config.json)

The inspected configs expose matching geometry: 40 target layers, hidden width
5120, 384 routed experts, six active experts and expert width 2304. They declare
FP8 dense weights with 32-by-32 blocks, UE8M0 scales and FP4 expert weights.
They also declare Hyper-Connections, Engram, sliding-window plus compressed
sparse attention, shared KV/index sources, candidate filtering, vision and
DSpark. Matching configs do not imply matching checkpoint bytes or outputs.

Use the selected revision's complete reference, including:

- [Inference instructions](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/blob/1bae0e1088993b9b82de08f59de5be5a34e42170/inference/README.md)
- [model.py](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/blob/1bae0e1088993b9b82de08f59de5be5a34e42170/inference/model.py): model/state ownership and mixed-format operators.
- [Prompt encoding instructions](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/blob/1bae0e1088993b9b82de08f59de5be5a34e42170/README.md): supplied encoding implementation; no Jinja chat template.

The official inference directory also provides conversion, kernel, Engram and
vision implementations. Its uninitialized-weight self-test checks plumbing,
not numerical correctness. Its DSpark forward path is not a complete
speculative generation loop.

## Canonical local entry points

| Entry point | Reuse or extension |
| --- | --- |
| [deployment/prepare.py](../deployment/prepare.py) | `load_profile` and `parse_placement`: authenticated admission and geometry checks; add a distinct architecture capability. |
| [profiles/](../profiles/) | Model identity and launch policy separation; SC117 policy is not a DeepSeek default. |
| [placement.py](placement.py) | CPU per-tensor inventory and contiguous partition proposals. |
| [layout.hpp](../src/pipeline/layout.hpp) | Native stage slicing and first/final ownership. |
| [stage_ring.hpp](../src/pipeline/ring/stage_ring.hpp) | Row ownership, acceptance and rollback contracts. |
| [wire.hpp](../src/pipeline/ring/wire.hpp) and [ring_coordinator.py](ring_coordinator.py) | Boundary transport and coordination; validate resource bounds for the new representation. |
| [build.py](../build.py) | Existing canonical build entry point; its pinned toolchain requirements need separate host preparation. |

Historical [V4 lane](../../../deepseek-v4-flash-reap-xpu-b70/README.md) and
[fixed-geometry decoder plan](../../../../plans/2026-07-20-deepseek-v4-flash-option4-fixed-geometry-decoder-build-plan.md)
contain useful kernel, capture and correctness evidence. They concern an
experimental V4 K160 checkpoint and vLLM/XPU integration, not V4.1 native support.
Old shape patches use hidden 4096 and expert width 2048; do not copy those
dimensions into this adapter or transfer old speed claims.

## Ordered development gates

1. **Fix identity and scope.** Obtain the owner's GGUF repository revision,
   variant, complete shard names and any separate Engram/vision artifacts;
   authenticate GGUF headers, tokenizer/encoding and matching llama.cpp reference.
   Keep formats, geometry, topology and tuning separate. Pending exact identity
   does not block CPU source review; do not download weights for this handoff.
2. **Inventory and budget on CPU.** Account for every tensor's actual packed
   bytes and scales, Engram tables, host shadows, expanded weights, runtime
   reserves, caches, scratch and checkpoint/rollback copies. HF metadata reports
   about 763B stored parameter entries for the official candidates; that is not
   the selected GGUF's byte size or a residency guarantee. Use actual GGUF types
   and storage lengths; select execution placement from actual hardware.
3. **Build independent operator fixtures.** Cover required GGUF decoding/scaling,
   routing, Hyper-Connections, Engram hashing/history, attention/index selection,
   RoPE and shared-cache lifetime. Engram remains required for text inference.
4. **Implement plain autoregressive text inference.** Gate one operator, one
   layer, then short prefill/decode against a pinned same-GGUF reference. Use
   official model code to resolve architecture semantics, not as an oracle for
   different quantized weight bytes.
   Preserve declared cache precision and record arithmetic differences explicitly.
   Keep independent-reference fidelity separate from repeatability/internal parity.
5. **Qualify lifecycle and transport.** Prove cold reset, append, state ownership
   and rollback. Check stream/checkpoint bounds against actual serialized state;
   the existing ring's bounded F32 transport is not automatic model admission.
6. **Measure before tuning.** After a meaningful correctness gate, use cold,
   uncached workloads and full fair timing with complete identity. Introduce
   multi-device execution, DSpark and vision through separate qualified gates;
   do not inherit SC117 tuning or older V4 acceptance/performance results.

## Small first task for the incoming AI

CPU only: inspect the canonical loader/kernel capability inventory and the
selected llama.cpp DeepSeek graph/metadata readers. Produce one table of required
operators and GGUF tensor formats versus implemented native support, with source
paths and a smallest missing fixture for each gap. Mark unknown tensor types
pending the exact GGUF header instead of guessing them. If identity is still
pending, finish the source-side architecture inventory and clearly label it
provisional. Do not attempt the whole adapter, run a model, or relax admission
guards as this first task. A second AI should be able to pick one bounded gap
from the table and implement it without re-auditing the entire engine.

Use [DEVELOPING.md](../DEVELOPING.md) for the build. This architecture inventory
does not qualify a GPU launch or require service or host-setting changes.
Follow the receiving workspace's main-only Git and fault-handling rules.
