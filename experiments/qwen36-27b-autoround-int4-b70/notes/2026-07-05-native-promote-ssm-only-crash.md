# Native GDN Promote SSM-Only Spike: Crash / Inconclusive

Date: 2026-07-05

## Question

The Python fallback GDN speculative state promotion keeps conv-state promotion
off by default because the accepted rolling conv window is already maintained
in the running row; copying speculative conv rows back into the running row can
corrupt the next ordinary decode. The native helper path copied both conv and
SSM rows, which looked like a plausible reason the fast draft-INT4/native rows
were invalid while the slower ReplaySSM/align lane was quality-clean.

## Patch Tested

Default-preserving Python helper change in `/home/steve/src/vllm/vllm/_xpu_ops.py`:

- `_xpu_gdn_copy_state_rows_native(..., copy_conv=True)` can skip the conv copy
  while still copying SSM rows.
- `_xpu_gdn_promote_running_state_native(..., promote_conv=None)` defaults to
  existing conv+SSM semantics unless
  `VLLM_XPU_GDN_NATIVE_PROMOTE_CONV_STATE=0` is set.
- Trace output records `copy_conv` when
  `VLLM_XPU_GDN_STATE_COPY_TRACE_FILE` is enabled.

This was only a partial test: the packed C++ native spec-decode op in
`/home/steve/src/vllm-xpu-kernels/csrc/xpu/gdn_attn/gdn_attn_interface.cpp`
still pre-copies accepted conv rows to running rows via
`copy_conv_rows_to_indices`, so the Python-only switch does not fully align the
native path with Python fallback semantics.

## Run

Label:
`qwen27-draftint4-native-ssmonly-promote-20260705T192203Z`

Key env:

```bash
VLLM_XPU_DRAFT_LM_HEAD_INT4=1
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16
VLLM_XPU_GDN_NATIVE_PROMOTE_CONV_STATE=0
QUALITY_REPEAT_RUNS=64
QUALITY_SKIP_LONG_CONTEXT=1
```

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-ssmonly-promote-20260705T192203Z-candidate-summary-20260705T192203Z.json`
- smoke:
  `data/qwen36-27b-autoround-int4-b70-baselines/smoke-qwen27-draftint4-native-ssmonly-promote-20260705T192203Z-20260705T192203Z.json`
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-native-ssmonly-promote-20260705T192203Z-20260705T192203Z/server.stdout.log`
- runner stdout:
  `/tmp/qwen27-draftint4-native-ssmonly-promote-20260705T192203Z.out`

## Result

Not a valid speed or quality result.

- OpenAI smoke passed with `cached_tokens=0`.
- Several strict-suite requests completed around the usual `~62-64 tok/s`
  server-side generation rate.
- The engine then hit `UR_RESULT_ERROR_DEVICE_LOST` while synchronizing
  `num_accepted_tokens_event` in `_prepare_inputs`.
- The strict benchmark returned HTTP 500; no strict benchmark JSON and no
  quality JSON were produced.
- Device discovery and a quick torch/XPU allocate+synchronize check after the
  run saw all four B70s healthy, so the runtime recovered enough for further
  work.

## Interpretation

The Python SSM-only switch is inconclusive. It may have exposed a native
spec-state bug, or it may have hit the existing XPU/device-lost fragility in
this draft-INT4 path. It does not prove correctness and must not be promoted.

The stronger follow-up is a matched C++ switch around
`copy_conv_rows_to_indices` inside `gdn_attention_spec_decode`, so both Python
promotion and the packed native spec-decode state setup agree on whether conv
rows are copied. Keep the default as current conv+SSM behavior, gate the
experiment behind an env var, and validate with repeat64 before measuring
headline throughput.

## Next Action

After the in-flight extension build finishes, add a default-preserving C++ env
gate for native spec-decode conv pre-copy and rerun the same repeat64 quality
screen. If it still crashes or fails repeat64, preserve the patch and close this
conv-copy lane unless a state trace identifies a narrower row/offset mismatch.
