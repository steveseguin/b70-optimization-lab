# 2026-07-06: Qwen27 MTP `fc` Runtime INT8 No-Win

## Context

Current strict record family for `webhie/Qwen3.6-27B-int4-AutoRound` uses:

- TP1 on one B70;
- XPU graph PIECEWISE, `max_cudagraph_capture_size=8`;
- MTP3;
- runtime INT8 target LM-head with BF16 scales;
- runtime INT4 draft LM-head with BF16 scales;
- ReplaySSM exact GDN state with commit-in-forward and Torch slot-management fallback.

The Qwen3.5 MTP drafter keeps `mtp.fc` as BF16 (`ColumnParallelLinear`,
`10240 -> 5120`, `bias=False`). The hypothesis was that quantizing this
draft-only layer at runtime to INT8 could reduce recurrent drafter overhead
without changing target verification semantics. Target output remains verified
by the declared target model, so the main risk is lower acceptance/speed, not
unverified output quality.

## Patch

Preserved patch:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mtp-fc-int8-no-win-20260706.patch`

The patch added default-off env flags:

- `VLLM_XPU_MTP_FC_INT8=1`;
- `VLLM_XPU_MTP_FC_INT8_SCALE_DTYPE=bf16`.

It detected only unquantized XPU linear layers with prefix `mtp.fc`, prepared a
per-output-channel INT8 copy of the BF16 weight, and called the existing
`per_token_quant_int8_xpu` + `int8_gemm_w8a8` path in `UnquantizedLinearMethod.apply`.

## Strict Fresh Screen

All completed speed rows used the fixed realistic Qwen27 suite, each prompt once,
`cached_tokens=0`, token-id timing, and `RUN_QUALITY=0` for speed-screen only.

Same-window controls:

- GPU0 control:
  - summary: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtpfcint8-control-gpu0-20260706T054935Z-candidate-summary-20260706T054935Z.json`
  - median `67.95399595631264 tok/s`;
  - mean `67.54298055203351`;
  - p10 `62.22812404960207`;
  - TTFT median `475.4159116419032 ms`.
- GPU2 control:
  - summary: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtpfcint8-control-gpu2-20260706T054935Z-candidate-summary-20260706T054935Z.json`
  - median `67.99449972803376 tok/s`;
  - mean `67.55076761355642`;
  - p10 `62.03931881967918`;
  - TTFT median `478.7820464698598 ms`.

Candidate:

- GPU3 `VLLM_XPU_MTP_FC_INT8=1`:
  - summary: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtpfcint8-candidate-gpu3-20260706T054935Z-candidate-summary-20260706T054935Z.json`
  - median `66.77669253248513 tok/s`;
  - mean `67.12570166395521`;
  - p10 `61.84543227259525`;
  - TTFT median `476.8169685266912 ms`.

Candidate startup failure:

- GPU1 `VLLM_XPU_MTP_FC_INT8=1` failed during engine startup:
  - summary: `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtpfcint8-candidate-gpu1-20260706T054935Z-candidate-summary-20260706T054935Z.json`
  - server log: `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-mtpfcint8-candidate-gpu1-20260706T054935Z-20260706T054935Z/server.stdout.log`
  - key error: `torch._subclasses.fake_tensor.UnsupportedOperatorException: _xpu_C.int8_gemm_w8a8.default`.

## Decision

Close as **no-win**:

- the only completed INT8-`mtp.fc` candidate was slower than both same-window
  controls by about `1.7-1.8%`;
- one candidate also exposed a TorchDynamo/fake-tensor compatibility hazard for
  using `_xpu_C.int8_gemm_w8a8` inside the compiled MTP predictor;
- fixing fake-tensor/meta support is not justified because the successfully
  compiled/run candidate already regressed speed.

The active source was reverted after preserving this patch and note. Do not
reopen draft `mtp.fc` runtime INT8 unless there is a stronger timing trace that
shows BF16 `mtp.fc` has become a dominant cost after another larger change.
