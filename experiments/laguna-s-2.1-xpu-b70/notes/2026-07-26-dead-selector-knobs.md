# Laguna — seven pinned selector variables are not read by anything

Date: 2026-07-26 America/Toronto

## The finding

The measurement leg sets thirteen `VLLM_XPU_LAGUNA_M8_*` selector variables and
records them in `identity.txt` as the run's selector stack. Seven of them are
read by nothing in the vLLM tree:

| variable | in `envs.py` | read elsewhere |
| --- | ---: | ---: |
| `W1_N_TILE` | no | **no** |
| `GATHER_SHARDED` | no | **no** |
| `GATHER_FINALIZE` | no | **no** |
| `SHARED_EXPERT_STREAM` | no | **no** |
| `SHARED_DOWN_MM` | no | **no** |
| `SHARED_GATE_MM` | no | **no** |
| `SHARED_GATE_UP_MM` | no | **no** |

The six that are live: `FUSED_TRANSACTION`, `REMOTE_ZERO`, `BF16_ATTN_MM`,
`BF16_ROUTER_TOPK`, `FUSED_W1_ROUTE_W2`, and `ROUTE_INTERLEAVE`.

## Why it matters

Two ways.

First, `identity.txt` records a `selector_stack` string that implies these
settings describe the run. For seven of them it does not, so the recorded
identity overstates what was controlled. Anyone comparing two runs on the
strength of that string is comparing something narrower than they think.

Second, it invalidates a route. `W1_N_TILE=64` looked like the most promising
unexplored lever -- a tile size chosen for eight rows now feeding twelve, on the
target forward that dominates the cycle. It is inert. The kernel does accept a
`w1_n_tile` argument, so a tile is being chosen somewhere, but not by this
variable.

## Not investigated further

The kernel binding declares `cutlass_grouped_gemm_m1_topk_interface` with
`w1_only, route_interleave, w1_n_tile`, while the vLLM fake registration for the
same name stops at `zero_remote_routes`. The two trees appear to disagree about
that op's signature. That may be harmless -- a stale fake affects tracing, not
execution -- or it may mean the tuned path is not the path being taken. It was
not chased down, and is recorded here rather than guessed at.

## Standing

Best measured result **100.524890** tok/s at width 12, 13/13 bitwise exact.
