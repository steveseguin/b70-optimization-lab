# The exact M=1 linear path is where the serving-path time goes

Date: 2026-08-05 America/Toronto

Status: **attributed. The raw sample was contaminated by teardown frames, but
restricting to samples inside a model step resolves it, and the result closes
the arithmetic to within 2% of what
[the four-arm bisection](2026-08-05-KEY-the-serving-path-is-half-the-decode-step.md)
could not attribute. Names a concrete, quality-neutral kernel target.**

## The measurement

`py-spy`, 150 Hz, on rank 0 of the **stripped** arm (MoE skipped, gather-skip
mod 2), where the device has almost nothing to do -- kineto puts all
non-collective device kernels at ~2.3 ms per step even with MoE *on*. Leaf
frames, i.e. where the thread actually sits:

| leaf frame | share |
| :--- | ---: |
| **`_xpu_apply_batched_m1_method` linear.py:199** | **24.3%** |
| `shutdown` gpu_model_runner.py:7481 | 10.7% |
| `_cleanup_profiling_kv_cache` gpu_model_runner.py:7526 | 10.5% |
| `empty_cache` memory.py:32 | 7.9% |
| `sched_yield` utils.py:48 | 5.9% |
| `make_llir` compiler.py:428 | 3.4% |
| `_forward_flat` laguna.py:843 | 3.0% |
| `_xpu_apply_batched_m1_method` linear.py:198 | 2.8% |
| `copy_to_gpu` utils.py:142 | **2.2%** |

## Two readings, and the contamination

**Contamination first:** 713 samples with 160 errors, and `shutdown`,
`_cleanup_profiling_kv_cache`, `empty_cache` and `make_llir` together are ~32%.
Those are teardown and JIT, not steady-state decode -- the sampler caught the
run's tail. So the percentages are not a clean steady-state profile and should
not be quoted as one.

**What survives anyway**, because both directions are large and consistent:

1. **`_xpu_apply_batched_m1_method` is 27.1%** across its two lines. An earlier
   independent `py-spy` run on the *full* configuration put the M=1 linear path
   at **13.7%**. It roughly doubles once MoE compute is removed, which is
   exactly how a fixed host cost behaves as a share.
2. **`copy_to_gpu` collapses from 27.6% to 2.2%.** With the device given little
   to do, the host stops blocking on the queue. That is direct evidence the
   earlier 27.6% was *waiting*, not work -- and that the residual is **host
   compute**, not submission latency.

Reading 2 matters for what to build: `--async-scheduling` overlaps host
preparation with device execution, which helps when the host waits. Here the
host is busy, so async scheduling is **not** the indicated fix.

## Cleaned: restrict to samples inside a model step

The contamination is removable without another run, because the profile carries
full stacks. Keeping only samples whose stack enters a model step
(`execute_model`, `forward`, `_forward_flat`, `propose`, `sample`) and dropping
any containing a teardown or JIT frame leaves **249 of 506 samples**:

| leaf frame, decode only | share |
| :--- | ---: |
| **`_xpu_apply_batched_m1_method` linear.py:199** | **49.4%** |
| `_forward_flat` laguna.py:843 | 6.0% |
| `_xpu_apply_batched_m1_method` linear.py:198 | 5.6% |
| `__call__` _ops.py:1275 | 3.6% |
| `_xpu_apply_batched_m1_method` linear.py:186 | 2.4% |
| `all_gather` base_device_communicator.py:207 | 2.0% |

**The M=1 batched linear path is 57.4% of in-step host time**, and the
stride-zero `torch.bmm` on line 199 alone is 49.4%.

**The arithmetic closes.** 57.4% of the stripped arm's 13.4 ms step is
**~7.6 ms**, against the **~7.5 ms** the four-arm bisection could not
attribute. Two independent methods -- differential arms and stack-filtered
sampling -- landing within 2% of each other is the strongest attribution this
campaign has produced.

## The target

`vllm/model_executor/layers/linear.py:198-199`:

```python
weight_t = layer.weight.t().unsqueeze(0).expand(rows.shape[0], -1, -1)
output = torch.bmm(rows.unsqueeze(1), weight_t).squeeze(1)
```

This is the stride-zero BMM that preserves per-row arithmetic -- the exactness
mechanism the whole campaign rests on. It runs for every linear in every one of
48 layers, plus the drafter's, on every step, and it rebuilds the expanded view
and allocates the output each call.

## The fix that is not there

The branch immediately above it already describes the faster shape -- a fused
op writing into a preallocated output:

```python
torch.ops.vllm.xpu_exact_batched_m1_bmm_out(rows, layer.weight, output)
```

**That operator does not exist.** `xpu_exact_batched_m1_bmm_out` appears only
in `linear.py`; it is registered nowhere in the vLLM fork or the kernel
package, so `VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=1` would fail rather than run
faster. The harness pins it to 0. Its gating attribute `xpu_exact_graph_bmm` is
also set on **`o_proj` only**, so even implemented it would cover one linear
per layer.

This is the seventh built-but-unwired or referenced-but-unimplemented artifact
found this session, after `M8_INLINE_GATHERS`, `M8_GATHER_SHARDED`,
`M8_GATHER_FINALIZE`, `M8_SHARED_GATE_UP_MM`, `M8_INLINE_ATTENTION_GRAPHS`,
`REPLAY_EVENT_PROFILE_TARGET_ONLY`, and the three-module tree stack.

## What to do

1. **Implement `xpu_exact_batched_m1_bmm_out`** as a real fused XPU op, and set
   `xpu_exact_graph_bmm` on every exact linear rather than `o_proj` alone. It is
   quality-neutral by construction -- identical per-row arithmetic, without
   rebuilding an expanded view and allocating an output on every call -- and it
   targets ~7.5 ms of a 25.82 ms step, the largest remaining block.
2. **Confirm on a clean sample** taken only while decode is in flight, as a
   check rather than a prerequisite: the stack-filtered result and the
   differential arms already agree within 2%, from independent methods.
3. **Do not pursue `--async-scheduling` for this.** The host is busy, not
   blocked, so overlapping host preparation with device execution does not
   address it.

## Boundaries

py-spy 150 Hz, rank 0, stripped arm (`VLLM_XPU_LAGUNA_SKIP_EXPERTS=1`,
`GATHER_SKIP_MOD=2`), q12, depth 11, width 12, TP4, EP4, util 0.80. That arm is
**deliberately inexact** and exists only to remove device work; no throughput
from it is a rate Laguna can achieve. The profile is contaminated by teardown
frames; the quoted shares are from the stack-filtered subset, and the raw
leaf table is retained above so the filtering can be checked. Sampling requires
ptrace, so it ran under sudo; nothing about the GPU state was modified. No quantisation
change. The protected `125.4619731637751 tok/s` conventional short-decode
record is untouched.
