# Qwen27 GDN qkvz/ba quant reuse screen: no win

Date: 2026-07-05

Objective: test whether the existing Qwen3-Next GDN input-activation
quantization reuse path can reduce target-forward cost for the current valid
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head (BF16 scales)`
record family.

Context:

- latest synchronized timing says the real short-decode bottleneck is target
  forward (`~32.7 ms` per verifier step), not the recurrent MTP-next body;
- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT` is an existing default-off XPU path in
  `gdn_linear_attn.py` that quantizes the GDN input once, then feeds both
  `in_proj_qkvz` and `in_proj_ba`;
- `clone`, `clone-ba`, and `clone-qkvz` modes preserve at least one cloned copy
  of the quantized buffers, avoiding the riskiest direct aliasing mode.

Run shape:

- same-window four-GPU strict fresh screen;
- current candidate runner:
  `experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh`;
- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- one B70 per run, TP1, MTP3/cg8, XPU graph on;
- `VLLM_XPU_LM_HEAD_INT8=1`;
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- `RUN_QUALITY=0` because this was a speed screen only;
- fixed realistic Qwen suite, each prompt once, `cached_tokens=0`.

Results:

| Mode | Summary | Median tok/s | p10 | Mean | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| control | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-reuseqkvzbaquant-control-20260705T174737Z-candidate-summary-20260705T174737Z.json` | `64.39757972150375` | `57.395137447179536` | `63.45994052556208` | pass |
| clone | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-reuseqkvzbaquant-clone-20260705T174737Z-candidate-summary-20260705T174737Z.json` | `63.91499347675155` | `59.26112510527906` | `63.538690027143225` | pass |
| clone-ba | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-reuseqkvzbaquant-cloneba-20260705T174737Z-candidate-summary-20260705T174737Z.json` | `63.24928464535833` | `57.95452548131983` | `63.67836266388531` | pass |
| clone-qkvz | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-reuseqkvzbaquant-cloneqkvz-20260705T174737Z-candidate-summary-20260705T174737Z.json` | `64.82431011932849` | `57.87064511408343` | `63.71761114210782` | pass |

Interpretation:

- All rows passed the strict fresh gate with `cached_tokens=0`.
- Best variant was `clone-qkvz`, but it only beat the same-window control by
  about `+0.66%`, far inside the known Qwen27 variance band.
- Full clone and `clone-ba` were slower than control on the primary metric.
- No variant was quality-gated or submitted to LocalMaxxing because there is no
  credible speed win.

Decision:

- Close `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT` as a no-win for the current
  Qwen27 record recipe.
- Do not carry it in the promoted recipe.
- Keep the experiment as evidence that simple GDN qkvz/ba quant reuse does not
  materially reduce target-forward time in this workload.
