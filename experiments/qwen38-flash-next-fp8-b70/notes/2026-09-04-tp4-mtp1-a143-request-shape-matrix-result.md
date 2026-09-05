# A143: request-shape matrix on the MTP1 graph identity (2026-09-04, 22:31-22:53)

Packet A120 (certified MTP1 line: full decode graph, sizes [1, 2], three
exact-verify selectors, overlay `1b2a17c1`) at attempt 143 on port 19814,
driven by `tools/probe-q38-request-shape-matrix.py`: two realistic-suite
prompts (`incident-retrospective`, 87 tokens; `architecture-tradeoff`)
through seven request shapes each, 512-token cap, per-chunk arrival
timing, after one 64-token warm-up, then the suite shape repeated at the
end. The question was why the frozen client's completions short bench
reports 27 tok/s for this identity while the realistic suite reports 8.7.

| cell (incident-retrospective / architecture-tradeoff) | ms per stream chunk, first50 / mid50 / last50 | tok/s after TTFT | tokens per chunk |
|---|---|---|---|
| suite shape (chat, seed, top_p, token ids, usage) | 178/175/191 ; 171/140/141 | 9.67 ; 11.31 | 1.78 ; 1.81 |
| chat without token ids | 190/193/169 ; 171/141/118 | 9.70 ; 11.48 | same |
| chat plain (temperature 0 only) | 178/173/163 ; 152/141/141 | 10.12 ; 11.69 | same |
| chat plain without usage | 203/163/161 ; 167/127/130 | n/a | n/a |
| completions raw (seed) | 206/146/177 ; 163/169/137 (ignore_eos row) | 9.61 ; 11.23 | 1.74 ; 1.79 |
| completions + ignore_eos | 222/152/162 | 9.62 | 1.74 |
| completions + token ids | 208/161/172 ; 149/156/122 | 9.57 ; 11.56 | same |
| suite shape repeated at the end | 200/164/170 | 9.90 | 1.78 |

Every request shape steps at 120-220 ms per size-2 verification step on
real prompts, at 100-600 tokens of context, and the chat outputs of one
prompt are identical across the chat cells (one sha256 per prompt per API).
The request path is not the cause. The remaining difference between the
harnesses is the prompt: the short bench (`bench-openai-concurrency.py`,
`repeated_text` prompt) makes the model emit ` benchmark benchmark
benchmark ...`, a degenerate output in which every step routes the same
experts and the drafter is always right. Its rows measure that regime, not
text generation.

Consequences:

- The frozen client's short rows (MTP0 `22.66`, MTP1 `27.15`, MTP2
  `32.2` tok/s) are degenerate-output rows; the realistic suite (MTP0
  14.43, MTP1 8.66 class-balanced) is the speed of the lines on text.
  The "short-context candidate" framing of the MTP1 line is withdrawn.
- The two-row cost is not a depth cost: a size-2 step costs 120-220 ms
  at 200 tokens of context as it does at 2K (A127: 144-255). It is the
  M=2 cost of the MoE block on text (A141/A142), where the expert kernel's
  time scales with the number of distinct experts the rows hit.
- The lever is the MoE kernel at small M for both lines. Queue: A147
  (platform XPU FP8 MoE backend instead of Triton on the MTP0 graph
  identity, exactness and step time), A146/A145 (graph MTP0 step timing
  with and without the expert kernel, `Q38_DIAG_SKIP=moe`, overlay
  `f8c7c0ee`), A144 (graph MTP1 without the expert kernel).

Data: `../data/20260904-tp4-mtp1-a143-request-shape-matrix.json`.
