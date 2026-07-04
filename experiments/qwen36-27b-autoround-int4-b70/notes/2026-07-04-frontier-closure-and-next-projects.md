# 2026-07-04 - Qwen27 frontier closure and next projects

## Current valid record

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- mode: AutoRound W4A16 plus runtime INT8 LM-head with BF16 scales;
- hardware: one Intel Arc Pro B70, TP1;
- recipe: MTP3/cg8, XPU graph on;
- validity: strict fresh Qwen realistic suite, each prompt once,
  `cached_tokens=0`, target-verified speculation only;
- record: `65.27648650325429 tok/s`;
- LocalMaxxing: `cmr5iu3gk00bfq901nidgcana`.

## Independent closure audits

Two subagent/source audits were run after the v3 EAGLE screen:

1. **LM-head kernel audit.** The preserved candidate-max kernel already tested
   the required semantics: true top IDs/values, candidate score, and
   `candidate_is_top`, exact versus dense logits. It measured rows `1/2/3/4`
   at `1.010x`, `0.984x`, `0.971x`, and `0.961x` versus dense oneDNN, missing
   the `>1.10x` / `<2.3 ms` promotion rule. Bounded follow-ups are closed:
   - atomic/global reduction: high exactness risk, low chance of `>10%`;
   - same-launch reduction: blocked by cross-workgroup sync unless using
     atomics;
   - fused quantization: only `~0.056 ms` per LM-head call, too small;
   - tile/policy tweaks: already below dense oneDNN and not a new mechanism.
2. **Non-kernel optimization audit.** Under the strict fresh-response policy,
   no unclosed configuration/runtime lane remains likely to beat the
   `65.276` record without a real source architecture change.

## Closed non-kernel lanes

- MBT: short-decode `1536/2048/4096` passed but measured
  `63.829/64.239/64.779`; keep MBT1024 for short decode.
- MTP depth: MTP3/cg8 remains best; MTP1/2/4/5 lost.
- capture size: cg8 remains best; cg4/cg16/cg32 lost.
- scale/scope: BF16 scales are the record; FP16 scales were slower; target-only
  BF16 scope failed repeat32 stability.
- scratchpad ring: apparent ring4 support rows were inside variance after
  crossover (`+0.42%`, `+0.27%`).
- token-tree/top-k: existing token-tree configs lost; top-k64 oracle is
  invalid for sequential MTP and cheap rerankers were flat/regressed.
- EAGLE/DFlash: current EAGLE attempts are not endpoint candidates; DFlash
  mixed-SWA/multi-KV remains unstable or low-acceptance.
- long-context/prompt-processing: MBT4096 is useful for the 32K service lane,
  not a short-decode record path.

## Decision

Stop launching Qwen27 endpoint/config screens until the candidate changes one
of the real mechanisms below. More screens of the existing recipe will mostly
measure variance.

Remaining credible projects:

1. **Real top-ID LM-head producer.** This is a larger kernel/runtime project:
   preserve dense oneDNN/XMX-class GEMM efficiency while emitting exact top
   IDs/values and candidate scores, without a second full reduction launch.
   The oneDNN Graph `MatMul -> ReduceMax` check did not provide a shortcut.
2. **Materially stronger drafter / branch-regenerate architecture.** The
   current v2/v3 EAGLE corpus and simple top-k/reranker attempts are closed.
   A future attempt needs materially more data, a different architecture, or a
   legal branch/regenerate/tree design that preserves target verification.
3. **Partial-group / dynamic-depth source support.** This requires scheduler,
   `SpecDecodeMetadata`, sampler rows, GDN/Mamba state commit, and graph
   capture shape support together. The Python-only/placeholder retries are
   closed.

If those deeper projects are not the next priority, switch models rather than
continuing Qwen27 config roulette.
