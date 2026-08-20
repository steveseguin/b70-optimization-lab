# bosd TRX50 Arc Pro B70/B60 field reports

> **Classification: `community-reported` unless a maintainer note says
> otherwise.** These pages are documentation, not recipes or project
> recommendations. One configuration now has a scoped reference-lab
> reproduction; it remains in this contributor collection.

This collection preserves nine report pages contributed by **bosd** in
[PR #16](https://github.com/steveseguin/b70-optimization-lab/pull/16), with two
follow-up measurements supplied in
[PR #17](https://github.com/steveseguin/b70-optimization-lab/pull/17), and four
later reports supplied in
[PR #30](https://github.com/steveseguin/b70-optimization-lab/pull/30),
[PR #31](https://github.com/steveseguin/b70-optimization-lab/pull/31),
[PR #33](https://github.com/steveseguin/b70-optimization-lab/pull/33),
[PR #32](https://github.com/steveseguin/b70-optimization-lab/pull/32), and
[PR #36](https://github.com/steveseguin/b70-optimization-lab/pull/36). The
reported host is an ASRock TRX50 WS with a Threadripper 9960X, two Intel Arc Pro
B70 GPUs, and an Arc Pro B60 used for some comparisons.

## Provenance

- Contributor commits:
  [`4fc422441`](https://github.com/steveseguin/b70-optimization-lab/commit/4fc422441fdaf41dda1681fb69d4364a6930be69)
  and
  [`f56bb4070`](https://github.com/steveseguin/b70-optimization-lab/commit/f56bb4070cdfba23b9057f9908dbd0dabe3ea1b4)
  from PR #16, and
  [`a1bb15c23`](https://github.com/steveseguin/b70-optimization-lab/commit/a1bb15c23018b17504f57f2e4d1bff0ad984cd0c)
  from PR #17;
  [`ff19b3567`](https://github.com/steveseguin/b70-optimization-lab/commit/ff19b3567b10ee9dc682423793724ea67b416883),
  [`96da1fe90`](https://github.com/steveseguin/b70-optimization-lab/commit/96da1fe90f7a49918e461d7165c8625a5bdc8a3b),
  [`a7a6b3eae`](https://github.com/steveseguin/b70-optimization-lab/commit/a7a6b3eae72ca49ff510e453208091fbfe34b490),
  and
  [`ba0629aa4`](https://github.com/steveseguin/b70-optimization-lab/commit/ba0629aa43a3a7aed82a1d7f41c69b2f58a18852),
  and
  [`a34d60243`](https://github.com/steveseguin/b70-optimization-lab/commit/a34d6024326bc4cd2917a0ec7fa4a99267d8157e)
  from PRs #30, #31, #33, #32, and #36 respectively.
- Contributor source snapshot:
  [`fda0d86c47ff02d8e36f813a8e0121a2152d4478`](https://github.com/bosd/trx50-arc-b70-benchmarks/tree/fda0d86c47ff02d8e36f813a8e0121a2152d4478).
- Reference-lab execution: the PR #33 TP2/MTP configuration was independently
  exercised on 2026-08-17; see the
  [maintainer audit](maintainer-audit-2026-08-17.md). The other new performance
  claims were not independently benchmarked.
- Maintainer review: documentation safety, source-link resolution, arithmetic,
  comparison scope, source inspection, and the scoped PR #33 reproduction.

The source snapshot contains narrative summaries and benchmark helpers, but it
does not contain the `raw-mtp1` or `raw-q8q4` run directories referenced by the
helpers. The build-freshness report links the source repository as a whole and
does not identify committed raw logs for its runs. The mixed B60+B70 result has
a narrative table in the pinned snapshot but no raw output. The batched-decode
addition was supplied only as prose and a table in PR #17 and is not in that
snapshot. Accordingly, the reported measurements are preserved but not
artifact-checked.

No external helper was imported here. In particular, the source snapshot's
`bench-mtp-1gpu.sh` uses a broad `pkill -9` match for llama processes; it should
not be run on a shared host without first replacing that cleanup with
PID-scoped process management.

## Reports

- [B60 versus B70](b60-vs-b70.md)
- [MTP single-stream observation](mtp-single-stream.md)
- [Q8_0 versus Q4_K_M](q8-vs-q4.md)
- [SYCL build freshness and layer-split regression](sycl-build-and-layer-split.md)
- [Single-B70 synthetic batched-decode throughput](batched-decode-throughput.md)
- [MTP backend comparison](mtp-vllm-xpu-flip.md)
- [Qwen3.8-27B MTP on Intel vLLM-XPU](qwen38-27b-mtp.md)
- [Dual-B70 TP2 plus MTP reproduction](tp2-mtp-reproduction.md)
- [vLLM-XPU MoE quantization observations](vllm-xpu-moe-quant-wall.md)
- [Qwen3.6-27B DFlash single-B70 report](dflash-qwen36-27b.md)
- [Maintainer audit of PRs #30–#33](maintainer-audit-2026-08-17.md)

## Maintainer normalization

The contributor's original text remains in Git history. The published field
reports correct the evidence label, recalculate several comparisons, pin the
available source snapshot, distinguish measurements from causal hypotheses,
interpret `llama-batched-bench` as a synthetic parallel-sequence workload rather
than server request throughput, and narrow conclusions that changed models,
quantization, GPU count, runtime, or backend at the same time.
