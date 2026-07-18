# DSpark Post-W1 Profile and Copy-Elision Closure

Date: **2026-07-18**

Status: **profile complete; copy-elision bundle exact but performance-rejected**

## Record-identity profile

A one-request profile of the promoted W1-only replication identity retained 48
decode cycles after the initial call on every rank. Profiler instrumentation
inflates host scopes, so the values are for attribution, not endpoint speed.
The slowest recurring host medians were:

| Scope | Approximate host median |
| --- | ---: |
| target forward / verification | 20.68-21.23 ms/cycle |
| complete DSpark proposal | 15.70-16.44 ms/cycle |
| DSpark generate-draft | 10.28-10.46 ms/cycle |
| Markov sample | 5.98-6.04 ms/cycle |
| DSpark backbone | 4.29-4.38 ms/cycle |
| target sample/rejection | 1.66-2.39 ms/cycle |

The target PIECEWISE replay is opaque to the host-to-kernel attribution method,
so its device kernels are not individually assigned in this trace. The result
does establish that target verification is now the largest complete boundary;
the next architectural target work needs an eager diagnostic twin or native
replay instrumentation.

Evidence:
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-replicated-w1-stage-profile-20260718T1830Z`.

## Copy-elision bundle

The persistent Markov path still wrote argmax into a one-token temporary and
then copied it into each of seven draft-token columns. A real-weight four-B70
gate wrote argmax directly to the final column and saved only **0.076263
ms/cycle** at the slowest rank. The adjacent greedy request-input copies were
also proven unused when `draft_logits is None`: temperature, seeds, and the
private index mapping are consumed only by probabilistic drafting.

vLLM commit `f7734caed96f2bb9672b3c9840972cce523e7f5f` preserves both
default-off experiments behind:

- `VLLM_XPU_DSPARK_DIRECT_DRAFT_OUTPUT=1`; and
- `VLLM_XPU_DSPARK_GREEDY_COPY_ELISION=1`.

The endpoint passed exact canaries before and after the strict suite, with all
12 realistic requests cache-zero, but reached only **64.764976 tok/s** median
versus the 67.501117 record. The p10 was 60.034575 tok/s. This bundle is
performance-rejected and must stay disabled.

Evidence:

- component:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-direct-draft-output-gate-20260718T1850Z`;
- endpoint:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-copy-elision-candidate-20260718T1900Z`.

## Decision

Keep the promoted `019e6f0e2` W1-only record identity. Do not accumulate the
copy-elision flags: the measured saving is too small and the endpoint lost.
Move to target-verifier attribution and changes large enough to affect the
approximately 21 ms target boundary.
