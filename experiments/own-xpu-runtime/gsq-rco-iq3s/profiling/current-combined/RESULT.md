# Current combined-engine class profile

The current combined attention/Q6 engine passes the fixed target-only diagnostic:
one disjoint eight-output warmup, full RESET, then original prompt00 with128 outputs.
Independent readback confirms every measured token and full target-state buffer,
214 consumed positions, exact original class launch/group counts, repeated captures
and unchanged closed files. Both owners exited0 with no signals or retained processes,
empty target descriptors and no new GPU faults. Vision remained unchanged.

These are summed GPU event execution durations across both ranks over the whole
measured request, including prompt processing. They exclude the warmup. They are not
wall time, decode-only costs, complete transfer costs or a throughput result. The
binary/arithmetic matches the qualified bundle engine; only existing instrumentation
changes from token timing to class timing, including rank1 queue profiling.

Total summed event time: **13743.110727ms**.

| Class | GPU event ms | Share | Launches |
| --- | ---: | ---: | ---: |
| expsgate | 1338.940 | 9.74% | 10,272 |
| expsup | 1334.840 | 9.71% | 10,272 |
| gdn.qkv | 1319.338 | 9.60% | 7,704 |
| gdn.z | 1211.911 | 8.82% | 7,704 |
| expsdown | 1093.978 | 7.96% | 10,272 |
| qsa.qgate | 768.147 | 5.59% | 2,568 |
| route | 702.142 | 5.11% | 51,360 |
| attention | 420.281 | 3.06% | 10,272 |
| gdn.recurrence | 377.963 | 2.75% | 7,704 |
| hc.f.low | 368.894 | 2.68% | 10,272 |
| hc.a.low | 364.431 | 2.65% | 10,272 |
| hc.f.inject | 357.569 | 2.60% | 10,272 |
| hc.a.inject | 356.792 | 2.60% | 10,272 |
| shexpgate | 350.691 | 2.55% | 10,272 |
| shexpup | 343.640 | 2.50% | 10,272 |

Expert gate/up together are the largest selected area (~19.45%). These classes mix
four weight formats; assigning their time by layer counts would be invalid. Next use
the existing narrow attribution mode to measure exact layer/format costs before
selecting a candidate. That mode samples fixtures9–16, which the controller maps to
early generated-token steps, not prefill. It does not establish all-decode averages.
No new instrumentation framework or native rebuild is needed.

The earlier original-binary class profile is a separate diagnostic; differences
between its event totals and these are not a matched end-to-end speed comparison.
The current separately audited resident engine remains14.85 target-only/22.13 MTP
 tokens/s on the short internal suite, not a public512-output record.

| Identity | SHA256 |
| --- | --- |
| Native binary | `5a8c9d3b58606022e21e2f0347360e4dd9cfdf6a869c8daac145e928fe4d4306` |
| Operational plan | `8a12f2b92b218b93c66e788b5b802d2fa140a812d9065b85a3dfcb23bd32c298` |
| Full result | `26c8f1a7b5b59e425666fcf04b038b5fdd9a35419dbb5bc3415d0597dbf00b89` |
| Independent audit | `24082f1789623e317c4447b374cf11bf1c7d568dcd25d5a6421505dd3b2321d0` |

[Independent review](evidence/device-a/review.json) and
[artifact index](evidence/device-a/artifact-index.jsonl.gz) bind169 artifacts,
716,862,277 bytes. Six bundles contain6,324 original ranges; initial and warmup
semantic comparisons remain informational. Retain the compact index and all raw
files at `/mnt/usb-models/own-xpu-runtime-results/gsq-current-class-a`; use the
[qualified reader](../../state-bundle/reader.py) for full range verification.
Coordinator receipts are at
`/home/steve/own-xpu-runtime-results/gsq-current-class-a.control`.
The coordinator took115.945seconds including loading/evidence, not an inference rate.

The raw bundle payloads are now preserved in [verified archives](../../storage/closed-bundles/RESULT.md); original
indices/seals/JSON remain in place. Restore a missing bundle before rerunning raw readback.
