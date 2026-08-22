# Independent B70 audit-host benchmarks — 2026-08-22

This directory preserves two independent raw-engine depth sweeps and two XPU
operator diagnostics from the two-B70, 15 GiB RAM audit host. Nothing here
replaces the measuring-host package results: the host CPU, storage path, and
IntelLLVM version differ.

## Identities and protocol

- Same upstream llama.cpp revision as the packet runs:
  `9fee29e9435f865ec0b811a783a6471a136d9317`.
- Audit binary: Release, `-O3 -DNDEBUG`, SYCL F16, AOT `bmg-g31`,
  IntelLLVM 2026.1.1; SHA-256
  `598cb811537c16c07ec702c3f698dc1ebaa79ca2f7b2424539cf06a10df6fb96`.
- Measuring-host binary SHA-256: `0ffeba4b...`; IntelLLVM 2026.0.0. Results
  are cross-host comparisons, not matched A/Bs.
- One B70, F16 KV, flash attention on, all layers offloaded, `pp2048` and
  `tg128`, five repetitions at exactly 0/2K/4K/8K/16K/24K/32K existing
  context depth. No point is interpolated.
- Models were read from the read-only NFS mount at `/mnt/lab-models`; its
  current 100 Mb/s link is the dominant cold-load constraint.

Exact host and binary identities are in `run-manifest.json`.

## LFM2.5 2.6B Q8_0: valid cross-host replication

All 14 rows completed with five samples and low dispersion. Decode closely
reproduced the measuring host at every depth; prefill is 4–10% faster on this
host/toolchain and remains a separate observation.

| Depth | Audit decode | Measuring decode | Delta | Audit prefill | Measuring prefill | Delta |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 134.486 | 135.198 | -0.53% | 9855.550 | 9130.855 | +7.94% |
| 2,048 | 130.657 | 131.260 | -0.46% | 5100.871 | 4699.373 | +8.54% |
| 4,096 | 126.844 | 127.211 | -0.29% | 4932.075 | 4584.946 | +7.57% |
| 8,192 | 119.939 | 120.196 | -0.21% | 4692.554 | 4399.720 | +6.66% |
| 16,384 | 108.147 | 107.980 | +0.15% | 4006.905 | 3752.425 | +6.78% |
| 24,576 | 98.414 | 98.138 | +0.28% | 3848.446 | 3698.150 | +4.06% |
| 32,768 | 90.513 | 89.938 | +0.64% | 3120.687 | 2824.910 | +10.47% |

Evidence: `lfm25-26b-q8-audit-host-oneapi2026.1.1.meta.json` and
`lfm25-26b-q8-audit-host-oneapi2026.1.1.sweep.json`.

## Ornith 1.5 9B Q8_0: decode support, prefill rejected

The first attempt performed model hashing and loading inside one 13 GiB
systemd scope. `systemd-oomd` killed it during final staging; it produced zero
rows and is retained as an operational negative.

A second run reused the already verified SHA record, loaded under a 14 GiB
scope, and completed 14 rows. Several prefill samples were contaminated by
low-RAM/NFS paging—for example, zero-depth prefill ramped
`114, 184, 291, 479, 593 tok/s` rather than reaching a stationary band.
Therefore this run must not become a public prefill curve.

Decode is useful only as supporting evidence. Stable points independently
matched the measuring host closely:

| Depth | Audit decode | Measuring decode | Delta | Audit CV | Classification |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 46.326 | 50.292 | -7.89% | 2.13% | paging-affected |
| 2,048 | 48.004 | 49.338 | -2.70% | 1.62% | support only |
| 4,096 | 48.424 | 48.555 | -0.27% | 0.51% | stable support |
| 8,192 | 46.965 | 47.045 | -0.17% | 0.26% | stable support |
| 16,384 | 41.332 | 44.350 | -6.80% | 13.93% | outlier-contaminated |
| 24,576 | 42.008 | 41.958 | +0.12% | 0.04% | stable support |
| 32,768 | 39.843 | 39.838 | +0.01% | 0.16% | stable support |

Evidence: `ornith-15-9b-q8-audit-host-oneapi2026.1.1.*`. The failed attempt
is classified in
`ornith-15-9b-q8-audit-host-oneapi2026.1.1.attempt1-oom.failure.json`.

## Host-memory conclusion

The 13 GiB failure does **not** mean inference intrinsically needs 13 GiB of
anonymous RAM. It means an ordinary 9.53 GB verification read retained cached
pages in the same cgroup that then staged the model. Separating the verified
read from the benchmark allowed the run to complete; the observed scope charge
reached at least 5.81 GB during loading with no swap or pressure event.

Operational recommendation (not a benchmark measurement): 16 GiB is marginal
for this 9B workflow, 24 GiB is a practical minimum, and 32 GiB is comfortable.
For repeatedly validating the full first-wave set, including 21–25 GB GGUFs,
use 64 GiB; 128 GiB avoids page-cache churn and is preferred for a measuring
host.

## XPU operator diagnostics

- Tiny XPU-to-host token copies, 1,000 iterations per mode on GPU 1:
  nonblocking/current-event median roughly 5.7–7.4 microseconds; side-stream
  event roughly 10–12 microseconds; blocking copy plus device synchronization
  roughly 28–34 microseconds. Evidence:
  `xpu1-d2h-token-copy-20260822.json`.
- Qwen draft W4A16 dense-logit primitive, GPU 1, 20 timed iterations:
  1/2/4-row medians `1.122/1.127/1.152 ms`; dense logits plus argmax
  `1.164/1.169/1.181 ms`. The installed runtime exposes no fused top-1 path,
  so this is a diagnostic floor, not endpoint throughput. Evidence:
  `qwen27-draft-int4-lmhead-gpu1-20260822.json`.

These operator numbers make no model-quality or serving-throughput claim.
