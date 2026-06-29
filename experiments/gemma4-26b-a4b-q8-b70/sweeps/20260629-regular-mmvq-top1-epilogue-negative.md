# 2026-06-29 Regular-Q8 MMVQ Top1 Epilogue Screen

Status: negative for the headline metric; preserve as a default-off experiment.

## Purpose

The selected-down VDR2 record profile showed the exact verifier LM head as the
largest single hot node. Prior `GGML_OP_MUL_MAT_ARGMAX` variants lost because
they used a scratch/reduce-heavy argmax route instead of the fast regular
reordered-Q8 `MUL_MAT` body. This experiment tried a narrower route: keep the
regular reordered-Q8 MMVQ dot loop and publish compact top1 token IDs through a
small epilogue, avoiding the large scratch candidate arrays and final reduce.

## Source Snapshot

The llama.cpp worktree was already a large detached dirty stack at
`c926ad098`; do not treat the patch as upstream-clean.

- pre-experiment snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-llamacpp-current-stack-before-next.patch`
- post-experiment full snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-llamacpp-current-stack-with-top1epilogue.patch`
- experiment file slice:
  `patches/gemma4-26b-a4b-q8-b70/20260629-regular-mmvq-top1-epilogue-experiment-current-files.patch`

Touched source files:

- `src/models/gemma4.cpp`
- `ggml/src/ggml-sycl/ggml-sycl.cpp`
- `ggml/src/ggml-sycl/mmvq.cpp`
- `ggml/src/ggml-sycl/mmvq.hpp`

Runtime gates used for the candidate:

```bash
LLAMA_SPEC_VERIFY_REGULAR_MMVQ_TOP1_EPILOGUE=1
LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE=1
```

Build result: `llama-server` rebuilt successfully in
`build-sycl-b70-aot-bmg-g31-q8reorder-vdr2`.

Follow-up activation proof: a diagnostic node-profile run later confirmed the
new graph node was selected:
`MUL_MAT_ARGMAX:spec_verify_regular_mmvq_top1_epilogue_token_rows`.
See
`data/gemma4-q8-gpu0-top1epilogue-on-nodeprofile-20260629T1455Z/profile-excerpt.md`.

## Strict128 Paired Screen

Both rows used the fixed realistic cold suite with each prompt run once,
`cached_tokens=0` for every request, no prompt/KV/context/response/ngram/history
reuse, and UD-Q8_K_XL target verification. Both rows passed 256 canary rows and
the realistic final gate.

Control:

- run:
  `data/gemma4-q8-gpu0-top1epilogue-control-strict128-20260629T1438Z/`
- primary median tokens 1-100 after TTFT: `112.52074349461066 tok/s`
- p10: `101.02194303981335`, mean: `113.26153975505589`
- full-output after-TTFT median: `110.2188654265698 tok/s`
- wall full median: `93.9522460230736 tok/s`
- TTFT median: `179.53709047287703 ms`

Candidate:

- run:
  `data/gemma4-q8-gpu1-top1epilogue-on-strict128-20260629T1438Z/`
- primary median tokens 1-100 after TTFT: `111.89428679462038 tok/s`
- p10: `103.68047382061938`, mean: `113.40228646397584`
- full-output after-TTFT median: `112.79174554536459 tok/s`
- wall full median: `96.10224331738794 tok/s`
- TTFT median: `179.61578350514174 ms`

## Decision

Do not promote and do not submit to LocalMaxxing. The candidate lost the
headline primary metric versus the paired control (`111.89` vs `112.52 tok/s`),
even though full-output and wall medians improved slightly in this short run.
The valid record remains:

`data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/`
at `115.8466634928202 tok/s`.

The activation ambiguity is now closed: the profile shows the new epilogue node
active, but still top-ranked at ~`1.325 ms/call`:

```text
MUL_MAT_ARGMAX:spec_verify_regular_mmvq_top1_epilogue_token_rows
total_ms=982.173 calls=741 avg_ms=1.325
```

This replaced the old `MUL_MAT:node_1930` naming but did not remove enough
verifier LM-head cost to improve the primary metric. Do not spend full512 runs
on this implementation as-is. A revisit would need a lower-cost backend
epilogue, not just the existing guarded graph route.
