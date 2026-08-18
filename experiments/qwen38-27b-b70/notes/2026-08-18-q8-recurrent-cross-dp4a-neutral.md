# Qwen3.8 Q8 recurrent-only crossed-DP4A experiment

Date: 2026-08-18

Status: closed performance-neutral; exact schedule experiment, not promoted

## Scope

The global crossed two-chain DP4A schedule had improved a deep direct gate by
`0.758%`, while crossing only the dense FFN projections was slightly negative
at `-0.1046%`. This arm therefore isolated the exact crossed schedule to the
promoted recurrent GDN quad (`K=5120`, `N=5120+3072+24+24`). Dense FFN,
attention, output head, collectives, model weights, equal TP2 split, F16 KV,
FlashAttention, and the accepted SG24 geometry were unchanged.

The runtime door was `GGML_SYCL_MMVQ_Q8_RECURRENT_CROSS_DP4A=1`. Every packed
weight word remained paired with its original activation word. Only the two
independent integer chains changed from `0->2 / 1->3` to `0->3 / 1->2`; their
exact integer sum still precedes the unchanged FP32 scale and subgroup
reduction.

No speculation, MTP, DFlash, cache reuse, peer write, profiler, PCI policy,
power-management setting, firmware, driver, or kernel setting was involved.

## Correctness and mechanism gates

The treatment binary was built from llama.cpp commit
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` with oneAPI DPC++ 2026.1.1 AOT for
`bmg_g31`, inside the repository's 6/8 GiB build cap. Its SYCL library SHA-256
was `7d261061a27779c7562f0c4d998c4cfc32b4e66f108588b94cd8853a72959d00`;
the changed `mmvq.cpp.o` was
`1ead7906846fb40d6e32de8a391158261ec35d3e17114c938634e28aa0202963`.

The strict Q8 verifier reported `VERIFY_MISMATCH=0`, but its dedup level 2
intentionally disables the meta-backend fused GDN quad, so it could not also
exercise this shape-scoped treatment. This is a verifier/mechanism
incompatibility, not live-treatment proof. Under the production dedup level 1,
a TP2 `p0/n2` mechanism smoke announced the exact recurrent treatment on both
devices and counted `fused_mmvq_gdn_quads=288`. Exactness rests on the same
verified Q8 dot product plus integer-only reassociation; no semantic promotion
is claimed because the arm failed the performance gate.

## Balanced direct result

The direct gate used the same binary for both arms: TP2 `p64/n512/r3`, equal
split, F16 KV, FlashAttention, `b1024/ub256`. Two complementary brackets fully
balanced arm and position:

| Order | Position | Arm | Decode tok/s |
| --- | ---: | --- | ---: |
| A-B-B-A | 1 | control | `36.718275` |
| A-B-B-A | 2 | treatment | `37.624352` |
| A-B-B-A | 3 | treatment | `36.687222` |
| A-B-B-A | 4 | control | `37.431015` |
| B-A-A-B | 1 | treatment | `36.746935` |
| B-A-A-B | 2 | control | `36.790306` |
| B-A-A-B | 3 | control | `36.813732` |
| B-A-A-B | 4 | treatment | `36.841604` |

The four control runs averaged `36.938332 tok/s`; the four treatment runs
averaged `36.97502825 tok/s`, a resolution-class `+0.099345%`. More
importantly, the individual brackets disagreed: A-B-B-A was `+0.21885%`, while
B-A-A-B was `-0.02106%`. The apparent pooled improvement is position/run noise,
not a repeatable optimization. The fixed endpoint suite was therefore skipped.

The exact cumulative source increment against the accepted DP4A2/SG24 source
is [`q8-recurrent-cross-dp4a-neutral-20260818.diff`](../patches/q8-recurrent-cross-dp4a-neutral-20260818.diff).
Structured evidence is
[`2026-08-18-q8-recurrent-cross-dp4a-neutral.json`](../data/2026-08-18-q8-recurrent-cross-dp4a-neutral.json).
Raw logs remain under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260818-recurrent-cross-dp4a/`.

Both B70s passed the post-run health gate. There was no new Xe/GuC fault,
reset, hang, timeout, device-lost event, host-memory pressure, or policy change.
