# IQ3_XXS block full-engine result — October 24, 09:32 UTC

The new full-engine qualification passes all26 requests and all24 measured arms
against the original SC117 baseline. Every output token and logical target-state
byte hash matches, including target/MTP equality on all12 prompt pairs. Independent
closed readback verifies54 bundles,56,916 ranges and5,987,065,536 target-state bytes.
The946 retained artifacts total6,343,854,808 bytes. Both ranks had positive physical
GPU contact, exited safely and released their devices; fault baseline and protected
vision owner are unchanged. The coordinator completed in452.745962 seconds.

| Resident decode measure | Target-only | MTP |
| --- | ---: | ---: |
| Interval-weighted tokens/s | 15.732355 | 23.303290 |
| Output tokens / measured intervals | 1536 / 1524 | 1536 / 1524 |
| Total interval time, ms | 96,870.433 | 65,398.490 |
| Target-first group, tokens/s | 15.716557 | 23.230029 |
| MTP-first group, tokens/s | 15.748184 | 23.377016 |
| Prompt-boundary time sum, ms | 26,713.800 | 28,084.191 |

Within this run, MTP delivers48.123% more decode tokens/s. All1,160 accepted and
364 rejected guesses match previous exact runs. Prompt-boundary times include the
first output token and are not isolated prefill-kernel throughput. All cases and
both balanced order groups are retained; two disjoint eight-output warmups are
excluded. Each request starts from full RESET with no prompt/KV reuse.

The candidate adds blockwise IQ3_XXS decoding at exactly34 gate/up sites, preserving
all512 experts per bank, dynamic ten-slot gathered inputs, lane accumulation order,
SG32 reduction and BF16 outputs. It retains the qualified attention/Q6 changes and
lossless bundle writer. Actual device allocations remain30,947,490,698 and
29,824,495,508 bytes. No target weights, quantization, KV precision, context limit,
draft vocabulary or target verification were changed.

This is a separate full-engine qualification. The [earlier micro](../../micro/RESULT.md)
remains physically incomplete; this run does not retroactively attest its device
or promote its isolated timings. The previous combined engine's14.85/22.13 rates
are a separate-session descriptive comparison, not a matched causal estimate.
Retain this exact candidate internally and investigate the next measured bottleneck.
This cap128 short-prompt screen is not a public512 gate, cold-start measurement,
independent full-model oracle or broad quality certification. See the
[publication coverage appraisal](../PUBLICATION-GAPS.md).

## Reproduction identity and durable evidence

- Model: SC117 IQ3_S revision`eec4e10a2c29b440a2ae85591fa11569ce752963`, original
  two verified shards; official local FP8/BF16 draft, full248,320-token head.
- Run: `gsq-iq3xxs-block-engine-a`, split24/24, draft_rank0, context4096,
  fullBF16KV, original12-prompt balanced schedule and cap128.
- [Admission plan](evidence/device-a/plan.json):
  `61e2e15a3577ae2d972f922cea8ff4a7e8f22567cf3354f761d4fa94b786359d`.
- [Native receipt](../evidence/native-build.json):
  `ecf34ebc193c59bc8ac4fecfe61bab0b305dc1b56454212d0187acef908613ee`;
  binary`97348925367e1ad67313cf9863d0c4cba47abea871c386972983965e036ea4b2`.
- [Independent actual review](evidence/device-a/review.json):
  `4e97f8a533de01c64d299582e8cdb884bb1979f7e2a405bd5794f36f4869294b`;
  [artifact index](evidence/device-a/artifact-index.jsonl.gz)
  `89ae281f5fc9747463ad8eb7d8037fddde57e98d1739603f18bcc42226c932b3`.
- Full result SHA256:
  `d3e5c9337c77b744668f999c84edb8e8397ee035884dc1c305f12579bffc31f4`.
  Raw/control roots are `/mnt/usb-models/own-xpu-runtime-results/gsq-iq3xxs-block-engine-a`
  and `/home/steve/own-xpu-runtime-results/gsq-iq3xxs-block-engine-a.control`.

All54 closed bundle payloads are now [losslessly archived](../../../storage/expert-block-closed/RESULT.md),
with complete readback before removal. All JSON, indices, seals and draft evidence
remain in place. Restore the needed original bundle from its verified archive for
later raw readback or fixture extraction. No model file was removed.
