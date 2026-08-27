# Qwen3.8 FP8 W8A16 dynamic Mamba allocation R4 result

R4 cleared the aggregate objective on the first preregistered run while
retaining the MTP2 single-user rate. It is a positive screen pending the
separately preregistered fresh-server replication and concurrent quality
canary; it is not yet a promoted package result.

## Measured result

- first eligible single-user row: **83.665 tok/s after TTFT** (gate 82.810);
- excluded c64 transition: **1,070.095 aggregate tok/s**;
- declared c64: **1,087.492 aggregate tok/s** (gate 875);
- change from the fixed-width dynamic R2: **+33.11%** at c64;
- change from static MTP2: **+47.52%** at c64;
- change from static MTP1: **-0.38%** at c64;
- single-user change from static MTP2: **+0.02%**.

The declared batch returned all 8,192 requested tokens, with complete token-ID
capture, zero cached prompt tokens, and zero cross-prompt output collisions.
It matched 56/64 sequential token oracles, so it remains an
output-isolation-qualified batch-shape variant. The independent semantic suite
passed 7/7 exact cases and 8/8 repeats and exactly matched the static-MTP2
baseline.

## Mechanism confirmed

R2 allocated three Mamba state blocks to every request because the service was
configured for at most MTP2. At c64 that left only 49 requests running and 15
waiting. R4 conservatively allocates the active lookahead required by the
dynamic FCFS schedule: the exact K2-at-one/K1-at-two-plus oracle is
`[3, 2, 2, 2]` state blocks for four requests.

Although the startup cache message remains a conservative static estimate,
the live scheduler reported **64 running, 0 waiting, 91.9% GPU cache use** on
both c64 batches. This directly confirms that the allocation change removed
the measured residency bottleneck.

The frozen patch is
[`../patches/vllm-qwen38-dynamic-mtp-mamba-active-allocation-20260826.patch`](../patches/vllm-qwen38-dynamic-mtp-mamba-active-allocation-20260826.patch)
(SHA-256 `3334c37f...919512190`). Its focused validation passed all 19 dynamic
speculation tests and the existing align-mode variable-draft regression. The
reproducible overlay image and build receipt are already tracked in this repo.

Raw evidence and checksums are in
[`../data/qwen38-fp8-w8a16-mtp2-dynamic-mamba-20260826-r4/`](../data/qwen38-fp8-w8a16-mtp2-dynamic-mamba-20260826-r4/).
No result is interpolated or extrapolated.
