# MTP single-stream observation on one B70

> **Evidence: `community-reported`; not run in the reference lab.** This is a
> useful negative observation for one configuration, not a general MTP or SYCL
> conclusion.

Pinned contributor write-up:
[`results/mtp-spec-decode-b70.md`](https://github.com/bosd/trx50-arc-b70-benchmarks/blob/fda0d86c47ff02d8e36f813a8e0121a2152d4478/results/mtp-spec-decode-b70.md).

## Reported setup

- One Arc Pro B70 on Fedora Server 44, kernel 7.0.10, `xe`, NEO
  26.18.38308.1, oneAPI 2026.0.
- llama.cpp commit
  [`dee2a846b82f15d27f84a48fa387cb53e0d99c25`](https://github.com/ggml-org/llama.cpp/commit/dee2a846b82f15d27f84a48fa387cb53e0d99c25),
  SYCL backend.
- Qwen3.6-35B-A3B MTP GGUF, reported as UD-Q4_K_M with F16 KV.
- One request stream, 512 generated tokens, temperature 0, maximum draft length
  3; flash attention compared off and on.

## Reported measurements

| Flash attention | MTP off | MTP on | Calculated effect | Reported acceptance |
| --- | ---: | ---: | ---: | --- |
| Off | 72.4 tok/s | 68.6 tok/s | −5.2% | 71% (348/487), mean length 3.13 |
| On | 72.6 tok/s | 65.1 tok/s | −10.3% | 66% (339/515), mean length 2.97 |

The arithmetic agrees with the contributor's rounded −5% and −10% values.

## Maintainer review

The pinned source contains the helper script but not its referenced raw server
logs or response directory. The helper explicitly sends a warm-up request
before the measured request, so this is not evidence for a cold-first-response
benchmark. Repeats and dispersion are not established by the published
artifacts. The helper also performs broad `pkill -9` cleanup and must be made
PID-scoped before use on a shared system.

The reported AMD comparison changes GPU vendor, GPU count, backend, runtime,
and likely build identity at once: one Intel B70 with SYCL is compared with two
Radeon 7800 XT GPUs using ROCm. Similar MTP-off throughput does not isolate the
backend as the cause of the different MTP response. The proposed
bandwidth/expert-routing explanation is therefore a hypothesis.

The supported conclusion is limited to the supplied measurement: MTP was
reported slower for these two single-stream settings on this contributor's
one-B70 system. It is a reasonable reason to measure MTP-on against an MTP-off
control before enabling it, not proof that MTP is always a loss on B70.
