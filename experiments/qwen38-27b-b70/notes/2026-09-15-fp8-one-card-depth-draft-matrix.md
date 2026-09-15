# One-card FP8: depth and draft-head matrix (broad metrics)

All rows: R309 (`7d3219a0`), one B70, official FP8, compiled whole graph, host
input embedding, `b70_gdn_head_groups` + `b70_fa_verify_rows`, FP16 KV, one user,
prefix cache off, `--gpu-memory-utilization 0.965`, 4,096 batched tokens,
warm-up before timing. Tested September 15, 2026. **Every row is 12/12 identical
to MTP0 (rung 35) on the strict suite, and every row passed the context screen
(512/2,048/12,288-token inputs, 2 repeats, complete 128-token continuations
identical to MTP0).**

| Depth | Draft head | Context | KV tokens | Strict (tokens 1-100) | Strict full answers | Prefill 512 / 2,048 / 12,288 | Decode after 512 / 2,048 / 12,288 |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 0 | - | 20,480 | 43,885 | 19.41 | 19.29 | 1,614 / 2,158 / 2,044 | 19.3 / 19.3 / 18.7 |
| 3 | FP16 (shared target head) | 13,824 | 21,451 | 41.30 | 36.86 | 1,297 / 1,955 / 1,942 | 37.8 / 39.4 / 44.6 |
| 4 | FP16 (shared target head) | 13,824 | 19,440 | 41.22 | 36.95 | 1,261 / 1,932 / 1,933 | 36.9 / 38.4 / 47.1 |
| 5 | FP16 (shared target head) | 13,824 | 17,773 | 42.19 | 35.36 | 1,227 / 1,915 / 1,929 | 35.3 / 40.5 / 51.8 |
| 4 | INT4 67k shortlist | 13,824 | 17,712 | 50.95 | 45.67 | 1,353 / 1,985 / 1,950 | 47.6 / 49.4 / 57.2 |
| 5 | INT4 67k shortlist | 13,824 | 16,193 | 53.40 / 53.40 | 45.18 / 45.30 | 1,340 / 1,979 / 1,947 | 46.2 / 56.1-56.5 / 61.7 |
| 6 | INT4 67k shortlist | 12,544 | 13,900 | 54.82 | 44.76 | 1,331 / 1,970 / 1,945 | 47.6 / 59.0 / 68.3 |

Speeds are tokens/s. Strict (tokens 1-100) is the class-balanced median over
tokens 1-100 of 12 natural prompts. Full answers is the median wall rate over
whole answers up to 512 tokens. Prefill is server prefill. Decode after N is
tokens 1-100 of a forced 128-token continuation.

## Reading

- **No single metric decides the depth.**
  - Depth 6 is fastest early in an answer and after long prompts. It is slightly
    slower over whole answers and costs 1,280 tokens of context.
  - Depth 4 has the best whole-answer rate but trails at long context.
  - Depth 5 is the balanced choice and stays the recommendation.
- **The draft-only INT4 head is worth 20-25% on every decode metric.**
  - FP16 drafting (sharing the target's full head) holds 41-42 tok/s at depths
    3-5.
  - Its advantage is 1,500-5,300 more KV tokens.
  - The INT4 copy only scores draft proposals. Every output token is verified by
    the unchanged FP16 target head, which is why all rows match MTP0.
- **Prefill** is set by the target model. MTP rows are 5-20% slower than MTP0 at
  512 tokens because the draft layer also processes the prompt, and within about
  6% at 2,048-12,288 tokens.

## A draft head with no quantization: FP16 shortlist

[`b70_draft_fp16_shortlist`](../overlays/b70-draft-fp16-shortlist/b70_draft_fp16_shortlist.py)
(launcher `--draft-fp16-shortlist <ids>`) builds the draft head from an exact
FP16 copy of the same 67,248 shortlisted rows of the target head. That costs
0.641 GiB and no INT4 buffers are created. It scores draft positions with the
ordinary FP16 linear kernel.

| Depth 5 draft head | Memory / context | KV tokens | Strict | Full answers | Prefill 512 / 2,048 / 12,288 | Decode after 512 / 2,048 / 12,288 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| FP16 shared full head (rung 43) | 0.965 / 13,824 | 17,773 | 42.19 | 35.36 | 1,227 / 1,915 / 1,929 | 35.3 / 40.5 / 51.8 |
| **FP16 67k shortlist** (rung 52) | 0.975 / 12,544 | 14,388 | 51.86 | 43.24 | 1,317 / 1,965 / 1,944 | 43.5 / 49.7 / 61.6 |
| INT4 67k shortlist (rungs 41/42/50) | 0.965 / 13,824 | 16,193 | 53.40 | 45.16-45.30 | 1,340 / 1,979 / 1,947 | 46.2 / 56.1-56.5 / 61.7 |

- **Result:** the FP16 shortlist is 12/12 strict and passed the context screen.
  It needs 0.975 memory for a 12,544 context; at 0.965 the estimate was 11,648
  (rung 49 refused to start).
- **Against INT4:** 2.9% slower on the strict metric, 4.3% on full answers,
  6-12% on short-prompt decode, and equal after a 12,288-token prompt.

## Chat-mode quality suite (a different workload)

[`qwen38-text-quality-suite.py`](../../../scripts/qwen38-text-quality-suite.py)
goes through `/v1/chat/completions` with thinking off. It covers:

- 7 exact-answer, arithmetic, logic, code and JSON cases
- a repeat-hash case
- a long-context needle (7,617 prompt tokens)

It ran with exact normalised-output and hash parity required against MTP0
(rung 51):

- MTP0: all pass.
- Depth 5 + FP16 shortlist (rung 52): all pass, baseline match all.
- Depth 5 + INT4 shortlist (rung 53): all pass, baseline match all.

Evidence: `/mnt/fast-ai/bench-results/optimization-validation-20260915/fp8-tp1-4[1-9]*`,
`fp8-tp1-5[0-3]*`
and [copied receipts](../data/2026-09-15-fp8-one-card-depth-draft-matrix/).
Summary tool: [`summarize-fp8-tp1-rungs.py`](../scripts/summarize-fp8-tp1-rungs.py).
