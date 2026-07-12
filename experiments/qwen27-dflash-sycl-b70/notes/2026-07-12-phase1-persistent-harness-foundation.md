# 2026-07-12 Phase 1 Persistent Harness Foundation

## Decision

Start Phase 1 with four long-lived llama.cpp server processes, one process per
physical B70, before implementing a private native executor. This immediately
removes repeated target-model loading from endpoint iteration while preserving
the option to replace the server workers with a lower-level executor later.

The initial assignment is deliberately homogeneous: all four GPUs use the
same Q4_0/Q8-KV MTP3 control. This makes the first executed run a cross-card
calibration. DFlash5 and DFlash15 `draft-simple` profiles using the DFlash GGUF are
defined as selectable profiles but are
not assigned until calibration is recorded.

## Artifacts

- `../harness/workers.json`: four worker roles, ports, runtime paths, common
  model identity, and MTP/DFlash profiles;
- `../harness/model-pack-manifest.json`: version-one B70 pack identity and
  admission requirements, explicitly marked manifest-only;
- `../harness/golden-corpus-manifest.json`: required M=1/4/8/16 tensor/state
  cases, explicitly diagnostic-only and promotion-ineligible;
- `../../../scripts/qwen27-tp1-workerctl.py`: validate, status, render, and
  dry-run-safe start/stop control.

## Safety And Evidence Rules

- The controller blocks occupied ports, managed live PIDs, and unmanaged llama
  processes pinned to the selected GPU. An unmanaged llama process with
  ambiguous affinity blocks every GPU.
- It never kills an unmanaged process and rejects a PID that appears reused.
- `start` and `stop` do not mutate process state without `--execute`.
- Runtime identities are written outside Git under `/mnt/fast-ai`.
- Persistent worker results are development screens.
- Golden activations and future post-prefill resets are diagnostic-only.
- Strict realistic promotion remains a separate cold unique-prompt gate with
  prompt/KV/history reuse disabled and `cached_tokens=0` throughout.

## Validation Performed

- Python bytecode compilation passed.
- All three JSON manifests passed `python3 -m json.tool`.
- Controller `validate`, `status`, `render`, dry-run `start`, and non-mutating
  absent-worker `stop` passed.
- The four configured endpoints were closed and no explicitly pinned foreign
  llama processes were detected during status validation.
- No server was launched and no active GPU process was changed.

## First Calibration

The first four-worker MTP3 calibration completed under
`data/qwen27-tp1-fourway-calibration/20260712T151554Z/`. All four independent
TP1 rows passed the realistic and cached-zero gates. Medians ranged from
`47.976` to `49.708 tok/s`; GPU0 was the fastest physical card in this pass.

Assign candidates to GPU2/GPU3 and preserve swapped-card comparison before
promotion. Native packed weights and device-to-device KV/GDN restoration are
still unimplemented and must not be implied by this foundation.
