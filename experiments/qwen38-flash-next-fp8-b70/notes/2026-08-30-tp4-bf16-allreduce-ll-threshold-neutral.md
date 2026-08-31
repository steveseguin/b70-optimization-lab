# Qwen3.8 Flash-Next FP8 TP4 BF16 allreduce threshold result

Date: 2026-08-30
Status: lossless component neutral; no endpoint arm

The frozen six-process A/B completed without a model load or reboot. All ranks
matched the exact BF16 oracle, every repeat and arm retained one output hash,
and all Kineto receipts proved the intended protocol change:

- 4,096-byte control: `Rt64_128_PCIE`;
- 8,192-byte candidate: `Rt64_PCIE`.

Across 1,500 slowest-rank samples per arm, control versus candidate was:

- median: 91.522 versus 90.490 us, candidate 1.13% lower;
- p95: 110.818 versus 105.278 us, candidate 5.00% lower;
- p99: 132.929 versus 124.634 us, candidate 6.24% lower;
- maximum: 342.864 versus 235.332 us, candidate 31.36% lower.

All three candidate trial medians were lower than their same-index controls,
but the combined median improvement is below the preregistered 5% component
gate. The result is therefore a genuine lossless tail improvement but a
component neutral for endpoint selection. Do not spend another full model load
on this threshold alone and do not add it to the protected launcher. The next
relevant component target is the actual production M1 real-weight MoE kernel,
followed by source-backed work on the rank-2/rank-3 submission skew.

Structured result:
[`20260830-tp4-bf16-allreduce-ll-threshold-neutral.json`](../data/20260830-tp4-bf16-allreduce-ll-threshold-neutral.json).
