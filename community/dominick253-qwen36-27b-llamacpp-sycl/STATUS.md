# STATUS — Qwen3.6 27B Q4_K_M llama.cpp SYCL

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-tested` |
| Patch review status | read; matching-name-and-size model artifact, exact engine commit, and device validation completed |
| Tested in reference lab | yes; one fixed greedy visible-output match and 2K/32K/120K depth checks |
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
| Contributor model revision / SHA-256 | unknown / unknown |
| Lab-selected official artifact | matching filename and exact reported byte size; revision `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`; SHA-256 `a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f` |
| Precision | Q4_K_M weights; F16 target and draft KV |
| Service | independent per-GPU process, `parallel=1`, MTP draft maximum 2 |

## What was run in the reference lab

The offline review remains preserved at
[`validation/2026-08-08-offline-review.md`](validation/2026-08-08-offline-review.md).
The follow-up built the reported llama.cpp commit with oneAPI 2026.0.0, loaded
the matching-name-and-size official Q4_K_M artifact in one process on one B70,
compared MTP2 against a target-only control, and completed exact 2K, 32K, and
120K prompt rows. The operator requested 150,000 context; the retained output
proves capacity through at least 120,128 tokens. See
[`validation/2026-08-08-reference-lab-validation.md`](validation/2026-08-08-reference-lab-validation.md).

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
5. MTP2 produced the same visible bytes as the fixed greedy 128-token
   target-only control and reached 38.112 tok/s versus 25.307 target-only.
   Generated token IDs were not retained, and the two request records differ
   in `min_p`, so this is not a token-exact A/B. At 2K/32K/120K, decode was
   33.412/24.752/16.027 tok/s and acceptance was 72.12%/59.13%/51.61%.
6. The historical table contains arithmetic defects: 58/68 is 85.3%, not 80%,
   and 54/72 is 75%, not 66%. Its raw artifacts remain unavailable.

## Disposition

Keep as a useful `B70-tested` community recipe. The one-process/one-B70 recipe,
one greedy visible-output match, and one 120K completion/depth row are
validated. The contributor's two-process topology, model-byte identity, a
realistic cold suite, and retrieval evidence remain unverified and are still
required for promotion outside `community/`.
