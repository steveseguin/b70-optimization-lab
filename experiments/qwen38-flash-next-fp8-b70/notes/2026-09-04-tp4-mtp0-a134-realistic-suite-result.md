# A134: fixed realistic suite on the promoted MTP0 deterministic line (2026-09-04, 10:35-10:58)

Packet A78 (the promotion pair's second server) at attempt 134, overlay
checked out at `2169dbfe`, launched through the frozen ritual with a
realistic-suite driver instead of the frozen client (the client's rows are
not the LocalMaxxing metric). `scripts/bench-openai-realistic-suite.py`
with `--api-mode chat --max-tokens 512 --metric-tokens 100`, the fixed
`realistic-suite-v1.json` (12 prompts), `enable_thinking=false`,
temperature 0, seed 20260609, each prompt once, cold.

| field | value |
|---|---|
| realistic final gate / cached tokens all zero / fresh response valid | passed / true / true |
| class-balanced median of prompt-class medians (99 intervals after TTFT) | **14.433684 tok/s** |
| all-prompt median / p10 | 14.757123 / 14.015291 tok/s |
| full after-TTFT median / wall median | 16.058 / 15.046 tok/s |
| TTFT median | 1.856 s |
| rows | 12 of 12 |

LocalMaxxing submission `cmtn32b2w000tmm01t7j2wlpn`, approved (HTTP 201).
Attestation `../data/20260904-tp4-mtp0-a134-promotion-attestation.json`
binds the suite JSON to the A78 and A73 summaries (quality 6/7 with the
inherited miss, 16/16 repeat, exact needle, outputs identical across five
servers). Data: `../data/20260904-tp4-mtp0-a134-realistic-suite-v1-result.json`,
`../data/20260904-tp4-mtp0-a134-identity.txt`,
`../data/20260904-tp4-mtp0-a134-localmaxxing-payload-queue.json`.
