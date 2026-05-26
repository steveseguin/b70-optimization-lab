# XPU KV Offload Artifact Index

This file lists the tracked files needed to review or reproduce the
session-cache, TurboQuant, and CPU-paged attention work.

## Scripts

- `scripts/serve_session_cache.sh` - starts c1/c2/c4/c8 profiles using the
  baseline MiniMax server wrapper.
- `scripts/switch_session_cache_profile.sh` - stops the current MiniMax server,
  starts a selected profile, waits for readiness, and writes a state file.
- `scripts/session_cache_status.sh` - prints profile state, vLLM processes,
  `/v1/models`, and optionally the current log tail.
- `scripts/session_cache_canary.py` - OpenAI-compatible endpoint canary for
  checklist, strict-word, and fact-word prompt modes.

## Patches

- `patches/kv-offload-admission-check-xpu-experiment-20260524.patch`
  - temporary scheduler/admission experiment for CPU KV budget accounting.
  - not a production patch.
- `patches/xpu-cpu-kv-worker-prototype-20260525.patch`
  - XPU CPU KV worker prototype.
  - demonstrated pinned host RAM movement and session-cache behavior.
  - does not provide true active-context overflow.
- `patches/vllm-xpu-gpu-split-attn-stagea-failed-20260525.patch`
  - failed/diagnostic GPU split-attention stage A patch.
  - retained as a negative artifact.

TurboQuant patch outside this folder:

- `../../patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`
  - works around XPU TurboQuant locked-workspace crashes.
  - experimental, not production.

Live source snapshots outside this folder:

- `../../patches/vllm-live-src-snapshot-20260525.patch`
- `../../patches/llm-scaler-live-src-snapshot-20260525.patch`

These are broad dirty-tree snapshots from the originating host. They are useful
for audit and recovery, but they should be split into smaller reviewed patches
before any upstream submission.

## Main Notes

- `README.md` - long running summary of the research lane.
- `REPRODUCE.md` - command-oriented reproduction guide.
- `notes-20260525-session-cache-operations.md` - live c2/c4 operations results
  and the current profile-switching model.
- `notes-20260525-c2-session-cache-ladder.md` - c2 capacity ladder.
- `notes-20260525-c4-c8-session-cache-ladder.md` - c4/c8 correctness ladder.
- `notes-20260525-sustained-concurrency-decode.md` - c4/c8 warmed total decode
  throughput.
- `notes-20260525-c2-quality-and-turboquant.md` - c2 quality checks plus
  TurboQuant workspace patch and k8v4 results.
- `notes-20260525-turboquant-active-context-boundary.md` - TurboQuant long
  active-context limits.

## CPU-Paged Attention Notes And Probes

- `notes-20260525-cpu-paged-attention-design.md`
- `notes-20260525-dense-staged-cpu-attention.md`
- `notes-20260525-stagea-gpu-split-attention.md`
- `probes/split_attention_merge_probe.py`
- `probes/xpu_flash_attn_split_probe.py`
- `probes/xpu_cpu_staged_attention_probe.py`
- `probes/xpu_cpu_dense_staged_attention_probe.py`

Tracked probe outputs:

- `split_attention_merge_probe_20260525.json`
- `split_attention_merge_probe_20260525-uneven.json`
- `xpu_flash_attn_split_probe_20260525.json`
- `xpu_kv_block_copy_probe_20260524.json`
- `xpu_kv_block_copy_probe_20260524-indexed-fail.json`
- `xpu_kv_block_copy_probe_20260524-slice.json`
- `xpu_stream_copy_probe_20260524.json`

## Reproduction Boundaries

Tracked in GitHub:

- scripts
- patches
- result summaries
- notes
- small probe outputs

Not tracked in GitHub:

- MiniMax model weights
- secrets
- compiled native build outputs
- Torch/AOT caches
- full raw `/mnt/fast-ai/bench-results` tree

If a note references a raw local log, treat the summarized values in the note as
the portable record unless the raw file is explicitly copied into GitHub.
