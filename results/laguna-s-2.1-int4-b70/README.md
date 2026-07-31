# Laguna S 2.1 INT4 on four Intel Arc Pro B70s

## Qualified result

The current four-B70 record is the confirmed exact decode-GRF128 treatment on
the segmented-DFlash inline-attention stack:

- current-policy conventional 99-interval median:
  **`121.29056097255466 tok/s`**;
- historical 100-event compatibility formula:
  **`122.51571815409562 tok/s`**;
- 13/13 canonical-q1 token IDs and output-text hashes equal;
- `cached_tokens=0` on all 13 unique cold requests;
- target 146/145 and draft 20/19 on all four ranks; and
- two independent cold suites passed; the supporting conventional result is
  `120.0863279502934 tok/s`; no warmup or retry, clean teardown and post-idle
  gates.

The complete source/patch/run packet is
[the confirmed GRF128 note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-decode-grf128-confirmed-record.md).
LocalMaxxing submission is pending. The preceding approved row is
[`cms8f38fd00ftpf01mk0bwfql`](https://www.localmaxxing.com/en/runs/cms8f38fd00ftpf01mk0bwfql).

### Superseded 2026-07-26 result

The sealed width-12 / DFlash-depth-11 run is exact and approved by
LocalMaxxing:

- submitted historical benchmark convention: `102.97143559613157 tok/s`;
- conventional 99-inter-token-interval rate from the same timestamps:
  `101.94172124017027 tok/s`;
- 13/13 canonical-q1 token IDs and output-text SHA-256 equal;
- `cached_tokens=0` on all 13 unique cold requests;
- four ranks each captured and replayed the exact 146/145 Breakable PIECEWISE
  topology;
- LocalMaxxing
  [`cms2ccv2d00lps201rej94pjy`](https://www.localmaxxing.com/en/runs/cms2ccv2d00lps201rej94pjy),
  `APPROVED`.

The historical helper counted 100 timestamped token events over a span
containing 99 intervals. The approved row is preserved as the receipt of what
was submitted; it must be described as the published legacy convention. Under
conventional interval accounting, the 102 tok/s threshold was missed by
`0.05827875982973 tok/s`.

## Identity

| field | value |
| --- | --- |
| target | `poolside/Laguna-S-2.1-INT4` at `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb` |
| draft | `poolside/Laguna-S-2.1-DFlash-INT4` at `5e07c246915c86dc6920fead03d019989224f2ba` |
| vLLM | `e596ef1543466ae1a05e5bb8091f58872e2b18ba` |
| XPU kernels | `6f9dd3c3a7b1b677a992ca4f431a968408f9c816` |
| hardware | 4x Intel Arc Pro B70 32 GB, TP4+EP4, one active generation |
| verifier / draft | exact width 12 / DFlash depth 11 |
| KV | BF16 |
| treatment | 31 E4M3FN W8A16 draft projections per rank plus the exact auxiliary workspace |

The FP8 treatment applies to disposable draft projections. It does not mean
FP8 KV, and no gain is attributed to the intended separate draft LM-head path
because its runtime preparation marker was absent.

## Evidence and reproduction

- [Standalone fail-closed reproduction](../../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md)
- [Source/runtime reconstruction and reproducibility tiers](../../repro/laguna-s-2.1-int4-b70-102tps-20260726/BUILD.md)
- [Structured record](../../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json)
- [Metric correction](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md)
- [Original experiment note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-width12-dflash-fp8-w8a16-record.md)
- [Source snapshots](../../patches/laguna-s-2.1-xpu-b70/README.md)
- [Campaign learning ledger](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-campaign-transfer-ledger.md)
- [KV precision decision](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-kv-cache-precision-decision.md)
- [LocalMaxxing ledger](../localmaxxing-submissions.md)

The immutable queue and HTTP 201/public-verification receipt remain under
`data/`. The submission is already approved; do not POST a duplicate.

The standalone packet now includes the sealed raw run, a release-only 32-file
model manifest and download-at-revision helper, complete observed package and
host identity, three kernel-source provenance points in addition to the final
kernel tree, and checks for every direct and transitively loaded native
library. Artifact-exact replay and source-equivalent rebuild are deliberately
separate claims; rebuilt binaries require the full gate and are not silently
substituted into the sealed environment.
