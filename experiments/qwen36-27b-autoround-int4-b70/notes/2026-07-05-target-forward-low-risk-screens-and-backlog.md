# Qwen27 target-forward low-risk screens and source backlog

Date: 2026-07-05

Context:

- current valid Qwen27 headline remains
  `65.27648650325429 tok/s` for
  `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head (BF16 scales)`;
- latest synchronized timing shows the real bottleneck is target forward
  (`~32.7 ms` per verifier step), not recurrent MTP-next (`~0.66 ms` per
  next call);
- quick config/source-path screens below were run under the strict fresh
  Qwen realistic gate, with each prompt once and `cached_tokens=0`.

## Screen 1: M-RoPE text-only fast path

Hypothesis: this suite is text-only, but Qwen3-Next still carries M-RoPE
positions shaped `[3, tokens]`. Enabling the local
`VLLM_XPU_MROPE_TEXT_ONLY_FASTPATH=1` path should route repeated T/H/W
positions through the ordinary XPU RoPE kernel and avoid the PyTorch
split/cat path.

Run shape:

- current candidate runner;
- one B70 per run, TP1, MTP3/cg8, XPU graph on;
- `RUN_QUALITY=0`;
- fixed realistic suite, `cached_tokens=0`.

Results:

| Mode | Summary | Median tok/s | p10 | Mean | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| control | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mropefastpath-control-20260705T175628Z-candidate-summary-20260705T175628Z.json` | `65.95970880506475` | `58.14211416426976` | `64.32183336747887` | pass |
| `VLLM_XPU_MROPE_TEXT_ONLY_FASTPATH=1` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mropefastpath-on-20260705T175628Z-candidate-summary-20260705T175628Z.json` | `65.7971075898297` | `57.97725485317493` | `64.31192388521039` | pass |

Decision: no win. Do not carry this flag in the promoted recipe. The result is
inside noise and slightly below same-window control.

## Screen 2: GDN native fallback policy

Hypothesis: default `VLLM_XPU_GDN_NATIVE_FALLBACK=decode,prefill` may keep a
decode fallback path active that costs target-forward time. Try `prefill` only.

Run shape:

- current candidate runner;
- one B70 per run, TP1, MTP3/cg8, XPU graph on;
- `RUN_QUALITY=0`;
- fixed realistic suite, `cached_tokens=0`.

Results:

| Mode | Summary | Median tok/s | p10 | Mean | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| `decode,prefill` control | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdnfallback-control-20260705T180005Z-candidate-summary-20260705T180005Z.json` | `65.96666567595972` | `58.17190147152139` | `64.7094104798731` | pass |
| `prefill` only | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdnfallback-prefillonly-20260705T180005Z-candidate-summary-20260705T180005Z.json` | `65.65507197315036` | `57.81115234148267` | `64.19583365985737` | pass |

Decision: no win. Keep the default/current fallback policy.

## Source-audit backlog

The low-risk knobs are not moving the target-forward bottleneck. The next
credible work is source/kernel-level and must preserve exact target
verification:

1. **Fuse or specialize GDN output norm**.
   - Files: `/home/steve/src/vllm/vllm/model_executor/layers/mamba/gdn_linear_attn.py`,
     `/home/steve/src/vllm/vllm/model_executor/layers/layernorm.py`.
   - Current GDN target path runs native core, then `RMSNormGated`, then
     INT8 `out_proj` across 48 linear-attention layers.
   - Completion gate: unit parity for `self.norm(core_attn_out, z)` rows 1/4,
     strict fresh `RUN_QUALITY=0`, then quality `RUN_QUALITY=1` with at least
     repeat64 if speed moves outside variance.
2. **Remove or reuse GDN core zero-fill scratch**.
   - File:
     `/home/steve/src/vllm/vllm/model_executor/layers/mamba/gdn_linear_attn.py`.
   - Current path allocates `core_attn_out = torch.zeros(...)` before the
     native core. If the native decode/spec path writes every actual row,
     replacing zero-fill with empty/reused scratch may remove repeated fills.
   - Risk: stale padded rows are correctness poison; needs row-coverage assert
     or a gated decode-only patch first.
3. **Port QK-norm+RoPE fusion to XPU**.
   - Files:
     `/home/steve/src/vllm/vllm/model_executor/models/qwen3_next.py`,
     `/home/steve/src/vllm/vllm/compilation/passes/fusion/qk_norm_rope_fusion.py`.
   - Existing fusion infrastructure is CUDA-focused; XPU path needs a real op
     and M-RoPE correctness checks.
4. **Full-attention output-gate fusion/in-place multiply**.
   - File: `/home/steve/src/vllm/vllm/model_executor/models/qwen3_next.py`.
   - Smaller opportunity than GDN, but quality-preserving if exact.
5. **Packed non-spec GDN decode with source promotion**.
   - File:
     `/home/steve/src/vllm/vllm/model_executor/layers/mamba/gdn_linear_attn.py`.
   - Only worth patching after trace confirms the current strict target path is
     blocked by `running_state_source_indices_tensor`.

Closed/not worth immediate repeat:

- generic `VLLM_XPU_DEDUP_INT8_QUANT=1|clone`: prior Qwen35 work showed no
  useful rewrites or repeat instability, and the Qwen27 GDN-local quant-reuse
  screen on 2026-07-05 found no credible speed win;
- wrapper-level LM-head/sampler/top-token plumbing: already closed for the
  current record family; the INT8 LM-head/local-argmax path is small.

## Follow-up implementation: GDN core empty scratch is a no-win

Patch artifact:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-core-empty-output-20260705.patch`

Patch:

- added default-off `VLLM_XPU_GDN_CORE_EMPTY_OUTPUT=1`;
- changed only the XPU `gdn_attention_core_xpu` allocation from
  `torch.zeros(...)` to `torch.empty(...)` when the flag is set;
- did not change default behavior;
- live source hunk was reverted after the screen because the result was a
  no-win.

Result:

| Mode | Summary | Median tok/s | p10 | Mean | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| zero control | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdncorezero-control-20260705T180618Z-candidate-summary-20260705T180618Z.json` | `65.86053213047938` | `58.11977144204768` | `64.11720788924745` | pass |
| empty output | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdncoreempty-on-20260705T180618Z-candidate-summary-20260705T180618Z.json` | `64.0721804176446` | `58.0498815506641` | `63.954491283999914` | pass |

Decision:

- no quality run, no LocalMaxxing submission;
- keep `torch.zeros` for the current recipe;
- do not revisit empty scratch unless a lower-level trace proves the zero-fill
  is still on the critical path and a kernel-level write-coverage guarantee is
  available.

## Follow-up implementation: full-attention output-gate in-place is a no-win

Patch artifact:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-inplace-output-gate-20260705.patch`

Patch:

- added default-off `VLLM_XPU_QWEN3_NEXT_INPLACE_OUTPUT_GATE=1`;
- changed `gate = torch.sigmoid(gate); attn_output = attn_output * gate` to
  `gate.sigmoid_(); attn_output.mul_(gate)` only when the flag is set;
- live source hunk was reverted after the screen because the result was a
  no-win.

Result:

| Mode | Summary | Median tok/s | p10 | Mean | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| control | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-outputgate-control-20260705T181209Z-candidate-summary-20260705T181209Z.json` | `64.25056198308314` | `58.241777082177464` | `64.45746668530738` | pass |
| in-place output gate | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-outputgate-inplace-20260705T181209Z-candidate-summary-20260705T181209Z.json` | `63.897688728122496` | `59.34183614149787` | `63.67442462586174` | pass |

Decision:

- no quality run, no LocalMaxxing submission;
- keep the ordinary out-of-place sigmoid/multiply for the current recipe;
- this is too small and compiler-sensitive to chase further unless a graph
  trace later shows `qwen3_next.full_attention.output_gate` as a new hotspot.
