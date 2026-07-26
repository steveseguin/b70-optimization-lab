# Laguna width-12 fixed-route MoE candidate

Date: 2026-07-26 America/Toronto

Status: **preregistered before implementation or device execution**.

## Source finding

The exact width-12 record does not use the optimized Laguna routed-expert
transaction. In `vllm_xpu_kernels.fused_moe_interface`, the native
fixed-route branch is limited to `1 <= num_rows <= 8`; width 12 therefore
falls through to generic atomic remap, expert-grouped W1/W2, and unpermutation
even though these selectors are set:

```text
VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1
VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
```

The earlier note that `VLLM_XPU_LAGUNA_M8_W1_N_TILE` was dead searched only
the vLLM source tree. The editable XPU-kernel Python package reads that
variable. The tile was not the width-12 issue: the complete optimized branch
was unreachable.

The native kernels already assign each `[row, top-k slot]` route an independent
M=1 arithmetic lane and size their workgroup grids from runtime `num_rows`.
Their C++ guards, Python scratch allocation, and dispatch condition are the
remaining width-eight pins. This candidate extends only the N64 fixed-route
path to exactly twelve rows.

## Hypothesis

Width 12 currently scores `100.524890 tok/s`, is bitwise exact 13/13, and has a
derived cycle of `39.35 ms`. Reaching 102 requires about `0.57 ms` per cycle.
The fixed-route W1+BF16-SiLU and route-parallel W2 path was a durable earlier
Laguna gain because it removes atomic remap/unpermutation and keeps every route
in an independent numerical lane. Restoring it across 47 MoE layers at width
12 has enough plausible device-time ceiling to close the gap.

## Treatment

Add a new default-off selector:

```text
VLLM_XPU_LAGUNA_MWIDE_FUSED_W1_ROUTE_W2=1
```

It must fail closed unless all of the following hold:

- `VLLM_XPU_LAGUNA_EXACT_MAX_M=12`;
- batched exact MoE, fused W1/route-W2, and route interleave are enabled;
- the model is the existing Laguna INT4/BF16 E256/K10 TP4+EP4 contract;
- W1 uses literal N64;
- shared-elementwise, QKNorm/RoPE, local argmax, draft graph, nested attention
  graph, and inline attention selectors are off; and
- the actual call has either the existing 1–8-row contract or exactly 12 rows.

The treatment changes no model, quantization, draft depth, prompt, scoring
window, cache policy, request order, retry policy, collective order, or
attention path. Width 8 remains byte-for-byte unchanged when the new selector
is unset.

## Gates

1. CPU/static tests must reject every selector/shape mismatch and prove the
   default path is unchanged.
2. A changing-input XPU component gate must compare the twelve-row treatment
   against twelve independently executed one-row fixed-route calls, bitwise,
   on every physical card. It must cover duplicate, local, and remote routes,
   input immutability, repeated determinism, W1 materialization, activation,
   W2 route output, and final local gather.
3. The component timing must show at least `0.60 ms` saving over 47 complete
   current generic width-12 local-MoE calls on every card before an endpoint
   leg is authorized. This threshold is slightly above the endpoint's derived
   `~0.57 ms` goal gap and prevents a low-ceiling campaign.
4. The endpoint leg must use the existing honest cold suite exactly once,
   report cache zero on all rows, match the frozen q=1 teacher 13/13 bitwise,
   and capture/replay exactly `146/145` on all four ranks.
5. Service shutdown, worker cleanup, port release, and post-run device idle
   must pass.
6. Promote only an honest scored median of at least `102 tok/s`. A component
   result, projection, invalid token stream, altered acceptance check, or
   different timing window is not a result.
