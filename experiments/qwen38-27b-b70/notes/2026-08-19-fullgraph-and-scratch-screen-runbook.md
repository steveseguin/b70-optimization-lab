# Runbook: the two server screens for >105 (measuring host)

Date: 2026-08-19
Status: ready to execute; both are diffs against the approved MTP5 record
recipe (`localmaxxing/qwen38-27b-int4-mtp5-101.922tok-20260818.queue.json`)

Both screens must satisfy every strict gate (25-prompt suite,
cached_tokens=0, token-ID determinism 25/25, Qwen3.8 target-only quality
baseline, sealed compile cache, kernel-log check, no orphan workers via the
patched run-vllm-candidate.sh process-group cleanup).

## Screen 1 — zero-init persistent scratch (expected ≈103.4, +1.5 tok/s)

Prerequisite: rebuild vllm-xpu-kernels with
`experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-scratch-zero-init-20260818.patch`
(kernel commit 0ab8205), or smoke first with the second host's staged
binary `_xpu_C.abi3.so` sha256
`3d3a8bde37761303f1d995b989ce21a78092c0aeb3cf5b33c5adc094bf437d3f`
(promotion still needs the source rebuild with proper provenance).

Record command, one flag flipped:

```
VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 \
VALIDATION_NUM_SPECULATIVE_TOKENS=5 cudagraph_capture_sizes=[6] \
VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0 \
VALIDATION_LM_HEAD_INT8=1 VALIDATION_DETERMINISTIC_GREEDY_MARGIN=0.03125 \
--dtype float16 --tensor-parallel-size 2 --max-model-len 2048 --max-num-seqs 1
```

Measured expectation from the op-level A/B (built fix, this host):
+8.8-9.2 µs/call × 53 calls/step (48 verifier + 5 draft; the op is
latency-fixed, M=1 == M=6) ≈ **0.47 ms/step**. If the measured delta
materially exceeds that, suspect something else changed; if it is smaller,
the scratch was already being amortized.

Gate bonus: passing here also unblocks `SERIAL_EXACT` at MTP4/5 (it
hard-requires PERSISTENT_SCRATCH=1), should exactness work resume.

## Screen 2 — full-graph capture of the GDN regions (largest lever)

Never benchmarked on the Qwen3.8 MTP5 config; every prerequisite is
validated (head256 stage 12k replays, oneCCL graph oracles, zero-init
scratch, GDN op 200-replay graph exactness). July's Qwen3.6 record proves
the door itself on this fork
(`qwen36-27b-webhie-int4-tp2-fp16-graphsafe-fa-fullgraph-20260711`).

Record command plus:

```
PYTHONPATH=<repo>/experiments/qwen27_graphsafe_flash_attention/staged-package
VLLM_XPU_KERNELS_SRC=<repo>/experiments/qwen27_graphsafe_flash_attention/staged-package
VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1
VLLM_XPU_DDTREE_FULL_GRAPH=1
VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=1
VALIDATION_COMPILATION_CONFIG_OVERRIDE='{"use_inductor_graph_partition":true,"pass_config":{"fuse_rope_kvcache_cat_mla":false},"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[6],"max_cudagraph_capture_size":6}'
```

Watch items, in order of likelihood:

1. **Draft-side capture.** The July lane needed
   `VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS` handling; if capture fails in the
   draft path, screen again with draft graphs disabled to isolate — a
   target-only full-graph win is still the big prize.
2. **Capture failure at width 6.** The head256 stage validated the packed
   6-row verifier tuple; if FULL mode still rejects it, the failure mode
   should be a clean fallback, not corruption — verify quality gates
   regardless.
3. **Numerics.** Full-graph changes execution order around GDN regions;
   the target-only quality baseline and 25/25 token-ID determinism decide.
   Any divergence = stop and triage, do not tune around it.

Expected recovery if it works: eager collectives alone are ~5 ms/step
(43 µs → 6.3 µs per allreduce captured); the eager dispatch penalty over
~700-1000 launches/step is the larger prize. See
`2026-08-19-autoround-int4-step-cost-model.md` for the full budget.

## Screen 3 — rerank K=2 (after 1+2)

`patches/vllm-qwen38-draft-int4-topk-rerank-candidate-20260818.patch`,
`VLLM_XPU_DRAFT_LM_HEAD_INT4_RERANK_TOPK=2`. Audit:
`2026-08-18-autoround-int4-draft-topk-rerank-audit.md`. Repeat the
previously divergent holdout prompt + one control across two cold runs and
require identical token IDs before the full suite; record
`avg_draft_acceptance` alongside tok/s.
