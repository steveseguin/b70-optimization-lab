# Qwen3.6 Phase 3: steady-state metadata copy skip

Date: 2026-06-21

Scope: `vllm/v1/worker/gpu_model_runner.py`, `_prepare_inputs()` metadata copies for TP4
single-request decode. All runs below used the guarded PIECEWISE forced-comm identity plus
`VLLM_XPU_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS=8` unless noted.

## Result Summary

- Matched baseline, `EE8-A-noskip`:
  - `data/qwen36-ablation-EE8-A-noskip-summary-20260621053801.json`
  - `91.18 tok/s`, `10.98 ms/tok`, JSON `16/16 PASS`, color `16/16 PASS`.

- Broad four-copy skip, `EE8-B-skip`:
  - skipped `query_start_loc`, `req_indices`, `query_pos`, `num_scheduled_tokens`.
  - Metrics: `92.62 tok/s`, `10.80 ms/tok`.
  - Hung during JSON canary with one running request and no generation progress.
  - Decision: reject. Do not skip `query_start_loc`.

- Safer two-copy skip, `EE8-B2-skip-idxpos`:
  - skipped only `req_indices` and `query_pos`.
  - `data/qwen36-ablation-EE8-B2-skip-idxpos-summary-20260621054919.json`
  - `92.07 tok/s`, `10.86 ms/tok`, JSON `16/16 PASS`, color `16/16 PASS`.
  - Current vLLM WIP has this safer version, gated by `VLLM_XPU_PI_SKIP_STEADY_STATE=1`.

- Three-copy skip, `EE8-B3-skip-idxpos-numsched`:
  - skipped `req_indices`, `query_pos`, and `num_scheduled_tokens`; kept `query_start_loc` live.
  - `data/qwen36-ablation-EE8-B3-skip-idxpos-numsched-summary-20260621055326.json`
  - `92.49 tok/s`, `10.81 ms/tok`, JSON `16/16 PASS`, color `16/16 PASS`.
  - Final96 validation hit `UR_RESULT_ERROR_DEVICE_LOST` during JSON repeat 4:
    `data/qwen36-ablation-EE8-B3-skip-idxpos-numsched-final96-summary-20260621055659.json`.
  - Kernel log recorded Xe engine resets/devcoredump starting at `2026-06-21 02:00:00`
    on `0000:23:00.0` (`/dev/dri/card3`).
  - Decision: not promotable without a clean post-reset 96/96 rerun.

- B2 final96 rerun after the B3 device loss:
  - `data/qwen36-ablation-EE8-B2-skip-idxpos-final96-summary-20260621060531.json`
  - Failed immediately with `UR_RESULT_ERROR_DEVICE_LOST` during the first metrics request.
  - This run is invalid as quality evidence because the driver was already in a reset/coredump state.

## Current Decision

Do not commit the copy-skip patch. The broad version is rejected, and the safer two-copy
version also failed a known-good 96-repeat quality lane after the driver reset.

Post-reset follow-up:

- The launcher initially failed XCCL preflight because `eth1` no longer existed after reset.
  Setting `FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1` fixed the all-reduce preflight.
- Matched EE8 no-skip final96:
  - `data/qwen36-ablation-EE8-postreset-A3-noskip-final96-summary-20260621154017.json`
  - JSON `96/96 PASS`, color failed at repeat 22 with `blue, green, red, yellow`.
- Matched EE8 B2 final96:
  - `data/qwen36-ablation-EE8-postreset-B2-skip-idxpos-final96-summary-20260621153649.json`
  - JSON `96/96 PASS`, color failed at repeat 22 with the same `blue, green, red, yellow`.
  - Conclusion: that color failure belongs to the EE8 graph lane, not B2.
- Known-good no-EE8 baseline lane:
  - `data/qwen36-ablation-tp4-baseline-verify-summary-20260621031153.json`
  - `GPU_MEMORY_UTILIZATION=0.90`, no eager-every-N, JSON `96/96 PASS`, color `96/96 PASS`.
- B2 on the known-good no-EE8 baseline lane:
  - `data/qwen36-ablation-tp4-baseline-verify-B2-skip-idxpos-final96-summary-20260621154414.json`
  - `91.90 tok/s`, `10.88 ms/tok`, JSON failed at repeat 12 with
    `{"answer": "12", "unit": "widgets"}`, color `96/96 PASS`.
  - Conclusion: B2 is not quality-safe. The WIP was removed from vLLM.

## Next Clean-Room Validation After Reboot

1. Do not retry metadata copy skipping unless a new correctness explanation is found.
2. Move to a different Phase 3 target: GPU-side `num_computed_tokens` update or slot-mapping reuse.
3. Include `FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1` in future launches on this post-reset host state.

## Follow-Up: GPU-Side `num_computed_tokens` Update

Tried replacing the steady-state `num_computed_tokens[:num_reqs].copy_(cpu_tensor)` with an
opt-in GPU `add_(1)` path guarded by `VLLM_XPU_PI_GPU_NUM_COMPUTED=1`.

- Smoke label: `tp4-numcomp-gpu-smoke16`
- Identity: no eager-every-N, `GPU_MEMORY_UTILIZATION=0.90`, same known-good TP4 baseline
  cache/flags, `FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1`.
- Artifact: `data/qwen36-ablation-tp4-numcomp-gpu-smoke16-summary-20260621155417.json`
- Result: `90.18 tok/s`, `11.10 ms/tok`, JSON failed at repeat 12 with
  `{"answer": "12", "unit": "widgets"}`, color `16/16 PASS`.
- Decision: rejected and removed from vLLM. It did not improve speed and failed the quick
  JSON gate on the known-good baseline lane.
