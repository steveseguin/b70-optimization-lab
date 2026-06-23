# Patch Archive

This folder preserves source deltas for wins, failures, and diagnostics. A bad
patch with clear results is valuable; do not remove it just because it failed.

## Patch Record Rules

- Name patches with project, model/lane, short purpose, and date.
- Keep successful and failed patches here unless a later fixed patch explicitly
  supersedes them.
- Pair every patch with a note in [../notes/](../notes/) and result artifacts
  in [../data/](../data/).
- For rejected patches, include the failure mode in the filename or nearby
  note when practical.
- Keep generated patch snapshots byte-faithful. Do not reformat logs or patch
  hunks just to satisfy whitespace checks.

## Promotion

Promote only after quality and identity are clear:

1. Patch saved here.
2. Summary/canary artifacts saved in `data/`.
3. Decision recorded in `notes/`.
4. If verified as reusable, move the recipe or explanation into `repro/`,
   `results/`, or `docs/`.

## Current Gemma Patch Pointers

- [gemma4-llamacpp-mtp-draft-fast-topk-20260623.patch](gemma4-llamacpp-mtp-draft-fast-topk-20260623.patch):
  current approved Gemma 4 26B A4B Q8 llama.cpp MTP fast top-k patch. It
  bypasses generic CPU sampler overhead for draft-MTP when backend sampling is
  disabled and top-k is small. Promoted result:
  `91.618942 tok/s`, 384/384 canary, LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`.
- [gemma4-llamacpp-mtp-draft-fast-topk-nosync-loss-20260623.patch](gemma4-llamacpp-mtp-draft-fast-topk-nosync-loss-20260623.patch):
  rejected attempt to remove the explicit sync before draft logits access;
  valid canaries but slower (`~89.8-90.3 tok/s`).
- [gemma4-llamacpp-mtp-draft-rowhelper-loss-20260623.patch](gemma4-llamacpp-mtp-draft-rowhelper-loss-20260623.patch):
  rejected attempt to stage logits and NextN embeddings with one helper/sync;
  valid canaries but slower (`~90.5-90.9 tok/s`).

## Current Qwen Patch Pointers

- [vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch](vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch):
  routed GEMM1 B-layout correctness fix.
- [llm-optimizations-qwen36-routegemm1-blayoutfix-results-20260620.patch](llm-optimizations-qwen36-routegemm1-blayoutfix-results-20260620.patch):
  paired lab notes/results snapshot for the B-layout work.
