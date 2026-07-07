# 2026-07-07 - Native XPU RMSNormGated Kernel: Microbench Win, Endpoint No-Win

## Goal

Test whether a true fused native XPU `RMSNormGated` op can reduce Qwen3.6 27B
INT4 MTP3 verifier-body cost without changing quality or benchmark validity.

This revisits the earlier `VLLM_XPU_RMS_NORM_GATED_NATIVE` route, but implements
the exact FLA expression order in one kernel:

```text
out = (x.float() * rsqrt(mean(x.float()^2) + eps) * weight.float()) * silu(z.float())
```

The op casts once at the end, instead of using `_C.rms_norm` followed by a
separate gate multiply.

## Patch Artifacts

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-rmsnorm-gated-native-xpu-no-win-20260707.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-rmsnorm-gated-native-xpu-no-win-20260707.patch`

The active source and `_C.abi3.so` were restored after the endpoint no-win.

## Microbench

Temporary build:

```text
/tmp/vllm-xpu-rmsnorm-gated-20260707T052615Z/vllm_xpu_kernels/_C.abi3.so
```

The op registered successfully when loaded from a temporary package wrapper.

Relevant microbench used Qwen's actual GDN output-norm shape:

- hidden size: `128`
- `norm_before_gate=True`
- dtype: `bf16`
- rows: `1, 4, 16, 48, 96, 192, 384`

Results were numerically exact against the existing FLA path (`max diff = 0`).
The Python-integrated native path was about `3.55x` to `3.63x` faster than the
current wrapper for these isolated shapes:

```text
rows= 48 diff=0 ref_ms=0.073444 native_ms=0.020212 direct_ms=0.007853 speedup=3.634x
rows= 96 diff=0 ref_ms=0.072894 native_ms=0.020255 direct_ms=0.007820 speedup=3.599x
rows=192 diff=0 ref_ms=0.073031 native_ms=0.020547 direct_ms=0.007869 speedup=3.554x
```

## Strict Fresh Endpoint Results

All endpoint runs used the current Qwen27 strict fresh-response recipe:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`
- one B70 GPU
- MTP3
- graph capture size 8
- runtime target LM-head INT8 with BF16 scales
- runtime draft LM-head INT4 with BF16 scales
- fixed realistic prompt suite, each prompt once
- `cached_tokens=0` for every row
- no warmed prompt/history/cache reuse
- metric: median generated tok/s for tokens 1-100 after TTFT

Standalone screen with `VLLM_XPU_RMS_NORM_GATED_NATIVE=1`:

```text
qwen27-rmsnorm-gated-native-xpu-screen-20260707T053124Z
median 68.45309693711278 tok/s
p10    62.63047366052588 tok/s
mean   68.00187632628713 tok/s
```

This was only `+0.3%` over the known `68.23626314761921 tok/s` record, so it was
inside normal variance and not promotable.

Same-window paired check:

```text
baseline GPU0, VLLM_XPU_RMS_NORM_GATED_NATIVE=0
median 67.97975834923001 tok/s
p10    62.34635104515781 tok/s
mean   67.77444475464199 tok/s

native GPU1, VLLM_XPU_RMS_NORM_GATED_NATIVE=1
median 67.92844343479861 tok/s
p10    62.30379569318671 tok/s
mean   67.83979563990616 tok/s
```

The paired result is a no-win. The isolated kernel is faster, but the endpoint
does not improve, likely because this norm is already hidden under graph replay,
interleaved with larger GDN/attention/body work, or not dominant enough to move
the strict median.

## Decision

Do not promote. Keep the patch as a reference for any future lower-level GDN
body fusion work, but do not enable it in the production Qwen27 recipe.

## Next Implication

Small wrapper/kernel cleanups around GDN output norm are not enough to move past
the current `68.236 tok/s` strict fresh record. The next credible work should
target one of:

- fewer verified target rows or stronger accepted tokens per verifier step;
- native graph-safe GDN/ReplaySSM transaction work needed for legal
  branch/regenerate or deeper speculation;
- a producer-integrated LM-head top-id/candidate-score primitive that avoids
  dense logits without adding a separate slow scan.
