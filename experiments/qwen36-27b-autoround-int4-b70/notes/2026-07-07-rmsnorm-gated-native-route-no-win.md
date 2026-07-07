# 2026-07-07: RMSNormGated Native Route No-Win

## Summary

Screened a low-risk Qwen27 target-body idea: route `RMSNormGated.forward_xpu`
through the existing XPU `_C.rms_norm` primitive plus a separate SiLU multiply
for the exact GDN output-norm case:

- XPU only;
- `z is not None`;
- no bias;
- no group norm;
- `norm_before_gate=True`;
- BF16/FP16 weight matching input dtype;
- activation `silu` / `swish` / `sigmoid`.

The microbench looked attractive, but endpoint A/B did not show a reproducible
strict fresh-response speed win. The patch also is not bit-exact to the FLA
path because `_C.rms_norm` rounds once before the gate multiply. It was
therefore reverted after the screen.

Status: **closed no-win; no LocalMaxxing submission**.

## Patch

Preserved experiment patch:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-rmsnorm-gated-native-route-experiment-20260707.patch
```

The active source was reverted after the A/B.

## Microbench

Direct XPU microbench against the current FLA/Triton-style
`rmsnorm_fn(..., z=z, norm_before_gate=True, activation="silu")` showed the
native route was about `2.0-2.14x` faster for relevant small rows/features.
Representative BF16 timings:

| rows | feature dim | FLA path ms | native route ms | speedup | max diff |
|---:|---:|---:|---:|---:|---:|
| 1 | 128 | `0.0707` | `0.0341` | `2.07x` | `0.015625` |
| 4 | 256 | `0.0694` | `0.0337` | `2.06x` | `0.015625` |
| 16 | 512 | `0.0716` | `0.0335` | `2.14x` | `0.125` |
| 4 | 1152 | `0.0717` | `0.0334` | `2.14x` | `0.0625` |

The diff is expected: the current `_C.rms_norm` kernel rounds the normalized
value to BF16/FP16 before multiplying by the weight/gate, while the FLA path
keeps more of the expression in FP32 before the final cast.

## Endpoint Screen

Single diagnostic screen, strict fresh/cached-zero mechanics, quality skipped:

| label | median tok/s | p10 | mean | interpretation |
|---|---:|---:|---:|---|
| `qwen27-rmsnorm-gated-native-screen-20260707T043847Z` | `68.444` | `62.715` | `68.302` | one-row apparent uplift; not enough to claim |

This looked slightly above the current `68.236` record, but the delta was far
inside expected variance and quality was skipped.

## Same-Window 4-GPU A/B

Ran two controls and two candidates concurrently with the same strict
fresh/cached-zero benchmark. Quality was skipped because this was a variance
screen, not a promotion attempt.

| GPU | mode | median tok/s | p10 | mean |
|---:|---|---:|---:|---:|
| 0 | control | `66.769` | `61.950` | `67.025` |
| 1 | candidate | `67.494` | `63.226` | `67.596` |
| 2 | control | `67.508` | `61.798` | `67.316` |
| 3 | candidate | `66.531` | `61.877` | `67.160` |

Averages:

- controls: `67.138 tok/s`;
- candidates: `67.013 tok/s`.

Decision: no reproducible speed signal. Do not run quality or promote.

## Artifacts

Compact summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-gated-native-screen-20260707T043847Z-candidate-summary-20260707T043847Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-native-ab-control-gpu0-20260707T044221Z-candidate-summary-20260707T044221Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-native-ab-candidate-gpu1-20260707T044221Z-candidate-summary-20260707T044221Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-native-ab-control-gpu2-20260707T044221Z-candidate-summary-20260707T044221Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-rmsnorm-native-ab-candidate-gpu3-20260707T044221Z-candidate-summary-20260707T044221Z.json
```

Raw run directories:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-rmsnorm-gated-native-screen-20260707T043847Z-20260707T043847Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-rmsnorm-native-ab-control-gpu0-20260707T044221Z-20260707T044221Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-rmsnorm-native-ab-candidate-gpu1-20260707T044221Z-20260707T044221Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-rmsnorm-native-ab-control-gpu2-20260707T044221Z-20260707T044221Z
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-rmsnorm-native-ab-candidate-gpu3-20260707T044221Z-20260707T044221Z
```

## Follow-Up

Do not promote this route and do not repeat it as a Python routing change.
If GDN output norm remains attractive later, the next version must be a true
single native gated-RMSNorm kernel that matches the FLA expression order more
closely and first wins a microbench with tighter numerical agreement.

