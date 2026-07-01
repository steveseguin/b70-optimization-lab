# Qwen3.6 INT8 Sequence Parallel SP1 Rejection

Date: 2026-06-10

## Context

I tested vLLM's sequence-parallel fusion pass on the accepted Qwen3.6 INT8
no-prefix runtime.

The intent was to reduce all-reduce plus norm/quant boundaries without changing
model math. The current generated graph has repeated BF16 hidden-state
all-reduces around `[tokens, 2048]` tensors and many RMSNorm / INT8 quant
boundaries, so sequence parallelism was the next plausible non-quantization
candidate after scheduler and oneCCL knobs were exhausted.

Candidate changes:

- `VLLM_XPU_EXPERIMENTAL_ENABLE_SP=1`
- compilation config `pass_config.enable_sp=true`
- compilation config `pass_config.sp_min_token_num=1`
- same TP4, 32K context, Quark W8A8 INT8, BF16 runtime, no-prefix baseline

## Startup Behavior

vLLM accepted the requested pass but rewrote the compile setup:

- removed capture sizes `1` and `2` because SP requires batch sizes divisible by
  TP size `4`
- changed requested `PIECEWISE` graph capture to `FULL`
- emptied `splitting_ops` to preserve SP

Effective capture sizes became:

```text
[4, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96]
```

That alone makes this risky for the single-user path, where the accepted
runtime can capture smaller decode sizes.

## Failure

The candidate failed before serving during startup memory profiling / compile:

```text
torch._inductor.exc.InductorError:
RuntimeError: The size of tensor a (s18) must match the size of tensor b
((s18//4)) at non-singleton dimension 0
```

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-sp1-startup-fail-20260610.json`

Log:

- `/tmp/qwen36-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix-sp1.log`

## Decision

Reject forced sequence parallelism for the current Qwen3.6 INT8 XPU runtime.
It does not reach the endpoint health gate, so no quality or speed benchmark is
valid.

The accepted no-prefix backend was restored after the failed startup. Future SP
work needs a code fix for the symbolic sequence dimension mismatch before it is
worth another endpoint test.
