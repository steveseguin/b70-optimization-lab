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
