# 2026-06-30 Record-Identity Full512 Repeat Variance

Purpose: repeat the current Gemma 4 26B A4B Q8 promoted short-decode recipe on
all four B70s with the strict realistic final gate, to check whether normal
run-to-run/GPU variance beats the current `121.41411987308553 tok/s` record.

This is a valid cold-suite batch, but it produced **no new record**.

## Recipe Identity

- Source: llama.cpp working record stack at commit baseline `c926ad098`, with
  the current default-off Gemma experiment code present in the local worktree.
- Target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`.
- Draft: Q4_0 MTP draft, target-verified.
- Hardware: one Intel Arc Pro B70 per lane, four lanes in parallel.
- Context / graph: `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`.
- Main knobs: `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`,
  `POLL=100`, `n_max=3`, `n_min=2`, `p_min=0.0475`.
- Promoted source flags:
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`.
- Exclusions: no n-gram/history acceleration, no context checkpoints, no prompt
  cache reuse, no response reuse.

## Validity

Every lane passed:

- fixed realistic suite, each prompt once as a cold request;
- `realistic_final_gate.passed=true`;
- `cached_tokens=0` for every measured request;
- canary pass, `128/128` rows;
- full512 output length.

## Results

| Lane | Data Dir | Median tok/s 1-100 | p10 | Mean | Full512 tok/s | Wall tok/s | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | `data/gemma4-q8-gpu0-record-repeat-full512-20260630T022340Z/` | 118.213116 | 103.740012 | 116.368145 | 109.412340 | 105.118086 | 179.170839 |
| GPU1 | `data/gemma4-q8-gpu1-record-repeat-full512-20260630T022340Z/` | 117.717326 | 104.472950 | 116.145497 | 110.773523 | 105.579857 | 180.627947 |
| GPU2 | `data/gemma4-q8-gpu2-record-repeat-full512-20260630T022340Z/` | 114.877635 | 100.323741 | 115.591739 | 108.480658 | 104.414685 | 180.273220 |
| GPU3 | `data/gemma4-q8-gpu3-record-repeat-full512-20260630T022340Z/` | 112.945442 | 106.935839 | 117.969771 | 111.175714 | 105.793008 | 180.126224 |

Current record remains:

`data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`

with `121.41411987308553 tok/s` median generated-token throughput for tokens
1-100 after TTFT.

## Decision

Closed as variance/no-new-record. Do not submit to LocalMaxxing and do not
change the promoted recipe. The batch is still useful support for the
`~113-121 tok/s` variance band of the current FA-on 32K/VMM selected-down VDR2
record identity.

Next useful short-record work remains source-level verifier cost reduction,
not more p_min/ubatch/config repeats.
