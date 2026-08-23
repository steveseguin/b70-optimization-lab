# Ornith 1.5 35B-A3B: beta-sigmoid/GDN fusion is server-neutral

Date: 2026-08-23 EDT

Status: **CLOSED NEUTRAL — do not ship**

Ornith's Qwen-derived recurrent path exposes a tempting 30-launch-per-token
transfer: fuse each 32-value FP32 `beta` sigmoid into the following Gated Delta
Net kernel. The candidate used a strict graph matcher, executed GDN at the
original sigmoid position so raw beta remained live, reproduced the stock
sigmoid arithmetic with FP32 rounding, required the accepted GDN-to-cache
fusion, and rejected output/cache aliasing.

Correctness was exact in the same frozen binary. Control and candidate produced
the same canonical 128-token transcript SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`;
the candidate reported 3,810 fused hits.

The isolated engine loop looked promising:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `117.971221`, `118.072975` | **118.022098** |
| candidate | `119.618176`, `118.877559` | **119.247868** |

That is +1.0386%, but it did not survive the realistic fresh-server gate:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `113.635135`, `112.164181` | **112.899658** |
| candidate | `113.447128`, `113.236306` | **113.341717** |

The pooled difference is only +0.3916%. Both candidates lost to control A and
beat control B, so process ordering/variation is larger than the apparent
effect. All freshness and final-response gates passed; this is a measurement
neutral, not an invalid run. It is not added to the user package, and canary
replay was intentionally skipped after the promotion gate failed.

The exact incremental source is preserved at
`../patches/llamacpp-ornith15-beta-gdn-realistic-neutral-20260823.patch` so the
same idea is not rediscovered and promoted from an engine-only benchmark. Raw
engine/server records, exactness, and the structured conclusion are under
`../data/2026-08-23-ornith35b-beta-gdn-*`.
