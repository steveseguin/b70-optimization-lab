# Q8 reordered pair-slot top8 negative

Date: 2026-06-28

Model/lane: Gemma 4 26B A4B IT, UD-Q8_K_XL target, Q4_0 MTP draft,
single B70, strict fresh-response realistic gate.

## Idea

Reuse the already-existing default-off pair-slot reordered Q8_0 MoE kernel for
Gemma's active verifier shape. The earlier pair-slot experiment only guarded
`ids->ne[0] == 2`, while the current Gemma verifier path uses `ids->ne[0] == 8`
with `ne11 == 1`. The tested patch changed the pair-slot lane to launch four
slot-pair groups per token:

- group 1 = `slot_pair`;
- `slot0 = 2 * slot_pair`;
- `slot1 = slot0 + 1`;
- destination offsets use `slot0/slot1 * dst_row_stride`;
- dispatch and graph eligibility require `n_experts_used == 8` /
  `ids->ne[0] == 8`;
- runtime flag: `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_PAIR_SLOTS=1`.

This was meant to reuse each quantized activation row across two experts
without the register pressure of the failed top8-slots kernel.

## Validation

Strict 128-token screen, four B70 lanes, current record recipe plus only:

```bash
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_PAIR_SLOTS=1
```

All lanes passed the chat canary and the strict realistic gate. All requests
were fresh-response benchmark rows; no headline or LocalMaxxing submission was
made because this did not beat the current strict full512 record.

| Lane | Summary | Median 1-100 | p10 | Mean | Full128 | Wall full128 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | `data/gemma4-q8-gpu0-strict-vdr2-pairslots8-n3-nmin2-p00475-ub1024-128-20260628T061048Z/summary.json` | `93.1952` | `86.9614` | `95.3774` | `95.1727` | `83.8521` | `179.114` |
| GPU1 | `data/gemma4-q8-gpu1-strict-vdr2-pairslots8-n3-nmin2-p00475-ub1024-128-20260628T061048Z/summary.json` | `98.2092` | `87.3417` | `96.1726` | `94.4179` | `82.8335` | `180.352` |
| GPU2 | `data/gemma4-q8-gpu2-strict-vdr2-pairslots8-n3-nmin2-p00475-ub1024-128-20260628T061048Z/summary.json` | `94.0377` | `88.4810` | `95.2924` | `91.9985` | `81.5866` | `179.329` |
| GPU3 | `data/gemma4-q8-gpu3-strict-vdr2-pairslots8-n3-nmin2-p00475-ub1024-128-20260628T061048Z/summary.json` | `98.1450` | `86.8008` | `98.2177` | `97.4697` | `85.0364` | `179.359` |

## Decision

Negative. Correctness held, but throughput stayed in normal record-lane
variance and did not crack reliable `>100`. Do not promote and do not spend
full512 budget on this lane unless paired with a new independent MoE reduction.
The active source edits were reverted after recording this result.
