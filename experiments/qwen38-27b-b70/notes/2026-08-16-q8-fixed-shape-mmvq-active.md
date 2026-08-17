# Qwen3.8 27B Q8 TP2 compile-time FFN MMVQ shapes

Date: 2026-08-16

Status: closed; output-exact and mechanism-proven, but performance-neutral
(`-0.0088%`) in the position-balanced TP2 screen.

## Hypothesis

The accepted reordered-Q8 SG16 kernels receive `ncols`, `nrows`, block counts,
scale-plane offsets, loop limits, and fused-pair matrix dimensions as runtime
arguments. Qwen3.8 repeatedly uses two dominant local TP2 FFN shapes:

- down projection: K=`8704`, N=`5120`, standalone reordered Q8 MMVQ;
- gate/up projections: K=`5120`, N=`8704` plus N=`8704`, fused pair.

These three matrices carry most of the dense model's weight bytes. Dedicated
template instantiations can make their loop bounds, block/scale strides, and
pair boundary compile-time constants while retaining the accepted weight
layout, one-chain integer DP4A order, per-lane FP32 block accumulation, SG16
reduction, launch geometry, and output stores.

This is materially different from the closed fixed-WG128 experiment: that arm
only annotated a workgroup size and left matrix geometry dynamic. It is also
different from row interleaving, two-row activation reuse, DPAS/ESIMD, and
subgroup-count sweeps.

## Contract

- isolated source/build derived from the accepted Qwen3.8 Q8 source stack;
- same binary mode 0 control and an explicit default-off runtime selector;
- specialize only exact admitted shapes; every other shape falls through to
  the accepted kernel unchanged;
- liveness log per device and family plus treatment-scoped poison control;
- normal fixed-shape output must match the accepted oracle; poison must differ;
- first use a bounded `p64/n256/r3` position-balanced screen;
- advance only a repeatable positive result to the complete 12-prompt
  cache-zero oracle, semantic canaries, long-context needle, and health gate;
- build at no more than two jobs under the established 8 GiB host-memory cap.

## Implementation and reachability

The candidate added compile-time instantiations for the exact standalone down
shape and fused gate/up pair. A default-off runtime door,
`GGML_SYCL_MMVQ_Q8_FIXED_SHAPES=1`, selected them without changing the accepted
binary's other paths. The standalone body retained the accepted reordered
layout, four-DP4A chain, per-lane FP32 block accumulation, and SG16 group
reduction. The pair body made its matrix boundary, block count, and scale-plane
offsets compile-time constants.

A fresh BMG-G31 AOT build completed under an 8 GiB host-memory cap. A TP2
liveness smoke logged both `pair K=5120 N=8704+8704` and
`down K=8704 N=5120` on devices 0 and 1. The existing fusion census ended with
`VERIFY_MISMATCH=0`.

## Quality and poison proof

The fixed 75-token incident-retrospective prompt generated 128 tokens that
were byte-identical to the accepted control. The response content base64 was:

```text
Cgo8dGhpbms+ClRoZSB1c2VyIHdhbnRzIG1lIHRvIHdyaXRlIGFuIGluY2lkZW50IHJldHJvc3BlY3RpdmUgZm9yIGEgcHJvZHVjdGlvbiBBUEkgb3V0YWdlIGNhdXNlZCBieSBhIGJhZCBjYWNoZSBpbnZhbGlkYXRpb24gcnVsZS4gTGV0IG1lIHN0cnVjdHVyZSB0aGlzIGNhcmVmdWxseSB3aXRoIGFsbCB0aGUgcmVxdWVzdGVkIHNlY3Rpb25zOiBpbXBhY3QsIHRpbWVsaW5lLCBjb250cmlidXRpbmcgZmFjdG9ycywgZGV0ZWN0aW9uIGdhcHMsIHJlbWVkaWF0aW9uLCBwcmV2ZW50aW9uIHdvcmssIGFuZCBvd25lciBoYW5kb2ZmLiBJdCBzaG91bGQgYmUgNDUwLTU1MCB3b3JkcywgcHJhY3RpY2FsIGxhbmd1YWdlIGZvciBlbmdpbmVlcnMgYW5kIG1hbmFnZXJzLCBjb25jaXNlIGJ1dCBjb21wbGV0ZS4KCkxldCBtZSB0aGluayBhYm91dCB3aGF0IG1ha2VzIGEgZ29vZCBpbmNpZGVudCByZXRyb3NwZWN0aXZlOgotIEJsYW1lbGVzcyB0b25lCi0gU3BlY2lmaWMgYnV0IG5vdCBvdmVybHkgdGVjaG5pY2FsIGphcmdvbgotIENsZWFyIHRpbWVsaW5lCi0gQWN0aW9uYWJsZSBpdGVtcyB3aXRoIG93bmVycwotIEhvbmVzdCBhYm91dCB3aGF0IHdlbnQgd3JvbmcK
```

With both the normal door and
`GGML_SYCL_MMVQ_Q8_FIXED_SHAPES_POISON=1`, the specialized vec-dot intentionally
reused the third weight vector for the fourth DP4A. Both shape families again
logged on both devices, and the completion diverged after ten generated tokens
(SHA-256 `1903bc0f6d623da99a66b17b5b80babb719d09e05f52f461fd194925e2526e5c`).
This proves the exact normal result exercised the specialized kernels.

## Position-balanced result

Same candidate binary, fresh process per arm, order `A-B-B-A`,
`llama-bench -p 64 -n 256 -r 3`, equal TP2 split, F16 KV, flash attention,
`b1024/ub256`, target only:

| Position | Arm | Prompt tok/s | Decode tok/s |
| ---: | --- | ---: | ---: |
| 1 | control | 382.311797 | 36.805223 |
| 2 | fixed shapes | 382.755569 | 36.788405 |
| 3 | fixed shapes | 381.989657 | 36.816559 |
| 4 | control | 382.504036 | 36.806235 |

- control decode mean: `36.805729 tok/s`
- treatment decode mean: `36.802482 tok/s`
- decode delta: `-0.008822%`
- prompt delta: `-0.009232%`

The compiler already removed the relevant dynamic-indexing overhead. Do not
promote or repeat these exact specializations. The complete 12-prompt suite was
not run because the candidate failed the performance gate.

## Reproduction artifacts

- structured result:
  [`../data/2026-08-16-q8-fixed-shape-mmvq-neutral.json`](../data/2026-08-16-q8-fixed-shape-mmvq-neutral.json)
- incremental patch against the accepted Q8 source stack:
  [`../patches/q8-fixed-shape-mmvq-neutral-20260816.diff`](../patches/q8-fixed-shape-mmvq-neutral-20260816.diff)
- incremental patch SHA-256:
  `88ee34147f1f2f71373d8933aabaf8f1fcecca4bf9cf9491075e20add59cea2b`
- local source: `/mnt/fast-ai/src/llama.cpp-q38-q8-fixed-shapes`
- local build: `build-sycl-aot-bmg-g31-fixed-shapes`
- `libggml-sycl.so.0.19.0` SHA-256:
  `3cd0b92fb25a3bc88e3dff3d960e178aa3a278985a03da31bb184a6c87bd8415`
- `llama-bench` SHA-256:
  `5ad7c26b123d41194a72f127052c50414a58a558a120548f17f11d54dba61abb`
- post-test GPU state: normal on both devices; no Xe fault/reset/hang this boot.
