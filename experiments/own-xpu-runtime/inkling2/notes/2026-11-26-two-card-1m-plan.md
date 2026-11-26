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

## Step 1 done (2026-11-26, one card)

`Engine(..., app_lo, app_hi)` runs applications app_lo .. app_hi - 1 with only their physical layers' weights
(`Engine::unused_tensor`: the other layers' tensors stay off the card, but every layer's mix query rows, which the
saved mix scores cover); the second engine replays the first's block bookkeeping (`carry_slots`) and takes the rows
it reads (split at 24: rows 0, 6, 12, 18, 24 and their saved mix scores, ~47 KB per token) through host memory
(`carry_out` / `carry_in`). Driver: `tools/ink_pipe.cpp` (`INK_SPLIT`, default 24; one card or two).
Both engines on one card, against the gate's baselines (v8, cards 1-5): haiku 64 logits rows identical, writing
85.1 tok/s (one engine 86.2); the 3,127-token prompt in steps of 784 and 16 logits rows identical; code 128 ids
identical; splits at 7, 18, 30, 42 identical (haiku 64 rows). Card memory: applications 0-23 10.72 GiB, 24-47
11.41 GiB (steps of 512, context 101).

## What two cards should give (measured on one card, 2026-11-26)

Each half of the split timed alone (`ink_pipe` `INK_PIPE_ONLY`) on the same card as the whole model, the engine's
step sizes (4,096 tokens at 100K, 1,024 at 200K):

| prompt | whole model, one card | applications 0-23 alone | 24-47 alone (zero inputs) |
|---|---|---|---|
| 100K (card 1) | 97.0 s (1,030.6 tok/s) | 46.8 s | 41.7 s |
| 200K (card 2) | 280.6 s (712.8 tok/s) | 136.7 s | 112.6 s |

The second half alone reads zero rows (only its time is meant), and zeros draw less power, so the whole minus the
first half (100K: 50.2 s) is the better figure for it. In a two-card pipeline the slower half sets the pace: ~2x on
long prompts (100K ~2,000-2,100 tok/s, 200K ~1,450), minus the hand-over through host memory (~0.2 GB per 4,096-token
step). Writing stays about one card's speed. Four cards (cuts 12, 24, 36) would take a quarter each: up to ~4x.

Where to cut (100K, the first part alone, card 1): applications 0-23 46.8 s, 0-24 48.1 s, 0-25 49.6 s against 97.0 s
for all: the halves are 46.8 / ~50.2 s at 24, 48.1 / ~48.9 at 25, 49.6 / ~47.4 at 26, so **25** (the same weights and
the same four full-attention caches per card as 24: ~2.6 % faster than 24). Card 2: 0-11 23.2 s, 0-35 72.6 s, so the
quarters of a four-card chain are ~23-26 s each (~3.8x). Gate with `INK_SPLIT=25 INK_UBATCH=1024`, both parts on one card: the same 12 checks
pass as at 24 (the 3 refusals: several conversations, pictures). `scripts/two-card-run.sh` cuts at 25 by default.

## Next: writing at long contexts on two cards (design, 2026-11-26, not built)

With the split, a writing step runs the halves one after the other, so writing stays at one card's speed. Past
~200K most of a step is reading the eight full-context caches: 32 KB a position, 32.5 GiB at 1M, ~65 ms a step at
~530 GB/s, on top of the ~11 ms of everything else (plain writing ~13-14 tok/s at 1M). While one card works, the other
waits. The idea: let the waiting card read part of the working card's cache.

- **Layout.** Each full-context application keeps its newest positions [S, N) on its own card and its oldest [0, S) on
  the other card. Card A then holds its 4 applications' [S, N) and B's 4 applications' [0, S), card B the reverse:
  4 x N positions a card, the same memory as today for any S.
- **Same bits as one card.** The attention definition (`src/attn_flash.hpp`) folds blocks of 128 keys in order from a
  state (M, L, A[128]); `attn_flash_dec` writes each block's parts and `attn_flash_sum` folds groups of 128 blocks,
  carrying the state between groups (already used at very long contexts). Every block's parts depend only on its own
  keys and the query, so the other card can compute blocks [0, S) and fold them into the state (to = 1). That state
  (130 floats a head a row) goes to the owning card, which folds [S, N) from it (from = 1). S is a multiple of 16,384
  positions (128 blocks of 128). The cache stays 16-bit; no arithmetic changes.
- **A step.** For application a on card A: A sends the row's query, gate, sink and bias inputs to B (hop 1, ~20 KB);
  B computes blocks [0, S) and their fold while A computes [S, N); B sends the state (hop 2); A folds and goes on. The
  new position's keys go to A as now. Two hand-overs per full application, 16 a step.
- **Expected** (hand-overs ~0.2 ms, measured from the split's own writing cost on one card: 83.4 vs 86.6 tok/s for
  two of them): 1M ~73 ms -> ~11 + 32.5 + ~3 = ~47 ms a step (plain ~21 tok/s, ~1.55x); 500K ~42 -> ~30 ms (~1.4x);
  below ~200K no gain. Four cards (each application's cache over the three others too): 1M ~23-27 ms (~3x).
- **Reading.** Long prompts keep today's layout (each card all positions of its own applications, the pipelined tiles).
  After a long read, the cards swap the [0, S) parts in pieces through host memory (1M: 8 GiB each way, ~2-3 s against
  a ~40 min read). A follow-up of a few hundred rows uses the same two-card fold (all its rows in one hand-over per
  application). A long follow-up either swaps back, or the prompt tile kernel learns to start from and stop at a state.
- **Also affected.** Saved prompt files and serving copies (`src/cache_file.hpp` `owner_of`, `src/snapshot.hpp`) would
  find each position range's owner instead of each application's; the drafter's own full layer stays on the last card.
- **Order of work.** (1) The step with two engines on one card (any S = 16,384; 31K prompt): logits rows identical to
  one engine. (2) The swap after a long read and the follow-up path. (3) Files and copies. (4) Two cards: speed at 200K,
  500K and 1M against the plain split, both orders. Steps 1-3 need no second card; 4 waits for the owner's OK like the
  rest of this plan.

### Step 1 done (2026-11-26, one card)

`INK_SHARD=<S>` (`Engine::shard_start` / `shard_attn`, `ink_run` after the prompt; two engines): each engine takes a copy
of positions 0 .. S - 1 of the other's full-context applications, and a writing step's rows (at S + 1,024 or later)
fold those blocks there into the state, which comes back for the owner's blocks. Card 3, both engines on it, the
31,270-token prompt, S = 16,384, 64 tokens: every logits row of all 64 steps byte-identical to one engine, to the
split without sharing, and with the drafter (ids and chosen rows); the second engine's profile shows its 4 own
attention launches plus the 4 it now runs for the first engine. Gate 15/15. Step 1 keeps the owner's full caches
(extra memory: 4 x S positions a card), so it is only a test of the arithmetic and the hand-overs.

Step 2 (memory-neutral layout): each card moves positions S .. n - 1 of its own applications down by S inside the same
buffers (keys [pos][kd]: one range; values transposed: per channel row, pieces of at most S so no piece overlaps),
reads them through a base pointer S positions back, and stores the other card's positions 0 .. S - 1 in the freed end
of the paired buffer (the last S positions of each key buffer and of each value row; applications paired 1:1, four
a card at cut 25). The data crosses through host memory (one application's S positions staged at a time, ~2 GiB at
S = 512K). The reverse (before a long follow-up read or a save) is the same moves backwards.

**Step 2 done (2026-11-26, one card):** `shard_start` now does exactly that (no extra card memory), `shard_end` the
reverse. Card 3, 31,270-token prompt, S = 16,384: logits rows of all 64 steps identical to one engine with sharing,
with `INK_SHARD_END=32` (caches back after 32 tokens, the normal paths for the rest), and with the drafter. Moving
took 0.17 s each way (S = 512K: ~5-6 s). Gate 15/15. `scripts/two-card-run.sh` has a `shard` stage (200K, S = 98,304,
both orders) and the needle shares its first 200 tokens. Left for later: serving and saves with shared caches
(`shard_end` before a prompt step or a save), more than two engines.

Serving with shared caches (plan, after the two-card numbers): a move costs ~S x 12 KB of host traffic (S = 250K at
500K: ~2.7 s each way at the 4.5 GB/s seen on one card), and sharing saves ~12 ms a token at 500K, so it pays only
past ~450 answer tokens. So: share lazily (after ~512 tokens of an answer still being written, when the context is
past ~300K), keep it shared across turns, read short follow-ups (steps of up to 16 rows, past S + 1,024) through the
shared path, and move back only for a long read, a save or a copy restore below S.

## Risks

- This host reset under card-to-card reads during six-card DeepSeek runs (Nov 10-17). The plan uses host-staged copies
  only and two cards; the DeepSeek stable-mode settings (Gen4, SMT off) stay as they are.
- Host RAM 15 GB: two engine processes or one process with two cards both stage weights; load them one after the
  other.
