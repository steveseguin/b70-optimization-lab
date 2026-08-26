# Qwen3.8 Flash-Next FP8 intake and XPU bring-up boundary

Date: 2026-08-26

## Decision

Qwen3.8 Flash-Next FP8 is the active lane now that its pinned download has
finished. The older Qwen3.8-27B matrix and the DeepSeek 0731 REAP qualification
are paused without changing their protected results or launch identities.

No Qwen3.8 Flash-Next model load or GPU exposure is authorized yet. The model
is cryptographically complete, but the public day-zero runtime implementation
does not support XPU and the checkpoint cannot fit in four 32-GiB B70s without
host offload.

## Pinned model and completed storage gate

- Model: `Qwen/Qwen3.8-Flash-Next-FP8`
- Revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`
- Root: `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`
- Pinned tree SHA-256:
  `4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2`
- Root inventory: 144 files, 185,563,783,127 bytes
- Safetensors: 131 shards, 185,523,317,458 bytes
- Index closure: 152,089 tensors, `total_size=185502232570`

The sequential pinned validator passed at `2026-08-26T21:25:03Z`. It checked
all Git/LFS identities, the tokenless Hugging Face dry-run, every safetensors
header and payload range, and exact index-to-shard closure. Evidence is under:

`data/model-intake/post-download-validation-20260826/20260826T211840Z/`

The four stale `.incomplete` cache artifacts found after downloader exit were
moved intact to quarantine before validation. Their separate reconciliation is
in `model-intake/qwen38-flash-next-fp8-stale-cache-reconciliation-20260826.md`.
They were cache residue, not missing root payload.

## Architecture and memory boundary

The checkpoint is not another dense 27B lane:

- `Qwen4ExpForConditionalGeneration`, `qwen4_exp`;
- multimodal checkpoint, with a language-only deployment option;
- 48 language layers arranged as 12 repeats of three Gated DeltaNet layers and
  one Qwen Sparse Attention layer;
- 512 experts, 10 routed plus one shared expert per token;
- official model-card wording: 125B main model / 6B active, plus 51B n-gram
  embeddings and 4B MTP;
- one reusable MTP layer;
- native 262,144-token context;
- fine-grained block FP8, dynamic activations, 128x128 weight blocks.

The indexed tensor payload is 172.76 GiB. A naive TP4 split averages about
43.19 GiB per card, already about 11.19 GiB above each B70 before runtime,
recurrent state, KV cache, or graph allocations. Tensor divisibility itself is
not the blocker: the important head and expert counts divide across TP4, with
the small KV/indexer head counts replicated. Host placement of the large PLE
n-gram table is mandatory, and the remaining allocation still needs a measured
budget with several GiB per card of runtime headroom.

## Day-zero upstream/runtime state

Literal upstream heads were resolved before runtime work:

- vLLM `main`: `76cfe1cd88d30d525eec8be5bff75f8b77471c88`;
- vLLM XPU kernels `main`: `a397c58eb7781e6fe0d6b3fb7c25d21b5f658784`.

The vLLM main head has no `qwen4_exp` model registration, and the XPU support
table does not list this architecture. The implementation is in two open,
pinned vLLM PR heads:

- model support: PR 53896, head
  `02f2b4c15dd987d9436e125aab29604447c77405`;
- model plus PLE CPU offload: PR 53899, head
  `f561eca6ca4f3f79808a696b1521cb76dc8aafa2`, whose two source commits are
  `d4d0f73ef171154eac6f1914dca47001d662cfbb` and
  `f561eca6ca4f3f79808a696b1521cb76dc8aafa2`.

The PR package explicitly raises `NotImplementedError` on XPU/TPU and selects
only AMD or NVIDIA implementations. The official vLLM recipe likewise states
that the initial implementation does not support XPU/TPU and that PLE host
offload currently runs only on NVIDIA. It requires the dedicated image
`vllm/vllm-openai:qwen38-flash-next`, rather than PyPI. The image resolved on
2026-08-26 to amd64 manifest
`sha256:0aea30240f3e3d9ffae8526643950e170eb5fa07fc427016a9dd90892afa2aa3`,
created `2026-08-26T09:14:16.546129915Z`, but its OCI/source labels record the
build commit as `unknown`. It is CUDA 13.0, not an XPU runtime or a reproducible
B70 base, and it was not pulled.

Primary references:

- <https://github.com/vllm-project/vllm/pull/53896>
- <https://github.com/vllm-project/vllm/pull/53899>
- <https://recipes.vllm.ai/Qwen/Qwen3.8-Flash-Next>
- <https://github.com/QwenLM/Qwen3.8-Flash-Next>

## FP8/PLE correctness hazard and local confirmation

A day-zero Hugging Face discussion reports two Transformers text-only load
hazards: multimodal-prefixed exclusion names can fail to match text-only module
names, and the FP8 PLE table requires explicit global-scale dequantization.
This is an external report, not lab proof of a vLLM failure, but its checkpoint
facts were confirmed without reading tensor payloads:

- 128 tensors named
  `model.language_model.layers.1.ple.ple_embedding.ngram_embedding.shard_N.weight`
  are `F8_E4M3`, each shaped `[2500012, 160]`;
- the single
  `model.language_model.layers.1.ple.ple_embedding.ngram_embedding.weight_scale`
  is `BF16[1]`;
- the checkpoint's `modules_to_not_convert` names use the multimodal
  `model.language_model...` prefix.

PR 53899's NVIDIA PLE implementation explicitly retains the scale, returns FP8
lookup results from the host process, and dequantizes them to the output dtype
by multiplying by that scale. An XPU port must preserve and test that behavior;
silently casting FP8 rows is forbidden. It must also test the exclusion-name
mapping in the exact language-only load path.

External report retained as a lead only:
<https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8/discussions/2>.

## Frozen implementation order

1. Fast-forward the clean local vLLM source to the pinned newest `main`, then
   reapply the two pinned PR commits as an explicit overlay. Preserve conflict
   resolutions and the original PR identities; do not overwrite any older
   Qwen performance frontier.
2. Add an XPU backend using common PyTorch/reference paths first. Reuse the
   already-supported XPU GDN and MoE primitives where their exact interfaces
   match. Keep CUDA/ROCm-only kernels and graph paths disabled.
3. Port PLE host offload with exact global FP8-scale handling. Prove its memory
   allocation and process/IPC lifecycle in CPU-only static/unit tests; this is
   preparatory testing, not the final model result.
4. Require no-GPU registry/config/model-construction checks for Qwen4Exp,
   block-FP8, PLE, QSA, GDN, language-only processing, and TP4 shapes.
5. Produce a measured prelaunch memory budget that leaves runtime/KV headroom
   on every B70. Do not attempt a stock 172.76-GiB TP4 load.
6. First GPU canary, after independent review: all four B70s, language-only,
   TP4, MTP0/target-only, eager/no compile/no graph, no prefix cache, FP16/auto
   KV, one sequence, 512--2K model length, dedicated cache, exact-token plus
   semantic canaries, and mandatory cleanup.
7. Only after target correctness: qualify MTP1, then deeper MTP doses. Graph is
   last because the sibling Qwen XPU lane has known graph-plus-MTP corruption
   risk. The existing Qwen3.8-27B W8A16 patch stays off until base Qwen4Exp
   correctness passes.

No speed, quality, context, MTP, or production-readiness claim exists for this
checkpoint on B70 yet.
