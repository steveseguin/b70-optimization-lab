# bosd TRX50 Arc Pro B70/B60 field reports

> **Classification: `community-reported`; not independently reproduced.**
> These pages are documentation, not recipes, validated results, or project
> recommendations.

This collection preserves four reports contributed by **bosd** in
[PR #16](https://github.com/steveseguin/b70-optimization-lab/pull/16). The
reported host is an ASRock TRX50 WS with a Threadripper 9960X, two Intel Arc Pro
B70 GPUs, and an Arc Pro B60 used for some comparisons.

## Provenance

- Contributor commits:
  [`4fc422441`](https://github.com/steveseguin/b70-optimization-lab/commit/4fc422441fdaf41dda1681fb69d4364a6930be69)
  and
  [`f56bb4070`](https://github.com/steveseguin/b70-optimization-lab/commit/f56bb4070cdfba23b9057f9908dbd0dabe3ea1b4).
- Contributor source snapshot:
  [`fda0d86c47ff02d8e36f813a8e0121a2152d4478`](https://github.com/bosd/trx50-arc-b70-benchmarks/tree/fda0d86c47ff02d8e36f813a8e0121a2152d4478).
- Reference-lab execution: none.
- Maintainer review: documentation safety, source-link resolution, arithmetic,
  and comparison scope only.

The source snapshot contains narrative summaries and benchmark helpers, but it
does not contain the `raw-mtp1` or `raw-q8q4` run directories referenced by the
helpers. The build-freshness report links the source repository as a whole and
does not identify committed raw logs for its runs. Accordingly, the reported
measurements are preserved but not artifact-checked.

No external helper was imported here. In particular, the source snapshot's
`bench-mtp-1gpu.sh` uses a broad `pkill -9` match for llama processes; it should
not be run on a shared host without first replacing that cleanup with
PID-scoped process management.

## Reports

- [B60 versus B70](b60-vs-b70.md)
- [MTP single-stream observation](mtp-single-stream.md)
- [Q8_0 versus Q4_K_M](q8-vs-q4.md)
- [SYCL build freshness and layer-split regression](sycl-build-and-layer-split.md)

## Maintainer normalization

The contributor's original text remains in Git history. The published field
reports correct the evidence label, recalculate several comparisons, pin the
available source snapshot, distinguish measurements from causal hypotheses,
and narrow conclusions that changed models, quantization, GPU count, runtime,
or backend at the same time.
