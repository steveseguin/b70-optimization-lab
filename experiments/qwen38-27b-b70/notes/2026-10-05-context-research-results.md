# Unlimited context for the 27B: what the night of 2026-10-05 found

Written for the owner. Plain words first; every number links to its detailed note at the end.
Hardware: two Arc Pro B70, Qwen3.8-27B FP8, 16-bit cache (nothing quantized), drafting on, R314 image.
Status: work in progress; rows marked *pending* are still running.

## The short answer

1. **You do not need pruning to get past 32K.** The model's whole 262,144-token window opens on two cards with the
   16-bit cache. It reads and uses all of it.
2. **A long context is now cheap to keep using.** A new exact prefix cache means each turn reads only what is new:
   a question over a cached 200K context starts in 2 seconds instead of 114.
3. **Small is still better where it can be had.** Writing speed falls from about 127 tokens a second at 8K to 26 at
   250K, and above about 60K the model occasionally (about 1 lookup in 40) reads a look-alike line instead of the
   one asked for. So the right design is a big window as the safety net and a pruned working context as the habit.
4. **"Unlimited" comes from the model managing its own state, and it already does that well.** Given a shell, the
   27B folds incoming data into a small running table or into files by itself and deletes the raw text. With files
   allowed it finished a 121K-token task in under two minutes with every answer right and never more than 9K of
   context. What broke the paper's agent in our test was the harness around the model, not the model's pruning.
5. **A CPU-side cleaner or classifier does not buy much.** Measured on real agent sessions, no-loss cleaning frees
   under 2 %. The cheap, real lever is to stop re-sending the model's old thinking (10 % of a typical call, up to
   56 %).
6. **Decisions do not need thinking tokens.** For a yes/no, a choice or a label, switching thinking off and
   restricting the output to the labels gave the same answers 6.5 times faster on easy items.

## What was tested, and what happened

### The window itself

| Context | Read speed | First word after (cold) | First word after (cached) | Write speed |
| ---: | ---: | ---: | ---: | ---: |
| 8K | 3,280 tok/s | 2.4 s | | 127 tok/s |
| 30K | 3,050 | 9.8 s | 0.8 s | 99 |
| 60K | 2,700 | 22 s | 1.0 s | 70 |
| 120K | 2,190 | 55 s | 1.5 s | 48 |
| 200K | 1,745 | 114 s | 2.0 s | 35 |
| 250K | 1,550 | 161 s | 2.4 s | 26 |

- Drafting gives exactly the no-drafting answer at every length.
- An early result of mine, "empty answer above 212K", was an artifact of sending the prompt as bare text. In chat
  form the model answers at 213K and 250K.
- These are single-server first looks, not package numbers.

### Recall by length (720 codes asked)

| Context | Codes buried in ordinary words | Wall of codes |
| ---: | ---: | ---: |
| 60K | 60 of 60 | 60 of 60 |
| 120K | 60 of 60 | 58 of 60 |
| 160K | 59 of 60 | 58 of 60 |
| 200K | 58 of 60 | 57 of 60 |
| 230K | 60 of 60 | 60 of 60 |
| 250K | 60 of 60 | 58 of 60 |

Every miss was another record's real code (the neighbour, or a record number sharing most digits). The model never
invented a value and never lost a region: the start of a 250K context is recalled as well as the end. The test is
built to be hard in exactly this way (up to 11,879 records that differ only in their number).

### The exact prefix cache (new: `overlays/b70-prefix-cache-exact`)

- The engine's own cache also stores blocks made while the model was *writing*, and with drafting it stores the
  recurrent layers' state at every block, four times the memory per token. A cached answer is then not guaranteed
  to equal a cold one. The add-on stores only what was made while *reading* a prompt, in fixed 832-token pieces, so
  a cached read runs the same arithmetic as a cold read.
- Tested with drafting on: 99 of 99 cases identical to a server without the cache, including second and third
  turns of a conversation; a cold repeat at 120K identical to the cached answer.
- An edit in the middle of a long context resumes from the last kept state before the edit (every 6,656 or 13,312
  tokens, a dial) instead of from zero.
- The standard 12-prompt gate is unchanged with the cache on: 12 of 12 exact on a cold pass and on a cached pass,
  and the write rate is the same (88.5-88.7 tok/s off, 89.6-89.7 on).
- Costs: a first, cold read is 14 to 27 % slower; each kept state costs the memory of about 2,500 tokens of
  context. Not yet tested: several users at once, the one-card server, a scores-level comparison.

### Self-editing context (the paper's idea)

Task: a stream of 20 batches (121K tokens) of counter updates with overwrites and deletes; at the end, the current
value of 24 counters. Files forbidden unless stated. Budget = how much context the agent may hold.

| Strategy | Right of 24 | Time | Written | Note |
| --- | ---: | ---: | ---: | --- |
| Keep everything in the big window, cache on | 24 | 26 min | 89K tok | 91 % of reads served by the cache |
| Keep everything in the big window, second seed | **0** | 38 min | 99K tok | all 24 blank: it ran out of window before the questions arrived (see below) |
| Paper's self-editing agent, 32K budget | 19 | 64 min | 233K tok | all 5 losses caused by the harness, see below |
| Summarise at 75 %, 32K budget | 24 | 41 min | 211K tok | 12 summaries, 57 calls |
| Self-editing, **files allowed**, 32K | 24 | **1.9 min** | 7K tok | context never above 8.2K; no edit needed |
| No management, **files allowed**, 32K | 24 | **1.9 min** | 8K tok | context never above 8.9K |
| Keep everything, old thinking dropped | none | stopped at 2.6 h | 397K tok | stuck: re-derived everything each call, hit the output cap, never acted |
| Improved self-editing agent, 32K, seed 0 | 24 | 15 min | 67K tok | peak context 20K; no delivered batch lost |
| Improved self-editing agent, 32K, seed 1 | 21 | 21 min | 91K tok | 3 wrong: a bug in the script the model wrote to fold batches in (see below) |
| Improved agent on a **478K stream** (1.8 times the whole window), 32K budget | 24 | **8.2 min** | 36K tok | peak context 10K; 76 batches, 37 calls |
| No management, **files allowed**, 478K stream | 24 | **1.9 min** | 8K tok | 11 calls, peak context 9.7K |
| Self-editing, **files allowed**, 478K stream | 24 | **1.3 min** | 5K tok | 12 calls, peak context 7.1K |
| No management, files allowed, 121K of **arbitrary key-values** (not a foldable table) | 24 | 1.1 min | 4K tok | 8 calls, peak context 5.8K |
| Improved self-editing agent, 32K, **prose ledger** 122K (narrative text a script cannot parse; the model must read) | **0** | **3.5 h** | 926K tok | failed: 6 of 20 batches fetched in 120 calls, 18 wrong and 6 stale, and it broke the no-files rule; cause being traced |
| Keep everything, no files, 121K of **arbitrary key-values** | 24 | 9.3 min | 19K tok | all 121K held in context (peak 129K); 24 look-ups all right |

**Keeping everything in the big window is not robust.** It was fully right on the first seed and returned nothing on
the second. On the second seed the model let every batch into its context raw and then typed the same 136 lines out
again in a command, about 13K tokens of growth per batch. Its running table was exact after all 18 batches it
received, but at 245,900 tokens the server refused the next request, one batch before the questions arrived, so no
answer was ever written. The model had said in its first call that it did not know its window size; without a
budget the harness never told it. Two cheap guards would have saved the run: always show the window and the current
size, and refuse a fetch that cannot fit.

**The clear winner so far is the plainest one: let the model keep its working data in files.** Same answers, a
context under 9K tokens on a 121K-token task, and 14 to 22 times faster than any strategy that keeps the data in
the context. Where files are forbidden, keeping everything in the big window and summarising at 75 % both got
everything right; summarising took longer than keeping everything (41 against 26 minutes), because the cache makes
a big context cheap to re-read and every summary breaks the cache.

What the transcripts show:

- **The model's own pruning lost nothing.** Once settled, it kept a small table of current values, folded each new
  batch in with a short script, and deleted the raw batch: about 650 tokens written per batch.
- **The five wrong values were batches the paper's harness threw away.** When the context overflowed, its "roll
  back and retry" removed batches that had already been delivered and could not be fetched again. The overflow was
  set off by thinking: the first call alone wrote 14K tokens of planning, and old thinking is re-sent every call.
- **The big-window run did not hold the raw text either.** It piped each batch through a small filter. About 95 %
  of its 26 minutes was writing, not reading.
- **First comparison (earlier in the night):** with files allowed the model saved every batch to disk at once and
  searched at the end, holding 11-35K of context on a 140K task. Its only losses came from one shell mistake
  (`tee | head` cutting files short).

- **Dropping old thinking is not safe as a blanket switch.** In the keep-everything run with old thinking dropped,
  the model had been carrying its working state in its reasoning. Without it, each call re-derived everything from
  113K of context, ran into the 16,384-token output cap without issuing a command, and repeated: 49 calls, 397K
  tokens written, no answer; I ended it after 2.6 hours. Old thinking can only be dropped when the working state
  lives somewhere else (a state block or a file).

- **The stream larger than the window was handled, and how matters.** On 478K tokens (76 batches) the improved
  agent wrote one small script, kept the running table in the pinned state, and ran `next | script` for each batch:
  every answer right in 8.2 minutes, never more than 10K of context. The model itself read only 2 of the 76
  batches; its script read the rest. That is a real answer to "can a 32K budget handle unlimited input": yes, when
  the model can write code that does the reading. It does not yet show the model *reading and understanding* more
  text than its window, which needs a task that code cannot parse (next task family).
- **When the model has to read the text itself, the improved agent failed badly.** On the prose ledger (the same
  counters, but each batch is narrative with numbers as words, pronouns, corrections and distractors; an 80-line
  parser scores 13-33 %) it spent 3.5 hours, wrote 926K tokens, got through 6 of 20 batches and had none of the 24
  answers right. Every earlier success in this table was a task that code could read. This is the first and so far
  only measurement of the model reading more than its budget and folding by understanding, and it is a failure.
  Whether the cause is the task, the harness or the model is being traced. A one-hour limit per trial was added
  after this run.
- **The improved agent's one imperfect run was the model's own coding slip.** On the second seed its running state
  was exact through batch 16. Then, after two very long thinking turns, it re-typed its fold script with a mistake
  in the pattern that reads delete lines, so every delete from batch 17 on did nothing, while the script still
  printed "errors: 0". Three counters that should have been reported as deleted came back with old numbers. No
  harness mechanism was involved and nothing was lost from the context. About 85 % of both runs' time was writing,
  and more than half of the written tokens came from a few turns of 4,000 tokens or more.
- **The fix under test** keeps the fold script in one place instead of having the model re-type it: the model
  writes it once with a self-test, and the harness refuses a fold whose self-test fails or whose count of handled
  lines does not match the batch. Replayed on the saved run, it refuses the buggy script and folds all batches to
  the right answers with the correct one. A thinking cap is a separate arm.

The improved agent (`scripts/context/clm_improved.py`) keeps the paper's idea and fixes the harness: a delivered
item is never rolled back, there is a room check before fetching, old thinking is dropped, and the running state is
shown last so the transcript stays append-only and the prefix cache keeps working.

### Where the time goes (reconstructed from the saved runs)

| Run | Total | Writing | Reading | Tools | Tokens written |
| --- | ---: | ---: | ---: | ---: | ---: |
| Keep everything | 26 min | 24 min | 1.8 min | 3 s | 89K |
| Paper's self-editing agent | 64 min | 58 min | 5.6 min | 6 s | 233K |
| Summarise at 75 % | 41 min | 34 min | 4.2 min | 4 s | 211K |
| Files allowed (both) | 1.9 min | 1.3 min | 0.3 min | 3 s | 7-8K |
| Improved agent, seed 0 | 15 min | 12.6 min | 1.8 min | 5 s | 67K |

- **Writing, mostly thinking, is where the time goes in every strategy.** Reading, the cache and the disk are small
  by comparison: all the file commands of a files-allowed run took under 3 seconds together.
- **The cache repays its slower first read by the fourth call.** Without it the keep-everything run would have
  read for about 14 minutes instead of under 2, and taken about 39 minutes instead of 26.
- **The cache does what the rules say** (its reuse was predicted exactly on 226 of 296 calls, within one block on
  292). Where reuse was low, the layout of the prompt was the cause: a notice near the top whose retry counter
  changes, a state block in an early turn that gets rewritten, and a chat-template effect that alters earlier
  turns when old thinking is dropped.
- **So the next lever is less writing per step**: no re-typing of state or scripts, and little or no thinking on
  routine fetch-and-fold steps (untested for correctness). Detail: `2026-10-05-context-time-and-reuse.md`.

### CPU help

Measured on 5.0 million tokens of real agent sessions and on the 27B's own transcripts:

| Rule | Context freed |
| --- | ---: |
| Exact duplicate outputs, repeated lines, whitespace and terminal noise (no loss at all) | 1.8 % |
| Large tool outputs moved to disk with a pointer (one in three is read back later) | 7.5 % |
| The 27B's earlier thinking, re-sent on every call | about 10 % typical, up to 56 % |

A 32K window holds about 33K tokens' worth after strict no-loss cleaning, not 100K. There is no hidden slack for a
small CPU model to find; the content of an agent's context is mostly commands and their results, each said once.

### One-step decisions

80 items (yes/no, A-D, sentiment, routing). Restricting the first token to the labels gave the same label as normal
decoding on 80 of 80, both right on 78; with thinking on, 23 of 24 right, and one-step agreed with it on 24 of 24.
Per item: 0.09 s one-step, 0.09 s decoded, 0.59 s with thinking. With drafting a label is already a single step,
so the saving is the thinking, and the restriction adds a guarantee that the output is one of the labels.
Not measured: hard decisions where thinking changes the answer.

## Your questions, one by one

- **Can 32K be enough for unlimited context?** For work whose state is small (a running table, a to-do list, a
  summary of decisions) yes, and the model does it by itself with a shell. For work that needs the raw text again
  later, no amount of pruning is free: what is deleted has to be stored somewhere (a file) or re-read.
- **One card runs, the other prunes?** Not worth it here. One card holds about 44K of context and writes about 54
  tokens a second; two cards together hold 262K and write 90-127. With the cache, pruning costs seconds and is
  rare, so there is nothing for a second card to do in the background that beats giving it to the main model.
- **Context on disk?** At the application level this is what the model already does (files and search), and it is
  lossless. At the engine level the cache is exactly 64 KiB per token, so a 200K conversation is about 12 GiB; a
  saved copy on the NVMe drive could restore in 5-10 seconds instead of a 2-minute re-read, byte for byte. Designed,
  not built.
- **CPU continuously trimming, or a small CPU classifier?** Measured: under 2 % without loss. Not the lever.
- **Stop early for decisions?** Yes: thinking off plus allowed labels. Same answers on easy items, 6.5 times faster.

## What did not work, and why

- **The paper's agent as shipped** lost data through its own rollback, and its nudges fired when there was room.
- **The paper's "suffix cache reuse"** reuses stale cache state after an edit. Not exact; rejected.
- **A CPU cleaner** (above).
- **Token scores on this host:** asking the drafting server for scores compiles a routine that needs over a
  gigabyte of host memory for a few seconds; with 15 GiB of RAM the memory guard stopped the server (five times
  before I found the cause). Tests now compare token ids, and one-step choices use label restriction.
- **A driver setting from the four-card host** (`EnableDeferBacking=0`) to win back host memory: the server does not
  start with it at the 95 % memory setting. Not pursued.

## Downsides and open points

- The window that opens (262K) is larger than the window that is needle-exact (about 60K in the hardest test).
- Writing at 200K+ is three to five times slower than at 30K.
- The exact cache slows a cold read by 14-27 % and is tested with one user only.
- All self-editing results so far are one task family and one or two seeds.
- Host memory, not video memory, is what limits this host.

## Notes and data

- Window, recall, decisions: `2026-10-05-context-window-prereg.md`; data `data/2026-10-05-context/{longctx,edge,recall}/`
- Exact prefix cache: `2026-10-05-prefix-cache-exactness-prereg.md`, `2026-10-05-prefix-cache-reuse-rules.md`;
  data `data/2026-10-05-context/{prefixcache,prefixcache-exact-mtp}/`
- Self-editing comparisons: `2026-10-05-self-editing-first-comparison.md`; scripts `scripts/context/`
- CPU cleaner census: `2026-10-05-context-hygiene-census.md`
- Research review (paper and related work): `2026-10-05-context-research-review.md`
