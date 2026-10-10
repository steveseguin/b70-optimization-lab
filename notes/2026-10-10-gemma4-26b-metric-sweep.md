# Gemma 4 26B A4B Q8 metric sweep on one B70, 2026-10-10

Owner ask: the Qwen packages publish draft-depth, card-count, prompt-reading and context-length curves; Gemma only had the
shapes the LAN service needed. This sweep fills the same matrix for Gemma on one card.

## How

- `tools/gemma4-26b-sweep.py run --gpu 1 --port 19361` (summary: `... summarize DIR`). Twelve server configurations, each
  in its own transient user unit on card 1, launched through the production launcher
  (`/home/steve/llm-optimizations/scripts/serve-gemma4-26b-q8-production.sh`, profile `service`, compat build c926,
  deterministic oneDNN, 16-bit KV). Measurements are llama.cpp's own `timings` counters (prompt_ms, predicted_ms, draft_n,
  draft_n_accepted); every measured request has prompt caching off; temperature 0; 256-token answers.
- Single user: 1 slot x 16K, draft length 0..5, prompts of ~300 / 512 / 2K / 8K / 16K filler tokens (3 runs at the short
  lengths, 2 at 8K/16K), plus the same 3K question three times for repeat identity.
- Many users: 8 slots x 4K (draft 0/1/3; 1, 2, 4, 8 people) and 4 slots x 16K (draft 0/1/3; 1, 2, 4 people, plus 4 people
  with 8K prompts). Each person sends a different 2K prompt at the same moment.
- Results: `data/profiles/2026-10-10/gemma-sweep/<label>.json` (+ `.server.log`). Folded into the package by
  `tools/gemma4-26b-sweep-to-package.py ... --write` (performance_profiles with ids `sweep-*`), which the model page renders.
- The service kept running on card 0 (`throughput-card0` recipe, new) during the sweep.

## One user, 1 slot x 16K (tok/s)

| draft length | decode after 300 / 2K / 8K / 16K | prefill 300 / 2K / 8K / 16K | draft acceptance | repeats |
| ---: | --- | --- | ---: | --- |
| 0 (none) | 77.8 / 62.9 / 57.6 / 56.2 | 938 / 2,076 / 1,717 / 1,503 | - | identical |
| 1 | 113.3 / 96.1 / 89.4 / 86.0 | 934 / 2,059 / 1,703 / 1,492 | 81% | identical |
| 2 | 118.6 / 108.5 / 93.2 / 91.0 | 936 / 2,058 / 1,702 / 1,492 | 71% | identical |
| **3** | **122.3 / 109.6 / 91.8 / 92.0** | 935 / 2,068 / 1,701 / 1,491 | 61% | identical |
| 4 | 114.6 / 108.3 / 95.6 / 88.4 | 935 / 2,065 / 1,700 / 1,490 | 54% | identical |
| 5 | 112.5 / 104.5 / 85.7 / 83.4 | 936 / 2,059 / 1,701 / 1,491 | 46% | identical |

Wait for the first token, no draft: 0.31 s at 300, 0.97 s at 2K, 4.8 s at 8K, 10.5 s at 16K tokens. Card memory 27.3 GB
(no draft) / 27.9 GB (with the Q4_0 MTP draft).

## Many users (per person, total in brackets, tok/s; 2K prompts)

| shape | draft | 1 | 2 | 4 | 8 | 4 people x 8K prompts |
| --- | ---: | --- | --- | --- | --- | --- |
| 8 slots x 4K | 0 | 65.9 (66) | 49.1 (98) | 32.1 (129) | 19.9 (160) | - |
| 8 slots x 4K | 1 | 95.7 (96) | 69.2 (139) | 41.7 (166) | 13.7 (106) | - |
| 8 slots x 4K | 3 | 119.9 (120) | 72.9 (146) | 24.8 (97) | 16.3 (130) | - |
| 4 slots x 16K | 0 | 65.7 (66) | 49.0 (98) | 34.0 (136) | - | 17.6 (79) |
| 4 slots x 16K | 1 | 95.8 (96) | 69.1 (138) | 42.0 (169) | - | 19.6 (94) |
| 4 slots x 16K | 3 | 118.5 (119) | 73.3 (147) | 23.5 (97) | - | 13.8 (62) |

(The 1-person column here is after a 2K prompt, so it is lower than the 300-token figures above.)

## What it says

- Draft 3 is the right single-user setting (the `single` recipe): 122 tok/s short, 110 after 2K, 92 at 8K-16K. Draft 2 is
  within noise of it; 4 and 5 lose acceptance faster than they gain tokens per step.
- With no draft, decode falls from 78 to 56 tok/s between a 300-token and a 16K-token prompt (attention cost over the
  context); with draft 3 the drop is 122 to 92.
- Drafting helps up to 4 people per card (draft 1: 166-169 total) and hurts at 8 (the fast MoE kernels take at most
  8 tokens per step; see the 2026-10-09 note). At 8 people no draft is best (160 total), which is the `throughput` recipe.
  The `balanced` recipe (4 x 16K, draft 1) is confirmed as the best 4-person shape.
- Reading speed peaks around 2K tokens (about 2,000-2,100 tok/s) and settles at 1,500-1,700 tok/s for 8K-16K prompts.
  It is the same with or without the draft.
- Every configuration repeated the same long question identically three times (deterministic oneDNN switch on).
- Two cards: the service runs one replica per card, so totals add (the 2026-10-09 note measured 1,230-1,313 tok/s total
  for 16 workers across both cards with the `throughput` recipe). A two-card layer split of one replica was not run; the
  model fits one card, so splitting it would only add transfer cost.

## The trap that cost an hour

The compat build's fast paths are switched on by about twenty environment variables (`LLAMA_GEMMA4_*`,
`LLAMA_SYCL_MUL_MAT_ID_*`, `LLAMA_MTP_*`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS`, ...) that only the production launcher sets.
The first attempt ran the bare binary and measured 43 tok/s instead of 78 on both cards; those runs are kept as
`*.noenv-card0.json` for reference. Any Gemma measurement must go through the launcher, as the sweep tool now does.
