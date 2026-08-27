# Qwen3.8 FP8 dynamic MTP8-through-c2 R21 negative

Extending MTP8 from one active request through batch size two preserved
singleton speed and passed the strict c2 canary, but substantially reduced c64
throughput and concurrent output identity. The threshold is closed negative.

| Shape | promoted MTP8 median | MTP8-through-c2 R21 | change |
| --- | ---: | ---: | ---: |
| one user, fresh after-TTFT decode | 146.814418 | 146.822210 | +0.01% |
| c64 aggregate decode | **1,094.314767** | 836.139048 | **-23.59%** |

The first K8 c2 canary passed 2/2 sequential-oracle exact with complete IDs,
cache zero, and no cross-base collisions. Sequential quality also passed 7/7
exact cases, 8/8 repeat stability, and the frozen baseline. The excluded c64
transition then measured 811.279556 tok/s with only 55/64 oracle matches. The
declared batch returned all 8,192 tokens with complete IDs, cache zero, and no
cross-base collision, but reached only 836.139048 tok/s and again 55/64 oracle
matches. It missed the promoted-median gate by 23.59%, so the protocol stopped
before the 512-request canary.

The selected boundary is therefore supported directly: K8 only for a genuine
singleton, K1 from two requests onward. Neither keeping K1 through the final
singleton (R20) nor extending K8 through c2 (R21) improves the balance. MTP8
at one/MTP1 at load remains the public profile.

Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp8-c2-dynamic-mtp1-20260827-r21/`](../data/qwen38-fp8-w8a16-mtp8-c2-dynamic-mtp1-20260827-r21/).
No missing shape is inferred, interpolated, or extrapolated.
