# Qwen3.6 INT8 N-Gram k=1 Hold-Prefill Rejection

Date: 2026-06-10

## Context

This was a follow-up to the rejected n-gram k=5 speculative path. The goal was
to test whether a single drafted token could avoid the GDN recurrent-state
corruption seen with multi-token prompt-lookup speculation while preserving the
high single-request speed ceiling.

Runtime:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- endpoint backend: `http://127.0.0.1:18080`
- frontdoor: `http://127.0.0.1:8000`
- TP4, 32K context, Quark W8A8 INT8, BF16 runtime
- prefix caching disabled
- XPU PIECEWISE graph capture capped at `128`
- `--speculative-config {"method":"ngram","num_speculative_tokens":1,"prompt_lookup_min":2,"prompt_lookup_max":5}`
- `VLLM_XPU_HOLD_SPEC_DECODE_WHEN_WAITING=1`

Patch snapshot:

- `patches/vllm-qwen36-ngram1-holdprefill-rejected-20260610.patch`

## Loader Lesson

After stopping the accepted backend, the first relaunch attempts failed before
serving because the editable `vllm_xpu_kernels._xpu_C` extension resolved helper
kernels from `/home/steve/src/vllm-xpu-kernels/build/temp`. Those helper
libraries were stale oneAPI 2026 artifacts and required `libsycl.so.9`.

Loading all oneAPI 2026 runtime libraries caused a Python import segfault. The
working fix was to put the packaged kernel directory before the build directory
through `LD_LIBRARY_PATH`:

```bash
export LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}
```

With that order, `_xpu_C` resolves the stable SYCL-8 helper kernels from
`vllm_xpu_kernels/` instead of the stale SYCL-9 `build/temp` helpers.

## Quality Result

Direct backend quality is not a valid parity check for this model because the
frontdoor injects `chat_template_kwargs={"enable_thinking": false}`. The direct
run emitted reasoning text for every chat canary:

- `data/qwen36-quark-int8-tp4-ngram1-cg128-holdprefill-direct-quality-rerun64-20260610.json`

The valid frontdoor quality run recovered exact canaries and long-context parity
but failed repeat stability:

| check | result |
| --- | --- |
| exact canaries | pass |
| baseline hash parity for exact canaries | pass |
| long-context needle | pass |
| long-context hash parity | pass |
| 64-repeat stability | fail |

Repeat outputs:

- `61/64`: `blue, green, orange, red`
- `1/64`: `utexile.tex.tex.tex...`
- `1/64`: `blue whiskey whiskey green, orange, red`
- `1/64`: `blue, green Cổng red, yellow`

Artifact:

- `data/qwen36-quark-int8-tp4-ngram1-cg128-holdprefill-frontdoor-quality-rerun64-20260610.json`

## Decision

Reject n-gram k=1 speculative decoding for production. It is closer than k=5
on the long-context gate, but it still violates the no-quality-loss rule because
the deterministic repeat gate produced corrupt outputs.

The accepted non-spec backend was restored afterward:

- session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- backend: `http://127.0.0.1:18080`
- restore log: `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix-restore-after-ngram1-20260610.log`
- health: pass
- frontdoor generation smoke: `Reply with exactly: OK` returned `OK`

## Next

Stop spending runtime on vLLM n-gram speculation until the token/state
contamination can be traced at the accepted-token boundary. The next quality-safe
optimization work should return to non-speculative dense/MoE boundary work, or
instrument token-level speculative parity without treating it as a promotion
candidate.
