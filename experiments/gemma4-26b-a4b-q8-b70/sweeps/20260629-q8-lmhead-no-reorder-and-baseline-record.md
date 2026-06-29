# 2026-06-29 Q8 LM-Head One-Column No-Reorder Screen

Status: no-reorder not promoted; baseline identity produced a new valid record
candidate.

## Question

After the DMMV guard lost full512, the next LM-head test kept regular MMVQ but
skipped Q8 weight reorder only for the large-vocab one-column Q8_0 LM-head
shape:

- flag: `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_NO_REORDER=1`;
- shape guard shared with the DMMV experiment:
  `src0 Q8_0`, `src1/dst F32`, `src1_ncols == 1`, `dst->ne[0] >= 131072`,
  all higher dims equal 1;
- intended dispatch: regular `mul_mat_vec_q8_0_q8_1_sycl` instead of
  `reorder_mul_mat_vec_q8_0_q8_1_sycl`;
- exact target/verifier semantics preserved: full F32 logits are still
  materialized by the target model.

Patch snapshots:

- source:
  `patches/gemma4-26b-a4b-q8-b70/20260629-q8-lmhead-1col-no-reorder-source.patch`;
- harness:
  `patches/gemma4-26b-a4b-q8-b70/20260629-q8-lmhead-1col-no-reorder-harness.patch`.

Build:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 12
```

The AOT link completed with the normal spill warnings.

## Strict128 Screen

All lanes used the current valid record identity:

- llama.cpp `c926ad098` dirty Gemma record stack;
- UD-Q8_K_XL target/verifier, Q4_0 MTP draft;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`;
- selected-down VDR2 record stack;
- fixed realistic suite, each prompt once, `cached_tokens=0`;
- no prompt/KV cache reuse, checkpoints, response reuse, n-gram/history
  acceleration, or warmed repeated prompts.

Strict128 `20260629T224718Z`:

| Lane | No-reorder | Summary | Median 1-100 | p10 | Mean | Full | Wall |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPU0 control | unset | `data/gemma4-q8-gpu0-q8lmhead-noreorder-control-strict128-20260629T224718Z/summary.json` | 117.13361108753044 | 105.01435790385311 | 117.37923707123265 | 116.72331216582339 | 99.8834559205354 |
| GPU1 no-reorder | `1` | `data/gemma4-q8-gpu1-q8lmhead-noreorder-on-strict128-20260629T224718Z/summary.json` | 117.95961028736723 | 108.64653469384754 | 118.64086364588668 | 117.08562646314562 | 100.30978909806547 |
| GPU2 control | unset | `data/gemma4-q8-gpu2-q8lmhead-noreorder-control-strict128-20260629T224718Z/summary.json` | 116.83291132989876 | 102.85339963423756 | 116.91489698407234 | 113.60343548044509 | 97.0422323800054 |
| GPU3 no-reorder | `1` | `data/gemma4-q8-gpu3-q8lmhead-noreorder-on-strict128-20260629T224718Z/summary.json` | 119.79823152054603 | 104.55169335671994 | 118.88417965518742 | 117.77229922775118 | 100.28532689795304 |

This was a clean strict128 positive, so it earned full512.

## Full512 Cross-Over

For full512, no-reorder moved to GPU0/GPU2 and controls moved to GPU1/GPU3.
Full512 `20260629T224927Z`:

| Lane | No-reorder | Summary | Median 1-100 | p10 | Mean | Full512 | Wall | TTFT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 no-reorder | `1` | `data/gemma4-q8-gpu0-q8lmhead-noreorder-on-full512-20260629T224927Z/summary.json` | 118.22064654400002 | 105.36629271341721 | 117.20658131119164 | 110.2391745865074 | 105.6347979478202 | 178.92981745535508 |
| GPU1 control | unset | `data/gemma4-q8-gpu1-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json` | 113.09298936308869 | 104.47028359232505 | 115.61320766599097 | 109.79453149842145 | 104.57583602002282 | 178.91419300576672 |
| GPU2 no-reorder | `1` | `data/gemma4-q8-gpu2-q8lmhead-noreorder-on-full512-20260629T224927Z/summary.json` | 117.81805633315116 | 102.93251644694027 | 116.3874919151297 | 107.51353704482787 | 103.58022802999892 | 179.85960998339579 |
| GPU3 control | unset | `data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json` | **121.41411987308553** | 107.03214367227781 | 120.13610933675466 | 110.39053979324245 | 105.88057667302085 | 179.117635008879 |

All lanes passed the realistic final gate, canary, and `cached_tokens=0`.

Decision: do **not** promote no-reorder. It beat one adjacent control, but the
best full512 result came from the control baseline with both
`LLAMA_SYCL_Q8_0_LM_HEAD_1COL_NO_REORDER` and
`LLAMA_SYCL_Q8_0_LM_HEAD_1COL_DMMV` unset.

## Baseline Record Confirmation

Because the control lane at `121.41411987308553 tok/s` beat the previous
`117.91456485086059 tok/s` record, a four-GPU baseline repeat was run with all
LM-head experiment flags unset.

Baseline confirmation `20260629T225215Z`:

| Lane | Summary | Median 1-100 | p10 | Mean | Full512 | Wall | TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 baseline | `data/gemma4-q8-gpu0-baseline-recordconfirm-full512-20260629T225215Z/summary.json` | 113.57217000462137 | 104.3800210317979 | 115.37620181028676 | 109.76791579398086 | 104.38700143441032 | 178.3927694777958 |
| GPU1 baseline | `data/gemma4-q8-gpu1-baseline-recordconfirm-full512-20260629T225215Z/summary.json` | 114.08757996952451 | 104.2669521660802 | 115.05284361205973 | 108.72507374034603 | 103.42632272684156 | 178.8758725160733 |
| GPU2 baseline | `data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json` | **119.94842631460949** | 107.41526220540041 | 119.37118785029499 | 111.9444876977782 | 106.90864788926861 | 179.77339948993176 |
| GPU3 baseline | `data/gemma4-q8-gpu3-baseline-recordconfirm-full512-20260629T225215Z/summary.json` | 111.98790227247221 | 102.57757457200339 | 114.51627778024151 | 111.00594356149509 | 105.09884654414859 | 179.45698945550248 |

All confirmation lanes passed the same validity gate. The `121.414` run did
not repeat exactly, but the same baseline identity produced another
record-beating run at `119.948`. This supports treating the current baseline
identity as a higher-variance `~120 tok/s` lane and submitting the best valid
single-run result with the confirmation rows attached.

## Decision

- Current best valid result across the Gemma 4 26B A4B Q8 single-B70 fixed
  cold suite: **121.41411987308553 tok/s**, from
  `data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`.
- Same-identity confirmation above the old record:
  **119.94842631460949 tok/s**, from
  `data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json`.
- Do not claim the no-reorder flag as the cause. Keep it as a default-off
  research artifact; headline is the baseline FA-on 32K/VMM VDR2 selected-down
  identity with LM-head DMMV/no-reorder flags unset.
