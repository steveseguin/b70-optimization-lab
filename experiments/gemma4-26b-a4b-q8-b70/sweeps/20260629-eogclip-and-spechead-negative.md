# 2026-06-29 Gemma EOG Clip And SPEC_HEAD Screen

Purpose: test two narrow verifier-side ideas after the current selected-down
VDR2 record:

- trim draft tokens after the first EOG token before building the verifier
  batch (`LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG=1`);
- revisit late-head bonus with a dedicated SPEC_HEAD fused argmax branch
  (`LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS=1` +
  `LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1`).

The current valid record remains
`115.8466634928202 tok/s` from
`data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/`.

## Source / Patch Artifact

The dirty llama.cpp experiment stack was rebuilt successfully after the
default-off changes. The tested source state is preserved as:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-eogclip-spechead-current-files.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260629-eogclip-spechead-current-files.diffstat`

Notes:

- The patch file is a current-stack snapshot for
  `/home/steve/src/llama.cpp-gemma-record-repro-c926` at detached
  `c926ad098`, limited to `tools/server/server-context.cpp` and
  `src/models/gemma4.cpp`.
- It includes previous default-off experiment code already present in those
  files. The flags actually tested in this note are listed per run below.

## Strict128 Screen

All rows used the fixed realistic cold suite, each prompt once,
`cached_tokens=0`, target/verifier `UD-Q8_K_XL`, Q4_0 MTP draft, `MAX_TOKENS=128`,
and the promoted VDR2 selected-down recipe unless stated otherwise.

| Label | Flags | Median tok/s 1-100 | p10 | Mean | Full after-TTFT median | Wall full median | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-control-strict128-20260629T175815Z` | control | `110.96220341085692` | `102.35270342597184` | `112.74453295447366` | `113.04496175703855` | `97.38257603582616` | pass |
| `gemma4-q8-gpu1-eogclip-strict128-20260629T175815Z` | `LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG=1`, profile on | `119.8786068604258` | `104.80667294532127` | `117.14970284010889` | `114.35815161973508` | `97.30597395405312` | pass |
| `gemma4-q8-gpu2-latehead-specheadargmax-strict128-20260629T175815Z` | `LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS=1`, `LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX=1` | `107.87375005033726` | `95.84513827288033` | `107.30682941118839` | `108.61214070427035` | `92.6358246712434` | pass |
| `gemma4-q8-gpu3-latehead-specheadargmax-strict128b-20260629T175815Z` | same as GPU2 | `107.29199126485827` | `98.93212308750566` | `108.71516251477685` | `106.5169446201407` | `92.3924426028056` | pass |

Decision from strict128:

- Late-head plus SPEC_HEAD fused argmax is closed as a loss for this
  implementation. It is valid, but it is slower than control by enough that a
  full512 promotion run is not justified.
- EOG clipping was real and worth a full512 check: the profiling run logged
  `eog_trim calls=512 tokens=640` by the end of the run.

## Full512 EOG Validation

The EOG-only full512 lock used `CANARY_REPEATS=512`, `MAX_TOKENS=512`,
`LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG=1`, and no profiling overhead.

| Label | Median tok/s 1-100 | Delta vs `115.8466634928202` | p10 | Mean | Full512 after-TTFT median | Wall full512 median | TTFT median ms | Canary | Headline eligible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-eogclip-full512-20260629T180241Z` | `113.58569073629727` | `-2.260972756522932` | `104.17318555349237` | `114.75230971652435` | `105.69648631445452` | `100.8299082257258` | `180.0482029793784` | pass, `2048` rows | yes |
| `gemma4-q8-gpu1-eogclip-full512-20260629T180241Z` | `112.87022244166417` | `-2.97644105115603` | `106.59224161584065` | `113.65826931153175` | `105.94224426455227` | `101.39184881212512` | `180.97444152226672` | pass, `2048` rows | yes |
| `gemma4-q8-gpu2-eogclip-full512-20260629T180241Z` | `110.53050651067699` | `-5.316156982143212` | `99.79766081480125` | `111.90840255190643` | `106.66090051046751` | `101.66700565012118` | `181.25264352420345` | pass, `2048` rows | yes |
| `gemma4-q8-gpu3-eogclip-full512-20260629T180241Z` | `107.30620554428963` | `-8.540457948530573` | `101.90945698251409` | `112.03562854805125` | `105.40976516054195` | `100.73357126361662` | `179.87282894318923` | pass, `2048` rows | yes |

Decision:

- Do **not** submit to LocalMaxxing. No lane beat the current valid record by
  the required primary metric.
- Keep `LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG=1` as a safe default-off utility
  patch candidate. It trims verifier work at termination and slightly improved
  full-completion after-TTFT medians in this batch, but it did not improve the
  primary `1-100 after TTFT` median record.
- Do not run more late-head/SPEC_HEAD promotion attempts unless the SPEC_HEAD
  graph can be folded into the existing verifier graph without an extra
  scheduler/copy/sync boundary.

## Next Implication

The remaining short-decode bottleneck is still exact verifier graph cost,
especially the regular Q8 full-vocabulary LM head and routed MoE gate/up work.
Small host-side or terminal-row cleanups are now mostly exhausted for the
primary record metric.
