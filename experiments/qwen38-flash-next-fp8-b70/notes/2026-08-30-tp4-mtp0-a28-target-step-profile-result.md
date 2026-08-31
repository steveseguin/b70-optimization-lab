# Qwen3.8 Flash-Next FP8 A28 target-step profile result

Date: 2026-08-30
Status: diagnostic capture positive; endpoint battery incomplete and no speed,
quality, reliability, or promotion credit

A28 was the first and only full Flash-Next load in boot
`b998940e-4b8c-481e-92cb-2844f8a6b389`. It produced four nonempty gzip-valid
rank traces and four rank tables. The profiled exact p4096/o128 request passed
every generic depth, transport, and cache-zero gate. Its output hash
`f9ba2586...8fe20` is byte-identical to A10 row 2's known non-authority family
and first differs from retained authority `1d833e5f...d5cc` at generated token
7. Profile timing is permanently ineligible for speed credit.

The frozen offline summarizer then failed closed before the semantic, repeat,
short, and ordinary exact-4K battery. This was an analyzer defect, not a model
or trace failure: XPU `submitted`/`appended` values are absolute nanoseconds,
while `execute_context` annotations are Kineto-relative microseconds. The
summarizer compared them directly. Each trace supplies
`baseTimeNanoseconds=1782967788000000000`; normalizing each device anchor as
`(raw_anchor_ns - baseTimeNanoseconds) / 1000` recovers exactly 5,586 events in
each of all four contexts on every rank, with only 56 events per rank outside
the windows. The synthetic contract fixture had reproduced the wrong unit and
time base, so it could not catch the defect.

The corrected analyzer requires the base-time field, rejects missing or
malformed values, and has five passing focused tests. It successfully produced
the recovered offline summary from the original raw traces; no endpoint or GPU
rerun was needed. A second latent helper issue was also found: its later
manifest assertion required `created_cache_tokens` to be explicitly present,
while this valid response omits the field. The ordinary battery therefore
would still not have started after the timestamp repair. Both defects are
recorded; neither changes the raw capture or any protected result.

## Bottleneck result

The retained contexts contain 97 BF16 allreduces, 96 fused-MoE kernels, 532
GEMMs, 86 QSA-bucket device events, and 72 GDN-bucket device events per target
token. The latter include 12 QSA sparse-split kernels plus 36 causal-convolution
and 36 gated-delta kernels. Across rank means, the concrete noncollective
buckets are approximately:

- routed/shared MoE: 26.08 ms/token;
- dense projections: 10.03 ms/token raw cross-rank mean, but approximately
  7.58 ms/token robust steady value after excluding one isolated rank-3
  profiler/scheduling episode;
- quantization/casts: 4.19 ms/token;
- elementwise work: 2.94 ms/token;
- QSA: 2.21 ms/token;
- GDN: 0.41 ms/token;
- PLE lookup: 0.0019 ms/token.

The dense mean needs that explicit qualification. Eleven of twelve rank-cycles
clustered between 7.528 and 7.632 ms (mean 7.5745, median 7.5795 ms). Rank 3's
second retained cycle alone measured 37.0568 ms because four unrelated layer-7
GEMM shapes slowed consecutively. Its other two cycles were 7.598 and 7.632 ms.
This is a rank-local profiler or scheduling episode, not evidence that four
steady kernels regress together. Use about 7.58 ms/token for component
projections while preserving 10.03 ms as the raw captured mean.

Collective kernel residence varies from 39.87 to 366.64 ms/token across rank
means, while the rank-3 noncollective sum is materially higher than the other
ranks. These collective durations include arrival and synchronization wait and
are not additive wall time. The asymmetry, 97 collectives per token, and
profiler-inflated 570--595 ms host contexts identify collective critical-path
and rank-arrival imbalance as the primary unresolved bottleneck class. They do
not justify treating raw oneCCL residence as wire time.

A28 therefore closes generic GDN, QSA, and PLE speed work as priorities for
this target-only lane. The strongest concrete noncollective work is the
production decode MoE path plus dense projections. The routed kernel receives
M1: although EP4 is enabled, DP=PCP=SP=1 keeps `use_all2all_kernels` false, so
there is no per-layer token all-gather. A27 only proved its tuned-config file
was loaded; its unchanged M1 entry remained active, so the M4 treatment was
not exercised. Before changing runtime code, use these already captured
aligned timelines to classify all 97 BF16 allreduces by ordinal/layer, message
size, rank arrival, and preceding compute. That discriminator requires no reboot or model load and
will choose among collective-count/fusion, topology/rank placement, and
production M1 MoE work.

Teardown was clean: no port-19700 listener or model worker remains, host memory
and swap recovered, and no B70 reset or fault occurred. Corrected NVMe PCIe
receive events appeared during load but were not GPU events. Protected
`5.515783 tok/s` target-only and approximately `20.727 tok/s` MTP4 results are
unchanged.

Structured result:
[`20260830-tp4-mtp0-a28-target-step-profile-result.json`](../data/20260830-tp4-mtp0-a28-target-step-profile-result.json).
