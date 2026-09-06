# Qwen3.8 Flash-Next lossless MTP1 overlay (`1b2a17c1`)

Exported: 2026-09-06

This is the exact vLLM overlay loaded by the certified lossless MTP1 line
(27.048435 tok/s, LocalMaxxing `cmtp5u0ip02eln701lntsl2ns`) and, as its
ancestor `2169dbfe`, by the deterministic full-decode-graph MTP0 line
(25.617613 tok/s, `cmtp3g14502cun701y5ey93rh`).

- public base: `vllm-project/vllm` commit `76cfe1cd88d30d525eec8be5bff75f8b77471c88`;
- overlay head: `1b2a17c1e7c41985d6a5e0eb324ada4775c25e60`, tree `1cb86e078991895906e75544207733ee7373c55d`;
- MTP0 lineage head inside the series: `2169dbfe` (tree `e3377212a70a67a426d244cf5ded86dfffa942df`);
- 55 linear commits, no merges; the complete-history bundle
  `vllm-q38-lossless-mtp1-1b2a17c1-20260906.bundle` carries tag
  `q38-lossless-mtp1-1b2a17c1`;
- `series.sha256` pins every patch and the bundle; `verify-series.sh`
  (`REPRO_VLLM_TREE=<clone> ./verify-series.sh --apply`) checks the bundle, the
  tag, the tree hash, and that the patches re-create the same tree from the base.

The older exports in `../vllm/` (2026-08-26, 20 patches) are a prefix of this
series and are retained for history; do not combine them with this directory.

| Patch | Subject |
| --- | --- |
| `0001-Merge-02f2b4c15dd987d9436e125aab29604447c77405-into-.patch` | Merge 02f2b4c15dd987d9436e125aab29604447c77405 into |
| `0002-support-PLE-Offload-for-Qwen3.8-Flash-Next.patch` | support PLE-Offload for Qwen3.8-Flash-Next |
| `0003-Support-eager-PLE-offload-transport-on-XPU.patch` | Support eager PLE offload transport on XPU |
| `0004-Enable-Qwen4Exp-model-dispatch-on-XPU.patch` | Enable Qwen4Exp model dispatch on XPU |
| `0005-Add-Qwen4Exp-XPU-hyperconnection-fallbacks.patch` | Add Qwen4Exp XPU hyperconnection fallbacks |
| `0006-Enable-Qwen4Exp-QSA-kernels-on-XPU.patch` | Enable Qwen4Exp QSA kernels on XPU |
| `0007-Fix-PLE-target-device-selection-across-accelerators.patch` | Fix PLE target device selection across accelerators |
| `0008-Restore-weight-skip-filters-for-Qwen4Exp.patch` | Restore weight skip filters for Qwen4Exp |
| `0009-Port-QSA-compressed-cache-to-tokens-per-state.patch` | Port QSA compressed cache to tokens per state |
| `0010-Avoid-copying-uninitialized-PLE-weights-during-offlo.patch` | Avoid copying uninitialized PLE weights during offload |
| `0011-Add-opt-in-XPU-MoE-phase-sync-trace.patch` | Add opt-in XPU MoE phase sync trace |
| `0012-Allow-selective-UVA-offload-of-Qwen4Exp-embeddings.patch` | Allow selective UVA offload of Qwen4Exp embeddings |
| `0013-Capture-routed-MoE-replay-inputs-on-demand.patch` | Capture routed MoE replay inputs on demand |
| `0014-Normalize-QSA-caches-from-logical-layout.patch` | Normalize QSA caches from logical layout |
| `0015-Support-legacy-XPU-GDN-ABI-for-target-decode.patch` | Support legacy XPU GDN ABI for target decode |
| `0016-Fail-closed-on-XPU-GDN-schema-mismatches.patch` | Fail closed on XPU GDN schema mismatches |
| `0017-Revert-Capture-routed-MoE-replay-inputs-on-demand.patch` | Revert "Capture routed MoE replay inputs on demand" |
| `0018-Revert-Add-opt-in-XPU-MoE-phase-sync-trace.patch` | Revert "Add opt-in XPU MoE phase sync trace" |
| `0019-Port-Qwen4Exp-MTP-tests-to-tokens-per-state-cache-AP.patch` | Port Qwen4Exp MTP tests to tokens-per-state cache API |
| `0020-Route-legacy-XPU-GDN-speculative-decode.patch` | Route legacy XPU GDN speculative decode |
| `0021-Add-bounded-greedy-decision-trace.patch` | Add bounded greedy decision trace |
| `0022-Revert-Add-bounded-greedy-decision-trace.patch` | Revert "Add bounded greedy decision trace" |
| `0023-Make-Qwen4Exp-XPU-QSA-selection-deterministic.patch` | Make Qwen4Exp XPU QSA selection deterministic |
| `0024-Add-opt-in-Qwen4Exp-repeatability-trace.patch` | Add opt-in Qwen4Exp repeatability trace |
| `0025-Trace-Qwen4Exp-PLE-layer-boundaries.patch` | Trace Qwen4Exp PLE layer boundaries |
| `0026-Trace-Qwen4Exp-PLE-internals.patch` | Trace Qwen4Exp PLE internals |
| `0027-Require-complete-Qwen4Exp-PLE-shard-coverage.patch` | Require complete Qwen4Exp PLE shard coverage |
| `0028-Cover-Qwen4Exp-4K-ngram-context-progression.patch` | Cover Qwen4Exp 4K ngram context progression |
| `0029-Allow-Qwen4Exp-traces-on-every-TP-rank.patch` | Allow Qwen4Exp traces on every TP rank |
| `0030-Validate-Qwen4Exp-PLE-shards-after-root-load.patch` | Validate Qwen4Exp PLE shards after root load |
| `0031-Skip-PLE-shard-coverage-on-GPU-placeholders.patch` | Skip PLE shard coverage on GPU placeholders |
| `0032-Bound-XPU-PLE-offload-waits.patch` | Bound XPU PLE offload waits |
| `0033-Filter-PLE-offload-weights-before-materialization.patch` | Filter PLE offload weights before materialization |
| `0034-Isolate-filtered-loader-bookkeeping.patch` | Isolate filtered loader bookkeeping |
| `0035-Add-opt-in-XPU-async-UVA-PLE-prefetch.patch` | Add opt-in XPU async UVA PLE prefetch |
| `0036-Add-guarded-Qwen-HC-grouped-up-integration.patch` | Add guarded Qwen HC grouped-up integration |
| `0037-Qualify-Qwen-HC-grouped-up-dynamic-shapes.patch` | Qualify Qwen HC grouped-up dynamic shapes |
| `0038-Add-opt-in-per-phase-Triton-MoE-configs.patch` | Add opt-in per-phase Triton MoE configs |
| `0039-Qwen4Exp-Add-default-off-GDN-internal-records-to-the.patch` | [Qwen4Exp] Add default-off GDN-internal records to the |
| `0040-Qwen4Exp-Read-repeatability-trace-settings-through-Q.patch` | [Qwen4Exp] Read repeatability-trace settings through |
| `0041-XPU-Add-VLLM_XPU_MKLDNN_DETERMINISTIC-worker-flag.patch` | [XPU] Add VLLM_XPU_MKLDNN_DETERMINISTIC worker flag |
| `0042-V2-runner-Report-CUDAGraphStat-so-cudagraph-metrics-.patch` | [V2 runner] Report CUDAGraphStat so --cudagraph-metrics |
| `0043-XPU-Serial-verifier-row-flash-attention-behind-VLLM_.patch` | [XPU] Serial verifier-row flash attention behind |
| `0044-XPU-One-time-diagnostic-of-the-serial-spec-attention.patch` | [XPU] One-time diagnostic of the serial-spec attention |
| `0045-XPU-Register-VLLM_XPU_FA_SERIAL_SPEC_DECODE-so-the-e.patch` | [XPU] Register VLLM_XPU_FA_SERIAL_SPEC_DECODE so the |
| `0046-XPU-One-time-entry-diagnostic-in-FlashAttentionImpl..patch` | [XPU] One-time entry diagnostic in |
| `0047-XPU-Remove-the-two-one-time-attention-diagnostics-A8.patch` | [XPU] Remove the two one-time attention diagnostics |
| `0048-XPU-Per-row-QSA-index-update-and-selection-for-small.patch` | [XPU] Per-row QSA index update and selection for small |
| `0049-XPU-Serial-QSA-indexer-build-the-single-row-query-of.patch` | [XPU] Serial QSA indexer: build the single-row query |
| `0050-XPU-Repeatability-trace-per-row-digests-for-small-mu.patch` | [XPU] Repeatability trace: per-row digests for small |
| `0051-XPU-GDN-verifier-rows-through-the-single-row-decode-.patch` | [XPU] GDN verifier rows through the single-row decode |
| `0052-XPU-Serial-GDN-verifier-rows-64-bit-indices-for-inde.patch` | [XPU] Serial GDN verifier rows: 64-bit indices for |
| `0053-XPU-VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS-all-reduce-s.patch` | [XPU] VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS: all-reduce |
| `0054-XPU-Qwen4Exp-repeatability-trace-QSA-layer-inner-rec.patch` | [XPU] Qwen4Exp repeatability trace: QSA layer inner |
| `0055-XPU-VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS-per-row-varian.patch` | [XPU] VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS: per-row |
