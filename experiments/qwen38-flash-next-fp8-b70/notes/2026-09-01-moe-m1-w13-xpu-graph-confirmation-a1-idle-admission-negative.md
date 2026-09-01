# Qwen3.8 Flash-Next FP8 W13 confirmation A1 idle-admission negative

Date: 2026-09-01
Status: preserved pre-device infrastructure negative

A1 stopped correctly before multi-GiB checkpoint-shard hashing, cache creation,
or any XPU component process. Static index/config and runtime identity checks
had passed. Its 60-second idle admission required exactly zero change in the
local-NVMe corrected-event counter. At approximately 21.6 seconds, that counter
changed from `345` to `346`, so the runner exited `1` without entering the W13
confirmation matrix.

The journal window contains one corrected PCIe endpoint report from APEI
Source 514 for `0000:01:00.0`, the local Samsung NVMe endpoint. It is an
`RxErr`; uncorrected status is zero. The root-port corrected counter stayed at
zero, local-NVMe sectors read stayed unchanged, swap use stayed zero,
`MemAvailable` remained about 125.9 million KiB, memory-full PSI stayed zero,
and no severe event appeared. Owned-process and cache teardown both passed.

This is an infrastructure-policy negative, not a component or quality result.
No model shard was read, no GPU arm ran, and the exact W13-N32 discovery win is
unchanged. The useful conclusion is narrow: demanding a continuously zero
corrected count during idle is not a viable admission rule on the observed
link. A successor may remove only that zero-change admission while retaining a
strict dynamic total cap and all root, read-volume, memory, pressure, severe
event, teardown, and evidence gates.

Evidence root:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w13-xpu-graph-confirmation-a1`

The evidence `SHA256SUMS` verifies. Key SHA-256 values:

- runner: `c81a2240542b75a3bf932fccf606f2db4b2872d201171c76f8e6f48ac5a7fad3`;
- health receipt: `5c42866f7277afbe69e202437b116d0f03f330a18b0d22c34d98a276fdda8074`;
- health samples: `8e95f12bf94df246ac8068b2910a5838c63bc4799a7ff2a50af42e9a8bd3eb00`;
- final kernel journal: `74051828b8ff5505833be644445fc76a35fd065b7824b69faaf678e39ddcfea0`;
- evidence `SHA256SUMS`: `c5cb0306edf1a5683585675389dbe931afe871a13f3cf0c12130a120e32b0abc`.

Structured result:

`experiments/qwen38-flash-next-fp8-b70/data/20260901-moe-m1-w13-xpu-graph-confirmation-a1-idle-admission-negative.json`
