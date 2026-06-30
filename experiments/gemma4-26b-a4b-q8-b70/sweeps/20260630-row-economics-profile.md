# 2026-06-30 Verifier Row-Economics Profile

Status: diagnostic only. Do not submit or promote this row.

## Run Identity

- label:
  `gemma4-q8-gpu0-rowecon-strict128-20260630T010708Z`
- summary:
  `data/gemma4-q8-gpu0-rowecon-strict128-20260630T010708Z/summary.json`
- server stdout:
  local ignored log
  `data/gemma4-q8-gpu0-rowecon-strict128-20260630T010708Z/server.stdout.log`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-rowecon-strict128-20260630T010708Z.server.log`
- target/verifier: Gemma 4 26B A4B IT `UD-Q8_K_XL`
- draft: Gemma MTP `Q4_0`, `n_max=3`, `n_min=2`, `p_min=0.0475`
- runtime: llama.cpp `c926ad098` patched Gemma stack, one B70
- key env/config:
  `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_SERVER_SPEC_PROFILE=1`, `LLAMA_MTP_DRAFT_PROFILE=1`,
  `LLAMA_SPEC_VERIFY_ROW_ECON_PROFILE=1`, `MAX_TOKENS=128`

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260630-spec-verify-row-econ-profile.patch`.

## Validity

The fixed realistic cold gate passed. This is still diagnostic only because
profiling and `MAX_TOKENS=128` were enabled.

- canary: `128` rows, pass
- fixed realistic suite: pass
- cached tokens: all zero
- prompt reuse/history acceleration: none
- primary metric, tokens 1-100 after TTFT:
  - median: `118.69362600230792 tok/s`
  - p10: `102.96667736304362 tok/s`
  - mean: `117.7441672554841 tok/s`
- full-output after TTFT median: `114.52760735987991 tok/s`
- wall full-output median: `99.37086070668855 tok/s`
- TTFT median: `179.64069353183731 ms`

The current headline remains the non-profiled full512 record:
`121.41411987308553 tok/s` in
`data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`.

## Profile Findings

Final target/draft profile:

| Phase | Time ms | Calls | Tokens | Avg ms | Avg token |
| --- | ---: | ---: | ---: | ---: | ---: |
| target decode | `38513.762` | `1208` | `9525` | `31.882` | `4.043` |
| target prompt | `19787.925` | `280` | `5839` | `70.671` | `3.389` |
| target generation | `18725.837` | `928` | `3686` | `20.179` | `5.080` |
| draft | `2654.407` | `1208` | `2758` | `2.197` | n/a |
| process | `27.705` | `1208` | n/a | `0.023` | n/a |
| sample accept | `3.825` | `921` | n/a | `0.004` | n/a |
| common accept | `9.453` | `921` | n/a | `0.010` | n/a |
| emit | `3.118` | `786` | n/a | `0.004` | n/a |

Target decode phase profile:

- calls: `1208`
- tokens: `9525`
- total: `38512.607 ms`
- process ubatch: `36824.297 ms`
- sampled extract: `1657.660 ms`

Draft decode phase profile:

- calls: `924`
- tokens: `925`
- total: `2662.249 ms`
- process ubatch: `2195.898 ms`
- sampled extract: `446.096 ms`

Row economics:

```text
server spec rowecon: steps=921 rows_current=3679 rows_oracle=2893
rows_saved=786 save_pct=21.365 full_match=541
full_match_with_bonus=541 accept_prefix_counts=(0:144, 1:118, 2:123, 3:536)
```

Interpretation:

- Oracle row-output saving is `786 / 3679 = 21.365%`.
- `541 / 921 = 58.7%` of verifier steps were full matches with a useful bonus
  row. The bonus pipeline is not expendable.
- Prefix distribution shows many partial mismatches, but a large full-match
  tail: `0:144`, `1:118`, `2:123`, `3:536`.

## Decision

This profile supports only a bonus-preserving row-output design. It does not
justify reopening simple no-bonus, adaptive bonus skip, staged MTP3 split-bonus,
late-head bonus, or prefix-tail verifier variants; those were already tested as
losses and this profile explains why.

The next credible source-level path must either:

- make verifier output rows row-adaptive while preserving exactness and the
  full-match bonus row, and remove actual LM-head/output work inside the target
  graph; or
- reduce a larger verifier graph boundary, especially routed MoE work beyond
  the selected-down VDR2 fusion already promoted.

Small host/sampler bookkeeping and sampled-ID vector copy cleanup remain poor
record candidates.
