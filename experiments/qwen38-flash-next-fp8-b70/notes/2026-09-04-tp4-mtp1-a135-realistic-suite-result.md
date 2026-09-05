# A135: fixed realistic suite on the certified MTP1 line (2026-09-04, 11:05-11:20), withheld

Packet A120 (the certified MTP1 client pair's first server: full decode
graph, sizes [1, 2], three exact-verify selectors, overlay `1b2a17c1`) at
attempt 135 on port 19806, the same realistic-suite driver as A134 (chat
mode, 512-token cap, 100-token metric window, `enable_thinking=false`,
temperature 0, seed 20260609, each of the 12 prompts once, cold).

| field | A135 (MTP1) | A134 (MTP0, approved) |
|---|---|---|
| realistic final gate / cached tokens all zero / fresh response valid | passed / true / true | same |
| outputs (12 response sha256) | **identical to A134, 12/12** | authority |
| class-balanced median of prompt-class medians (99 intervals after TTFT) | 8.659225 tok/s | 14.433684 |
| all-prompt median / p10 | 8.782788 / 8.146481 | 14.757123 / 14.015291 |
| full after-TTFT median / wall median | 10.239 / 9.612 | 16.058 / 15.046 |
| TTFT median | 2.870 s | 1.856 s |
| stream chunks per 512-token response | 282-307 (1.75-1.82 tokens per chunk) | 504-512 |

MTP1 changes none of the 12 realistic answers either, so the lossless
claim now covers the frozen client (A120/A121), the graph battery (A113)
and this suite. It was **withheld** from LocalMaxxing: 0.60x the approved
MTP0 line on the suite metric, which would only lower our own record.

The suite rows contradict the frozen client's short rows (MTP1 27.15 tok/s
against MTP0 22.66 at p146/o256): here each size-2 verification step
takes 145-206 ms of wall time per stream chunk from the first tokens on
(context 100-600 tokens), against about 66 ms per step implied by the
completions short bench, and the MTP0 rows also run 51-67 ms per token
against 44 ms in the short bench. The two harnesses differ in request
shape (chat template versus raw completions, `return_token_ids`,
`top_p`, `ignore_eos`, real prompts versus synthetic tokens), so the next
diagnostic is a request-shape matrix on the same server (A143,
`tools/probe-q38-request-shape-matrix.py`). Data:
`../data/20260904-tp4-mtp1-a135-realistic-suite-v1-result.json`,
`../data/20260904-tp4-mtp1-a135-identity.txt`.
