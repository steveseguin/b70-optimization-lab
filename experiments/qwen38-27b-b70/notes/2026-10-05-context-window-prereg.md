# Context length: plan and first test, written before any run (2026-10-05)

## The owner's question, in plain words

Can the 27B have an effectively unlimited context, without quantizing the cache or any other numeric loss? Ideas on
the table: let the model edit its own context like a file (the Context Language Models paper, arXiv 2609.37725), a
second card or the CPU doing the pruning, context kept on disk, a small CPU model that removes wasteful spans, and
stopping early when the answer is just a decision. Trimming and editing context is allowed for this work; numeric
loss is not.

## What is already true on this hardware (checked 2026-10-05)

- The model has **262,144 trained positions** (`max_position_embeddings`, `model_max_length`).
- The two-card server's 16-bit cache pool is **268,177 tokens** at the shipped memory setting. The 33,024-token
  window is a packaging choice. One card: 43,885 tokens.
- So the first step needs no new idea: open the window and measure. That is lossless by definition.

## Four tracks

1. **A bigger exact window.** How far can one user go on two cards, how fast is reading and writing at each length,
   and does drafting still give exactly the no-drafting answer there?
2. **Self-edited context ("context as a file").** The paper's zero-shot harness against our server at 32K, against
   a summarising baseline and against simply using the bigger exact window. What is exact here is the arithmetic;
   what the model chooses to keep is its own judgement and is reported as that.
3. **Context that is cheap to edit, exactly.** No stale-cache reuse. Layouts that keep the unchanged prefix long,
   so an edit only costs re-reading what follows it; cache save and restore to host memory or disk between turns.
4. **One-step answers.** When the answer is one of a known set, read it from the first step instead of decoding it.
   Exactly equal to constrained greedy decoding when the choices start with different tokens.

## First test (track 1), `MU_MODE=longctx`

Two fresh two-card servers on image R314 with `--max-model-len 262144`, one with the shipped depth-5 drafting and
one with drafting off. Client `scripts/qwen38-fp8-long-context-probe.py`: a ledger of numbered records with random
codes, sized to 8K, 30K, 60K, 120K, 200K and 250K tokens, then a question asking for six codes spread from the
first record to the last.

**Recorded:** whether the server accepts each length; seconds to the first token and tokens read per second;
writing speed; whether all six codes come back exactly; the answer's token ids.

**Rules.**
- A length counts as usable only if the server accepts it and returns all six codes exactly.
- Drafting counts as exact at a length only if its answer is token-for-token the no-drafting server's answer.
  (By construction this holds where the verify-path census reaches: attention is covered to 6,524-token contexts
  directly and beyond that by the verify-rows overlay, which makes each verify row a plain decode call.)
- Speeds are reported as measured, one server each; this is a first look, not a published number.
- No server is left running.

## One-step answers (track 4), first test, written before it runs

On the long-window server after the ledger probe (the window size does not matter for this).
`scripts/qwen38-fp8-one-step-choice-probe.py`: 80 generated decision items of four kinds (yes/no, A to D, sentiment,
routing) with known answers. Three ways to answer the same chat prompt: (1) one step: `max_tokens=1`, the label is
the best-scoring allowed first token among the top 20; (2) thinking off, decode the label; (3) thinking on, reason
then answer (24 items).

**Recorded:** agreement of (1) with (2) and with (3); accuracy of each; seconds per item; tokens generated.
**What would make it useful:** (1) agrees with (2) on every item (it is the same decision, read earlier) and is
faster; how far (1) and (2) fall short of (3) shows what skipping the reasoning costs on these items. The items are
easy on purpose; this measures the mechanism, not the model.

## Self-editing, first comparison (track 2), written before it runs

The paper's benchmark is not released, so this uses a re-creation of its key-value store task
(`scripts/context/make_kvstream_tasks.py`): the agent receives batches of 100 `SET key = value` lines (each value 24
words), each batch is gone once delivered, and at the end it must return the values of 24 keys exactly. "Pressure"
1x, 2x and 4x is how many times the total input exceeds a 32,768-token budget. Scoring is exact match; no judge
model. It is not the paper's data, so scores are not comparable with the paper's.

**Arms, one two-card server (R314, drafting on, tool calling on, greedy, thinking on, a 262,144-token window so the
last arm fits):**
1. self-editing: the paper's own agent code and prompt, 32,768-token budget;
2. summary at 75 % of the budget (a Codex-style compaction written for this test);
3. no management at the same budget (stops when the context overflows);
4. no management and no budget: the whole task simply stays in the big window.

**Recorded per arm and pressure:** score (fraction of the 24 values exactly right), model calls, edits or
summaries made, prompt tokens read, tokens written, wall time.

**What it can and cannot show.** Arm 4 is the lossless baseline: nothing is ever dropped. Arms 1 and 2 show how much
is kept when the model has to choose. A 24-key answer needs about 800 tokens of values out of up to 130,000 tokens
of input, and the model does not know in advance which keys will be asked, so this task is hard for any pruning by
design; it measures faithful retention under pressure, which is the owner's worry about "lossy" context. One seed,
so differences of one or two keys mean nothing.

## Result of the first long-window test (01:45 EDT)

Two fresh two-card servers on R314 with a 262,144-token window, full 16-bit cache. The cache pool is 369,670 tokens
with drafting and 430,606 without. Data: `data/2026-10-05-context/longctx/`.

| Prompt | First token after | Reads | Writes, drafting on | Writes, drafting off | Six codes recalled | Drafting = no drafting |
| ---: | ---: | ---: | ---: | ---: | --- | --- |
| 7,848 | 2.4 s | 3,288 tok/s | 118 tok/s | 33 | see below | yes |
| 29,865 | 9.8 s | 3,059 | 88 | 31 | see below | yes |
| 59,836 | 22 s | 2,704 | 61 | 28 | **6 of 6** | yes |
| 119,720 | 55 s | 2,187 | 38 | 25 | **6 of 6** | yes |
| 199,588 | 114 s | 1,745 | 31 | 21 | **6 of 6** | yes |
| 249,599 | 161 s | 1,552 | none | none | **0 of 6: the model ended its answer at once** | yes (both empty) |

- **The window opens with no loss.** The server accepts the model's full 262,144 positions; nothing is quantized.
- **Recall is exact to 200,000 tokens** in this test: codes from the first record to the last, right every time.
- **At 250,000 the answer is empty** on both servers: the first token is the end-of-turn token. Whether that is the
  model near its limit or something in the stack is not known yet; the edge between 200K and 250K is the next probe.
- **The two short rows are a flaw in my probe, not a recall failure.** At 8K and 30K the model chose to reason out
  loud and the 96-token allowance ran out after three codes, all three correct. Rerun with a larger allowance.
- **Drafting gives exactly the no-drafting answer at every length**, as the kernel censuses predict.
- **The cost of length:** reading slows from 3,300 to 1,750 tok/s at 200K, so a cold 200K prompt takes about two
  minutes before the first word. Writing with drafting falls from about 90 to 31 tok/s. A long window is usable,
  but every turn that re-reads it is expensive, which is why the exact prefix cache matters.
- The one-step decision test did not run: its first request was dropped by the server without an error message.
  **Cause found (02:55 EDT): the host memory guard stopped the server, and my test client set it off.** With the
  full window and drafting, the server leaves about 2.4 GiB of host memory free; the guard stops the server below
  2.0 GiB. The choice client imported `transformers` to load the tokenizer, which takes about a gigabyte for a
  moment (`tp2-long262144-mtp5/MEMORY-GUARD.json`: "available host memory fell to 1.84 GiB", four seconds after the
  client started). The server without drafting had 3.6 GiB free and was not touched, so the empty answer at 250,000
  is a separate matter. Fix: the three probe clients now load the tokenizer with the small `tokenizers` library
  alone. Rule for this lane: **next to a full-window server, nothing heavy runs on the host.**

## Second long-window test, written before it runs (02:55 EDT)

`MU_MODE=serve_run` with `scripts/context/edge-and-choice.sh`, one two-card server, R314, 262,144 window, drafting on.

1. The one-step choice probe on the fresh server (plan above, unchanged).
2. Recall asked the way an application asks: chat form, thinking off, 400-token allowance, at 8K, 30K and 120K.
   This repairs the two short rows of the first test.
3. Recall with ordinary words around the codes (`--style prose`: about forty common words after every record) at
   30K, 120K and 200K. The first test was a wall of codes; real context is mostly words.
4. The edge: one ledger, prefixes of it at 200K and 250K, then halving the gap until the longest prompt that answers
   all six codes and the shortest that does not are at most 1,600 tokens apart. Finish reason and first token ids
   are recorded at every length.
5. Both edge lengths again in chat form and in prose form.

**Reading rule.** If the edge is the same number of tokens for the wall of codes and for prose, and sharp, the
suspect is the stack (a size limit somewhere), and the next step is to find it. If recall fades gradually or the
edge moves with the content, it is the model, and the longest reliable window is the largest length at which all
forms answer everything, less a margin. The number that goes into the recipe is that window, not 262,144.
