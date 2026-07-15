# DeepSeek V4 K160 native M1 biased-top-k record

Date: 2026-07-15

## Result

The nonspeculative TP4+EP record is now **41.733256 tok/s** median for
generated tokens 1-100 after TTFT, with an independent strict suite at
41.513661 tok/s. The two p10 values are 41.259748 and 41.188482 tok/s.
LocalMaxxing approved the result as `cmrmjd3io1nn1mj013stqoe4b`.

The same vLLM and XPU-kernel commits with only
`VLLM_XPU_V4_M1_BIASED_TOPK=0` measured 40.067691 tok/s. The native router
therefore improves the paired control by 3.61-4.16% and removes approximately
0.87-1.00 ms from every decoded token. Both candidate suites and the control
suite pass the fixed cold-response gate with `cached_tokens=0` on every row.

Evidence:

- candidate: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-m1-router-candidate-20260715T2021Z`;
- same-commit control: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-m1-router-control-20260715T2027Z`;
- vLLM: `a66f3486cc6ebc530c74ee29934986eb75ed6b63`;
- XPU kernels: `2a07cf2e8af3da69a767f4e9131123e50d2ac5c8`.

## What changed

Forty normal MoE layers used a generic PyTorch chain for M=1 routing:

1. add the 160-element expert correction bias;
2. run generic `torch.topk`, which selected a radix/sort implementation;
3. gather the six unbiased routing weights.

The new default-off Xe2 kernel assigns ten experts to each SIMD16 lane and
performs six subgroup max/min reductions. It returns sorted expert IDs and the
corresponding raw unbiased FP32 weights. The existing sqrt-softplus,
normalization, and routed scaling remain unchanged. The first three hash-MoE
layers retain their lookup path.

The decisive hardware gate improved the isolated boundary from 77.128 to
7.178 us, a 10.75x speedup. All four B70s passed 40/40 changed inputs with
bitwise-identical IDs and raw weights; candidate medians ranged from 7.223 to
7.280 us. The full graph delivered less than the eager microgate projection,
but still cleared the required 0.50 ms/token end-to-end gate.

## Correctness and repeatability

Twenty ordered exact captures pass 20/20, ten before and ten after the two
strict suites. Every arithmetic, changed-input replay, exact-copy, fact, and
strict-JSON output is exact, and all requests report zero cached tokens.
Reusable PIECEWISE and FULL decode graphs capture successfully.

Long 128-token output hashes are not a bitwise promotion invariant for this
K160 lane: the two prior flag-off record suites also differ from one another
on several open-ended prompts. The candidate shows the same pattern while the
deterministic exact suite remains stable. This does not remove the existing
warning that uniform K160 is a hash-pruned performance artifact rather than a
quality-selected final checkpoint.

An initial candidate restart omitted `--enable-prompt-tokens-details`.
Although its six outputs were exact, cached-token values were unavailable, so
that run is preserved at `nospec-m1-router-candidate-20260715T2017Z` and is
excluded from all speed and qualification claims.

## Decision

Promote the native M1 router in the record recipe while retaining the
default-off guard in source. This is the first measured proof that deleting a
generic framework boundary inside the reusable decoder graph still produces
a material full-model gain on B70: approximately one millisecond per token.
Continue with similarly bounded M=1 fusion candidates; reject microbenchmarks
whose projected saving is below 0.50 ms/token.
