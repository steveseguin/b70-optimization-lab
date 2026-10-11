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

## Finding A Patch

Start with the lane catalogs below. They connect source identities, accepted
and rejected deltas, result evidence and restoration instructions. A snapshot
is historical evidence; check the lane's current result packet before choosing
an overlay for a new run.

- [Gemma 4 26B Q8](gemma4-26b-a4b-q8-b70/README.md)
- [Qwen3.6 27B Q8 TP2](qwen36-27b-q8-tp2-asrock-b70/README.md)
- [Qwen3.6 27B INT4 record](qwen36-27b-autoround-int4-b70/record-20260711/README.md)
  and [later determinism closeout](qwen36-27b-autoround-int4-b70/determinism-closeout-20260818/README.md)
- [Qwen3.6 27B Q4 MTP](qwen36-27b-mtp-gguf-q4-b70/README.md)
- [Qwen3.8 27B Q8 TP2](qwen38-27b-q8-tp2-asrock-b70/README.md)
- [Qwen3.8 27B Q4 TP1](qwen38-27b-q4km-tp1-b70s/README.md)
  and [Q4 TP2](qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Qwen3.8 MTP FC INT4](qwen38-27b-mtp-fc-int4-b70/README.md)
- [Qwen3.8 Flash-Next FP8](qwen38-flash-next-fp8-b70/README.md)
  — [October 10 source-recovery gap](../audits/repository-cleanup/2026-10-10/bundle-portability-gap.md)
  for the exact-GDN kernel bundle; its required commit is not yet recovered.
- [Laguna S 2.1](laguna-s-2.1-xpu-b70/README.md)
  and [separate FP8-KV research](laguna-s-2.1-fp8-kv-xpu-b70/README.md)
- [DeepSeek V4 Flash REAP](deepseek-v4-flash-reap-xpu-b70/README.md)
- [Muse-Glimmer 30B](muse-glimmer-30b-b70/README.md)
- [Ornith 15](ornith-15-35b-a3b-q4km-b70/README.md)
- [Preserved vLLM work in progress](vllm-codex-wip-preserved-20260821/README.md)

Other flat patches and source directories remain at their original paths.
Use the [model effort index](../docs/model-effort-index.md) to follow their
lane-specific results. Similar filenames, shared source bytes, rejected
outcomes and old dates are not evidence that a patch can be deleted.

<a id="current-gemma-patch-pointers"></a>

## Historical Gemma Patch Examples

- [gemma4-llamacpp-mtp-draft-fast-topk-20260623.patch](gemma4-llamacpp-mtp-draft-fast-topk-20260623.patch):
  historical approved Gemma 4 26B A4B Q8 llama.cpp MTP fast top-k patch. It
  bypasses generic CPU sampler overhead for draft-MTP when backend sampling is
  disabled and top-k is small. Promoted result:
  `91.618942 tok/s`, 384/384 canary, LocalMaxxing `cmqqsecuk01azqo018ahv0i1s`.
- [gemma4-llamacpp-mtp-draft-fast-topk-nosync-loss-20260623.patch](gemma4-llamacpp-mtp-draft-fast-topk-nosync-loss-20260623.patch):
  rejected attempt to remove the explicit sync before draft logits access;
  valid canaries but slower (`~89.8-90.3 tok/s`).
- [gemma4-llamacpp-mtp-draft-rowhelper-loss-20260623.patch](gemma4-llamacpp-mtp-draft-rowhelper-loss-20260623.patch):
  rejected attempt to stage logits and NextN embeddings with one helper/sync;
  valid canaries but slower (`~90.5-90.9 tok/s`).
- [gemma4-llamacpp-mtp-draft-backend-topk-loss-20260623.patch](gemma4-llamacpp-mtp-draft-backend-topk-loss-20260623.patch):
  rejected incremental patch on top of the fast-top-k baseline. It consumed
  backend sampled top-k candidates/logits directly for MTP and sorted only the
  returned `k` entries, but valid full-gate runs regressed to
  `84.26-89.68 tok/s`.

<a id="current-qwen-patch-pointers"></a>

## Historical Qwen Patch Examples

- [vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch](vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch):
  routed GEMM1 B-layout correctness fix.
- [llm-optimizations-qwen36-routegemm1-blayoutfix-results-20260620.patch](llm-optimizations-qwen36-routegemm1-blayoutfix-results-20260620.patch):
  paired lab notes/results snapshot for the B-layout work.

## Laguna S 2.1 Snapshot Pointer

- [laguna-s-2.1-xpu-b70/](laguna-s-2.1-xpu-b70/): exact vLLM and XPU-kernel
  bundles, reviewable combined patches, supplemental attention-runtime source
  provenance, and links to the qualified four-B70 result and standalone repro.

## Muse-Glimmer-30B Snapshot Pointer

- [muse-glimmer-30b-b70/](muse-glimmer-30b-b70/): complete public-base-to-record
  llama.cpp patch, private commit-history bundle, split final WOQ/measurement
  deltas, checksums, and links to the closed four-B70 result and standalone
  repro.
