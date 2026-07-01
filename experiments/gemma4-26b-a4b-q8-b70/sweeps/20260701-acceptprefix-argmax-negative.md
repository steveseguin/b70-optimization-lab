# 2026-07-01 Accept-Prefix Argmax Verifier Prototype

Status: valid strict128 screen, closed negative. Do not full512-confirm or
submit.

## Question

The accept-prefix audit showed that, for the narrow Gemma MTP verifier rows,
the shifted verifier input tokens can identify the draft candidate token. The
hypothesis was that a backend LM-head op could skip later verifier rows once an
earlier row rejected, reducing exact-verifier work without changing quality.

This experiment implemented the idea as a default-off prototype:
`LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1`.

## Implementation

Source patch:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-acceptprefix-preedit-source.patch`
  captures the dirty source before this experiment.
- `patches/gemma4-26b-a4b-q8-b70/20260701-acceptprefix-argmax-negative.patch`
  captures the full post-edit source delta.
- `patches/gemma4-26b-a4b-q8-b70/20260701-acceptprefix-argmax-negative.diffstat`
  records the patch shape.

Key source changes:

- added guarded cparam/env plumbing for
  `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX`;
- added `ggml_mul_mat_argmax_accept_prefix(ctx, a, b, tokens)` as a mode of
  the existing argmax matmul op;
- added a SYCL Q8_0 reordered LM-head backend path for small verifier rows;
- row 0 computes exact top1; row `i > 0` computes only if the previous output
  ID matched verifier input token `i`, otherwise it writes `-1`;
- limited to the current record shape: direct backend verifier argmax,
  reordered Q8_0 output, no scale/lora/suppress bias, no split output,
  `n_outputs == n_tokens`, and `n_outputs <= 4`.

The AOT BMG-G31 `llama-server` build completed successfully.

## Run Identity

- source: `/home/steve/src/llama.cpp-gemma-record-repro-c926`, llama.cpp
  `c926ad098` dirty Gemma record stack
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- common config: `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `UBATCH_SIZE=1024`, `MAX_TOKENS=128`,
  `--ctx-checkpoints 0`, Q4_0 MTP draft `n_max=3`, `n_min=2`,
  `p_min=0.0475`
- promoted flags held constant:
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`
- candidate flag: `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1`

## Results

All rows below passed the fixed realistic cold gate, with `cached_tokens=0`,
and passed the canary. These are valid fresh-response runs, but they are not
headline candidates because they are below both the same-build control and the
current `123.67689864739785 tok/s` record.

| Lane | Result dir | Median tok/s 1-100 after TTFT | p10 | Mean | Median TTFT |
| --- | --- | ---: | ---: | ---: | ---: |
| accept-prefix argmax + parity | `data/gemma4-q8-gpu0-acceptprefixargmax-parity-strict128-20260701T013426Z/summary.json` | `101.42166943454674` | `98.72760456946612` | `105.05076249600359` | `177.62999248225242 ms` |
| accept-prefix argmax | `data/gemma4-q8-gpu0-acceptprefixargmax-strict128-20260701T013622Z/summary.json` | `104.27951393842321` | `95.54704337620137` | `104.81740425511255` | `178.89104399364442 ms` |
| same-build control | `data/gemma4-q8-gpu0-acceptprefix-control-strict128-20260701T013907Z/summary.json` | `111.26833798937403` | `103.89145804036288` | `114.94386506792635` | `177.36206849804148 ms` |

Delta versus same-build control: `-6.98882405095082 tok/s` on the primary
median metric.

## Decision

Closed negative. The semantics are valid, but the implementation loses too much
backend efficiency. The serial row-by-row tile/reduce structure saves some
verifier rows after early rejection, but it gives up the efficient multi-row
behavior of the existing `MUL_MAT_ARGMAX` path and adds extra ordering work.

Do not promote this flag and do not submit it to LocalMaxxing.

Future accept-prefix work should not repeat this serial design. It would need a
single-kernel/global-row scheduler, or a larger graph redesign that removes
verifier LM-head rows without adding per-row launches or reducing Q8 reorder
throughput.
