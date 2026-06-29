# 2026-06-29 Q8 LM-Head One-Column DMMV Screen

Status: negative. Valid, but not a full512 record candidate.

## Question

The current FA-on 32K/VMM node profile shows the hottest verifier node is the
one-column Q8_0 LM head:

- `MUL_MAT:node_1775`, `token_embd.weight`;
- output shape around `ne=[262144,1,1,1]`;
- about `1.367 ms/call` in the diagnostic profile.

Read-only audit found that the regular `GGML_OP_MUL_MAT` path for Q8_0 x F32
with `src1_ncols == 1` suppresses DMMV when reordered MMVQ is available, then
uses `reorder_mul_mat_vec_q8_0_q8_1_sycl`. The multi-column reordered-Q8 path
only helps `src1_ncols > 1`; for one column it cannot reuse weights across
columns but still pays Q8_1 activation quantization and full-vocab output
materialization.

Experiment: add a default-off guard
`LLAMA_SYCL_Q8_0_LM_HEAD_1COL_DMMV=1` that keeps DMMV enabled only for the
large-vocab one-column Q8_0 LM-head shape:

- `src0->type == GGML_TYPE_Q8_0`;
- `src1->type == GGML_TYPE_F32`, `dst->type == GGML_TYPE_F32`;
- `src1->ne[1] == 1`, `src1->ne[2] == 1`, `src1->ne[3] == 1`;
- `dst->ne[0] >= 131072`, `dst->ne[1..3] == 1`.

This preserves exact target/verifier semantics: it still produces full F32
logits through an existing backend path.

Patch snapshots:

- source:
  `patches/gemma4-26b-a4b-q8-b70/20260629-q8-lmhead-1col-dmmv-source.patch`;
- harness identity:
  `patches/gemma4-26b-a4b-q8-b70/20260629-q8-lmhead-1col-dmmv-harness.patch`.

Build:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 12
```

The first build wrapper failed with shell `set -u` because Intel
`setvars.sh` references an unset `OCL_ICD_FILENAMES`; rerunning without
nounset matched prior successful builds. SYCL AOT link completed with normal
spill warnings.

## Strict128 Screens

All runs used the current valid record identity unless noted:

- llama.cpp `c926ad098` dirty Gemma record stack;
- UD-Q8_K_XL target/verifier, Q4_0 MTP draft;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`;
- selected-down VDR2 record stack;
- fixed realistic suite, each prompt once, `cached_tokens=0`;
- no prompt/KV cache reuse, checkpoints, response reuse, n-gram/history
  acceleration, or warmed repeated prompts.

Initial strict128 `20260629T222834Z`:

| Lane | DMMV | Summary | Median 1-100 | p10 | Mean | Full | Wall |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPU0 control | unset | `data/gemma4-q8-gpu0-q8lmhead-dmmv-control-strict128-20260629T222834Z/summary.json` | 118.47500667767588 | 105.40327991184263 | 117.22570569636395 | 116.30308824046166 | 99.10793948635578 |
| GPU1 DMMV | `1` | `data/gemma4-q8-gpu1-q8lmhead-dmmv-on-strict128-20260629T222834Z/summary.json` | 119.37331427194674 | 107.14743963593567 | 117.85952686614796 | 119.35362350189573 | 100.04485308213815 |
| GPU2 control | unset | `data/gemma4-q8-gpu2-q8lmhead-dmmv-control-strict128-20260629T222834Z/summary.json` | 123.27132560564803 | 105.23902305680004 | 119.73780521536588 | 118.22102945313856 | 100.89479054526237 |
| GPU3 DMMV | `1` | `data/gemma4-q8-gpu3-q8lmhead-dmmv-on-strict128-20260629T222834Z/summary.json` | 121.38565613521337 | 107.20076940991636 | 120.74420160202249 | 117.28166120157329 | 99.58950580515369 |

Cross-over strict128 `20260629T223041Z`:

| Lane | DMMV | Summary | Median 1-100 | p10 | Mean | Full | Wall |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPU0 DMMV | `1` | `data/gemma4-q8-gpu0-q8lmhead-dmmv-on-xover-strict128-20260629T223041Z/summary.json` | 118.73650199400936 | 101.1850562062643 | 116.2282069145249 | 112.57371033549777 | 96.862215891126 |
| GPU1 control | unset | `data/gemma4-q8-gpu1-q8lmhead-dmmv-control-xover-strict128-20260629T223041Z/summary.json` | 116.39467679073377 | 104.65624459005721 | 116.34630316910546 | 115.78639953553504 | 99.58814143282672 |
| GPU2 DMMV | `1` | `data/gemma4-q8-gpu2-q8lmhead-dmmv-on-xover-strict128-20260629T223041Z/summary.json` | 118.37416692432424 | 105.28048221901256 | 117.84575793587326 | 112.08917576618177 | 94.60339145103487 |
| GPU3 control | unset | `data/gemma4-q8-gpu3-q8lmhead-dmmv-control-xover-strict128-20260629T223041Z/summary.json` | 114.69375289325079 | 104.96094612171267 | 115.1342834890293 | 114.75924486374188 | 97.11036877956503 |

Decision after strict128: mixed but worth a full512 check. DMMV won the
primary median in three of four paired comparisons, but full-output/wall
metrics were inconsistent and one control lane hit `123.27 tok/s`, showing
substantial lane variance.

## Full512 Promotion A/B

Full512 `20260629T223258Z`:

| Lane | DMMV | Summary | Median 1-100 | p10 | Mean | Full512 | Wall | TTFT |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 DMMV | `1` | `data/gemma4-q8-gpu0-q8lmhead-dmmv-on-full512-20260629T223258Z/summary.json` | 115.03967309586312 | 107.09387938754344 | 116.3890808014549 | 111.56300109767861 | 106.456677250421 | 180.39709754521027 |
| GPU1 control | unset | `data/gemma4-q8-gpu1-q8lmhead-dmmv-control-full512-20260629T223258Z/summary.json` | 115.94365502528078 | 104.27593926498719 | 116.07417447125583 | 108.2930766649774 | 104.32771047748113 | 180.33415853278711 |
| GPU2 DMMV | `1` | `data/gemma4-q8-gpu2-q8lmhead-dmmv-on-full512-20260629T223258Z/summary.json` | 115.49055156031608 | 105.11359727583397 | 116.65326284824646 | 108.69212199109427 | 104.4319987355426 | 180.29477150412276 |
| GPU3 control | unset | `data/gemma4-q8-gpu3-q8lmhead-dmmv-control-full512-20260629T223258Z/summary.json` | 117.7230028513285 | 103.28372140342537 | 116.75746950862508 | 108.12894160049169 | 104.01523006732194 | 179.86063798889518 |

All full512 lanes passed the realistic final gate, canary, and
`cached_tokens=0`.

## Decision

Negative. Do not promote or submit.

The DMMV shape guard is correctness-safe and useful as a diagnostic, but the
full512 promotion run lost to controls and stayed below the current
`117.91456485086059 tok/s` record. The better p10 on one candidate lane did
not translate into the primary median.

Next LM-head variant to try, if continuing this path: keep MMVQ but skip Q8
weight reorder only for the same one-column large-vocab LM-head shape. That
tests whether the reordered single-column Q8 kernel itself is the cost, without
falling all the way back to DMMV.
