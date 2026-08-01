# Laguna S 2.1 INT4 on four Intel Arc Pro B70s

## Qualified result

The current four-B70 record adds exact width-12 Q/K RMSNorm plus RoPE fusion
to the decode-transposed-scale, decode-GRF128, and segmented-DFlash
inline-attention stack:

- current-policy conventional 99-interval median:
  **`124.64241272122038 tok/s`**;
- historical 100-event compatibility formula:
  **`125.9014269911317 tok/s`**;
- 13/13 canonical-q1 token IDs and output-text hashes equal;
- `cached_tokens=0` on all 13 unique cold requests;
- target 146/145 and draft 14/13 on all four ranks; and
- two independent cold suites passed; the supporting conventional result is
  `124.44278011260164 tok/s`; no warmup or retry, clean teardown and post-idle
  gates.

The complete source/patch/run packet is
[the confirmed QKNorm/RoPE note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-qknorm-rope-m12-confirmed-record.md).
LocalMaxxing submission is pending. The preceding approved
`cms9osksu00b3pm010hf9bnk8` row remains the public record until the new
submission is accepted.

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
| vLLM | `58608c6361f1a958a7e933bed0be8c88c35aa26e` |
| XPU kernels | `69e8ad9119a9cc70c3906b82be6254dd0160f00e` |
| hardware | 4x Intel Arc Pro B70 32 GB, TP4+EP4, one active generation |
| verifier / draft | exact width 12 / DFlash depth 11 |
| KV | BF16 |
| treatment | segmented inline DFlash attention, decode-only GRF128, width-12 target decode-transposed BF16 scale tables, and exact M12 Q/K RMSNorm plus RoPE fusion |

The FP8 treatment applies to disposable draft projections. It does not mean
FP8 KV, and no gain is attributed to the intended separate draft LM-head path
because its runtime preparation marker was absent.

## Evidence and reproduction

- [Standalone fail-closed reproduction](../../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md)
- [Source/runtime reconstruction and reproducibility tiers](../../repro/laguna-s-2.1-int4-b70-102tps-20260726/BUILD.md)
- [Current structured record](../../data/laguna-qknorm-rope-m12-confirmed-record-20260731.json)
- [Current confirmed record note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-qknorm-rope-m12-confirmed-record.md)
- [Historical structured record](../../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json)
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
