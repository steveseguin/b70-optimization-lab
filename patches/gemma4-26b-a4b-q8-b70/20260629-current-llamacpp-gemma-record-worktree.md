# 2026-06-29 Current llama.cpp Gemma Record Worktree Capture

This records the exact dirty source state of:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926
```

Base upstream commit:

```text
c926ad098 vulkan: link ggml-cpu when GGML_VULKAN_CHECK_RESULTS / RUN_TESTS are enabled (#24444)
```

Patch artifact:

```text
patches/gemma4-26b-a4b-q8-b70/20260629-current-llamacpp-gemma-record-worktree.patch
```

The patch is a cumulative research stack, not a minimal upstream patch. It
preserves both promoted/default-off code paths and later negative experiments
so the local state can be reconstructed before switching model efforts.

Current promoted Gemma Q8 result tied to this source family:

- result packet: `results/gemma4-26b-a4b-q8-b70/README.md`
- reproduction: `results/gemma4-26b-a4b-q8-b70/reproduce.md`
- evidence:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json`
- primary metric: `98.34046474459183 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT on the fixed cold realistic suite
- validity: `cached_tokens=0` for every prompt, no repeated-output/history
  acceleration, Q4_0 MTP draft verified by the UD-Q8_K_XL target

High-value enabled flags in the promoted lane include:

- `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`
- `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1`
- `GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2` at compile time
- `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`
- `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`
- `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`
- `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1`
- `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`
- `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`

Reapply from a clean llama.cpp checkout at `c926ad098`:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
git checkout c926ad098
git apply /home/steve/qwen36-results-main/patches/gemma4-26b-a4b-q8-b70/20260629-current-llamacpp-gemma-record-worktree.patch
```

Then rebuild with the VDR2 command in
`results/gemma4-26b-a4b-q8-b70/reproduce.md`.

Do not treat every code path in this patch as promoted. See the adjacent
negative patch notes and sweep notes for failed flags, including BF16 direct
mulmat-id, rowpack/pairslot variants, selected-softmax split-N, no-bonus
verifier variants, stage-split MTP, skip-identity out-ids, and dFlash PR 22105.
