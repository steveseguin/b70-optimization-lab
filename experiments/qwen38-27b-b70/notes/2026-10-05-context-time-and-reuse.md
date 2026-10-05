# Where the time went in the self-editing runs, and what the prefix cache could reuse (2026-10-05)

CPU-only reading of existing records; nothing was run on the GPUs. Script:
`scripts/context/time_and_reuse_census.py` (no arguments = the runs below; `--calls` adds per-call rows).
Follow-up items 3 and 5 of `2026-10-05-context-followup-ideas.md`, CPU-first parts only.

## In plain words

- **In every arm the model's writing takes the time, not its reading.** Writing is 84-94 % of each memory-only run
  and about 70 % of the two-minute files runs. Reading is 7-14 %. Running commands takes 3-6 seconds a run. Most of
  what it writes is thinking: 59-99 % of the written tokens, and 84-90 % in the memory-only self-editing arms.
- **The fastest fix is to write less**, above all less thinking in the routine "fetch a batch, fold it in" steps.
  The improved agent (B32i) thinks about 1,300 tokens per call. The files runs write about 70 tokens per batch. Its
  thinking alone is about 11 of its 15 minutes.
- **Keeping everything in the big window (A) is slow for a second reason: writing slows as the context grows.** It
  wrote at about 58 tokens a second against 80-100 for the small-context arms. It also re-typed its state table in
  every command, about 9 of its 26 minutes.
- **The prefix cache already pays off in arm A from the 4th call.** Reading took about 2 minutes with the cache. It
  would take about 14.5 minutes without it, so the run would be about 39 minutes instead of 26.
- **The self-editing agents cache poorly because the harness changes text that was already sent.** B32 rewrote a
  retry counter near the top of the context and edited its state block near the top. B32i rewrote earlier turns when
  re-reading its mirror, and the chat template's handling of dropped thinking changed old turns. The text was not
  moved to the end. Fixing the layout would save about 3 minutes of B32's 64 and only 20-30 seconds of B32i's 15-21
  minutes. B32i is limited by writing, not reading.
- **The 1.9-minute files result shows a different workflow, not cheap disk access or fast writing.** The data went
  straight to disk without passing through the context, a small script folded it in, and the model wrote about 7K
  tokens in all against 67-233K. Disk time is invisible: all 27 commands together took 2.7 s, including the container
  overhead. The records cannot measure a decode rate.

## Task A: where the wall time went

Seconds per trial. Ledger task, 121K tokens, 20 items, memory-only unless marked *notes*. Writing = call time minus
estimated reading (it also contains each call's fixed overhead). Reading is estimated from the measured cold-read speeds.
Tools = sandbox command time as the harness measured it. Other = the rest: harness, mirror sync, container setup and
verifier.

| trial | right | calls | prompt tok | cached | new read | written | wall s | writing | reading | tools | summaries | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A keep all | 24 | 27 | 2,005,423 | 1,830,400 | 175,023 | 89,419 | 1,589 | 1,461 | 110 | 2.7 | – | 16 |
| At keep all, thinking dropped | stopped | 49 | 4,199,076 | 3,887,104 | 311,972 | 396,563 | 9,288 | 8,734 | 189 | 2.5 | – | 362 |
| B32 paper agent | 19 | 65 | 1,253,647 | 365,248 | 888,399 | 233,308 | 3,841 | 3,476 | 336 | 5.8 | – | 23 |
| C32 summarise | 24 | 44+12 | 1,040,504 | 370,240 | 670,264 | 211,405 | 2,464 | 2,068* | 253* | 4.4 | 1,266* | 139 |
| D32 self-edit, notes | 24 | 27 | 190,410 | 147,264 | 43,146 | 7,272 | 112 | 76 | 16 | 2.7 | – | 18 |
| E32 plain, notes | 24 | 25 | 180,644 | 138,944 | 41,700 | 8,050 | 111 | 80 | 15 | 2.5 | – | 13 |
| B32i improved, seed 0 | 24 | 46 | 625,830 | 333,632 | 292,198 | 66,899 | 896 | 758 | 109 | 4.5 | – | 24 |
| B32i improved, seed 1 | 21 | 58 | 585,692 | 229,632 | 356,060 | 91,364 | 1,258 | 1,095 | 130 | 5.6 | – | 27 |

\* C32: the harness does not time its 12 summary calls. Their time (12 cold reads plus 113,811 written tokens) is
estimated from the constants and is included in the writing and reading columns. Per-call usage exists for only 19 of
its 44 agent calls (`ctx-export ... attaching min()`), so its reading is a trial-average estimate. B32t and the
third run's A seed 1 were unfinished and are skipped. At ended by cancellation and is shown for cost only.

**Cross-checks that hold.** The server's 10-second engine lines inside each trial's window add up to the same totals:

- tokens read: A 175,015 against 175,023 cached-adjusted; B32i s0 292,181 against 292,198;
- tokens written: A 89,328 against 89,419; B32 233,057 against 233,308.

So the server counts "prompt throughput" as tokens actually computed, and the usage records are complete.

**Writing speed: what can be said.** There are no streamed token timestamps, so the decode rate per call is **not
measured**. Two trial-level views agree:

| trial | written ÷ writing time (tok/s) | median of 10-s engine averages with no prompt reading (tok/s) | draft acceptance (median mean length) | context range |
|---|---:|---:|---:|---|
| A | 61 | 58.5 (p90 81) | 5.55 | 1K-146K |
| At | 45 | 45.5 | 5.52 | to 126K |
| B32 | 67 | 59.3 | **3.64** | 2-30K |
| C32 | 102 | 96.4 | 5.61 | 1-29K |
| D32 / E32 | 96 / 100 | 89 / 92 (3 intervals each) | 4.5 / 4.3 | 1-11K |
| B32i s0 / s1 | 88 / 83 | 82 / 78 | 4.36 / 3.91 | 2-22K |

Assumptions: writing time is the residual after the reading estimate, so it also holds per-call overhead. The engine
medians are 10-second averages and can include short gaps between calls. B32 writes slower than its small context
would suggest (59 against about 99 tok/s expected at 30K). Its long planning thinking accepts fewer drafted tokens
(3.6 against 5.5). The table's write speeds therefore depend on what is written, not only on context length.

**What was written** (completion tokens split by characters. Thinking-dropped arms read their thinking back from
`dropped_thinking.jsonl`. Numbers and JSON tokenize denser than prose, so the split is approximate):

| trial | thinking | visible text | tool-call arguments | note |
|---|---:|---:|---:|---|
| A | 53,135 (59 %) | 2,739 | 33,545 (38 %) | arguments are mostly the state JSON re-typed in every command (~2,900 chars) |
| At | 395,161 (>99 %) | 707 | 695 | re-derived everything each call, hit the 16,384 cap |
| B32 | 210,207 (90 %) | 4,116 | 18,985 | first call 120 s; 10 calls of 10K+ tokens |
| C32 | 131,833 (62 %) | 57,776 (summaries) | 21,796 | first summary hit the cap with thinking, retried without |
| D32 | 5,167 (71 %) | 432 | 1,673 | 2,839 tokens in the first call (32 s), then ~70 per batch |
| E32 | 5,682 (71 %) | 773 | 1,596 | 3,859 in the first call (42 s) |
| B32i s0 | 59,669 (89 %) | 259 | 6,971 | first call 134 s |
| B32i s1 | 76,592 (84 %) | 2,898 | 11,874 | |

**File operations in the files-allowed runs** (from the commands. Item sizes come from the task's `stream.jsonl`.
`state.json` is taken as about 4 KB, i.e. 160 counters at about 25 bytes. These are estimates.)

| trial | files created | writes | bytes written | reads | bytes read | command output shown to the model | all tool time |
|---|---:|---:|---:|---:|---:|---:|---:|
| D32 | 20 | 39 | ~385 KB | 174 | ~2.5 MB (final `grep` loops over all 20 batch files) | 4,622 chars | 2.7 s / 27 commands |
| E32 | 20 | 40 | ~389 KB | 43 | ~409 KB | 4,412 chars | 2.5 s / 25 commands |

Both runs follow the same pattern:

- the first call writes a 30-line `apply.py`;
- then `next > /app/notes/batch_NN.txt && python3 /app/notes/apply.py batch_NN.txt` runs 19 times, about 1 s of
  model time each;
- then a short script reads `state.json` and answers;
- the 121K-token stream never entered the context. Prompts stayed at 1-11K, and the model saw about 4.5K characters
  of command output in the whole run.

**What the 1.9 minutes is evidence of, and what it is not.**

- *Is evidence of:* the model, given files, chooses a workflow that keeps the data out of its context and does the
  folding in code. That workflow needs about 7-8K written tokens and about 43K read tokens for the whole task. For
  the same task, the memory-only arms needed 67-233K written tokens and 175-888K read tokens.
- *Is not:*
  - a measure of disk cost. All commands, including container exec overhead, took 2.7 s. Disk I/O cannot be
    resolved below the 0.1 s per command the harness records, and buffered and durable writes cannot be told apart.
  - a decode-speed result. No token timestamps exist, there are only 3 decode-only engine intervals per run, and the
    prompts are small.
  - a like-for-like comparison with A. Prompts are 15 to 20 times smaller and written tokens 11 to 12 times fewer.

A matched check (item 3's later steps) is still needed for any claim about file overhead.

## Task B: how much of each prompt was reusable

Each call's sent messages were rendered the way the served template renders them. Common prefixes were measured in
characters and **converted** to tokens with that trial's own per-call ratio of server tokens to rendered characters
(2.2-3.3 characters per token). No tokenizer was loaded. "Predicted" applies the exact-cache rules:

- the prompt is cached in 832-token blocks, and only prompt blocks are cached;
- recurrent state is kept at each prompt's last block boundary, one block before it, at junctions, and every
  13,312 tokens;
- with drafting the hit drops one block.

| trial | shared with previous call | predicted reusable | actually cached | prediction exact / within one block |
|---|---:|---:|---:|---:|
| A | 92.7 % | 91.3 % | 91.3 % | 27/27 / 27/27 |
| At | 94.0 % | 92.6 % | 92.6 % | 48/48 / 48/48 |
| B32 | 37.2 % | 30.1 % | 29.1 % | 50/65 / 65/65 |
| C32 | n/a (snapshot files of agent and summary calls overwrite each other) | | 35.6 % (agent calls alone 51.7 %) | |
| D32 | 94.5 % | 77.3 % | 77.3 % | 27/27 / 27/27 |
| E32 | 93.9 % | 76.9 % | 76.9 % | 25/25 / 25/25 |
| B32i s0 | 69.7 % | 59.0 % | 53.3 % | 13/46 / 42/46 |
| B32i s1 | 57.1 % | 42.3 % | 39.2 % | 36/58 / 58/58 |

The rules reproduce the server's cached count exactly on 226 of 296 calls and within one block on 292 of 296. The
remaining one-block misses come from converting characters to tokens. So the cache behaves as documented, and every
loss below comes from the prompt layout.

**Why D32/E32 cache only 77 % even though they only append.** Their prompts are 5-10K, and each call re-reads the
last one to two blocks (up to 1,664 tokens) because of the 832-token block and the drafting rule. That is about 16 s
of 112. It is a small, structural cost for agents that take many short steps.

**Where the prefix breaks** (new tokens read per break kind; "saved" = estimated reading seconds an append-only layout
would save):

| trial | break kind | calls | new tokens | saved s |
|---|---|---:|---:|---:|
| B32 | retry notice at message 2 rewritten ("CONTEXT LIMIT HIT (retry 13/50)" → "14/50") | 19 | 466,882 | 152 |
| B32 | own `@@STn@@` state block at message 4 rewritten at every fold | 13 | 112,343 | 23 |
| B32 | pure append (unavoidable new text) | 26 | 182,877 | 1 |
| B32 | other edits near the top / mirror re-rendering | 6 | 124,650 | 11 |
| B32i s0 | new turns replace the pinned state shown last (mostly the new batch, unavoidable) | 25 | 216,666 | 16 |
| B32i s0 | mirror sync rewrites earlier assistant turns (merges two turns, tool call turned into `bash {...}` text) | 19 | 72,331 | 4 |
| B32i s1 | **empty-think flip** in the template (below) | 15 | 147,860 | 13 |
| B32i s1 | the model's own `===STATE===` block in an early turn (message 3 or 7) rewritten | 13 | 85,495 | 15 |
| B32i s1 | pure append | 18 | 64,256 | 0 |
| B32i s1 | other edits near the top, compactions | 11 | 56,552 | 4 |
| At | empty-think flip | 3 | 128,319 | 73 |

**The empty-think flip.**

- With `preserve_thinking=false`, the Qwen3.8 template writes an empty `<think>\n\n</think>\n\n` only into assistant
  turns that come after the last real user message, and writes nothing for those before it.
- When the harness adds a user message (a nudge, a notice, the pinned state), the earlier turns move before that
  point and lose their empty think tags. The text that was already sent changes, so the cache misses from that turn.
- The harness already strips old thinking itself. Sending `preserve_thinking=true` with the stripped turns would make
  every turn render the same way, at a cost of about 4 tokens per turn. This is a one-line harness change.

**Why only 53 % / 39 % (B32i) and 29 % (B32) was cached, and what would raise it.**

- **B32** (29 %) has two causes:
  - The harness's rollback notice sits near the top (message 2) and carries a counter that changes on every retry,
    so each retry re-read all ~26K tokens from zero: 19 times, 467K tokens.
  - Each fold rewrote the state block at message 4, so everything after it was read again.
  - Fix: put notices at the end and never edit them in place; keep the state only at the end.
  - Estimated reading 336 s → 152 s: **about 3 minutes saved out of 64**.
- **B32i** (53 % / 39 %) has three causes. It shows the pinned state last as intended, but:
  - (s0) the mirror sync re-renders earlier assistant turns differently, merging two turns or turning a tool call
    into `bash {...}` text;
  - (s1) the model also kept its own `===STATE===` block inside an early turn and edited it, which is the paper
    agent's habit;
  - (s1, At) the empty-think flip.
  - Fixes:
    - re-render mirror turns byte-for-byte as they were sent;
    - send `preserve_thinking=true` with the thinking stripped;
    - reject or move any state-like block that is not the pinned last message;
    - delete a folded batch only when it is the last raw turn.
  - Estimated reading 109 → 90 s (s0) and 130 → 102 s (s1): **20-30 s saved per trial, 2-3 % of the run**.
  - B32i's 53 % is mostly not waste. Even with the append-only layout it would read about 239K of its 292K new
    tokens, because most of that is new text that has to be read once anyway: the batches, its own previous replies
    (only prompt blocks are cached) and the state. That estimate includes up to two blocks of re-read per call.
- A server-side alternative that needs no harness change: keep a recurrent state at every message start (the
  `cache_blocks` overlay in the reuse-rules note). It recovers less: B32i 109 → 92 s and 130 → 116 s, B32 336 → 330 s.
  Most breaks there land inside or just before long messages that change anyway.

**Break-even of the cache for the keep-everything arm (A).** With the cache, cold reading is slower (832-token pieces)
but only new text is read. Without it, every call re-reads the whole prompt in 4,096-token pieces.

| | after call 3 | after call 4 | after call 6 | whole run (27 calls) |
|---|---:|---:|---:|---:|
| cumulative reading, cache on (s) | 2.1 | 6.1 | 12.2 | 110 |
| cumulative reading, cache off (s) | 2.1 | 6.2 | 19.1 | 866 |

- The cache repays itself at **call 4**. Over the run it saves about 756 s (12.6 minutes).
- The slower cold read cost almost nothing here because A's first prompt is 983 tokens.
- A full cold re-read of A's last prompt (146K tokens) would cost about 20 s more with the cache than without it.
  The next call earns that back.
- At (48 calls) reaches break-even at call 6 and reads for 189 s against 1,866 s.

## What would save the most time (in order)

1. **Less thinking in routine steps.** Thinking is 84-90 % of written tokens in the memory-only self-editing arms,
   99 % in At, and 59-71 % in A, C32 and the files runs:
   - B32i s0: about 60K thinking tokens at about 88 tok/s, roughly 11 of its 15 minutes;
   - B32: 210K tokens, about 52 minutes.

   Candidates, all untested for correctness on this task:
   - thinking off, or a thinking cap (`THINK_CAP`, untested on the server), for "fetch" and "fold" steps;
   - a fold script written once and reused, as the files runs did (about 70 tokens per batch);
   - a step protocol that does not ask the model to re-plan every call.
2. **Keep the raw data out of the context and the state out of the written text.** Pipe `next` into a stored fold
   script, as A did inline and the files arms did with a file. Do not re-type the state in every command: in A that
   is about 33K tokens, roughly 9 minutes at its large-context write speed. For memory-only rules this needs a
   harness-owned fold step or state store that the grader accepts.
3. **Append-only prompt layout** (Task B fixes above): about 3 minutes for B32-like runs, 20-30 s for B32i, and
   73 s for At from the template fix alone. The fixes are cheap, but this is the smallest lever of the three for
   the agent that already works.

## Method, assumptions, what is not measured

- Records:
  - `context-clm-second-20261005/client/runs/jobs/*` (A, At, B32, C32, D32, E32; B32t unfinished, skipped);
  - `context-clm-third-20261005/client/runs/jobs/*` (B32i s0, s1; A s1 still running, skipped);
  - the two `server.log` files.
- Per call: `trajectory.ctx.json` step metrics (the server's prompt/cached/completion tokens; equal to `usage.json`
  totals in all trials except C32), `timing.json` (`llm_s` per call, `bash_s` per command) and
  `context_snapshots/turn-*.json` (the messages sent).
- Reading-time model:
  - a prompt of L tokens takes L / R(L) seconds cold, where R is the whole-prompt rate interpolated between the
    measured points: 832-token pieces 2,600 tok/s at 30K, 2,250 at 60K, 1,720 at 120K; 4,096-token pieces 3,280 at
    8K, 3,050 at 30K, 2,700 at 60K, 2,190 at 120K, 1,745 at 200K;
  - a call with K cached tokens costs T(P) − T(K);
  - *assumed:* the 832-piece rate at 8K (2,790 = the 4,096 rate × 0.85) and at 200K (1,330, × 0.76), needed only
    above 120K (A, At).
- Writing time is the residual (call time minus estimated reading), so it includes per-call fixed overhead. A
  constants-only estimate is lower (A 1,355 s against 1,461; B32 2,328 against 3,476) because content-dependent
  draft acceptance is not in the constants.
- Not measured:
  - per-token or per-call decode rate (no streamed timestamps);
  - time to first token;
  - disk I/O time below 0.1 s per command;
  - page-cache effects;
  - checkpoint memory;
  - eviction (ignored in the prediction; the 370K-token pool was not under pressure with one user).
- Task B token figures are converted from characters, not tokenized. The rendering leaves out the constant tool
  schema block. The "append-only layout" estimate is a counterfactual: per call, it counts the rendered messages not
  present in the previous call plus two blocks. The model's behaviour under a different layout could differ.
- One seed per arm except B32i (two), one task family. No speed claim comes from this note.
