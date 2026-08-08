# STATUS — Qwen3.6 35B A3B offline-FP8 TP2 on Intel B70

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | read; offline evidence executed; no model/container execution |
| Tested in reference lab | offline review only |
| Safe to merge as documentation | yes, after maintainer isolation and launcher hardening |
| Eligible for `repro/` or `results/` | no |

## Provenance

- Contributor: `dominick253`.
- Source: [PR #18](https://github.com/steveseguin/b70-optimization-lab/pull/18).
- Contributor head: `1604d0b1d444f47c58c1abedd88d879908425b21`.
- Right-to-submit statement: present in the PR.
- Third-party material: Intel `llm-scaler`, vLLM, PyTorch, llama-benchy,
  and Qwen are referenced; model weights and container layers are not included.

The contributor's original files remain recoverable through the merge parent.
Raw contributor artifacts and the exact measured launcher are under
[`reported/`](reported/). Maintainer-produced checks are under
[`validation/`](validation/).

## Contributor claim

The contributor reports that a digest-pinned Intel B2 image served
`Qwen/Qwen3.6-35B-A3B-FP8` on two B70s with TP2 and MTP2. Three same-start
pp1024/tg256 sweeps reportedly averaged 432.17 aggregate generation tok/s at
concurrency 12, and four saved responses totaling 11,024 completion tokens
contained no detected `!!!!` corruption.

## Contributor environment

| Field | Value |
| --- | --- |
| GPU | 2x Intel `8086:e223`, 32 GiB each |
| OS / kernel | Ubuntu 26.04 / `7.0.0-29-generic` |
| Driver | `xe`, reported srcversion `85B7CA089405934276CBAD3` |
| Image | `intel/llm-scaler-vllm@sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e` |
| vLLM / XPU kernels | `0.21.1.dev0+gad7125a43.d20260802.xpu` / `0.1.8.3.dev0+g3cab97a.d20260802` |
| Model revision | `95a723d08a9490559dae23d0cff1d9466213d989` |
| Precision | offline FP8 E4M3 weights, FP16 compute, FP8 E4M3 KV scale 1.0 |
| Parallelism | TP2, eager, MTP2, text-only |
| Context / concurrency | 131,072 maximum context; maximum 12 sequences |
| Benchmark | llama-benchy `e9be34457`; pp1024/tg256; c1/2/4/8/12; 3 sweeps |

## What was run in the reference lab

No model, container, GPU, service, or network benchmark was run. The maintainer
performed only isolated offline review:

- all JSON parsed;
- all changed scripts passed syntax parsing;
- Python review tools passed Ruff;
- the contributor verifier ran, and its `assert`-under-`-O` weakness was found;
- the corrected fail-closed verifier recomputed hashes, means, request totals,
  and bounded output checks;
- launcher dry-run and invalid-input guards were exercised;
- secret-pattern, path, file-type, and dangerous-command review completed.

See [`validation/2026-08-08-offline-review.md`](validation/2026-08-08-offline-review.md).

## Findings

1. The submitted benchmark numbers and quality-manifest hashes are internally
   consistent with the submitted raw JSON.
2. That consistency does not independently prove the host identity, workload,
   journal contents, or absence of competing traffic.
3. The contributor fault counter was fail-open on journal-access failure, so
   the reported `697 -> 697` field is retained as contributor evidence rather
   than accepted as a maintainer-verified no-fault gate.
4. The long-output detector is a useful bounded corruption screen, not a
   semantic-equivalence test.
5. Intel issue #550 documents the four simple-collective threshold variables,
   and Intel PR #464 documents the GDN bounds guard cited by the packet.

## Known issues

- The exact reported launcher is privileged, host-networked, host-IPC, disables
  seccomp, publishes an unauthenticated endpoint, force-removes containers, and
  enables restart persistence. It is preserved as non-copy-ready evidence.
- The hardened launcher is offline-reviewed but has not been run. Reduced
  privileges may require further adjustment on a fresh isolated host.
- FP8 KV scale 1.0 has no native-KV semantic control here.
- All three sweeps share one service start; no cold-start replication exists.
- There is no clean matched MTP-off control.

## Disposition

Keep this packet in `community/` at `community-reported`. A future reference-lab
run records new artifacts under `validation/<date>/` and may raise the status to
`B70-tested`. Promotion to `repro/`, `results/`, or LocalMaxxing requires a
separate maintainer decision and the repository's full quality gate.
