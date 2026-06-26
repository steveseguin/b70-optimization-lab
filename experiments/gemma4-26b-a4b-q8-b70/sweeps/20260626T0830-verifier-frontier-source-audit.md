# Verifier Frontier Source Audit

Date: 2026-06-26
Owner/agent: Codex + explorer subagent

## Context

The current valid Gemma 4 26B A4B Q8 fresh-response record is still
`103.2992004295621 tok/s` row0 after TTFT:

- `data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z/summary.json`
- LocalMaxxing `cmqsylo2l011nqr011yydjvne`

The profile run
`data/gemma4-q8-gpu0-record-profile-20260626T0810/summary.json` showed the
draft side is not the meaningful bottleneck:

- draft acceptance: `445/462`, mean accepted length `7.74`
- draft side: `1355 ms` total across `324` calls
- target side: `24242 ms` total across `324` calls
- target `process_ubatch`: `23740 ms`
- post/sample extraction: about `484 ms`

This means the next serious source-level wins must reduce target verifier
graph/model compute, not p-min/sampler/depth/runtime micro-knobs.

## Plausible Source Directions

1. **Fused Gemma4 router selection + selected-weight materialization**
   - pointers: `src/llama-graph.cpp` around the `build_top_k`/argsort +
     selected-weight path; `src/models/gemma4.cpp` around the MoE block
   - mechanism: for verifier-sized `n_tokens <= 8`, fuse router top-k/argsort,
     selected-logit gather, reshape, and selected softmax into one SYCL op that
     emits expert IDs plus normalized selected weights for the existing MoE
     matmul/weighted-sum path
   - avoid repeating the failed selected-softmax-inside-weighted-sum attempt;
     this is a router-materialization fusion before MoE matmuls
   - risk: medium; tie ordering and softmax numerics can change expert choices

2. **Device-side route compaction reused across gate/up/down**
   - pointers: `ggml/src/ggml-sycl/ggml-sycl.cpp`, `ggml/src/ggml-sycl/mmvq.cpp`,
     `src/llama-graph.cpp`
   - mechanism: build a verifier-sized `(token, slot, expert)` route table once
     per layer on device and reuse it across gate/up/down work, reducing
     duplicate route scans and expert-weight reads
   - risk: medium-high; only worthwhile if it is materially different from the
     already-screened `MUL_MAT_ID_FAST`, grouped Q8, per-slot, and fused-down
     toggles

3. **Small contiguous verifier attention specialization**
   - pointers: `src/models/gemma4.cpp` attention block
   - mechanism: specialize the single-sequence, contiguous verifier rows
     produced by MTP (`~8` rows) to reuse K/V cache reads and simplify
     causal/SWA masking
   - risk: high; Gemma4 alternates full and sliding-window attention, and
     verifier correctness bugs can be subtle

4. **Gemma4 shared dense FFN fusion for verifier rows**
   - pointers: `src/models/gemma4.cpp` shared expert path,
     `src/llama-graph.cpp` dense FFN helpers
   - mechanism: fuse shared gate/up + GEGLU and possibly down epilogue for
     `n_tokens <= 8`, reducing kernel launches and intermediate traffic
     independent of routing
   - risk: medium-high because `UD-Q8_K_XL` has mixed quant layouts and GEGLU
     parity must be exact enough for canaries

## Explicitly Exhausted / Low-Value For This Identity

- fused output argmax: tested and slower
- backend sampled-ID extraction: small part of profile and prior losses
- `n > 7`: acceptance remains high but throughput falls badly
- lower precision target or QAT/Q4XL target transfer: separate quality lane
- warmed/history n-gram: not fresh-response headline
- selected-softmax inside weighted-sum: tested and slower
- p-min/thread/batch micro-sweeps around the current record:
  `20260626T0717-runtime-frontier-recheck.md`

## Next Engineering Bias

Start with router-selection materialization fusion if taking a source patch,
because it is narrower than attention specialization and more directly tied to
small verifier-row MoE overhead. Validate with:

1. 96-repeat chat canary minimum for screens;
2. row0 fresh `cached_tokens=0`;
3. full 1536/1536 canary before any LocalMaxxing submission;
4. compare against `103.2992004295621 tok/s`, not warmed means.
