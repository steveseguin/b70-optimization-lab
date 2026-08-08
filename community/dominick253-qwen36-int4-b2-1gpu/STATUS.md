# STATUS — Qwen3.6 27B/35B INT4 vLLM B2 TP1

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | read; artifacts checked offline; no model/container execution |
| Tested in reference lab | no |
| Safe to merge as documentation | yes, after maintainer corrections |
| Eligible for `repro/` or `results/` | no |

## Provenance

- Contributor: `dominick253`.
- Source: [PR #18](https://github.com/steveseguin/b70-optimization-lab/pull/18).
- Contributor head: `1604d0b1d444f47c58c1abedd88d879908425b21`.
- Right-to-submit statement: present in the PR.
- The original launcher, benchmark scripts, raw JSON/CSV, and contributor
  interpretation are preserved under [`reported/`](reported/).

## Contributor claim

The contributor reports successful TP1 online `sym_int4` serving for Qwen3.6
27B and a quality failure for Qwen3.6 35B-A3B under one Intel B2 container
image. The contributor also reported large deep-context MTP slowdowns.

## Contributor environment

| Field | Value |
| --- | --- |
| GPU | 2x Intel Arc Pro B70, one independent TP1 service per card |
| OS / kernel | Ubuntu 26.04 / `7.0.0-29-generic` |
| Image | reported tag `intel/llm-scaler-vllm:0.21.0-b2`; digest not recorded |
| Models | `Qwen/Qwen3.6-27B` and `Qwen/Qwen3.6-35B-A3B`; revisions not recorded |
| Precision | online `sym_int4`, FP16 compute, FP8 E4M3 KV |
| Benchmark | llama-benchy `0.4.1.dev1+ge9be34457`, depth sweeps at concurrency 1 |

## What was run in the reference lab

No model, container, GPU, service, or endpoint test was run. Maintainer review
parsed all JSON and scripts, recomputed the stored means, inspected the command
surface, and dry-ran the hardened launcher. See
[`validation/2026-08-08-offline-review.md`](validation/2026-08-08-offline-review.md).

## Findings

1. The stored benchmark JSON is parseable and its displayed means match its raw
   values.
2. The claimed MTP “only change” A/B is not controlled. MTP-on artifacts use
   1,024 output tokens and five measured runs; MTP-off artifacts use 512 output
   tokens and three runs on a later date. The ratios remain contributor
   observations, not a causal A/B or production policy.
3. The contributor's 35B benchmark wrapper looked for JSON key `results`, while
   the actual tool output uses `benchmarks`; the wrapper would fail during CSV
   conversion. A corrected generic wrapper is under [`tools/`](tools/).
4. The submitted CSV files used CRLF endings and failed repository
   `git diff --check`; they remain preserved under `reported/` with their
   provenance and are excluded from the clean runnable surface.

## Known issues

- Exact image digest and model revisions are missing.
- The reported launcher is privileged, host-networked, persistent, destructive
  to a same-named container, and includes `--trust-remote-code`.
- The hardened launcher requires an explicit digest-pinned image and is not a
  reproduction of the contributor's measured identity until that digest and
  model revision are supplied.
- The 35B INT4 `!!!!` output report is a valuable negative observation but is
  not independently reproduced here.

## Disposition

Keep as `community-reported`. Do not use the submitted MTP comparison as a
shipping rule and do not submit it to LocalMaxxing. A matched same-output,
same-repeat, alternating MTP A/B plus strict quality gate is required before
performance interpretation or promotion.
