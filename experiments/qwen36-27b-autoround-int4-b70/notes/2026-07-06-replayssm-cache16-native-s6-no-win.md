# Qwen27 ReplaySSM Cache16 Native Spec6 Kernel: No Win

Date: 2026-07-06

Classification: source/kernel experiment, strict fresh diagnostic endpoint
screen, quality disabled, no promote, no LocalMaxxing.

## Purpose

The earlier deeper-MTP screen found that MTP4/MTP5 require
`VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=16`, but cache16 fell out of the native
ReplaySSM fast path and collapsed even ordinary MTP3 to about `12.5 tok/s`.
This experiment added a narrow native cache16/spec6 path so MTP4 and MTP5 could
run without the slow generic ReplaySSM fallback.

## Patch

Preserved patch:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-cache16-spec6-no-win-20260706.patch
```

The patch widened:

- `gdn_linear_attn.py` native ReplaySSM gate from `max_spec_len <= 4` and
  `max_cache_len in (2, 4, 8)` to `max_spec_len <= 6` and
  `max_cache_len in (2, 4, 8, 16)`;
- `spec_decode.hpp` dispatch with `REPLAY_CACHE_CASE(16)` and
  `REPLAY_SPEC_CASE(6)`.

The live source/runtime was restored to the promoted cache8/spec4 range after
the no-win result so future baseline runs do not accidentally depend on an
unpromoted binary.

## Build

Candidate `_xpu_C` build:

```text
/home/steve/src/vllm-xpu-kernels/build/xpu-c-only-20260706T073624-replayssm-cache16
/tmp/vllm-xpu-xpu-c-only-20260706T073624-replayssm-cache16-s6/vllm_xpu_kernels/_xpu_C.abi3.so
```

Candidate sha256:

```text
df253c2e5adfeb71ef7d5131daa0b2f0acdf3e0be2c44e791e807ea55aef11bb
```

Restored prior live `_xpu_C` sha256:

```text
9ffb840adbf45a1cd52b42fedde62532a1643a1b8c8b25076728c6548f5de84a
```

The S8 bucket attempt was too heavy in AOT final link and was abandoned. The
S6 build completed, but final AOT emitted large spill warnings for the wider
ReplaySSM templates, especially `MaxSpecLen=6`/`CacheLen=16` variants. That is
consistent with the endpoint throughput loss below.

## Direct Parity

New reusable harness:

```text
scripts/check-gdn-replayssm-spec-native.py
```

The harness can preload a temporary `_xpu_C.abi3.so` with
`--xpu-c-extension` so candidate kernels can be tested without replacing the
live runtime.

Native-vs-PyTorch fallback parity passed for cache16/spec4, cache16/spec5, and
cache16/spec6 across BF16, FP16, and FP32. Tracked outputs:

```text
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s4-bf16-20260706.json
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s5-bf16-20260706.json
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s6-bf16-20260706.json
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s4-fp16-20260706.json
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s5-fp16-20260706.json
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s6-fp16-20260706.json
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s4-fp32-20260706.json
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s5-fp32-20260706.json
data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-spec-native-cache16-s6-fp32-20260706.json
```

## Endpoint Screen

All endpoint rows used the fixed realistic Qwen suite, one cold response per
prompt, `cached_tokens=0`, token-id timing, and no prompt/KV/history reuse.
`RUN_QUALITY=0` because this was a diagnostic screen after direct parity, and
no candidate beat the current record.

Common exact recipe:

- `webhie/Qwen3.6-27B-int4-AutoRound`
- one B70, TP1
- target LM-head runtime INT8 with BF16 scales
- draft LM-head runtime INT4, group size 128, BF16 scales
- ReplaySSM exact GDN, `COMMIT_IN_FORWARD=1`, slot management Torch fallback
- XPU graph enabled

| Label | MTP / graph / cache | Median tok/s | p10 | Mean | TTFT median ms |
| --- | --- | ---: | ---: | ---: | ---: |
| `qwen27-replayssm-s6-mtp3-cache8-control` | MTP3 / cg8 / cache8 | `67.81601753129405` | `61.80083279124912` | `67.33471995731747` | `483.64797490648925` |
| `qwen27-replayssm-s6-mtp3-cache16` | MTP3 / cg8 / cache16 | `65.4101584878007` | `56.41840985257063` | `64.84735488364964` | `480.836407514289` |
| `qwen27-replayssm-s6-mtp4-cache16-cg16` | MTP4 / cg16 / cache16 | `61.63715286869575` | `55.234781922766565` | `61.709133348382984` | `570.1365609420463` |
| `qwen27-replayssm-s6-mtp5-cache16-cg16` | MTP5 / cg16 / cache16 | `58.140373133944` | `52.959479744634315` | `58.81044506697564` | `663.8985238969326` |

Tracked compact endpoint summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s6-mtp3-cache8-control-candidate-summary-20260706T0837diag.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s6-mtp3-cache16-candidate-summary-20260706T0837diag.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s6-mtp4-cache16-cg16-candidate-summary-20260706T0837diag.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s6-mtp5-cache16-cg16-candidate-summary-20260706T0837diag.json
```

## Interpretation

The patch fixed the endpoint readiness failure for MTP4/MTP5 by keeping cache16
inside native ReplaySSM, but it did not create a faster path. Cache16 at MTP3
lost about `2.4 tok/s` versus same-window cache8 control, and deeper MTP got
slower as speculation depth increased.

Likely causes:

- wider ReplaySSM templates have high register/private-memory spill in AOT;
- MTP4/MTP5 increase target/draft/verifier work without enough extra verified
  accepted tokens on this fixed realistic suite;
- cg16/deeper graph capture adds pressure but does not improve the expensive
  verifier-step economics.

## Decision

No promote. No LocalMaxxing.

Do not repeat cache16/spec6 as a simple dispatch-widening experiment. Future
deeper-spec work needs a lower-pressure ReplaySSM transaction, a stronger
drafter/acceptance change, or a kernel design that reduces verifier/LM-head
work enough to offset deeper speculation. Config-only MTP4/MTP5 sweeps on this
recipe remain closed.
