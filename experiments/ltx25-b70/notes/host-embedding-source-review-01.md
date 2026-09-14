# Host embedding ownership: inactive source review

2026-09-14. Read-only review of the initial candidate snapshot
[`ltx_host_embedding_candidate.py`](../scripts/ltx_host_embedding_candidate.py),
SHA256 `95e2ce140a5cf27580377d72d321a7f3797ca32a0cd04cd4ec52749325f526ae`.
A successor is being prepared separately; these findings describe this snapshot,
not a later corrected implementation. No Torch/native imports, endpoint requests,
device queries, or runtime changes were performed for this review.

Two issues need explicit CPU coverage before integration:

1. The bare scaled embedding used as a `ModelPatcher` root cannot traverse the
   standard `_load_list()` path: the empty root name produces `.weight`, and
   `get_key_weight()` resolves an empty attribute. Use a named child in the CPU
   owner and test loading that owner, not only the remaining encoder.
2. The candidate reads `weight._version` unconditionally. Comfy constructs nodes
   under `torch.inference_mode()` (`execution.py:745`); inference-created weights
   may lack a version counter. The original CPU fixture constructs normal
   tensors, so it does not cover this startup condition.

The integration must construct CLIP with `initial_device=cpu` before extracting
ownership: `sd.py` can otherwise full-load in its constructor. The normal
`CLIP.load_model()` passes only its encoder patcher, and this version of
`model_patches_models()` does not enumerate `additional_models`; the CPU owner
needs explicit inclusion in the actual load/accounting path. While extraction
is active, save/reload APIs must reject or first restore ownership, because
ordinary `state_dict()` omits the table and `load_sd(strict=False)` can ignore it.
Normal shared-model clones use filtered live weak references in this snapshot;
different-model/deep clones remain unsupported.

The fixed text-encoding arithmetic is compatible in source: `process_tokens()`
requests F32 output for 2D int64 indices on the execution device. The original
manual-cast embedding gathers BF16, converts to F32, then its wrapper applies the
Python `sqrt(hidden_size)` scalar. CPU BF16 gather, BF16 row transfer, and the
same separate XPU cast/multiply preserve that sequence. This is not a native
equality result. Full-model `.to(device)` skips the separately owned table.

Reading only the safetensors header found BF16 `[262144,3840]` embedding storage
of 2,013,265,920 bytes (1,920 MiB). Remaining checkpoint tensors total
23,127.087 MiB, an upper bound rather than the exact instantiated model size.
The unchanged 6 GiB reserve plus the existing minimum BF16 text estimate
(`642 × 3 MiB`) leave a nominal 24,586 MiB model budget on the recorded
32,656 MiB card: approximately 1,459 MiB headroom before other allocations.
Later packet10 logs report lower usable budgets, so source arithmetic does not
prove actual residency. Retain the full-residency guard and supplied budget;
do not bypass it with forced loading.

Inspected source root:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-10/source`.
Packet manifest: `d6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a`.

| Relative source | SHA256 |
| --- | --- |
| `comfy/ops.py` | `6058f688d936b083c49fa49a57964837476db6d95750ea70198ad60e884ffed0` |
| `comfy/model_patcher.py` | `768d9b6f24b632dffba9e4c3c2d2962b3c309bf33182cf599d8c9abda2125d99` |
| `comfy/sd.py` | `41cbf195657cc81a60173f13f192966c4276bf7931a6c10f75870a66c59546b0` |
| `comfy/sd1_clip.py` | `fc2c7e8442e00d525740699c936a00e93a87f58d7c63a1c23a87cd96226962f8` |
| `comfy/model_management.py` | `ef3f3af0657c1b022ad69b25928fa52dd429db9aed9cb688e89c7fbe68ab50cd` |
| `comfy/text_encoders/llama.py` | `7a1c57dd6e94ff1731f4cc6d98db2baaf8fed03e2fe996f79e49e06d9199717f` |
| `comfy/text_encoders/lt.py` | `9b504b20b9a430479c2de8a166ef7994100655857d122b5d18fc17eaf88ecebf` |
| `execution.py` | `0a648063cd651692f1d8e67ff8dcf73372730b86161e892d3fffc196dde78827` |
