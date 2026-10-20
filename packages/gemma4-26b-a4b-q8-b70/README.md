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
> retained. Source rebuilds passed the lab-host gates on September 7; a fresh
> OS installation and byte-identical historical replay remain unverified.
> Every new build must pass the full canary and cold-suite gates.

Start with the [reproduction guide](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md).
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

## Latest prompt-reading measurements

The October 10 16K-slot sweep now plots actual input tokens instead of the
requested lengths. The request for 512 tokens produced **509 tokens**:
prefill was **1,323.8 tok/s with draft 3** or **1,327.8 tok/s without a
draft** (median of three timings per setting). That is a measured 509-token
result, not a measured 512-token result. The five actual graph coordinates
are 292, 509, 2,042, 8,185 and 15,793; requested counts remain annotations.
See the [draft-3 receipts](../../data/profiles/2026-10-10/gemma-sweep/single-16k-draft3.json)
and [no-draft receipts](../../data/profiles/2026-10-10/gemma-sweep/single-16k-draft0.json).

A separate October 15 production profile measures **1,307.54 / 1,167.81 /
909.27 tok/s** at **1,867 / 7,623 / 29,400 actual input tokens**, respectively.
Each point averages four timings on two servers. It uses one 32K slot, no
draft, f16 KV, deterministic oneDNN, and prefill micro-batch 1024. Timings
come directly from the server's prompt counters, with prompt caching
disabled. The diagnostic prompts repeat; this is not the cold-suite decode
headline or the July curve's TTFT approximation.

The [guide's exact table and method](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md#october-15-production-prompt-reading-profile)
and [source-linked timing summary](../../experiments/gemma4-26b-a4b-q8-b70/data/2026-10-15-prefill-reorder/publication-summary.json)
keep the complete precision and observed ranges.

The October 15 experimental coalesced conversion measured 13–22% faster
prefill with tested token parity, but **has not shipped in this package**.
Full build/library identities, tracked prompt inputs and clean-rebuild
replay remain open. Its gain is not silently applied to the package curves
or the decode headline. The guide links the retained patch and exact gates.

The remaining baseline packaging gate is an end-to-end fresh-host install
with retained source/model/binary receipts; the documented September 7
lab-host rebuild is already complete. The historical binary and draft
identity gaps remain explicit.
