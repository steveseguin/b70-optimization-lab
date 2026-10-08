# Screen 1 runtime/source review (2026-10-08; CPU only)

Scope: static portability and experiment preparation under the repository's
review-model-contribution skill. Lumnus/wu1ff deltas remain community-reported;
no new speed, exactness or safe memory-fit result has been measured.

## Runtime choice

Choose official `vllm/vllm-openai-xpu:v0.30.0`, resolved to the inspected amd64
manifest, with the reviewed Lumnus Python files mounted over the corresponding
installed files. This is the cheapest way to screen a modern runtime without a
native compile. Do not mount a whole `vllm/` directory over site-packages: that
can hide wheel-provided compiled/Rust artifacts. Run from `/`, because the image's
`/workspace/vllm` source checkout otherwise shadows the installed package.
Pin each overlaid file and the official image digest. This is a **partial modern
stack**, not Lumnus's complete served stack. Static compatibility is not proof of
successful FP8 loading or adequate GPU memory.

Source inputs in `/home/steve/src/lumnus-20261008/`:

- `vllm` HEAD `9d79d28d7e32f33bdbd115c85d116583ce679cb6`;
  official V30 `ced6857afa0ea7b2e3f0846a62e1394e90f15607`.
- Official xpu-kernels 0.1.14.1 `6d92b1bfbf32767ecda8e819613eb151e70030ad`.
- `b70-flash-next/patches/vllm/`, `image/verify-overlay.sh` and `PROVENANCE.md`
  describe Python file identities and scoped wu1ff/Lumnus authorship.

Stock V30 explicitly rejects XPU in `vllm/models/qwen4_exp/__init__.py`.
Lumnus patch 0001 enables the NVIDIA-derived implementation. The certified lab
line used AMD-derived model code; changed model lineage, graph/compiler,
collectives and MoE arithmetic all confound a pin mismatch. A fused GDN miss is
expected, but Screen 1 cannot isolate its cost from all these other changes.

**Unchanged checkpoint handling:** mount the original 131-shard tree read-only;
never run Lumnus `prepare-serve.sh` or use its supplied serve config. Those expect
an external PLE table and a dense-QSA configuration. Preserve the actual FP8
checkpoint's indexer keys and quantization exclusions, and do not enable
`B70_PLE_FP8`, `B70_PLE_INT8`, `B70_PLE_INT8_NVME`, external `PLE_TABLE_PATH`,
CPU KV offload, sampler defaults or the private residency shim.

### Memory route and its limits

The new model's exact suffix is still
`ple_embedding.ngram_embedding.weight`: `Qwen4ExpDecoderLayer.ple` contains
`Qwen4ExpPLELayer.ple_embedding`, which contains
`Qwen4ExpNGramEmbedding.ngram_embedding`.
`model_executor/models/utils.py:make_layers` routes each decoder layer through
`model_executor/offloader/uva.py:UVAOffloader.wrap_modules`; this covers PLE.
Token embeddings are outside that loop, so merely listing `embed_tokens.weight`
does not guarantee their offload. Keep them resident and budget ~0.3 GiB/rank.

A concrete no-native-port candidate is:

```text
--offload-backend uva --cpu-offload-gb 16.25
--cpu-offload-params ple_embedding.ngram_embedding.weight mlp.experts.w13_weight mlp.experts.w2_weight
--moe-backend triton
```

This is whole-tensor expert offload, not the lab's selected 3.5 GiB/rank expert-row
placement. It preserves all callable weights but can be slower on ordinary
prompts. The checkpoint declares `ple_layer_ids=[2]`: the first decoder layer's
expert tensors are considered before the second layer's ~11.92 GiB/rank PLE,
then later expert tensors consume the remaining budget. The UVA offloader checks
its budget before each parameter and can exceed it by one whole parameter.
The runtime must record actual offloaded bytes, served backend and memory fit;
16.25 GiB is an admission assumption, not a measured fit. Do not silently reduce
KV precision or change placement if it fails. The four ranks need approximately
65 GiB of pinned weight storage plus loading/runtime overhead; require a separate
host-RAM admission (100 GiB MemAvailable is conservative preparation guidance).

`platforms/xpu.py` automatically disables Inductor's static Triton launcher for
UVA. Without that, host-USM pointers can be rejected. `PLE_TABLE_PATH` is not a
safe dummy switch: it eventually invokes `torch.load` on that file. Selecting
Lumnus pinned-host PLE explicitly in source is an alternative, but its slab
materialization temporarily retains pageable and pinned copies and needs its own
memory audit. It is not needed merely to enable the existing generic UVA route.

### What missing b70.3 native changes lose

`b70-flash-next/docs/kernels.md` and
`patches/vllm-xpu-kernels/b70.3/` list seven changes:

| Native change absent from the official wheel | Consequence for this screen |
| --- | --- |
| `fa542f6`, int64 conv-state offsets | Large block indices can overflow signed 32-bit addressing; bound the actual cache geometry below that threshold. Lumnus's example fails at block 5,042 with stride 425,984. |
| `ba19ef4`, upstream #600, ragged speculation | Structured-output trimmed drafts may fail; no grammar/JSON-schema request is part of this fixed screen. This does not prove every ragged path unreachable. |
| `dd87485`, upstream #564, pinned UVA strides | Non-contiguous host views can have wrong strides; require contiguous offloaded tensors and inspect the actual route. |
| `d00fbf7`, upstream #563, unaligned-vocab top-k/top-p | Sampling correctness fix; greedy pin/suite requests avoid stochastic sampling, but retain the limitation. |
| `5fcc722`, upstream #578, negative expert IDs | EP padding guard missing in native XPU remap; the selected Triton/allgather-reducescatter path uses `moe_align_block_size`, not the affected `remap_hidden_states` route. Assert the served backend. |
| `e68951b`, upstream #586, grouped-GEMM counter initialization | Native Xe2 grouped-GEMM race fix absent; explicit Triton MoE avoids that expert implementation, subject to route verification. |
| `493364a`, B70-K1 direct pinned H2D KV copies | Faster transfers and bounded cached host staging for CPU KV offload; inactive here because CPU KV offload is disabled. |

The selected Triton route is source-distinct from `XpuFusedMoe`: its
`experts/triton_moe.py` calls `fused_moe._prepare_expert_assignment` and
`moe_align_block_size`; the affected `remap_hidden_states` callers are in
`vllm_xpu_kernels/fused_moe_interface.py` and `moe_utils.py`. Use explicit
`--all2all-backend allgather_reducescatter` and verify the actual backend at
startup. Keep missing native fixes visible as blockers if a different unsafe
route is selected. Python-only does not mean numerically qualified. No private `libgdn_index64.so` is supplied; patch 0027 falls back to the
official op and 0032 only rate-limits its warning. It does not repair that op.

## Other runtime paths and build estimates

**(b) Lumnus make-tree/build:** `scripts/make-tree.sh 0.30.0-b70.2 DIR`
fetches/clones or applies Python patches and verifies hashes. It compiles
nothing and is not a Docker build. Its `image/Dockerfile` derives the official
image, patches installed and source Python copies, copies two binary-only DSOs
from a pinned wu1ff image, and runs CPU verification. That Dockerfile does not
build/install the current b70.3 kernel wheel. A complete source kernel rebuild is
a separate operation: `_C`, `_xpu_C` including GDN, `_moe_C`, FlashAttention,
architecture kernels and allocator, with oneDNN/SYCL-TLA dependencies.
`docs/kernels.md` reports 2 h 40 min at 12 jobs and peak ~100 GB RAM; the <3 min
number is only an incremental b70.2-to-b70.3 `_C` rebuild. Its released wheel is
351,983,263 bytes, built against torch2.13/oneAPI2026.0. Full native work needs
hours and a separately admitted large build workspace, not this screen's
~1-hour pull/start/request budget. The lab's historical conservative full-stage
admission was 150 GiB free NVMe and 100 GiB available RAM; preserve the separate
50 GiB reserve when planning new allocations. Exact serial GDN reimplementation
is additional engineering and qualification, potentially days.

**(c) Existing historical image plus ports:** no pull is cheapest in disk, but an
old torch/vLLM image cannot receive V30 Python files wholesale. The available
local labels/history identify R276-era artifacts, not a confirmed R304 or V30
runtime; their approximately 23 GB disk footprint is no evidence of kernel
version. Selected orchestration ports would measure the old stack, not answer
the modern-stack Screen 1 question. Preserve those images as historical anchors.
Do not install packages into old environments or mix torch2.11 kernel DSOs with
new torch2.13 binaries.

## Confirmed launch vocabulary in V30

`config/compilation.py` defines `CUDAGraphMode.FULL_DECODE_ONLY` with that exact
spelling and accepts `cudagraph_capture_sizes`; no renamed setting is needed.
`platforms/xpu.py` requires `VLLM_XPU_ENABLE_XPU_GRAPH=1` and compatible torch.
Use TP4, `--enable-expert-parallel`, BF16 activations/KV, `--max-model-len 4352`,
one sequence, `--max-num-batched-tokens 64`, no async scheduling or prefix cache,
`--enable-prompt-tokens-details`, and a declared bounded KV allocation.
Capture sizes `[1]`, `[1,2]`, `[1,4]` correspond to separate no-MTP, MTP1 and
MTP3 arms; inspect what actually captures, since padded shapes are not evidence
of active-row geometry. Stock configuration is per-engine:

```text
MTP off: omit --speculative-config
MTP1: --speculative-config '{"method":"mtp","num_speculative_tokens":1}'
MTP3: --speculative-config '{"method":"mtp","num_speculative_tokens":3}'
```

There is no reviewed per-request switch. The morning note's maximum32 requests
(4 pins +12 realistic for each of K1/K3) requires unimplemented drained scheduler,
proposer, rollback and graph controls. A one-launch K1 screen is16 requests.
Separate arm command lines do not authorize a three-launch sweep. Do not edit an
environment variable mid-process or discard extra drafts and label it K1.

## Community queue beyond Lumnus; offline evidence only

The requested command was run against the local clone:

```sh
git -C /home/steve/src/lumnus-20261008/vllm log --oneline \
  76cfe1cd88d30d525eec8be5bff75f8b77471c88..v0.30.0 -- \
  vllm/models/qwen4_exp vllm/model_executor/models/qwen3_8.py \
  vllm/model_executor/layers/mamba/gdn \
  vllm/model_executor/layers/fused_moe/experts/xpu_moe.py \
  vllm/model_executor/layers/quantization/fp8.py \
  vllm/v1/attention/backends/gdn_attn.py
```

It returns only the unrelated V30 tip `ced6857`, CPU build PR#57871. The clone's
`.git/shallow` contains the old base, V30 and Lumnus HEAD: this is **not a
complete post-76cfe1cd PR history**. Do not invent PR numbers from endpoint diffs.
No fetch was performed. Useful pinned endpoint findings from
`../notes/2026-10-08-lumnus-v0300-stack-analysis.md` and local
`/home/steve/src/lumnus-20261008/upstream-review.md`:

- New Qwen4Exp package and PLE TP shard coverage; XPU needs the reviewed selector.
- GDN CPU metadata construction avoids a device-to-host draft-count copy;
  graph/capture orchestration changed. Inspect the saved
  `audit-evidence/vllm-selected-endpoint.diff`.
- FP8 loader scale-grid refinement handles incompatible TP/block partitioning;
  the XPU MoE implementation itself is byte-identical between the two endpoints.
  Native block-FP8 is pre-existing, not a new claimed speedup.
- Kernel history is available: #544 `5802a414` conv rollback layout, #537
  `1d5b4f5e` mixed speculative groups, #517 `95d80c7a` SYCL-TLA update.
  These are source/common-base deltas, not necessarily chronologically after
  certification. Relevant later upstream fixes adopted by Lumnus are
  #600/#564/#563/#578/#586 above; preserve upstream authorship.
- nacolias llama.cpp SYCL quad-B70 is a useful lead for TP/communication/kernel
  scheduling ideas. The supplied context has no locally pinned source or tested
  result. The earlier note's attempted URL read failed. Queue source/revision,
  exact GGUF quantization, topology, cache and quality evidence for a later
  authorized intake; do not transfer a GGUF speed to the unchanged FP8 lane.

No network beyond the parent's Docker manifest metadata inspection was used.
