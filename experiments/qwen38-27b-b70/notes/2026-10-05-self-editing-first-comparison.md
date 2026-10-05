# Self-editing, first comparison: what really happened, and the second comparison (2026-10-05)

Results: `/mnt/fast-ai/bench-results/context-clm-first-20261005/client/` (summary.txt, `kv32k/jobs`, `kvbig/jobs`).
Plan: `2026-10-05-context-window-prereg.md`, section "Self-editing, first comparison".
Scripts: `experiments/qwen38-27b-b70/scripts/context/` (README there).

## In one paragraph

The first run did not test what it was meant to test. In all 12 trials the model did the
same sensible thing: it saved each batch to a file and searched the files at the end.
None of the arms kept the data in its context, so the peak contexts are small (11-35K)
whatever the task size. Every lost key was lost the same way. The model ran
`next | tee file | head -N` to save a batch while showing only its first lines. `head`
exits early, which kills `tee` before it has written the whole batch (a "broken pipe").
Most files kept only their first 8,192 bytes, about half a batch. Self-editing, summarising
and the big window had nothing to do with any score. The p4 scores of the three
non-self-editing arms (0.625 / 0.583 / 0.542) follow one identical command sequence, and the
spread is only the race over which batches `tee` finished. The summary arm also had a bug of
our own: 3 of its 5 summaries came back empty, because thinking used up the 4,096-token cap.

## The table, and what each cell really was

reward = fraction of 24 queried values exactly right; pN = input about N × 32,768 tokens
(6 / 11 / 22 batches of 100 SETs, about 6,400 Qwen tokens each; p4 = 140,700 Qwen tokens). One seed.

| arm | p1 | p2 | p4 |
|---|---|---|---|
| self-editing, 32K budget | 0.458 | 1.000 | 1.000 |
| summary at 75 %, 32K | 1.000 | 1.000 | 0.583 |
| no management, 32K | 1.000 | 1.000 | 0.625 |
| no management, no budget | 1.000 | 1.000 | 0.542 |

- **Self-editing p1 (0.458)**: it saved batches with `next | tee -a /app/stream_log.txt | head -1`.
  The broken pipe cut batches 2-6 short: the log held 355 of 600 SET lines, some ending mid-line.
  The model found the gap ("Items 3–6 were lost to SIGPIPE when `head -1` killed `tee`") and
  submitted with 11 blanks. Of its 13 written values, 11 were right; the other 2 were most likely
  values cut mid-line. One thinking turn hit the 8,192-token cap with no command (27K characters
  of reasoning). That turn alone pushed the context from 15.6K to 24K and set off 3 of its 4
  nudges. The one real edit came after the urgent nudge, once the answers were already written:
  it replaced batch 1's text with a one-line note (25.4K → 19.5K). That edit lost nothing that
  mattered. It ended by submitting.
- **Self-editing p2 (1.0)**: `next > /app/item_NN.txt; head -1 ...` (no pipe race), then a Python
  script over the files. No edits, one 25 % nudge, peak 11.5K. Ended by submitting.
- **Self-editing p4 (1.0)**: batch 1 arrived in the context. The model copied it out of its own
  mirror file into `/app/kv_log.txt`, then ran `next >> /app/kv_log.txt` four times per command.
  No edits, peak 13.4K, 13 calls. Ended by submitting.
- **Summary p1, p2 and no-management p1, p2 (all 1.0)**: these are the same runs, token for token.
  Greedy decoding plus an identical prompt (a summary never fired) gives identical output, and
  the big-window p1/p2 are identical too. Each saved batches with `next > file` (or `next | tee`
  with no `head`), which is safe. Ended by submitting.
- **No management p4, 32K (0.625)**: batch 1 was printed into the context. The model then tried
  to retype it into a heredoc and hit the 8,192-token cap in the middle of the command. It
  retyped the batch again by hand, then used `next | tee itemK.txt | head -3` for batches 2-22.
  16 of 21 files were cut at 8,192 bytes. It wrongly concluded that the 9 keys it could not find
  had never been set, and left them blank. The budget's final-turn notice ended the run
  (`budget_stop`), but the answers were already computed. The loss came from the pipe, not the
  budget.
- **Summary p4 (0.583)**: the same opening as above, so the same broken-pipe files (17 cut).
  It then spent about 25 turns on the 8,192-byte puzzle (it even tested `tee` on its own). The
  context passed 75 %, and 3 of the 5 summary calls returned nothing because thinking used up
  the 4,096-token cap. The context went over the limit and the final-turn notice fired; a later
  summary worked and the run went on. It answered 14 and submitted. Nothing was lost to a
  summary.
- **No management, no budget p4 (0.542)**: the same opening and the same broken pipe (14 files
  cut). It decided that the 11 missing keys were "distractors" and submitted. Its peak was
  35.4K, not 140K, because the data was in files.

Harness settings that did **not** cause any loss: step cap 89 and call cap 202 were never
reached; no output was ever cut by `OBS_MAX_CHARS` (60,000 against a ~16,000-character batch);
no rollbacks. `CONTEXT_BUDGET=0` really means unlimited in the harness (`_parse_budget`: 0 → no
gate; usage.json shows budget 0, no nudges, no final turn). Things that do count but did not
decide any score: thinking text counts against the budget. The harness counts
`reasoning_content`, and the Qwen3.8 chat template sends all earlier thinking back to the server
(`preserve_thinking` defaults to true): server prompt tokens jumped 15,562 → 23,968 after the one
long thinking turn. Five of twelve trials had at least one turn cut at `max_tokens` 8,192.

## What this run shows and does not show

- (a) **Self-editing vs summarising vs keeping everything: nothing.** No arm kept the data in
  its context, so the three context policies were never tested. The p4 differences are noise
  from the pipe race. The self-editing p1 failure is the same pipe bug.
- (b) **The model's own tendency: strong and immediate.** Left free, it moves the data to files
  in every trial, from the first batch, at every budget, even with no budget at all. So with
  files allowed, this task measures how well the model writes files, not context management.
  Two shell habits break it: `| tee | head` (the broken pipe) and retyping 16K characters into a
  heredoc (hits the token cap).
- (c) **Where information was actually lost: when saving, never in the context.** Every miss was
  a value that never reached a file whole. Most misses were honest blanks; 2 were values cut
  mid-line. No edit, summary or rollback removed a needed value, and the model never invented a
  value. It did twice explain the gap wrongly ("never set", "distractors"), partly because the
  instructions allowed "".

## Second comparison (designed before it runs)

Script: `scripts/context/second-comparison.sh` (env API_BASE, MODEL_NAME, OUT_DIR; SUBSET=full|core|quick;
DRY_RUN=1 prints the plan and a time estimate).

**What changed and why**

1. **Fixed absolute sizes**: total input of about 60K, 120K and 180K Qwen tokens (counted with the
   served model's tokenizer), all inside the 200K that the model recalls exactly. Same task files for
   every arm. 2 seeds.
2. **Two storage modes**:
   - *memory-only*: stream data may live only in the model's context (for self-editing, the mirror
     file is the context). Enforcement: `next` refuses (without using up the item) when its output
     goes to a file or into `tee`. Audit: after the run, the grader scans every file created or
     changed after the image build. Any file other than answers.json and the mirror that holds 4
     consecutive words of any value (kv), or 3 or more counter names (ledger), **voids** the run
     (reward 0, raw score kept). Exported shell variables land in the harness state file and are
     caught. A file written and deleted again is not seen; the summary marks commands that redirect
     or `tee` `next`, or write data lines to a file, as "suspect".
   - *with notes*: files are explicitly allowed. The grader reports how many queried values ended
     up in files ("stored"), which separates losses while saving from losses while reading back.
3. **A second task, `ledger`**: about 160 counters get SET / ADD / DEL updates, 136 lines per batch
   (~6,400 tokens). Each line carries a 16-word memo that never matters. The last item asks for 24
   current values, about 3 of them deleted (answer null). The state that matters is small (~1.5K
   tokens) and changes all the time, so an agent that keeps one up-to-date table and replaces stale
   entries can be lossless at 32K. That is the paper's "surgical update". In `kv`, by contrast,
   any of 2,800 values may be asked, so a 32K context cannot hold them all: kv measures *what is
   lost and whether the loss is admitted*.
4. **Caps that cannot end a run**: steps = 4 × items + 40, calls = 3 × steps, observation limit
   ≥ 2 × the largest item. Each trial is labelled with what ended it (`submit`, `submit(final)`,
   `budget_stop`, or `CAP:*` / `EXC:*` / `server_window` / `unknown`). Any of the last four makes
   the trial invalid; the script prints `!!!` and exits 1.
5. **Clearer task text**: every queried key really was set; a blank is scored like a wrong answer
   but counted separately as an admitted loss; the batch size in tokens is stated.
   `task_template=open_problems`, so the task text is not wrapped in "write a script, edit files"
   advice.
6. **Summary arm fixed**: the summary cap is max(4,096, max_tokens), with one retry with thinking off
   if the reply is empty. A summary also runs right before a call if the context is already over the
   limit, so the summary arm is not stopped by the plain arm's final-turn rule.
7. **max_tokens 16,384** (8,192 cut 5 of 12 trials).
8. **More diagnostics per trial**: correct / blank / stale (an older value) / wrong. Items delivered,
   items seen whole in the context, items cut by the harness, broken pipes. Turns cut at
   max_tokens. For kv, each missed key gets a cause: *never* in any context, *dropped* (in an
   earlier context, not the last), or *copy* (in the last context but answered wrong).

**Dropping old thinking** (added the same night): the served template re-sends all earlier thinking
(about 10 % of a typical call, up to 56 % on long tasks). Arms At, B32t, C32t, E32t repeat A, B32, C32,
E32 with `preserve_thinking=false` on every call and earlier reasoning stripped from the history, so the
budget counts what is actually sent. `core` runs them after the first five arms (≈ 5 h in total).
Reading: a thinking-dropped arm is "no worse" if, on both seeds, it is within 1 key of its parent arm.

**Arms** (`second-comparison.sh` header): A = no management, no budget, memory-only (the lossless
baseline). B32 / B131 = self-editing at 32,768 / 131,072, memory-only. C32 / C131 = summary at
75 % at the same budgets, memory-only. D32 = self-editing with notes. E32 = no management with
notes, 32,768. The 131K arms run only where the task is at least 0.8 × 131K (the 120K and 180K
sizes); below that there is no pressure.

**Cost** (estimated at 3,000 tokens/s reading with no prefix caching, 75 tokens/s writing):
full matrix ≈ 20 h (2 seeds; arm A at 180K and the 131K arms are the expensive cells, and reading
above ~150K is slower than 3,000/s, so those numbers are optimistic). Cheaper subsets, in the
order to keep:
- `SUBSET=core` ≈ 3.0 h for arms A, B32, C32, D32, E32 (≈ 5 h with At, B32t, E32t added after them):
  120K only; ledger with both seeds and kv with seed 0. This answers the central question: is self-editing at 32K lossless when the state is
  small, compared with keeping everything?
- `SUBSET=quick` ≈ 1.0 h: 60K, seed 0, both tasks, arms A, B32, C32, D32, E32 (a sanity pass).
- Add next, in this order: 180K for ledger (A, B32, C32); then B131 / C131 at 180K; then kv seed 1;
  then the rest.

**How to read the results (fixed now, before the run)**

1. A trial counts only if `ended_by` is `submit`, `submit(final)` or `budget_stop` and its rule is
   not VOID. An invalid trial is fixed and re-run, never read. A "suspect" rule means reading that
   trajectory before using the cell.
2. Arm A is the ceiling at each size. If A is below 1.0 on a task, the losses at that size are the
   model's own recall or copy errors (check `lost_copy`). Other arms are judged against A, not
   against 1.0.
3. **Ledger, self-editing passes** at a size if both seeds score ≥ A's score at that size (and
   ≥ 0.958, at most one miss). It **fails** if either seed is 2 or more counters (≥ 0.083) below A.
   Anything in between is "unclear".
4. **Summary vs self-editing** (same budget and task): a difference counts only if both seeds point
   the same way and the gap is at least 3 keys (0.125).
5. **kv memory-only at a budget** is expected to lose data (32K cannot hold 120K of values). The
   numbers that matter are the fraction kept, compared with budget / size, and **honesty**: a
   strategy is honest about loss if `wrong + stale == 0` (every miss is a blank). Any confident
   wrong value is reported as a failure of honesty, however high the score.
6. **Notes arms (D32, E32)** measure external memory. They pass at 1.0 on both seeds. If not, the
   loss is classed by `stored`: below 1.0 means a saving failure (e.g. the pipe race); 1.0 means
   it was saved but read back wrong.
7. Cost is compared only between arms with equal reward: prompt tokens read, calls and wall time.
   No speed claim comes out of this test.

## Second comparison: the first two trials, read closely (ledger, 121K tokens, memory-only, seed 0)

Results: `/mnt/fast-ai/bench-results/context-clm-second-20261005/client/runs/` (prefix cache on).

**A, keep everything, no budget (24/24).** The model did not keep the raw batches. After the
first batch, it piped every `next` into an inline Python script (`next | python3 -c '…' '<state
JSON>'`). The script applied the updates and printed only the item header, the bare updates
(memos removed) and the new state. The memos, which are noise, never entered its context, and
the state table was carried as a JSON argument that the model re-typed in every command (~2,900
characters). This is allowed under memory-only: piping is permitted, no file was written, and
the grader found only harness files.

Its 89K written tokens are about 109K characters of thinking (~700-1,000 tokens per call) plus
about 69K characters of commands, mostly the state JSON copied again each call. Call 5 alone
wrote 12.3K tokens: it hand-transcribed batch 1.

Time: 1,571 s of the 1,589 s were model calls. The new prompt tokens to read were only about
0.17M (2.0M sent, 1.83M from the cache), about 1.5 minutes at 1,700-2,600 tokens/s. Writing
89K tokens took the rest: about 95 % of the time is writing. The rate fell from about 90 to 41
tokens/s as the context grew to 137K. The answers were computed by its inline script, not in
its head.

**B32, self-editing at 32,768 (19/24: 4 wrong, 1 "stale").**

Every loss came from one cause. The five missed counters equal the true state with batches
2, 3, 4, 5 and 7 left out, and all 24 answers match that simulation exactly. Those five batches
were delivered by `next` and then deleted by the harness's rollback-and-retry, and a delivered
item cannot be fetched again. No arithmetic slip, no edit and no copying error lost anything.
The "stale" one only happens to equal an older value.

How it got there:

- **Calls 1-44 (the thrash).** The first call wrote 14,425 tokens of planning (55,800
  characters). The template keeps re-sending that thinking, so batch 1 (6.9K) already left the
  context near 27K of the 30,720 limit, and the "urgent" nudge fired at once. Then came:
  - many turns of 4-16K thinking, several cut at max_tokens with no command (10 calls of 10K
    tokens or more);
  - two of its own edit scripts crashing, because their marker text also appears inside the
    mirror (the mirror contains its commands);
  - the four `next` calls for items 2-5, each rolled back with its batch;
  - item 7, delivered and rolled back as well.

  All 20 rollbacks (56 turns dropped) were the harness cutting the newest turns after a huge
  thinking turn or a delivered batch had pushed the context over the limit. No edit was ever
  refused. The 22 nudges were mostly the "persistent" urgent nudge: it nags whenever the free
  room is less than twice the last tool output (a 6.9K batch), so it said "about to be cut off"
  at 55 %.
- **Calls 45-86 (the settled loop).** Then it found the right pattern by itself:
  - a state block between its own markers (`@@STn@@ … @@STnE@@`);
  - after each `next`, one inline Python script reads the 136 new lines from the mirror by
    code, applies them to the state, rewrites the block, and replaces the batch with one line;
  - about 650 tokens written per batch.

**The 21 real edits:**

| edit | what it did |
|---|---|
| 1 | built the state block from batch 1 |
| 1 | replaced the 55.8K-character planning turn with a summary |
| 2 | folded item 6 and removed its leftover script turn |
| 2 | cut everything after the state block |
| 14 | the per-batch "apply and delete" edits for items 8-19 |
| 1 | a final trim |

**Cost.** It wrote 233K tokens: 213K in calls 1-44, 20.5K in the settled loop. Only 365K of
1.25M prompt tokens came from the cache, because every edit rewrote the state block near the
top, so everything after it was read again.

**Rule.** The 17 "suspect" commands are false positives of the summary script's check: they
open the mirror for writing and contain the text `| memo:` inside a regular expression. The
grader found no file holding stream data. The new files were the mirror, the shell-state
files and Python bytecode caches. The trial is clean.

## Improved self-editing agent (proposal; `scripts/context/clm_improved.py`, not wired in yet)

Built only from what B32 and A showed:

1. **A delivered item is never rolled back.** Rollback may drop the turns after the newest
   delivered item, but never that item. The model is asked to fold it in; going over the
   budget for that one turn is allowed and recorded.
2. **Room check before a destructive read.** A `next` (configurable) is not run when the
   context plus the largest item seen so far plus 4K would not fit. The model gets "NOT RUN:
   fold first".
3. **Earlier thinking is dropped** (as in arm B32t). It caused the first overflow.
4. **A pinned state file owned by the harness.** `/tmp/.live_ctx/STATE.txt` is shown as the
   last message of every call, so the transcript stays almost append-only and the prefix cache
   works. The harness checks its format and size after each edit and restores the last valid
   version if an edit breaks it, so no marker can collide with command text. The memory-only
   grader must then exclude STATE.txt like the mirror: a one-line change in GRADE_PY_V2 before
   the next task generation.
5. **A short protocol in the prompt:** fold every item right after it arrives, by code, then
   delete the raw turn.

**Weighing the listed ideas against the evidence:**

| idea | verdict |
|---|---|
| (a) pinned state block | supported; the model invented it, the harness should own and validate it (item 4) |
| (b) edit only at batch boundaries | supported for cache reuse; with the state shown last, deleting the just-folded batch touches only the tail |
| (c) archive of removed spans | not supported; no loss came from pruning, so it is left out (it would be its own rule class) |
| (d) drop old thinking | supported; it caused the first overflow |
| (e) thinking cap per turn | supported by the evidence (10 calls of 10K tokens or more), but the server only has max_tokens, which cuts the action too |
| (f) harness decides WHEN, model decides WHAT | partly; the timing was not the problem, the rollback of a delivered item was. The room check (item 2) is the harness's "when" |

For (e), a real cap would cut the thinking at T tokens, close `</think>`, and continue with
vLLM's `continue_final_message`. This is possible with this server but untested, so it is not
implemented.

**What the paper's harness already does:** nudges at 25/50/75 %, the adaptive persistent nudge,
rollback-and-retry (the loss mechanism here), the editable mirror, free edit turns, and capping
the newest output. **What it does not do:** a validated state, protection of a delivered item,
a room check, dropping or capping thinking, an archive.

**First test once the stub checks pass:** B32 against this agent ("B32i") on ledger 120K, both
seeds.

**Pass rule:** B32i passes if both seeds are within 1 key of A, with no delivered item lost
(`delivered == seen_whole`).
