# Inkling-2-Mini: the full 1M context on two cards (plan, 2026-11-26, needs the owner's OK)

## Why

One card now holds 530K positions (needle passed, prompt 351.6 tok/s) and the one-card engine is near its floors:
prompts are power-bound with exact arithmetic (attention multiply-adds ~79 % of the FP32 peak, experts at ~24 pJ per
exact multiply-add), writing after long prompts reads keys and values at 518-533 GB/s. The model's trained context is
1,048,576 (`inkling2.context_length`). Its keys and values need 32 KB per position (8 full-attention applications x
K and V x 8 heads x 128 x 2 bytes), so 1M = 32 GiB: more than one card, whatever else we cut.

## Shape: the 48 applications split between two cards

- The model: 24 physical layers applied 48 times: prelude 0-5, core 6-17 applied 3 times (applications 6-41), coda
  18-23 (applications 42-47). Full attention at applications 5, 11, 17, 23, 29, 35, 41, 47; each application has its
  own key/value cache. Attention residuals mix the outputs of earlier 6-layer blocks; the core passes read the
  previous pass's bank.
- Card A runs applications 0-23, card B 24-47. Each holds 4 full-attention caches: 16 KB per position, 1M = 16 GiB.
  Weights: A needs prelude + core (18 of 24 physical layers), B core + coda (18 of 24): ~75 % of the 12.2 GB each,
  so ~9-10 GB + 16 GiB + step buffers: about the card's 31.9 GiB. Step size and score rows from free memory, as now.
- Each application's arithmetic is unchanged, so every logit is bit-identical to one card (the gate's baselines
  apply as they are). Short-conv states and window caches stay on the card that owns the application.
- Hand-over at application 24, per step: the current row block plus the block outputs and loop state that
  applications 24-47 read (a few arrays of tokens x 2,304 floats). Through ordinary host memory (no pinned memory,
  no card-to-card reads: those were this host's reset trigger in the DeepSeek lane): ~0.3 GB per 4,096-token step
  (~1-2 % of a step at 100K), ~70 KB per written token (tens of microseconds).
- Prompts: steps flow A -> B, so A reads step s + 1 while B reads step s: up to ~2x on long prompts. Writing: one
  token passes both cards in turn, about one card's speed; the drafter runs where the last application runs.

## Steps

1. Engine: a range of applications per Engine (weights uploaded only for the physical layers it needs), the hand-over
   arrays in and out, and the model id / saved-prompt format extended with the range. One card first: two Engines
   on one card (one context) give the same logits as one Engine (gate).
2. Two cards (owner's OK): gate on cards 1+2 against the one-card baselines, then 700K and 1M needles, prompt speed.
3. Server: the LAN server with two cards (owner's call).

## Risks

- This host reset under card-to-card reads during six-card DeepSeek runs (Nov 10-17). The plan uses host-staged copies
  only and two cards; the DeepSeek stable-mode settings (Gen4, SMT off) stay as they are.
- Host RAM 15 GB: two engine processes or one process with two cards both stage weights; load them one after the
  other.
