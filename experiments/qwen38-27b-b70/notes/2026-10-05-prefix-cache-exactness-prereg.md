# Reusing the unchanged start of a prompt, exactly: test written before any run (2026-10-05)

Addendum to `2026-10-05-context-window-prereg.md` (track 3) and experiment E0 of
`2026-10-05-context-research-review.md`.

## The question, in plain words

If the model is to edit its own conversation, each turn must not re-read the whole prompt. The server can keep what it
already read (the "prefix cache") and only read what changed. Our rule is that an answer served this way must be
**exactly** the answer a fresh server gives to the same request: same tokens, same scores, bit for bit. Our published
servers keep this feature off because a probe on 2026-09-12 saw cached answers differ from fresh ones on prompts where
two tokens are nearly tied.

## Why they differed, and why they should not have to (from reading the server's source, R310/R314)

- The server reads a long prompt in pieces. With the cache **off** it cuts pieces of 4,096 tokens from the start.
  With the cache **on** (`--mamba-cache-mode align`) it stores the recurrent layers' running state only at the end of
  a piece that lands on an 832-token boundary, cuts every piece to end on such a boundary, and a later request can
  only resume at one of those stored boundaries.
- The stored state loses nothing: the recurrent state is kept in 32-bit floats (the model's config asks for it), and
  the short convolution memory is the last three 16-bit inputs, which are exactly what a one-pass read would use.
- What differs is the **size of the pieces**. Several of our kernels give slightly different rounding for a
  different number of rows (the FP8 matrix multiplies, the attention kernel, the convolution's tiled path), so 4,096-
  token pieces and "resume at block 7, then 4,096 more" are different arithmetic. The 2026-09-12 difference was
  cache-on versus cache-off with different piece sizes, not a damaged cache.
- **The fix by construction:** make every piece exactly one block (832 tokens). Then a fresh server and a resumed
  request make the same calls, with the same sizes, on the same stored numbers, from the resume point on; everything
  before the resume point was itself computed by those same calls when it was first read. The cache-off server cuts
  the same 832-token pieces, so it serves as the fresh reference.

## Setup

Image R314, two cards, one request at a time, no drafting (`--mtp 0`), greedy. Two servers, one after the other (only
one two-card server fits): first the reference with the cache off, then the cache server. Same flags otherwise:

    run-fp8-tp1-server.py --tp 2 --image <R314> --max-model-len 33024 --batched 832 --mtp 0 --keep --out .../control
    run-fp8-tp1-server.py --tp 2 --image <R314> --max-model-len 33024 --batched 832 --mtp 0 --keep --out .../cache \
        --prefix-cache align

Check `server.log` says "Setting attention block size to 832 tokens" on both. If it says another number, `--batched`
must equal that number.

Client `scripts/qwen38-fp8-prefix-cache-exactness-probe.py`: `--save control.json` against the reference server,
then `--compare-with control.json` against the cache server. Prompts: the eight long-prompt-suite prompts and number
ledgers of 3K, 10K and 30K tokens. For each prompt: (a) first read; (b) the same again; (c) the last 200 tokens
replaced; (d) a new paragraph added at the end; (e) 300 tokens deleted from the middle; (f0) the prompt cut to end
just before a block boundary. 16 answer tokens each, with the top 5 scores of every answer token.

One extra case, (f), the shape of a real next turn: f0's prompt, then f0's own answer, then a new message. Here the
reused block contains tokens the server produced while *writing* the answer. Writing a token is different arithmetic
from reading it as part of a prompt, so the cached copy of that block is not what a fresh server would compute.
**Prediction: (f) can differ.** It is recorded but is not part of the pass rule. If it does differ, editing
conversations exactly needs one more change: the cache must only keep blocks that were read, not written (the turn
then re-reads the previous answer, which is usually short).

## Recorded

For every case: tokens reused from the cache (the server reports it), the expected reuse from the block arithmetic,
time to the first token with and without reuse, the answer's token ids and top-5 scores on both sides, the first
position where they differ and the largest score gap.

## Rules

- **Pass:** every case (a) to (e) and (f0), on all eleven prompts, gives the same tokens and the same top-5 scores as
  the fresh reference, bit for bit, **and** the cases (b) to (e) really were served from the cache (reused tokens
  above zero where the prompt is long enough; (e) on the shortest prompts can legitimately reuse nothing).
- **Fail:** any single difference in a ruled case. Then the first differing case says where to look (its reuse point
  and first differing token); nothing is published.
- (a) compares the cache server's first read with the reference: it shows that turning the cache on changes nothing
  by itself.
- Speed is reported as measured (one server each, a first look). The cost of exactness is that prompts are read in
  832-token pieces instead of 4,096; expected 5 to 15% slower on a first read, unmeasured. The saving is everything
  before the reuse point (about 2,000 tokens per second of prompt not re-read).
- No server is left running.

## Not covered by this test

Several requests at once (the step mix changes the row counts), drafting on (the drafter adds its own cache and moves
the last reusable block back by one), the one-card server (needs `--gdn-head-groups 2` for repeatable prompt reading
before any of this applies), and caches saved to disk.

## Result, first run (03:00 EDT): every compared answer identical; the ledger prompts were not compared

Two fresh two-card servers on R314, drafting off, prompts read in 832-token pieces on both: first without the cache
(reference), then with it. Data: `data/2026-10-05-context/prefixcache/`.

- **56 of 56 compared cases gave the same tokens and the same top-5 scores as the fresh reference**, bit for bit:
  the eight suite prompts, seven cases each, including the chat next-turn case (f) that I had predicted would differ.
- **Reuse works and is fast:** a repeated 8,300-token prompt starts answering in 0.04 to 0.14 s instead of 2.7 s.
- **Why the next-turn case was exact:** the server reused one block *less* than the shared text in all eight (f)
  cases. The block that was finished while the model was writing its answer was not reused, so the predicted
  exception never came into play. Whether that is a rule of the engine or luck is being read from its source
  (`notes/2026-10-05-prefix-cache-reuse-rules.md`); until then it is "exact in test", not "exact by construction".
- **Reuse is patchier than the block arithmetic says.** A prompt with 64 tokens removed from the middle reused
  nothing in all eight cases, and a changed ending reused nothing whenever the change reached back past the last
  full block. The answers were still identical; the cost is speed. This matters for self-editing: an edit in the
  middle of the context seems to throw away the whole cache, not just what follows the edit. Same source reading.
- **The rule as written is not met yet:** the three ledger prompts (3K, 10K, 30K) were not compared. My mistake: I
  edited the ledger builder for another probe while this test was between its two servers, so the second server was
  asked different ledgers than the first. The probe refused to compare them, which is what it should do.
- Next: the same test with drafting on, all eleven prompts (the builder is no longer being touched). Drafting is
  how the lane is actually served, so that is the result that decides whether the cache goes into later runs.
