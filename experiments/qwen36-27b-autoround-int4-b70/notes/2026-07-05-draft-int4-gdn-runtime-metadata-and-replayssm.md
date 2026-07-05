# 2026-07-05: draft INT4 GDN runtime metadata fix, fast invalid lanes, ReplaySSM valid no-win

Objective: beat the current valid one-B70 Qwen27 record
`65.27648650325429 tok/s` for
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head BF16 scales`
without lowering quality or using cached/history effects.

Current record remains unchanged:

- result packet:
  `results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json`;
- LocalMaxxing id: `cmr5iu3gk00bfq901nidgcana`;
- strict fresh gate: fixed realistic suite, each prompt once,
  `cached_tokens=0`, median tokens 1-100 after TTFT.

## Source patch

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-runtime-mode-metadata-20260705.patch
```

What it changed:

1. `gpu_model_runner._build_attention_metadata()` now threads the *actual*
   XPU cudagraph runtime mode into `GDNAttentionMetadataBuilder`.
2. `GDNAttentionMetadataBuilder.build()` uses static speculative graph
   metadata only when the current runtime mode is really PIECEWISE (or when no
   runtime mode was supplied, preserving the previous compile-config fallback).
3. `_prepare_input_ids()` no longer returns before scattering draft tokens when
   the async common-token copy path also has speculative draft indices.

Why: graph-bypass flags (`VLLM_XPU_DISABLE_FIRST_DECODE_CUDAGRAPH_REPLAY`,
initial decode bypass, etc.) set the model runner runtime mode to
`CUDAGraphMode.NONE`, but GDN was still deciding to use static speculative graph
metadata from the compile-time `PIECEWISE` config. Before the patch, first
decode/init2/init4 bypass lanes crashed with `UR_RESULT_ERROR_DEVICE_LOST` at
`num_accepted_tokens_event.synchronize()` after dumping scheduler rows with
`scheduled_spec_decode_tokens=[-1, -1, -1]`.

Result: the bypass lanes no longer crash. This is a real stability fix, but it
does not by itself make the fast draft-INT4 path valid.

## Key result table

All rows below are strict fresh-response screens unless marked otherwise. They
use fixed prompts once, no warmed prompt averaging, and `cached_tokens=0` for
completed strict runs.

| label | median tok/s | p10 | quality | status |
| --- | ---: | ---: | --- | --- |
| `qwen27-candidate` draft-INT4 runtime-metadata probe | `71.9205867428926` | `65.66740414625727` | fail repeat32 | invalid fast |
| target INT8 + draft INT4 + promote + firstdecode eager | `70.01300192352346` | `63.415753656227494` | fail repeat32 | invalid fast |
| target INT8 + draft INT4 + promote + init2 eager | `71.06724146402561` | `64.95668630773118` | fail repeat32 | invalid fast |
| target INT8 + draft INT4 + promote + init4 eager | `71.13536242151972` | `65.22797297025743` | fail repeat32 | invalid fast |
| target INT8 + draft INT4 + promote + no async | `67.38932250893724` | `60.64806665568682` | fail repeat32 | invalid fast |
| target INT8 + draft INT4 + zero fresh GDN state | `70.30037291587749` | `66.38921076374783` | fail repeat32 | invalid fast |
| target INT8 + draft INT4 + zero all prefill GDN state | `71.33858857030877` | `64.7416031601105` | fail repeat32 | invalid fast |
| target INT8 + draft INT4 + align + restore partial/full accept | `72.19979074970183` | `65.09589083757628` | fail repeat32 | invalid fast |
| target INT8 + draft INT4 + ReplaySSM + align | `61.412051018335944` | `57.34833328687105` | pass repeat32, baseline match | valid no-win |
| no-bonus / no-bonus+recompute / draft-only recovery knobs | none | none | smoke only, strict bench failed | closed |

Important artifacts:

```text
data/qwen36-27b-autoround-int4-b70-baselines/draftint4-gdnmeta-runtime-patch-20260705T154622Z/qwen27-candidate-candidate-summary-20260705T154622Z.json
data/qwen36-27b-autoround-int4-b70-baselines/draftint4-targetint8-promote-runtime-gdnmeta-20260705T155132Z/
data/qwen36-27b-autoround-int4-b70-baselines/draftint4-targetint8-statehygiene-20260705T155654Z/
data/qwen36-27b-autoround-int4-b70-baselines/draftint4-targetint8-recoveryknobs-20260705T160207Z/
```

Run logs:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-candidate-20260705T154622Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-targetint8-draftint4-promote-init4-gpu2-20260705T155132Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-targetint8-draftint4-replayssm-gpu3-20260705T155654Z
```

## Quality failure signature

The invalid fast lanes pass smoke, exact quality cases, baseline-match checks,
and strict fresh-response validity, but fail repeat stability. The repeat
output alternates between:

```text
blue, green, red
blue, green, red, yellow
```

This is not prompt cache cheating: all completed rows report `cached_tokens=0`.
It is also not the earlier graph-bypass crash after the runtime metadata patch.
The signature points to GDN recurrent state accounting at request boundaries /
full-accept packed rows. ReplaySSM+align fixes it, proving the issue is state
transaction correctness, but the current ReplaySSM implementation costs too
much and falls below the existing record.

## Conclusion

No LocalMaxxing submission. The best valid row from this batch is
`61.412 tok/s`, below the current `65.276 tok/s` record. The `70-72 tok/s`
lanes are diagnostic only and must not be promoted or submitted.

Next credible implementation work:

1. Profile ReplaySSM+align to split the `61.4` cost into ReplaySSM commit,
   metadata, snapshot/restore, and target/draft LM-head work.
2. Reduce ReplaySSM overhead or replace it with a targeted full-accept state
   transaction that preserves the `blue, green, red, yellow` repeat stability
   without replaying every speculative GDN row.
3. Keep the runtime GDN metadata patch: it fixes graph-bypass crashes and makes
   future targeted bypass/recovery experiments measurable.
