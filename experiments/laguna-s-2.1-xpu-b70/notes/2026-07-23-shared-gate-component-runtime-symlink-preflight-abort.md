# Shared-gate component runtime-symlink preflight abort

Date: 2026-07-23 EDT / 2026-07-24 UTC

## Classification

- Outcome: rank-0 pre-tensor tooling abort; no component measurement.
- Authorization packet:
  `data/laguna-s-2.1-shared-gate-m8-component-authorization-20260724T022700Z.json`
- Authorization commit: `f465685fbfb64f098d3e1bbffb6ea9a20980ed1e`
- Tools commit: `878369f7de0a81d48902ccd34d5cfa8e19a94fc1`
- Artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-component-878369f7d-20260724T022700Z`
- Runner diagnostic:
  `required regular file missing: runtime level_zero_driver`
- Failure classification:
  `pre_tensor_identity_or_tooling`, with `tensor_work_started=false`.
- Campaign terminal:
  `campaign_failed_stop_before_analyzer`, with all downstream authorization
  fields false.
- Cards 1 through 3: not started.
- Component tensors, exactness epochs, timing, counters, model generation,
  endpoint work, network access, reboot, and submission: not started.

This authorization and artifact root are terminal and must not be reused.

## Preserved evidence

- `campaign-start-checkpoint.json`:
  `2367daff165129ed30806f1c8a1492d3545a97e2b200497f5120e8ee6ef9962f`
- `rank-0-pre-tensor-failure.json`:
  `f6b9471ddbb222d5fd3f7f623b2d0523563629e1853b970b4c24d3e09e0f2941`
- `rank-0-terminal.json`:
  `74adb0e44ec9f42a1730f8a27d26ee15d8b3fc69bdac2c5e0653e7af8efab6ab`
- `campaign-terminal.json`:
  `62d541af17b4deb88b1f7d0227b26cda975b1bd1c79fcb9388216346ec60dbce`

The coordinator acquired the campaign root only after its one unfiltered and
four card-filtered `xpu-smi discovery -j` probes matched the frozen four-card
mapping.

## Root cause and correction

The packet and Stage 0 identity schema intentionally record both a SONAME path
and its immutable resolved target. The installed Level Zero driver and loader
SONAME paths are normal symlinks. The component runner alone reused an evidence
helper that rejects every symlink before checking `resolved_path` and SHA-256;
the Stage 0 runner, component contract, and component analyzer all accept the
recorded path only when its resolved target and bytes match.

The correction permits the recorded runtime path to be a symlink, resolves it
strictly, requires the resolved target to be a regular non-symlink file, and
compares the exact recorded path, resolved path, and target SHA-256. A CPU-only
regression test proves the frozen symlink target is accepted and a retargeted
symlink is rejected. After full regression and independent review, use a new
tools commit, authorization packet, and NVMe campaign root.
