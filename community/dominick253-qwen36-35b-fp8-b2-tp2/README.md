# Qwen3.6 35B A3B offline-FP8 TP2 on two Intel B70s

> **Community contribution by `dominick253`.** This is contributor-host
> evidence, now paired with a separate reference-lab validation. Maintainer
> corrections isolate the reported artifacts and provide a tested
> maintainer-reduced launcher;
> the contributor's original tree remains in Git history. Read
> [STATUS.md](STATUS.md) before use.

## Reported result

The contributor reports serving `Qwen/Qwen3.6-35B-A3B-FP8` with an Intel B2
vLLM image on two B70s using TP2, FP8 KV, eager execution, and MTP2. Three
same-start pp1024/tg256 sweeps reportedly reached a mean 432.17 aggregate
generation tok/s at concurrency 12. Four saved outputs totaled 11,024 tokens
without triggering the submitted repeated-punctuation detector.

The exact model revision, image, and vLLM workload are now `B70-tested` under a
maintainer-reduced container configuration: two 165-request sweeps and bounded
functional checks passed in the reference lab. The reported 432.17
aggregate c12 tok/s was not reproduced; the hardened run measured 268.87 and a
contributor-privilege control measured 286.00. See
[`validation/2026-08-08-reference-lab-validation.md`](validation/2026-08-08-reference-lab-validation.md).

| Evidence source | c1 generation tok/s | c12 generation tok/s | Interpretation |
| --- | ---: | ---: | --- |
| Contributor, three same-start sweeps | 105.23 | 432.17 | Contributor-host report; arithmetic and submitted hashes checked |
| Reference lab, hardened launcher | 54.87 | 268.87 | Exact model/image/runtime identity replayed; functional gates passed |
| Reference lab, contributor privileges | 52.61 | 286.00 | Broader privileges did not reproduce the reported rate |

A follow-up Gen4 x16 / Gen3 x16 / Gen4 x16 causal test found that the Gen3
decode observations remained inside the Gen4 control envelope, while an
adjacent bulk XCCL calibration did respond to the link change. PCIe bandwidth
does not explain the missing throughput in this packet. See the
[`PCIe link-sensitivity validation`](validation/2026-08-08-pcie-link-sensitivity.md).

## Reported identity

| Field | Contributor report |
| --- | --- |
| Hardware | 2x Intel Arc Pro B70, 32 GiB each |
| Image | `intel/llm-scaler-vllm@sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e` |
| Model revision | `95a723d08a9490559dae23d0cff1d9466213d989` |
| vLLM | `0.21.1.dev0+gad7125a43.d20260802.xpu` |
| XPU kernels | `0.1.8.3.dev0+g3cab97a.d20260802` |
| Precision | offline FP8 weights, FP16 compute, FP8 E4M3 KV scale 1.0 |
| Parallelism | TP2, eager, MTP2 |
| Limits | context 131,072; maximum 12 sequences; batched tokens 8,192 |
| Workload | pp1024/tg256 exact; c1/2/4/8/12; 5 measured + 1 warmup; 3 sweeps |

## Packet layout

- [`reported/exact-contributor-launcher.sh`](reported/exact-contributor-launcher.sh):
  exact submitted launcher, including its dangerous privileges and destructive
  cleanup. Preserve for provenance; do not run without a separate review.
- [`reported/evidence/`](reported/evidence/): contributor JSON, logs, raw
  outputs, benchmark/quality scripts, and original verifier.
- [`vllm-qwen36-35b-fp8-b2-tp2.sh`](vllm-qwen36-35b-fp8-b2-tp2.sh):
  maintainer-hardened launcher with digest pinning, localhost publication,
  no container replacement/restart, reduced privileges, and dry-run support.
- [`validation/`](validation/): maintainer offline review and the separate
  exact-model/image/runtime reference-lab execution record.

## Maintainer-reduced launcher

The hardened launcher requires a local model cache and validates every
variable that is interpolated into the container command:

```bash
MODEL_REPO=/path/to/models--Qwen--Qwen3.6-35B-A3B-FP8 \
DRY_RUN=1 \
bash vllm-qwen36-35b-fp8-b2-tp2.sh
```

Inspect the dry-run output, confirm GPU ownership and ports, then omit
`DRY_RUN=1`. The endpoint is published only on `127.0.0.1:18018` by default.
The reduced-privilege launcher is device-tested. It remains a trusted-local-
workload launcher: the rootful container receives every `/dev/dri` node, the
host IPC namespace, `CAP_SYS_PTRACE`, and a nominal 200 GiB shared-memory
allocation. Use only the pinned trusted digest in an exclusive all-GPU window.
oneCCL additionally requires host IPC and `CAP_SYS_PTRACE` in this tested
Docker configuration; it does not require
the contributor's privileged mode, host network, unconfined seccomp, or
restart persistence.

## Offline evidence check

```bash
python3 validation/verify-reported-evidence.py
```

This recomputes raw means, aggregate means, hashes, reported request totals,
and bounded long-output checks with explicit fail-closed conditions. It does
not promote the evidence level or validate the original journal access.

## Important limitations

- The original fault scanner can report zero when journal access fails.
- The contributor's three sweeps used one service start.
- No native-KV quality control or matched MTP-off control was submitted or
  added by the narrow reference-lab replay.
- The output detector checks obvious corruption, not correctness or usefulness.
- The reported endpoint was unauthenticated and host-networked; the maintained
  launcher deliberately does not reproduce that exposure.
- The reference lab validated the exact model/image/runtime identity under its
  reduced-privilege container configuration but did not reproduce the reported
  throughput or the contributor's exact deployment surface.

The simple-collective variables are grounded in
[Intel issue #550](https://github.com/intel/llm-scaler/issues/550#issuecomment-5187718030).
The cited GDN bounds guard is documented by
[Intel PR #464](https://github.com/intel/llm-scaler/pull/464). Neither source
independently verifies this contributor benchmark.
