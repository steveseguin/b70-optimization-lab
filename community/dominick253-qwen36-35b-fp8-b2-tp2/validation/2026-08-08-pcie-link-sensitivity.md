# PCIe link-sensitivity validation - 2026-08-08

## Question and conclusion

The contributor reported 432.169 aggregate generation tok/s at concurrency 12,
while the reference lab reproduced 268.866 tok/s with the same model revision,
container filesystem, vLLM/XPU-kernel packages, TP2/MTP2 configuration, and
benchmark shape. This follow-up tested whether a faster contributor PCIe fabric
could plausibly explain that gap.

It did not. Reducing both selected B70 links from PCIe Gen4 x16 to Gen3 x16 did
not reduce single-request decode throughput and produced no repeatable c12 loss
outside the ordinary control drift. A separate 256 MiB-per-rank all-reduce did
slow at Gen3, confirming that the link change affected effective bulk-fabric
performance. PCIe bandwidth is therefore not supported as the cause of the
reported approximately 1.6x c12 gap (or the approximately 2x c1 gap).

This is a maintainer diagnostic, not a promoted benchmark result.

## Fixed identity

- model revision: `95a723d08a9490559dae23d0cff1d9466213d989`;
- restored image filesystem/config identity: contributor B2 digest
  `sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e`,
  loaded from the USB archive as `community-b2-export:3f0a8c60`;
- vLLM/XPU kernels: `0.21.1.dev0+gad7125a43.d20260802.xpu` /
  `0.1.8.3.dev0+g3cab97a.d20260802`;
- local kernel/xe srcversion: `7.0.0-28-generic` /
  `85B7CA089405934276CBAD3`;
- two local Intel `8086:e223` B70s, `ZE_AFFINITY_MASK=0,1`, TP2, eager,
  MTP2, FP16 compute, FP8 E4M3 KV, maximum 12 sequences;
- llama-benchy `e9be344578cec17745066b220798b80a0d2686d3`, pp1024,
  exact tg256, concurrency 1 and 12, one warmup and five measured batches.

Each A/B service arm used a fresh container start. The repeated rows reused the
same corresponding service only after the first complete sweep.

## Counter capability probe

XPU-SMI exposes PCIe Read/Write metrics 19 and 20, but all 210 one-second
device samples collected during a live shadow benchmark were exactly zero.
The shadow run remained in the observed performance range, so this is not a
claim that polling suppressed real traffic: the installed stack simply did
not provide usable physical PCIe byte counters. The zero-valued series is
retained and is not used as bandwidth evidence.

The host is AMD Threadripper Pro and exposes no Intel IIO PMU. No reliable
physical wire-byte measurement was available, so the causal link-state A/B/A
and an adjacent XCCL bulk calibration were used instead.

## Link treatment and safety gates

The physical root-facing links for selected devices 0 and 1 are:

- `0000:20:01.1` to `0000:21:00.0` (GPU endpoint `23:00.0`);
- `0000:20:03.1` to `0000:25:00.0` (GPU endpoint `27:00.0`).

The internal B70 bridge readings that show Gen1 x1 were not treated as the
external link and were not modified. With the model stopped and both cards
idle, the saved root-port Link Control 2 word was `0004` on both ports. A masked
target-speed write and retrain changed both root and peer ends from 16.0 GT/s
x16 to 8.0 GT/s x16. The links were changed one at a time; device discovery,
AER totals, kernel faults, and a bounded two-device XPU computation were gated
around the transition.

Immediately after the B arm, both links were restored to 16.0 GT/s x16 and both
saved root words were restored exactly to `0004`; the bounded two-device
compute passed. After the A2 model start, both root-port target-speed fields
read `0003`. A post-teardown attempt to restore `0004` persisted for two
seconds, then both fields returned to `0003` again without retraining the live
links; the component responsible was not identified. No further register
writes were attempted in that boot. The pre-reboot state remained 16.0 GT/s
x16 at both root and peer ends, with root target fields `0003`, all relevant
AER totals at zero, and no inference container, worker, or listener.

A clean host reboot then restored all four B70 root-port target fields to their
normal `0004` values. All four root/peer paths negotiated 16.0 GT/s x16, all
AER totals remained zero, and a real allocation/matrix-compute check passed on
all four B70s. Model services remained disabled and inactive. The USB model
volume was remounted read/write and its Qwen aliases, FP8 snapshot, GGUF, and
runtime archive were checked. The pre-reboot, post-reboot, and compute files in
the external manifest preserve both states.

## Throughput observations

Generation throughput in tok/s:

| Arm | Service state | c1 mean (std) | c12 mean (std) |
| --- | --- | ---: | ---: |
| Gen4 A1 | fresh | 54.089 (1.564) | 263.630 (14.288) |
| Gen3 B1 | fresh | 58.331 (2.288) | 266.054 (14.158) |
| Gen3 B2 | same-service repeat | 54.482 (1.834) | 274.437 (12.053) |
| Gen4 A2 | fresh | 58.081 (1.629) | 285.708 (15.623) |
| Gen4 A2 repeat | same-service repeat | 53.205 (2.904) | 276.902 (9.387) |

Gen3 spans 54.482-58.331 tok/s at c1 and 266.054-274.437 at c12. Gen4
spans 53.205-58.081 at c1 and 263.630-285.708 at c12. The Gen3 observations
are inside the Gen4 control envelope and do not show the monotonic loss that a
bandwidth-bound explanation requires.

The fresh A2 control was 7.38% above fresh A1 at c1 and 8.37% above it at c12,
so the preregistered 3% A1/A2 stability rule was not met. The arms are not
pooled into a precision estimate. This control drift weakens any claim about a
small percentage effect, but it cannot conceal the approximately 35-50% loss
that would be required to explain the contributor/reference-lab gap.

## Adjacent effective-bandwidth calibration

With the model stopped, the same B2 runtime executed a two-rank BF16 all-reduce
over a 65,536 x 2,048 tensor (268,435,456 bytes per rank), five warmups and 30
measured iterations. The script was
`experiments/deepseek-v4-flash-reap-xpu-b70/scripts/bench-xccl-allreduce.py`
from source-repo commit `30dbf3dfc1f7fb67555655f57b03e8e4f1f5e369`, SHA-256
`4bc9a6888e78cbc591f999bb17410fd2c54d72f644b0c4bf3d109d19c36aaaf0`.

| Link state | Rank-0 median | Payload bytes / median |
| --- | ---: | ---: |
| Gen3 x16 | 58.478 ms | 4.590 GB/s |
| Gen4 x16 | 48.240 ms | 5.565 GB/s |

The adjacent calibration gained 21.2% at Gen4. It is an effective all-reduce
payload rate, not physical wire bytes or a PCIe peak claim. It confirms that
the treatment produced a measurable bulk-fabric change even though decode
throughput did not follow it.

PCIe has discrete Gen3 and Gen4 link rates; there is no native "Gen3.5" mode.
A contended-Gen4 midpoint would also consume copy-engine and memory resources.
Because the binary treatment showed no decode slope, that confounded midpoint
was not run.

## Evidence and disposition

Raw artifacts are outside Git under:

`/mnt/fast-ai/llm-optimization-artifacts/community-dominick253/qwen36-35b-fp8-b2-tp2/`

The focused 20-entry manifest is
`20260808-pcie-bandwidth-manifest.sha256`, whose SHA-256 is
`182f182198a895e1a21262ab57ac7bc3bc2bdaea169436e185034daeb237fc92`.
It covers benchmark JSON, the zero-valued counter series, container identity,
link/AER state, saved registers, the post-A2 state, the clean reboot gate, and
both all-reduce rows.

The contributor's faster rate remains valid only as contributor-host evidence.
The current data close PCIe link bandwidth as the leading explanation; they do
not identify the remaining cause and do not justify changing this packet's
`B70-tested` community-only classification.
