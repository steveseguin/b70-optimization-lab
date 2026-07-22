# Laguna S 2.1 four-B70 bring-up recon (2026-07-21)

## Decision

Bring up the official **INT4 checkpoint in the existing DeepSeek vLLM-XPU
fork first**.  Laguna's target and DFlash model definitions, expert parallel
infrastructure, and generic group-32 INT4 dense/MoE kernels are already there.
The first hard delta is bounded: implement the checkpoint's online Hadamard
transform on XPU and make it TP-safe.  This path is substantially closer to
using all four cards for one decode stream than llama.cpp-SYCL.

Do not start with NVFP4.  Its fast kernels are NVIDIA-oriented and there is no
native XPU dense or MoE backend.  Do not download any checkpoint yet:
`/mnt/fast-ai` has only **7,316,484,096 bytes (6.81 GiB)** free, while the
official Q4 GGUF alone is **75,173,103,200 bytes (70.01 GiB)**.

## Load-today and porting verdict

| Backend / artifact | Loads on four B70s today? | Required delta | Engineering estimate |
|---|---|---|---|
| Protected local llama.cpp-SYCL at `e3546c7948e3` | **No** | It has no `LLM_ARCH_LAGUNA`, Laguna tensor map/model graph, or tokenizer pre-type.  Preserve this dirty tree.  Use a separate clean checkout of Poolside's `laguna` branch or the open upstream PR. | Clean-checkout base load smoke: 4-8 hours; SYCL correctness/performance validation: 1-2 days. |
| Poolside llama.cpp Laguna branch / upstream PR | **Partial** | The graph covers the target, but upstream PR #25165 remains open and is base-model-only; Poolside's branch also carries DFlash.  On SYCL, `MUL_MAT_ID` rejects split buffers, so layer split may fit the model but will not combine four-card memory bandwidth for MoE decode. | Base + DFlash validation: 1-3 days.  A real four-card split-buffer/EP throughput path: **5-10+ days**. |
| Customized vLLM-XPU + official INT4 | **No, unchanged** | Target/DFlash definitions and W4A16 kernels exist.  Add an XPU 128-wide FWHT/Hadamard op, remove the current TP>1 transform restriction correctly, and validate group-32 compressed-tensors layout, EP4, shared expert, and quality. | **2-3 days** to a credible load/parity result; another **3-7 days** for Laguna-specific single-stream tuning. |
| vLLM-XPU + official NVFP4 | **No** | New XPU NVFP4 dense and MoE support or a conversion is required.  Current selection tables expose CUDA/ROCm paths, not XPU. | Several days before tuning; worse first target than INT4. |

“Partial” does not mean a verified B70 load.  Recon intentionally performed no
build, model load, or GPU job.  The BF16 repo is about 219 GiB and cannot fit in
128 GiB VRAM; the FP8 repo is about 112.7 GiB and leaves impractical runtime
headroom.

## llama.cpp-SYCL findings

Upstream architecture support is not merged.  [llama.cpp PR
#25165](https://github.com/ggml-org/llama.cpp/pull/25165) is still open; its
reported Q4 test is useful evidence but not an Intel/SYCL or four-GPU result.
[Poolside's `laguna` branch](https://github.com/poolsideai/llama.cpp/tree/laguna)
contains both the target and DFlash.  Its Laguna graph is composed from
ordinary ggml operations: attention Q/K RMS norms, per-head softplus gates,
two RoPE modes, sigmoid top-k routing, routed and shared experts.  See
[Poolside's graph implementation](https://github.com/poolsideai/llama.cpp/blob/04b2b72cb54048ead292884adbe11f284e3ec950/src/models/laguna.cpp#L150-L349).

The protected local checkout does not know the architecture:

- architecture enum/table: `/home/steve/src/llama.cpp/src/llama-arch.h:125` and
  `/home/steve/src/llama.cpp/src/llama-arch.cpp:110`;
- model loader switch: `/home/steve/src/llama.cpp/src/llama-model.cpp:275`;
- tokenizer pre-types: `/home/steve/src/llama.cpp/src/llama-vocab.cpp:2340`.

The primitive SYCL coverage is encouraging: sigmoid/softplus are registered at
`/home/steve/src/llama.cpp/ggml/src/ggml-sycl/ggml-sycl.cpp:8916`, RoPE/YaRN at
`:9189`, and top-k through 32 at `:9213`; head-dimension-128 flash attention is
covered at `/home/steve/src/llama.cpp/ggml/src/ggml-sycl/fattn.cpp:136`.
GQA ratios 6 and 9 have a generic fallback at
`/home/steve/src/llama.cpp/ggml/src/ggml-sycl/fattn-tile.hpp:1162`, and Q4/Q6
MoE GEMV exists at `/home/steve/src/llama.cpp/ggml/src/ggml-sycl/mmvq.cpp:3614`.
Thus no Laguna math primitive looks novel.

The blocker for this optimization goal is distribution, not parsing: SYCL's
`MUL_MAT_ID` path asserts that split buffers are unsupported at
`/home/steve/src/llama.cpp/ggml/src/ggml-sycl/ggml-sycl.cpp:5456`.  A layer
split can distribute capacity but ordinarily executes each MoE layer on only
one card, leaving the other three cards' bandwidth idle.  That makes the
apparently shorter llama.cpp bring-up a poor first route to maximum
single-session throughput.

## vLLM-XPU findings

Laguna is no longer a missing model definition.  Upstream merged the target in
[vLLM PR #41129](https://github.com/vllm-project/vllm/pull/41129) and Laguna
2.1 DFlash in [PR #46853](https://github.com/vllm-project/vllm/pull/46853).
The clean DeepSeek fork at `e4af6e380dc1be771a8695720e688ff12af5169d`
registers them at:

- `/home/steve/src/deepseek-v4-vllm-xpu-dspark/vllm/model_executor/models/registry.py:142`;
- `/home/steve/src/deepseek-v4-vllm-xpu-dspark/vllm/model_executor/models/registry.py:597`.

Its Laguna model implements sigmoid routing, top-10 and the shared expert at
`vllm/model_executor/models/laguna.py:120`, attention gating and dual attention
at `:249`, per-layer head counts at `:493`, and the mixed cache policy at
`:590`.  The DFlash integration is in
`vllm/model_executor/models/laguna_dflash.py:244`.

The official [INT4
configuration](https://huggingface.co/poolside/Laguna-S-2.1-INT4/blob/main/config.json)
uses compressed-tensors group-32 W4A16 with online Hadamard transforms.  This
checkpoint also mixes INT4 and grouped INT8 layers; the local tree contains
the relevant mixed grouped-WNA16 landing.  The transform is the immediate XPU
load blocker:

- `vllm/model_executor/layers/quantization/compressed_tensors/transform/module.py:49`
  rejects online transforms when tensor parallel size is greater than one;
- the runtime call at the same file `:95` reaches
  `vllm/_custom_ops.py:3837`, which unconditionally calls
  `torch.ops._C.hadacore_transform`;
- only a CUDA implementation is present, while
  `vllm/platforms/xpu.py:114` explicitly does not import `vllm._C`.

Dropping the transform is not a quality-valid workaround.  Implement and test
the transform instead.

The rest of the INT4 route is present.  The dense XPU W4A16 backend accepts
group sizes divisible by 32 at
`vllm/model_executor/kernels/linear/mixed_precision/xpu.py:20`; XPU MoE
accepts group-32 INT4 at
`vllm/model_executor/layers/fused_moe/experts/xpu_moe.py:261`; its oracle
selects XPU at
`vllm/model_executor/layers/fused_moe/oracle/int_wna16.py:94`; and the paired
kernel tree launches the grouped INT4 expert GEMMs at
`/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/fused_moe_interface.py:984`.
Relevant upstream landing work includes [XPU W4A16 MoE PR
#41426](https://github.com/vllm-project/vllm/pull/41426), [group-32 PR
#45136](https://github.com/vllm-project/vllm/pull/45136), and [mixed grouped
WNA16 PR #47154](https://github.com/vllm-project/vllm/pull/47154).

Native NVFP4 is not an alternative shortcut.  The local linear backend table
has CUDA/ROCm entries but no XPU entry at
`vllm/model_executor/kernels/linear/__init__.py:446`; its MoE oracle similarly
selects NVIDIA/ROCm-oriented implementations at
`vllm/model_executor/layers/fused_moe/oracle/nvfp4.py:38`.

Compared with the DeepSeek custom-kernel baseline, generic INT4 grouped GEMM,
TP4/EP4, and scheduling machinery are reusable.  The headline DeepSeek direct
paths are not: they are specialized for 40 local / 160 global MXFP4 experts at
`vllm_xpu_kernels/fused_moe_interface.py:292`, and its specialized router only
accepts top-k through 8 at
`csrc/xpu/sycl/deepseek_m1_biased_topk.cpp:220`.  Laguna needs 64 local / 256
global experts and top-10, so record-speed work follows successful generic-path
bring-up.

One configuration fixture also deserves an early unit test: the local fallback
config converter flattens `rope_parameters` at
`vllm/transformers_utils/configs/laguna.py:70`, whereas the model reads Laguna
2.1's nested full/sliding entries.  Hugging Face remote config loading may
avoid this path, but a config-only test should prove it before downloading
weights.

## Architecture feasibility

The phrase “per-head-gated MoE” conflates two independent mechanisms in the
published config:

- **Attention** has a learned per-query-head softplus output gate.
- **MoE** uses a per-token sigmoid router over 256 experts, selects top-10,
  normalizes and scales routed output by 2.5, and adds one shared expert.

Neither mechanism requires a novel primitive in the Poolside llama.cpp graph
or the vLLM model.  The remaining quirks are validation/performance cases:

- 48 full-attention Q heads versus 72 sliding-attention Q heads, always 8 KV
  heads and head dimension 128 (GQA ratios 6 and 9);
- 12 full and 36 sliding layers, sliding window 512;
- full attention uses RoPE theta 500,000 plus YaRN and partial rotary 0.5;
  sliding attention uses theta 10,000;
- TP4 divides both Q-head counts and the eight KV heads cleanly; EP4 assigns 64
  routed experts per rank.

The official [base config](https://huggingface.co/poolside/Laguna-S-2.1/raw/main/config.json)
and [model card](https://huggingface.co/poolside/Laguna-S-2.1) are the authority
for these values.  The Poolside llama.cpp graph and local vLLM implementation
cover them.  On llama.cpp the four-GPU split limitation is the significant
blocker; on vLLM it is the checkpoint transform followed by shape-specific
kernel validation.

## GGUF, disk, tokenizer, and speculative decoding

A range-only inspection fetched the first 16 MiB of the Q4 object into a
sparse temporary file; no full weights were downloaded.  The header reports
GGUF v3, 814 tensors, 56 metadata keys, and
`general.architecture = "laguna"`.  It contains Q/K norms, per-head attention
gate weights, routed expert/router tensors, and shared-expert tensors.  The
tokenizer metadata says `tokenizer.ggml.model = "gpt2"` and pre-tokenizer
`laguna`: this is a fast **byte-level BPE**, not SentencePiece (100,352-token
vocabulary; 100,026 merges).

The official [GGUF repository](https://huggingface.co/poolside/Laguna-S-2.1-GGUF)
publishes:

| File | Exact object bytes | GiB |
|---|---:|---:|
| `Laguna-S-2.1-Q4_K_M.gguf` | 75,173,103,200 | 70.010 |
| `Laguna-S-2.1-DFlash-F16.gguf` | 2,233,764,000 | 2.080 |
| Q4 target + draft | 77,406,867,200 | 72.090 |
| `Laguna-S-2.1-Q8_0.gguf` | 127,650,800,960 | 118.884 |
| `Laguna-S-2.1-F16.gguf` | 235,202,258,240 | 219.049 |

At recon time `df -B1 /mnt/fast-ai` reported 7,316,484,096 bytes free on a
982,240,026,624-byte filesystem (100% displayed use).  The Q4 target is short
by **67,856,619,104 bytes (63.20 GiB)**; target plus draft is short by
**70,090,383,104 bytes (65.28 GiB)**.  Operational headroom, conversion space,
logs, and cache mean substantially more than the exact deficit should be freed
or added before download.  The initial ~62 GB estimate therefore understates
the official GGUF object.  Poolside's official INT4 safetensors total about
71.9 GB (67.0 GiB), also far beyond current free space.

Poolside ships a trained [Laguna S 2.1 DFlash
draft](https://huggingface.co/poolside/Laguna-S-2.1-DFlash) plus FP8, INT4,
NVFP4, and GGUF variants.  It is a six-layer sliding-attention draft using
target hidden states; the config names target layers 1, 10, 19, 29, 38, and 47
(zero based) and allows up to 15 proposals.  This is **DFlash**, not a named
MTP or EAGLE checkpoint.  Some implementation fields reuse EAGLE plumbing,
but the artifact should not be relabeled.  No separate Poolside MTP/EAGLE
artifact was found in the official [Laguna S 2.1
collection](https://huggingface.co/collections/poolside/laguna-s-21).

Speculative support can stack after a correct target load:

- vLLM has merged Laguna 2.1 DFlash and the local XPU fork registers it, but it
  has no published XPU/B70 acceptance or quality validation;
- Poolside's llama.cpp branch carries DFlash and the official GGUF draft, while
  the open upstream base-model PR does not;
- generic runtime n-gram speculation may be available, but Poolside publishes
  no trained n-gram artifact or B70 result.  It is not a substitute for the
  strict cold, target-verified DFlash gate used by the prior DeepSeek work.

## Proposed bring-up sequence (after disk is resolved and execution is authorized)

1. In the clean DeepSeek vLLM-XPU fork, add a config-only Laguna 2.1 fixture and
   prove nested RoPE/head layouts without weights.
2. Implement a reference-tested XPU FWHT/Hadamard transform and TP-safe
   application; test it independently at the checkpoint's 128 width.
3. Load official INT4 on TP4+EP4, first through generic kernels; run exact-token,
   semantic, arithmetic, and practical gates with `cached_tokens=0`.
4. Establish the nonspec one-session control, then add DFlash with target-side
   verification and acceptance telemetry.
5. Profile Laguna's 64-local-expert/top-10 shapes before specializing router,
   direct-MoE, shared-expert overlap, graph capture, or collectives.

This preserves the prior DeepSeek framing: one active generation, never
aggregate throughput; cold prompts; no response/history/cache reuse; and no
speed promotion before target identity and quality are proven.

## Recon integrity

- Main repo was clean before creating this note (`main` ahead of origin by 245
  commits).
- The protected llama.cpp tree was inspected read-only and remains at
  `e3546c7948e3af463d0b401e6421d5a4c2faf565` with its pre-existing dirty
  changes untouched.
- The selected vLLM fork was inspected read-only and is clean at
  `e4af6e380dc1be771a8695720e688ff12af5169d`.
- No full checkpoint, build, GPU process, service mutation, or DeepSeek quality
  / held-out-pack access occurred.
