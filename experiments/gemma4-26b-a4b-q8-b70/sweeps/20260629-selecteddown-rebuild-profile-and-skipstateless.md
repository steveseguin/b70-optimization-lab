# 2026-06-29 Gemma 4 26B Q8 selected-down rebuild, profile, and skip-stateless retest

Purpose: resume optimization from the current strict realistic-suite record after
the top1 fused-argmax patch was reverted in source. The first requirement was to
rebuild `llama-server` so later runs were not contaminated by the stale
top1-patched binary.

## Baseline identity

- Repo: `/home/steve/qwen36-results-main`
- Source tree: `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- Build target:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`
- Target model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- Record recipe:
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1`,
  `UBATCH_SIZE=1024`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `--ctx-checkpoints 0`.
- Current promoted record before this note:
  `115.72789384447941 tok/s` median tokens 1-100 after TTFT,
  `data/gemma4-q8-gpu1-vdr2-selecteddown-reordervdr2-full512-20260629B/summary.json`,
  LocalMaxxing `cmqyo0jyt08ippk01vhiobdnm`.

All runs below used the fixed realistic cold suite. Every prompt was sent once,
all rows reported `cached_tokens=0`, and all canaries passed.

## Rebuild

Command:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

Result: build completed. Warnings were the usual SYCL/AOT register-spill
warnings and the tolerated UI npm engine warning. No source changes were made in
this step.

## Strict128/profile screen

Four lanes were run after the rebuild:

| Lane | Path | Median 1-100 | Notes |
| --- | --- | ---: | --- |
| Rebuilt control | `data/gemma4-q8-gpu0-rebuilt-record-control-strict128-20260629F/summary.json` | `115.08532189612076` | Valid strict128 control on rebuilt binary |
| Spec profile | `data/gemma4-q8-gpu1-selecteddown-specprofile-strict128-20260629F/summary.json` | `110.48567905322372` | `LLAMA_SERVER_SPEC_PROFILE=1`, `LLAMA_MTP_DRAFT_PROFILE=1`; diagnostic only |
| Node profile | `data/gemma4-q8-gpu2-selecteddown-nodeprofile-strict128-20260629F/summary.json` | `68.85844327848075` | `GGML_SYCL_NODE_PROFILE=1`; disables graph, diagnostic only |
| Skip stateless accept | `data/gemma4-q8-gpu3-selecteddown-skipstateless-strict128-20260629F/summary.json` | `116.19120949977454` | Promising strict128 screen, required full512 confirmation |

Profile interpretation:

- The result-mining and fused-argmax audits confirmed that standalone
  `p_min`/`n_min`/`n_max`/thread/poll/affinity sweeps are exhausted unless
  paired with a new source mechanism.
- `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` remains a bad direction as currently
  implemented: it uses the separate scratch-heavy `GGML_OP_MUL_MAT_ARGMAX`
  path instead of the fast regular Q8 reordered LM-head matmul plus backend
  `ggml_argmax`.
- The current record already uses the same-graph bonus row: verifier rows are
  `[sampled_token, draft0, draft1, draft2]` with all output flags true, and bulk
  sampled IDs consume rows `0..3`. The old `LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS`
  path is the separate slow head-only graph, not a new optimization target.

## Full512 skip-stateless confirmation

Because strict128 showed a possible small win, `LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT=1`
was retested at full512 on all four GPUs:

| Lane | Path | Median 1-100 | Full512 after TTFT | Wall full512 | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| GPU0 | `data/gemma4-q8-gpu0-selecteddown-skipstateless-full512-20260629G/summary.json` | `111.99709293679811` | `103.23173666758433` | `99.1902861986404` | Below record |
| GPU1 | `data/gemma4-q8-gpu1-selecteddown-skipstateless-full512-20260629G/summary.json` | `111.00630502682648` | `105.06106527186087` | `99.89523292462738` | Below record |
| GPU2 | `data/gemma4-q8-gpu2-selecteddown-skipstateless-full512-20260629G/summary.json` | `115.09605873968734` | `107.2343605403209` | `102.42626359284961` | Below record |
| GPU3 | `data/gemma4-q8-gpu3-selecteddown-skipstateless-full512-20260629G/summary.json` | `116.49033532835452` | `107.07748344340155` | `102.69091666156572` | One-off high |

The GPU3 high was a valid cold result, but the margin over the existing
`115.72789384447941` record was small and the batch showed high variance. A
same-GPU full512 repeat was run before promotion:

| Lane | Path | Median 1-100 | Full512 after TTFT | Wall full512 | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| GPU3 repeat | `data/gemma4-q8-gpu3-selecteddown-skipstateless-full512-repeat-20260629H/summary.json` | `113.5884492388314` | `104.6475373326957` | `100.6145830011576` | Did not confirm |

## Decision

Do **not** promote or submit the `116.49033532835452` one-off. The full512 repeat
did not beat the current `115.72789384447941` record, so this is best treated as
variance/inconclusive-negative for the selected-down stack.

Current promoted record remains:

- `data/gemma4-q8-gpu1-vdr2-selecteddown-reordervdr2-full512-20260629B/summary.json`
- `115.72789384447941 tok/s` median tokens 1-100 after TTFT
- LocalMaxxing `cmqyo0jyt08ippk01vhiobdnm`

## Next useful work

Avoid more flag-only skip-stateless/config retries. Useful next source work must
reduce exact target/verifier cost:

1. Compact exact argmax epilogue on the regular Q8 reordered LM-head MMVQ path,
   not the current scratch-heavy `ggml_mul_mat_argmax` path.
2. Row-adaptive verifier output rows, but only if the verifier remains exact and
   full target verification is preserved for any accepted token.
3. Backend sampled-ID/output-path tightening around the current full LM-head
   plus backend `ggml_argmax` path. Upside is smaller, but it preserves the
   current winning compute path.
