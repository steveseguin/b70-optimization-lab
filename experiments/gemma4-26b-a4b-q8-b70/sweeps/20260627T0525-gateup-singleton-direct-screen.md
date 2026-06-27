# 2026-06-27T05:25Z Gate/Up Singleton-Direct Screen

## Question

Can the current route-cache `MUL_MAT_ID:ffn_moe_gate_up-*` path avoid
gather/scatter overhead for singleton expert routes without replacing the tuned
Q8 matmul schedule?

This is a narrow follow-up to the route-profile finding that verifier gate/up
is still the dominant fresh-response cost. It intentionally does **not** revive
the broad `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST` or grouped Q8 paths, which
were already slower.

## Patch

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260627T0525-llamacpp-gemma4-gateup-singleton-direct-current-stack.patch`

The patch is against the current experimental llama.cpp stack. It adds a
default-off flag:

```bash
LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT=1
```

The path triggers only for the current Gemma verifier gate/up Q8 shape and keeps
the existing `ggml_sycl_mul_mat()` arithmetic. For routed experts with one row,
it points the one-row source/destination views at the original/final buffers and
skips full gather/scatter. Duplicate expert routes fall back to the existing
contiguous gather/matmul/scatter path.

## Screen Result

Candidate:

- run dir: `data/gemma4-q8-gpu2-gateup-singleton-direct-screen-20260627T052517Z`
- canary: `64/64` pass
- cached tokens: `[0]`
- fresh row0 after TTFT: `104.12278210887227 tok/s`
- wall row0: `90.65344097799117 tok/s`
- output hash: `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31`

Same-GPU control with the new flag off:

- run dir: `data/gemma4-q8-gpu2-gateup-singleton-direct-control-20260627T052623Z`
- canary: `64/64` pass
- cached tokens: `[0]`
- fresh row0 after TTFT: `102.16498485841758 tok/s`
- wall row0: `89.17361263230586 tok/s`
- output hash: `d3236ebed08dda8f19a0fec78622967b3622704da06819c98a7e0e63f90d982b`

Current valid record for comparison:

- run dir: `data/gemma4-q8-gpu0-ub768-nmin3-pmin010-fullrepeat-20260627T035307Z`
- canary: `6144/6144` pass
- fresh row0 after TTFT: `104.22626983476746 tok/s`
- output hash: `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31`

## Interpretation

The candidate is canary-clean and output-hash stable against the current record,
but it does **not** beat the record on the screen: `104.12 < 104.23`. The
same-GPU control was slower and produced a different benchmark text hash, so the
flag is not an obvious loss, but there is no valid headline improvement to
promote or submit.

Do not run full validation for this exact screen result unless a follow-up
profile shows that gate/up node time actually fell enough to justify another
attempt. The next useful check, if this path remains interesting, is a node
profile with and without the flag to verify whether `ffn_moe_gate_up-*` time
moved or whether any savings were lost elsewhere.

## Decision

Status: **inconclusive / no record**.

Keep the patch as a default-off experiment artifact. Do not enable it in the
promoted recipe and do not submit to LocalMaxxing.
