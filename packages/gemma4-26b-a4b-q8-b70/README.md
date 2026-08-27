# Gemma 4 26B A4B Q8 — one-B70 reconstruction package

This is the user-facing front door for our one-card Gemma 4 Q8 research lane.
The lab moved this model from an early roughly `15.55 tok/s` one-card Q8
starting point to a valid `124.977 tok/s` high through our llama.cpp/SYCL,
MoE, and target-verified MTP work. Those historical endpoints are not a
like-for-like percentage comparison; use the linked result evidence for exact
identities.

Under the 2026-08-27 class-balanced publication rule, the same raw suite's
headline is **`122.160357 tok/s`**: median within input class, then median
across the six class medians. `123.727369` is the secondary all-prompt
99-interval median and `124.977141` is the historical 100-event compatibility
figure; neither is the current headline.

> **Status: source-verified reconstruction candidate, not a beginner install.**
> The exact aggregate source stack now applies cleanly from its pinned base.
> The original record binary hash and historical local Q4_0 draft hash were not
> retained, and this audit host does not have the record's oneAPI 2026.0
> toolchain or a B70 replay slot. A rebuilt package must pass the full canary and
> cold-suite gates before anyone calls it reproduced.

Start with the [125 tok/s reproduction guide](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md).
Every required project artifact is linked inside our repository:

- [canonical aggregate patch](../../patches/gemma4-26b-a4b-q8-b70/README.md);
- [source restore/build helper](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/restore-and-build.sh);
- [pinned model manifest](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/model-manifest.json);
- [record evidence](../../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json);
- [full result packet](../../results/gemma4-26b-a4b-q8-b70/README.md).

## Who built what

**neural.download lab — integrated:** Gemma 4 B70 bring-up, llama.cpp/SYCL and
MoE optimization, target-verified MTP work, source reconstruction, and package
validation. The roughly `15.55 tok/s` early one-card Q8 starting point and the
`124.977 tok/s` high use different configurations, so they document this
lab's development history and are not presented as one like-for-like boost.
The exact identities and matched increments remain in the
[result packet](../../results/gemma4-26b-a4b-q8-b70/README.md).

## Performance over context

The guide library graphs the validated one-card service sweep below. Each
point is the arithmetic mean of four independent B70 lanes. Every prompt was
unique and cache-zero, and every exact JSON retrieval gate passed.

| Actual prompt/context tokens | Decode after TTFT | Approx. prefill | TTFT |
| ---: | ---: | ---: | ---: |
| 741 | 161.90 tok/s | 847.96 tok/s | 0.874 s |
| 2,806 | 144.87 tok/s | 1,401.02 tok/s | 2.003 s |
| 5,643 | 141.11 tok/s | 1,469.44 tok/s | 3.841 s |
| 10,976 | 135.93 tok/s | 1,330.39 tok/s | 8.251 s |
| 16,213 | 127.64 tok/s | 1,256.95 tok/s | 12.899 s |
| 22,730 | 120.48 tok/s | 1,128.98 tok/s | 20.134 s |
| 30,400 | 114.00 tok/s | 1,028.20 tok/s | 29.568 s |
| 32,571 | 114.85 tok/s | 1,001.69 tok/s | 32.517 s |

This uses the long-context service profile and a 128-token output ceiling; it
is not the same operating identity as the short-context `122.160 tok/s`
headline. Prefill is approximated as actual prompt tokens divided by TTFT.
See the [compact profile](../../data/gemma4-26b-a4b-q8-b70-context-performance-profile-20260702.json)
and [all 32 source rows](../../data/gemma4-long-context-service-gate-20260702Tservice-ladder-current-rep4.json).

The next promotion step is a clean one-B70 rebuild with oneAPI 2026.0, a newly
recorded Q4_0 draft digest, `512/512` canary pass, 12/12 cache-zero cold suite,
and retained source/model/binary receipts.
