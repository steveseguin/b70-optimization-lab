# 2026-07-06 - Mixed draft-KV metadata regression guard; draft INT4 group/scale no-win

## Summary

After the external `Qwen/Qwen3.5-0.8B` draft-model no-win experiment, the
current Qwen27 ReplaySSM record recipe stopped reproducing: the exact
`67.519 tok/s` command shape fell to `~60-61 tok/s`. The run identity matched
the record, so this was source drift, not a benchmark identity mistake.

Root cause: the external-draft compatibility patch broadened mixed draft-KV
metadata construction from DFlash-only to **any** `draft_kv_cache_gids`. Normal
intrinsic Qwen MTP then carried `_draft_common_attn_metadata_by_gid` and took
the slower per-group slot-mapping path in `llm_base_proposer.py`, even though
the current record path does not need mixed external-draft KV metadata.

Fix applied in active vLLM source:

- preserve DFlash behavior;
- preserve an explicit opt-in for future external-draft work via
  `VLLM_XPU_SPEC_DECODE_MIXED_DRAFT_KV_METADATA=1`;
- restore default intrinsic Qwen MTP to the record path.

Focused patch artifact:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mixed-draft-kv-metadata-guard-20260706.patch
```

## Evidence

Pre-fix strict fresh screens:

| label | median tok/s | p10 | mean | status |
|---|---:|---:|---:|---|
| `qwen27-wave1-control-gpu0-20260706T100559Z` | `60.349` | `56.659` | `61.388` | pass, cached-zero |
| `qwen27-solo-control-repro-20260706T101502Z` | `61.469` | `57.721` | `62.316` | pass, cached-zero |

The source compare was against the preserved record patch:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-active-source-diff-replayssm-draftint4-record-20260706.patch
```

Post-fix strict fresh support rows:

| label | median tok/s | p10 | mean | quality |
|---|---:|---:|---:|---|
| `qwen27-regressionfix-solo-control-20260706T102009Z` | `68.371` | `62.680` | `68.263` | speed screen only |
| `qwen27-regressionfix-quality-confirm-20260706T102729Z` | `67.338` | `62.325` | `67.642` | repeat64 pass, baseline match all |

Quality-confirm artifacts:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-regressionfix-quality-confirm-20260706T102729Z-candidate-summary-20260706T102729Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-regressionfix-quality-confirm-20260706T102729Z-realistic128-chat-tokenids-qwensuite-20260706T102729Z.json
data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-regressionfix-quality-confirm-20260706T102729Z-repeat64-ctx1024-20260706T102729Z.json
```

This is a reproducibility restoration/support row, not a new LocalMaxxing
submission. The current conservative record remains `67.51904968102535 tok/s`
from `qwen27-replayssm-draftint4-slotmgmt-torchfallback-solo-confirm`.

## Draft INT4 group/scale mini-screen

The only cheap current-record family that was not already closed was draft
INT4 LM-head packing/scale. After the metadata guard restored the record path,
a four-GPU same-window strict fresh screen tested:

| label | delta | median tok/s | p10 | mean | status |
|---|---|---:|---:|---:|---|
| `qwen27-wave2-control-fixed-gpu0-20260706T102352Z` | group128 BF16 scales | `67.665` | `61.591` | `67.190` | pass, cached-zero |
| `qwen27-wave2-draftg64-fixed-gpu1-20260706T102352Z` | `VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=64` | `66.138` | `61.411` | `65.972` | pass, cached-zero |
| `qwen27-wave2-draftg256-fixed-gpu2-20260706T102352Z` | `VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=256` | `65.819` | `63.558` | `66.948` | pass, cached-zero |
| `qwen27-wave2-draftscale-fp32-fixed-gpu3-20260706T102352Z` | `VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=fp32` | `66.501` | `61.478` | `66.139` | pass, cached-zero |

Conclusion: keep `group_size=128` and BF16 draft scales. None of the group or
scale variants beat the same-window control, so no quality reruns or
LocalMaxxing submissions are warranted.

## Lessons

- Reconfirm the record recipe after compatibility experiments, even when new
  paths are intended to be default-off. A default-off feature can still add
  metadata or dispatch work to the hot path.
- For explicit external-draft experiments that need mixed draft KV groups, set
  `VLLM_XPU_SPEC_DECODE_MIXED_DRAFT_KV_METADATA=1` deliberately.
- Do not repeat draft INT4 group64, group256, or fp32-scale screens under the
  current ReplaySSM record family unless the draft LM-head implementation
  changes materially.
- Cheap env/config space is now essentially closed for this record family.
  Further >100 tok/s work needs a stronger target-matched drafter,
  graph-safe/exact GDN transactions for a better speculative path, or real
  target-forward/kernel reduction.
