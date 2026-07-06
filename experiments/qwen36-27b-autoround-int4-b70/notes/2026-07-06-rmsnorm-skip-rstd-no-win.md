# 2026-07-06: Gated RMSNorm `rstd` Skip No-Win

## Context

The current Qwen27 frontier note points at target-forward/model-body cost, not
LM-head wrapper work. Eager/no-compile timing showed the GDN output norm path
around `0.109 ms/layer`, repeated across many GDN layers. The active
`RMSNormGated` path in `fla/ops/layernorm_guard.py` allocates and writes an
`rstd` tensor even though inference callers of `rmsnorm_fn` ignore it.

Hypothesis: skipping the `rstd` allocation/writeback for RMSNorm inference could
reduce repeated GDN-body overhead without changing output values.

## Patch

Preserved patch:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-rmsnorm-skip-rstd-no-win-20260706.patch`

Patch behavior:

- added default-off `VLLM_XPU_RMSNORM_SKIP_RSTD=1`;
- added a Triton constexpr `STORE_RSTD`;
- when enabled for `is_rms_norm`, reused the output storage as an unused dummy
  pointer, skipped the `tl.store(Rstd, rstd)` path, and returned `None` for the
  ignored `rstd` output;
- default behavior unchanged.

## Strict Fresh Screen

Run shape:

- fixed Qwen27 realistic suite;
- each prompt once;
- `cached_tokens=0` on every completed row;
- token-id timing;
- `RUN_QUALITY=0` speed screen only.

Same-window controls:

- GPU0 control:
  - summary: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-rstd-control-gpu0-20260706T055853Z-candidate-summary-20260706T055853Z.json`
  - median `67.71592045373396 tok/s`;
  - mean `67.59823939724272`;
  - p10 `62.10107676852655`;
  - TTFT median `484.9030689802021 ms`.
- GPU2 control:
  - summary: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-rstd-control-gpu2-20260706T055853Z-candidate-summary-20260706T055853Z.json`
  - median `67.91016116675588 tok/s`;
  - mean `67.39192349183048`;
  - p10 `61.85500585315465`;
  - TTFT median `481.00104148034006 ms`.

Candidates:

- GPU1 `VLLM_XPU_RMSNORM_SKIP_RSTD=1`:
  - summary: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-rstd-skip-gpu1-20260706T055853Z-candidate-summary-20260706T055853Z.json`
  - median `66.3292224544168 tok/s`;
  - mean `67.01162573190287`;
  - p10 `61.79784007197728`;
  - TTFT median `495.9458914818242 ms`.
- GPU3 `VLLM_XPU_RMSNORM_SKIP_RSTD=1`:
  - summary: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-rstd-skip-gpu3-20260706T055853Z-candidate-summary-20260706T055853Z.json`
  - median `66.59453333146752 tok/s`;
  - mean `67.2958320272507`;
  - p10 `61.99598676615535`;
  - TTFT median `482.47650754638016 ms`.

## Decision

Close as **no-win**:

- both candidates were slower than both controls;
- no quality run or LocalMaxxing submission;
- source reverted after preserving the patch and result summaries.

Do not reopen `rstd`-skip unless a future trace shows this exact store/allocation
has become a dominant path after a larger target-forward change.
