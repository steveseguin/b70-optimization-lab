# A182: fixed realistic suite on the VRAM-headroom MTP0 line (2026-09-05, 18:13-18:33)

Packet A179's identity (promoted deterministic full-decode-graph MTP0 line, overlay
`08df70ea`, plus UVA host offload of `embed_tokens.weight` and the routed experts
matched by `mlp.experts` under a 13.4 GiB budget: every rank reports 13.78 GiB
offloaded = embedding, layer-0 experts, PLE, layer-1 experts, layer-2 `w13_weight`)
at attempt 182, launched through the frozen ritual with the realistic-suite driver.
`scripts/bench-openai-realistic-suite.py` with `--api-mode chat --max-tokens 512
--metric-tokens 100`, the fixed `realistic-suite-v1.json` (12 prompts, sha
`0ad543d1…`), `enable_thinking=false`, temperature 0, seed 20260609, each prompt
once, cold. Same flags, suite and seed as the approved A134 run.

| field | A134 (approved, PLE-only placement) | A182 (headroom placement) |
|---|---|---|
| realistic final gate / cached tokens all zero / fresh response valid | passed / true / true | passed / true / true |
| class-balanced median of prompt-class medians (99 intervals after TTFT) | 14.433684 tok/s | **25.273193 tok/s** |
| all-prompt median / p10 | 14.757123 / 14.015291 | 25.544318 / 25.482566 |
| full after-TTFT median / wall median | 16.058 / 15.046 | 25.320 / 24.502 |
| TTFT median | 1.856 s | 0.592 s |
| rows | 12 of 12 | 12 of 12 |
| output sha256 of every row | authority | identical to A134 |

Class medians: analysis 25.30, code 25.28, documentation 25.33, operations 25.27, prose 25.26, structured-writing 25.23.

Why it is faster without changing a byte of output: the promoted placement fills the
B70 to 31.75 GiB of 31.89 per rank and the xe driver pages whole expert buffers over
PCIe on every cold touch (see the day summary and the offline cliff at 48 weight
sets). Offloading 1.56 GiB of expert weights to pinned host memory through the same
UVA path the PLE already uses ends the paging; the Triton MoE kernels read the same
bytes, so the ids match token for token (exact-2K `afffd211…` on A179, A180 r1/r2;
the twelve suite outputs here).

Data: `../data/20260905-tp4-mtp0-a182-realistic-suite-v1-result.json`,
`../data/20260905-tp4-mtp0-a182-identity.txt`. Certification battery: A183 (frozen
client, quality suite, short r1-r3, exact 2K/4K pairs). Attestation and LocalMaxxing
payload follow A183.
