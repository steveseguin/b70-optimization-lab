# STATUS — Qwen3.6 27B Q4_K_M llama.cpp SYCL

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | read; shell dry-run only; no model/service execution |
| Tested in reference lab | no |
| Safe to merge as documentation | yes, after maintainer corrections |
| Eligible for `repro/` or `results/` | no |

## Provenance

- Contributor: `dominick253`.
- Source: [PR #19](https://github.com/steveseguin/b70-optimization-lab/pull/19).
- Contributor head: `22c1bea916c5ae2e8c6f8eaff84c3e4e2e0a200d`.
- Right-to-submit statement: present in the PR.
- The contributor's exact final launcher and historical benchmark summary are
  preserved under [`reported/`](reported/).

## Contributor claim

The contributor reports two independent Qwen3.6-27B MTP Q4_K_M llama.cpp/SYCL
services, one per B70, and supplies a historical context-sweep summary.

## Contributor environment

| Field | Value |
| --- | --- |
| GPU | 2x Intel Arc Pro B70, 32 GiB each |
| OS / kernel | Ubuntu 24.04.4 / `6.17.0-1009-intel` |
| llama.cpp | reported commit `15586e2d7165570fb3aa7c26e0d442e289ef69de` |
| Model | Qwen3.6-27B MTP Q4_K_M GGUF, reported size 17,106,773,120 bytes |
| Model revision / SHA-256 | unknown |
| Precision | Q4_K_M weights; F16 target and draft KV |
| Service | independent per-GPU process, `parallel=1`, MTP draft maximum 2 |

## What was run in the reference lab

No contributor host, model, GPU, service, or endpoint was accessed. Maintainer
review covered the full diff, shell syntax, dry-run argument generation,
identity consistency, paths, links, and secret patterns. See
[`validation/2026-08-08-offline-review.md`](validation/2026-08-08-offline-review.md).

## Findings

1. The contributor head is internally inconsistent: its identity table and
   launcher say 175,000 context, while the retained inspection finding says the
   exact live launcher used 150,000. The 160K and 175K updates added no matching
   raw runtime record. Current exact context is therefore unknown.
2. No raw benchmark JSON/CSV/log is included. The historical summary uses
   greedy temperature 0.0 and draft widths 1/2, while the reported service uses
   temperature 0.6 and draft maximum 2.
3. Contributor-authored “maintainer note” and review-state claims were replaced
   by this maintainer-owned status rather than accepted as prior certification.
4. The hardened launcher requires the caller to choose context explicitly,
   provide model and server-binary SHA-256 values, and use the reported clean
   llama.cpp commit. It defaults to loopback and validates device and port
   inputs.

## Disposition

Keep as a useful `community-reported` recipe. Before reference-lab execution,
capture the exact model revision/hash and choose one explicit context identity.
Raw matching benchmark and quality artifacts are required for any promotion.
