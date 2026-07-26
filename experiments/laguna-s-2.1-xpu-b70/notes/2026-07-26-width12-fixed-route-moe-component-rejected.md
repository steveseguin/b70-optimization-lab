# Laguna width-12 fixed-route MoE component rejection

Date: 2026-07-26 America/Toronto

Status: terminal component negative. No cards 1-3, model service, prompt,
generation, endpoint benchmark, payload, or submission were run.

## Result

The optimized Laguna fixed-route MoE transaction is row-generic and bitwise
exact at width 12, but it is drastically slower than the width-12 generic
expert-grouped path. The card-0 smoke passed every exactness check and lost
every paired timing block:

| Metric | Generic width-12 path | Fixed-route width-12 candidate |
| --- | ---: | ---: |
| Median time per 47 MoE layers | 10.827870 ms | 26.256207 ms |
| Paired median saving | — | **-15.458431 ms** |
| Paired mean saving | — | -15.080555 ms |
| Paired wins | — | 0/3 |

The preregistered component floor required the candidate to save at least
`0.60 ms` per 47-layer cycle on every card. The candidate missed in the wrong
direction by more than 15 ms, so the lane stopped on card 0 without a formal
four-card run.

This explains why the old fixed-route transaction was useful at width 8 but
not width 12. It launches one independent M=1 lane for every route. At width
12 that is 120 lanes, while the generic path groups the local routes by expert
and finishes the same 47-layer component in less than half the time.

## Exactness evidence

Two changing card-0 epochs proved all of the following bitwise:

- the 12-row candidate output equals twelve independent one-row fixed-route
  calls concatenated in row order;
- local W1, BF16 SiLU, local W2, and final output boundaries all match that
  oracle;
- the candidate final output also equals the current generic width-12 output;
- remote scratch remains untouched or zero according to the production
  contract; and
- hidden states, weights, scales, routes, router weights, and expert map remain
  unchanged.

The source extension is therefore a valid exact experiment, not a useful
throughput optimization.

## Identity and evidence

- preregistration main commit: `c2b73a023`;
- XPU-kernel source commit:
  `0cca9cb012b07a2524b79b7bd1e612d419bdb815`;
- vLLM commit:
  `4a03b432437258575754ca6798769fe3df056771`;
- candidate `libgrouped_gemm_xe_2.so` SHA-256:
  `619ca9cce77ff1595d686828a9a00d082d940f60fbbcac3676f9ee173bda97ab`;
- incumbent `_xpu_C.abi3.so` SHA-256:
  `f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8`.

Result:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/mwide-fixed-route-smoke-0cca9cb-c2b73a023-20260726/card0/result.json
```

Build artifacts, build log, installed-control backup, and candidate binary:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/builds/mwide-fixed-route-0cca9cb-20260726/
```

## Disposition

Preserve the exact source and component harness as a negative result. Do not
run cards 1-3 or an endpoint with this identical treatment. Width 12 should
continue to use the generic expert-grouped MoE path.
