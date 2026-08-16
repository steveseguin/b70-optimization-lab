# Qwen3.8 Q8 reordered-MMVQ VDR2 at c2: rejected

Status: **slower and not exact; do not promote**.

## Hypothesis

The accepted VDR4 kernel is optimized for one stream. At concurrency two,
halving the vector dot ratio to VDR2 could expose more independent subgroup
work. This is materially different from the historical single-request VDR
sweeps, so it warranted one bounded cross-batch test.

The candidate was rebuilt from the exact accepted Qwen3.8 source packet. Its
only increment made Q8's compile-time VDR selectable, chose VDR2, and retained
wide aligned vector loads as `sycl::vec<int, vdr>`.

## Result

Using the published two-slot harness and the same two 256-token prompts:

- accepted VDR4: `57.398122 tok/s` aggregate conventional;
- candidate VDR2: `55.687035 tok/s` aggregate conventional;
- delta: **`-2.9811%`**;
- candidate per-request rates: `27.844202` and `27.844796 tok/s`;
- candidate aggregate wall rate: `54.788764 tok/s`.

All cache counters were zero. Both GPUs remained normal and the kernel journal
contained no fault, reset, or hang.

## Quality failure

Prompt 0's candidate sequential token hash was
`5858b15368f93f00f87da3f57f0d18b73c33c4e0776de94fb3b97da25ac2fc47`,
while its simultaneous-request hash was
`528009fcc00e49cec4c23c5390349c56f7b010cbcff5ecbdf286588ac264dfff`.
Prompt 1 remained exact. Because VDR2 changes the FP32 reduction grouping, the
first prompt crossed a greedy-token boundary. This fails the repository's
no-quality-loss gate independently of the performance regression.

The compact evidence is
[`2026-08-16-q8-vdr2-c2-negative.json`](../data/2026-08-16-q8-vdr2-c2-negative.json).
The exact two-file source increment is
[`q8-vdr2-c2-negative-20260816.diff.gz.b64`](../patches/q8-vdr2-c2-negative-20260816.diff.gz.b64)
and applies only after the accepted Qwen3.8 Q8 patch packet. Decode it with
`base64 -d | gzip -dc`; the decoded SHA-256 is
`8b855dbf22feb998b5a2864c07e618b192c3ed9a05291d9ef52f547f93183020`.

## Decision

Retain VDR4. Do not retry VDR2 for Qwen3.8 Q8 TP2 c1 or c2 unless the compiler,
kernel reduction, or model revision changes materially.
