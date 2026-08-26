# Qwen3.8 aggregate, RMS-W8A8, and native-XMX screen

No quality-qualified Qwen3.8-27B lane reached the requested `875 tok/s`
aggregate target on this two-B70 host. The screen did identify why the obvious
routes do not close the gap, and it preserves the diagnostic code and raw
receipts without changing the website or promoting a package.

## Results

| lane | measured aggregate | quality result | decision |
| --- | ---: | --- | --- |
| Official FP8 TP2, c128, first shape | `688.46 tok/s` | 256/256 concurrent semantic canaries; 5/128 strict token identity | capacity negative |
| Official FP8 TP2, c128, conditioned x2 | `662.61`, `691.36 tok/s` (median `676.99`) | 5/128 then 2/128 strict token identity | c64 remains faster |
| AutoRound INT4 native-XMX TP2, c64 | `556.97 tok/s` | sequential 7/7, but 111/128 concurrent canaries and 0/64 token identity | quality and capacity negative |
| AutoRound INT4 native-XMX TP1, c64 | `106.84 tok/s` | sequential arithmetic returned `54`, expected `60` | replication cannot reach target |

The c128 FP8 experiment used a 1,024-token service cap, 128 active slots, and
512 batched tokens. It had ample KV capacity and passed the semantic concurrent
suite, but doubling c64 to c128 reduced throughput. The full 128-prompt oracle
is frozen in the raw evidence directory; no point is extrapolated.

TP4 was not benchmarked: `xpu-smi`, PCI discovery, and the container runtime
all exposed exactly two B70s. The attempted TP4 service failed before model
loading with ranks 2 and 3 out of bounds. That is a host-capacity result, not a
model performance result.

## AutoRound oneAPI guard

The libsycl9 nightly image still fell back to FP16 because
`auto_round_kernel.utils.is_oneapi_ge_2026()` executes `icpx --version`; the
lean serving image intentionally omits the compiler frontend. A fake `icpx`
was rejected because Triton also invokes it. The retained Dockerfile adds a
default-off `AUTO_ROUND_XPU_ASSUME_ONEAPI_GE_2026=1` override to that one guard.

With the override, both ranks loaded the native XMX INT8 path and no fallback
warning appeared. Strict quality then rejected the lane. This is diagnostic
evidence for fixing the upstream capability probe, not a user recommendation.

## RMS-scaled W8A8

Selected-layer telemetry measured activation `max/RMS` ratios from about 5.8
to 68.4. Alpha 4 and 12 collapsed output. Alpha 48, 52, 54, and 56 passed the
sequential suite but respectively failed 30/256, 3/256, 10/512, and 2/128
concurrent canaries. Alpha 64 failed sequential code execution and 2/256
concurrent requests. A static mixed FP8/W8A8 reference also failed 35/256.

The narrow 52–56 window is not a trustworthy solution: misses vary with live
batch composition and remain concentrated in arithmetic/code answers. Global
clip tuning is closed. The next useful optimization must identify and repair
the batch-shape-sensitive layer/row error directly, while retaining the raw
W8A8 speed ceiling as research-only evidence.

## Reproduction material

- [Structured summary](../data/2026-08-26-qwen38-aggregate-rms-runtime-screen-summary.json)
- [Raw HTTP, quality, telemetry, verifier, and c128 oracle receipts](../data/qwen38-aggregate-rms-runtime-screen-20260826-r1/)
- [vLLM RMS/W8A8 diagnostic patch](../patches/vllm-qwen38-w8a8-rms-diagnostic-20260826.patch)
- [vLLM XPU kernels RMS/W8A8 diagnostic patch](../patches/vllm-xpu-kernels-qwen38-w8a8-rms-diagnostic-20260826.patch)
- [AutoRound oneAPI guard diagnostic Dockerfile](../patches/autoround-kernel-oneapi-guard-diagnostic-20260826.Dockerfile)

The RMS patches are full diagnostic snapshots against vLLM
`ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9` and vLLM XPU kernels
`2dd55f380df753a10a88fcd9e96192561066e713`; they supersede the earlier
W8A8-only experimental snapshots for this branch. All behavior remains
default-off.
