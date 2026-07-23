# Laguna shared-down native M=8 BF16 MM counter failure

Date: 2026-07-23 America/Toronto

The down-only native-M8 shared-expert treatment failed its frozen four-card
hardware-counter gate. Exactness held, but the preregistered matched-pair,
per-card timing, and XVE guardrails did not. This result is terminal for this
treatment's endpoint progression: no endpoint service, model generation,
payload, record claim, or LocalMaxxing submission is authorized.

## Sealed evidence

The first and only counter campaign is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-down-m8-counters-20260723T173812Z
```

Its immutable open and complete manifests have SHA-256
`c2ae3b524d010e118df0be0fed17e5c81718dc5376f38db8ca3d3c9ac3ccbb46`
and
`164d124d7d88b9ec4dd3a7f1280feb7ec274538fb9ccc842f62671e951562c12`.
The original parser failed closed because unitrace included five expected
memory-copy summary rows alongside the selected GEMM. We did not rerun the
counters.

The separately authorized parser-only repair analyzed the sealed capture in
the fresh local-NVMe sibling:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-down-m8-counters-20260723T173812Z-analysis-repair-20260723T175756Z
```

Its `analysis.json` SHA-256 is
`01f69094a1d1e130564f05b4c22ef59363d4497866953465eaeea291ea5de074`.
The repair changed only device-timing and kernel-property parsing. It loaded
the frozen original source bytes and reused the original metric parser,
campaign validator, comparisons, and thresholds unchanged. The original
campaign hashes remained intact.

An independent read-only audit rehashed 4/4 card manifests, 16/16 arm
manifests, and 96/96 raw evidence files with zero closure errors. It also
recomputed every comparison and verified all 208/208 stored call-output
hashes.

The execution authorization SHA-256 is
`3b8aa2cf10f27e50ccae778071b8d0b96480dd7c03a852b7199cb0de40928b1a`;
the analysis-repair authorization SHA-256 is
`222bf99a41bdbea6dd9ea812e9c13fd418a4174de513f6d3ef79996072bc2ab6`;
and the frozen protocol SHA-256 is
`670bc61704fded10a08ca0d42d24d8e39534bb5c07f15e7341ce6029cf6c8576`.

## Exactness and aggregate signal

All 16 control/candidate arms produced the same raw output SHA-256:
`250551cd2f3ea4ccf98ee8dc8e42d38215695003fff634d26a57d2ebdf2f7322`.
All control/candidate outputs were bitwise exact. The validity, split,
overrun, lost, inconsistent, spill, SLM, partial-write, and LSC-write failure
proxies were zero.

Across all four cards, candidate mean GEMM time was 11,772.091 ns versus
12,166.227 ns for control, a 394.136 ns or 3.240% reduction. That global
GPU-time-only check passed, but the frozen protocol explicitly forbids a
global mean from overriding any matched-pair or per-card failure.

## Frozen-gate failures

| Rank | BDF | B1/A1 time | B2/A2 time | Aggregate time | Failed aggregate guardrails |
|---:|:---|---:|---:|---:|:---|
| 0 | `0000:23:00.0` | 0.929698 pass | 1.002122 fail | 0.962963 | XVE stall +0.691 pp |
| 1 | `0000:27:00.0` | 1.001366 fail | 1.225220 fail | 1.112879 | time; occupancy -0.565 pp |
| 2 | `0000:43:00.0` | 1.230313 fail | 0.931368 pass | 1.076420 | time; occupancy -2.155 pp |
| 3 | `0000:47:00.0` | 0.773389 pass | 0.634434 pass | 0.696631 | XVE active -1.086 pp; stall +9.406 pp |

Ratios below one favor the candidate. Four of eight matched pairs lost, no
card passed every frozen requirement, and two cards were slower in aggregate.
The candidate therefore fails despite the positive global mean and the earlier
four-card component timing pass.

The result also explains why the endpoint variance wall cannot be handled by
selecting a favorable run: the same candidate spans a 30.3% aggregate win on
one card and 11.3%/7.6% losses on two others under the sealed ABBA capture.
Accepting only the attractive aggregate would violate the preregistration and
amount to sample selection.

## Authorization boundary

The counter gate is evaluated and failed. Counter reexecution under this
authorization, endpoint-preregistration construction, endpoint execution,
model generation, payload creation, promotion, record claims, and
LocalMaxxing submission are all false. The sealed campaign must not be altered
or reused as if it passed.

The durable structured result is
[`data/laguna-s-2.1-shared-down-m8-counter-failure-20260723.json`](../../../data/laguna-s-2.1-shared-down-m8-counter-failure-20260723.json).
The next permissible optimization step is a separately preregistered exact
occupancy treatment. All live evidence remains on local NVMe/ext4; the
external USB remains backup-only.
