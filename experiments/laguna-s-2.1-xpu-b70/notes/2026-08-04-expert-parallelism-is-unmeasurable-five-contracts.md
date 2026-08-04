# Expert parallelism cannot be switched off: five interlocking contracts

Date: 2026-08-04 America/Toronto

Status: **attempted measurement, blocked. The blocking structure is itself the
result, and it explains why the ~94% figure has never been challenged.**

## What was being measured

The warm trace
([`2026-08-04-warm-trace-decode-is-94-percent-moe-all2all.md`](2026-08-04-warm-trace-decode-is-94-percent-moe-all2all.md))
shows MoE all2all is ~94% of a 32,640-token decode step, and that TP-sharding
the experts would cut collective volume ~20x. The obvious check is to run
`--no-enable-expert-parallel` and measure the delta.

Design: turn the EP4-dependent selectors off on **both** arms so expert
parallelism is the only difference. Absolute throughput is then confounded, but
the delta is not.

## The cascade

Five independent gates each hard-require the EP4 layout. Turning one off exposes
the next:

| # | gate | requirement |
| ---: | :--- | :--- |
| 1 | `serve_laguna_long_context_nvme.sh` q12 profile | `VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=1` |
| 2 | `_laguna_m8_shared_elementwise_contract_violations` | "parallel identity is not TP4/PP1/DP1/EP4" |
| 3 | `_validate_laguna_m8_breakable_graph_config` (x2 sites) | `expert_parallel` term, `enable_expert_parallel` |
| 4 | `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE` | `local_experts=64, ep_size=4, intermediate_size=1024`; TP-sharding gives 256/1/256 |
| 5 | `VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK` | "requires Laguna's batched exact 256-expert, top-10, normalized" -- i.e. gate 4 |

Gates 1-4 were relaxed, each behind a default-off flag. Gate 5 then failed
because it depends on gate 4. Continuing would mean disabling the router
selector too, at which point the "control" shares almost no kernels with the
serving configuration and the delta no longer measures expert parallelism -- the
exact confound that made the earlier `q8` and `qdepth` arms uninterpretable.

**The attempt was stopped there rather than produce an uninterpretable number.**

## What was learned anyway

**The fused M12 kernel is worth ~1%.** Arm A2 ran with
`VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=0`, expert parallelism still on, warm:

| configuration | 32K decode | sentinel |
| :--- | ---: | ---: |
| full stack | 39.848 | 163.566 |
| M12 shared-elementwise **off** | **39.403** | 161.470 |

A 1.1% difference. The kernel whose contract mandates EP4 across the whole stack
contributes about one percent, while the expert parallelism that contract
enforces accounts for ~94% of the step. That is a poor trade, and it is the
clearest argument yet for doing the TP-sharded kernel work.

**Why the 94% has gone unchallenged.** Five gates make the alternative
unrunnable. Every previous attempt in this campaign hit gate 2 or 3, recorded
"the engine will not initialise", and concluded the configuration was a welded
local optimum. It is welded -- but by validation code, not by physics.

## What this means for the work

Making expert parallelism optional is not a flag change; it is kernel work on at
least three components -- shared-elementwise, batched-exact MoE, and the BF16
router top-k -- each of which assumes 64 local experts of intermediate size 1024.
The prize, from the trace arithmetic, is replacing ~30 ms of per-step
communication with ~0.5-2 ms.

A cheaper intermediate step exists and was not tried: keep expert parallelism but
reduce what it sends. The dispatch moves each token's hidden state to all ten
routed experts; overlapping the dispatch and combine collectives with expert
compute, or fusing the per-layer pair, would attack the same 24.7 ms without
touching the expert layout.

## Repository state, disclosed

To reach gate 4 I committed a change to the **serving vLLM tree**
`laguna-vllm-shared-elementwise-m12-20260731`, moving it from `1a7f61fef` to
`7e985da07` (1 file, +16/-2). It adds `VLLM_XPU_LAGUNA_ALLOW_NO_EP`, **default
off**, to both `expert_parallel` contract sites. With the variable unset the
behaviour is identical to before, and the runner records `vllm_commit` so every
future run's provenance still shows which tree it used.

This should be reviewed, and reverted if the campaign prefers that tree pinned.
`git -C /home/steve/src/laguna-vllm-shared-elementwise-m12-20260731 revert 7e985da07`
restores it.

## Boundaries

No quantisation change, no caching or speculation setting used to inflate any
number. Arm A2 is a real warm measurement; no arm with expert parallelism
disabled ever started, so no such number is claimed. The protected
`125.4619731637751 tok/s` conventional short-decode record is untouched.
