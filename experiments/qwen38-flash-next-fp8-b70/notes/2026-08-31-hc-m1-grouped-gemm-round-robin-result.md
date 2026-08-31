# Qwen3.8 Flash-Next FP8 97-weight HC grouped-GEMM result

Date: 2026-08-31
Status: two-process family gate passed

The production-order full-bank screen passed. Both distinct one-B70 processes
loaded all 97 MTP0 target hyperconnection up weights—attention and MLP for all
48 layers plus the final mixer—and executed 97 separate E=1 calls per sweep.
Every BF16 `[1,10240]` grouped output remained finite and byte-identical to the
control-only `F.linear` authority through warmup, every timed block, and 100
post-timing exactness sweeps per provider.

| Repeat | Linear 97-call median | Grouped median | Saving | Reduction | Worst cycle | Order bias |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| r1 | 3.256665 ms | 1.579440 ms | 1.675420 ms | 51.4522% | 50.0902% | 0.0919 points |
| r2 | 3.326745 ms | 1.545463 ms | 1.779963 ms | 53.4852% | 52.4345% | 0.0017 points |

The median component saving across the two process medians is 1.727691 ms.
Both processes used the same exact packed-bank and device-state manifests; the
reduction spread was 2.033 points and the absolute-saving spread was 0.104543
ms. Prepacking the complete bank took about 60--62 ms.

The component retained both the 635,799,040-byte linear allocation and the
635,699,200-byte packed bank only to compare them. That duplicate 1.271 GB
layout is not endpoint eligible. A source candidate may now be built, but it
must replace or release the original bank after packing and remain opt-in until
a complete endpoint quality/reliability A/B passes.

The observed 1.727691 ms component delta is not an endpoint measurement. If it
were perfectly additive to the protected 5.515783 tok/s target lane it would
imply about 5.56885 tok/s (+0.96%); the A28 profile's 1.298 ms total up-kernel
bucket gives the more conservative additive ceiling of about 5.55556 tok/s
(+0.72%). Scheduling and overlap can reduce either estimate, so neither is a
claim or reason to change a protected result.

Exact raw hashes, process metrics, gates, and authorization boundaries are in
the [structured result](../data/20260831-hc-m1-grouped-gemm-round-robin-result.json).
