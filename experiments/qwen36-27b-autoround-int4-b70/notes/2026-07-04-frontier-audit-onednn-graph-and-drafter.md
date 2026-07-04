# 2026-07-04 - Qwen27 frontier audit: oneDNN Graph and drafter routes

## Context

Current valid Qwen27 record:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- mode: AutoRound W4A16 plus runtime INT8 LM-head with BF16 scales;
- hardware: one Intel Arc Pro B70, TP1;
- recipe: MTP3/cg8, XPU graph on, strict fresh realistic Qwen suite;
- record: `65.27648650325429 tok/s` median generated-token throughput for
  tokens 1-100 after TTFT, `cached_tokens=0` on every request;
- LocalMaxxing: `cmr5iu3gk00bfq901nidgcana`.

This note closes the remaining cheap "frontier audit" questions before more
GPU endpoint work:

1. Can oneDNN Graph give us a fused MatMul -> ReduceMax route that avoids dense
   logits for the Qwen LM-head?
2. Is there still a cheap accepted-token/drafter route left after the EAGLE,
   top-k, dynamic-depth, and token-tree screens?

## Source and result audit summary

Two independent source/result audits agreed:

- `get_top_tokens()` is the right semantic integration point, but it still pays
  the dense LM-head producer before reduction. Sampler plumbing and precomputed
  top-token ID plumbing are already close enough; they do not remove the
  expensive producer.
- Current public/local Qwen3.6 27B MTP variants appear to use a single MTP
  layer recursively rather than a stronger multi-position drafter. That matches
  the local checkpoint/config audit and the observed MTP4/MTP5 acceptance
  losses.
- The current local EAGLE/DFlash/token-tree/top-k experiments did not produce
  a strict fresh endpoint win. The only credible drafter route is a materially
  stronger target-matched drafter trained and evaluated on isolated non-final
  data, with an offline gate before any endpoint benchmark.

## oneDNN Graph partition check

Diagnostic script added:

`scripts/inspect-onednn-graph-matmul-reducemax.cpp`

Purpose:

- test Qwen LM-head-like shapes: rows `1-4`, hidden `5120`, vocab `248320`;
- construct `MatMul -> ReduceMax` in oneDNN Graph;
- inspect partitioning under both `fusion` and `debug` policies;
- test BF16 and an s8/s8 -> BF16 graph form;
- do not execute a model and do not claim throughput.

Build/run used:

```bash
cd /home/steve/llm-optimizations
source /opt/intel/oneapi/setvars.sh >/tmp/oneapi-setvars.log 2>&1 || true
/opt/intel/oneapi/compiler/2026.0/bin/icpx -std=c++17 -fsycl \
  -I/opt/intel/oneapi/dnnl/2026.0/include \
  scripts/inspect-onednn-graph-matmul-reducemax.cpp \
  -L/opt/intel/oneapi/dnnl/2026.0/lib -ldnnl \
  -Wl,-rpath,/opt/intel/oneapi/dnnl/2026.0/lib \
  -o /tmp/inspect-onednn-graph-matmul-reducemax
/tmp/inspect-onednn-graph-matmul-reducemax
```

Output is preserved locally at:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-onednn-graph-matmul-reducemax-partition-20260704.txt`

Result:

- BF16 `MatMul -> ReduceMax` was accepted, but oneDNN Graph produced two
  separate supported single-op partitions for every tested row count under both
  `fusion` and `debug` policies. It did not fuse the pattern.
- The tested s8/s8 -> BF16 graph form returned `add_matmul_status=8` for rows
  `1-4`; local status inspection maps that to `invalid_graph_op`.
- Even if ReduceMax fused, it would still emit only max values, not token IDs,
  so exact greedy/spec decode would still need an ID-producing path.

Conclusion:

Do not spend more time trying to get the current oneDNN Graph API to produce
the Qwen27 greedy LM-head IDs. The current public oneDNN MatMul and Graph
fusion docs describe dense MatMul output plus value post-ops/fusion patterns,
not an argmax/top-k/candidate-ID emitting LM-head primitive for this use case:

- `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html`
- `https://uxlfoundation.github.io/oneDNN/dev_guide_graph_matmul_fusion_patterns.html`
- `https://oneapi-spec.uxlfoundation.org/specifications/oneapi/v1.2-rev-1/elements/onednn/source/primitives/attributes/post-ops`

## Closed routes to avoid repeating

- configuration roulette around MTP depth, capture size, parser mode, MBT,
  scratchpad ring size, output buffer reuse, sampler/top-token plumbing, and
  target-only runtime INT8 scope;
- Python/chunked oneDNN top-1;
- standalone full-vocab compact INT8 LM-head top-1/candidate-max kernels that
  scan vocabulary after or outside the oneDNN-class GEMM. The exact local
  prototypes lost to dense oneDNN plus reduction at rows `1-4`;
- existing `speculative_token_tree` configurations, because the current
  proposer still pays full draft logits for alternatives;
- current EAGLE1/EAGLE3/DFlash endpoint attempts, because they are slower,
  unstable, or blocked by mixed-SWA/multi-KV draft metadata.

## Remaining credible lanes

1. **Real top-ID LM-head producer.** This means a oneDNN/XPU-class primitive or
   custom XMX kernel that preserves the dense GEMM efficiency while returning
   exact top IDs/values and candidate scores. It must help both draft greedy
   LM-head calls and target verifier calls. This is high-risk kernel work, not
   another wrapper around the existing dense logits path.
2. **Materially stronger target-matched drafter.** Train/evaluate a stronger
   drafter on isolated non-final data and require an offline gate before any
   endpoint run: held-out mean accepted draft tokens should be clearly above
   the current MTP3 path, step-3 conditional acceptance should be healthy, and
   a separate calibration split should improve target-verified tokens/step by
   enough to beat variance.
3. **True partial-group / branch-regenerate support.** This requires scheduler,
   `SpecDecodeMetadata`, sampler row handling, GDN/Mamba state commit, and graph
   capture shape support together. Do not retry the previous Python-only
   dynamic-depth patches.

## Recommendation

The current Qwen27 short-decode lane is no longer blocked on missing
documentation or cheap screens; it is blocked on a real producer/drafter
architecture change. If continuing Qwen27 immediately, start by designing an
offline drafter v3 gate or by scoping the real XMX/oneDNN-level top-ID producer.
Do not launch more endpoint benchmarks until the candidate changes one of those
mechanisms.
