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

## What the engine source says, and the second test, written before it runs (03:20 EDT)

The reuse rules were read from the R314 engine source (`notes/2026-10-05-prefix-cache-reuse-rules.md`). In short:

- The engine keeps the recurrent layers' state at only one point per prompt (its last full block) plus the point
  where a new prompt left the cached text. That is why an edit in the middle reused nothing the first time.
- **Two holes in "exact by construction", both real:** (1) blocks finished while the model is *writing* are cached
  as well, so a third turn of a conversation can be served attention data made by the writing kernels instead of
  the reading kernels a cold read uses (the first run had only two turns, so it never met this); (2) with drafting
  on, the engine switches to keeping the state at every block, including blocks reached while writing, and that
  costs four times the memory per token of context.
- So the first run's "56 of 56" stands as measured, but the cache as shipped is **not** exact by construction.

**The fix under test: `overlays/b70-prefix-cache-exact`** (CPU test `tests/test_b70_prefix_cache_exact.py`).
It changes what is kept, never what is computed: nothing past the end of a prompt is ever cached (the next turn
re-reads the previous answer as prompt, at reading speed, and caches it then), the state is also kept one block
before each prompt's last full block (where a hit lands when drafting is on), and a sparse periodic state every
6,656 tokens (eight blocks) lets an edit in the middle resume from just before the edit. Every cached block is then
the product of the same 832-token reading piece a cold read would run.

**Test** (`MU_MODE=prefixcache MU_MTP=1 MU_PC_EXACT=1`, R314, two cards, drafting on): reference server without the
cache, then the cache server with the overlay, both reading in 832-token pieces. Eleven prompts (eight suite prompts,
ledgers of 3K, 10K, 30K), nine cases each: the seven from before plus **e2** (the middle edit sent a second time) and
**g** (a third turn, so the shared text holds two answers the server wrote). 48 tokens generated per case.

Scores are not compared in this run, only token ids: asking the drafting server for scores makes it compile a
scoring routine that needs over a gigabyte of host memory for a few seconds, and this host does not have it (three
servers were stopped by the memory guard tonight before I found that; `context-memsample-20261005`). Token ids
over 48 tokens on 99 cases is a weaker check than scores; a scores run without drafting follows if this passes.

**Rules.** Pass: all 99 cases give the reference's tokens, including f and g, and cases b, c, d, e2, f, g are
served from the cache (reused tokens above zero where the prompt has at least two full blocks before the change).
Any difference is a fail and the first differing case is the lead. Also recorded: how much is reused after the
middle edit the first time (the periodic state should give a hit now), and the time saved.

## Result of the second test (03:32 EDT): pass, 99 of 99, drafting on

Two fresh two-card servers on R314 with drafting on, both reading in 832-token pieces: the reference without the
cache, then the cache server with `b70-prefix-cache-exact` and a periodic state every 6,656 tokens.
Data: `data/2026-10-05-context/prefixcache-exact-mtp/`.

- **All 99 cases gave the reference's tokens**: eleven prompts (the three ledgers included this time), nine cases
  each, among them the second turn (f) and the third turn (g) of a conversation, where the shared text holds
  answers the server wrote. The server log confirms the add-on stopped caching at the end of each prompt.
- **The cache was used** in 10 of 11 prompts for repeat, append, repeated edit, second turn and third turn (the
  eleventh is 1,700 tokens, too short to have a reusable block once drafting moves the reuse point back by one).
- **An edit in the middle now reuses the first time on a long prompt:** the 30K ledger with 300 tokens removed at
  the half-way point resumed from token 13,312 (6.7 s instead of 11.3 s); sent again it resumed from 28,288 (0.7 s).
  On prompts shorter than about 14K the first edit still reuses nothing, because the first periodic state is at
  6,656 and the reuse point is one block earlier; the interval is a memory-for-reuse dial.
- **Time:** over all cached cases the wait for the first token fell from 228 s to 69 s. A repeated 30K prompt
  starts in 0.8 s instead of 11.4 s.
- **Costs, measured:** reading in 832-token pieces is slower when nothing is reusable: 30K cold in 11.4 s
  (2,620 tok/s) against 9.8 s (3,060 tok/s) in 4,096-token pieces, about 14 %. Reuse with drafting lands one block
  (832 tokens) earlier than without. Each kept state costs as much memory as three blocks of context.
- **What this is and is not.** By construction: every cached block was made by the same 832-token reading piece a
  cold read runs, on the same earlier text, and nothing made while writing is ever stored. By test: token ids on 99
  cases, up to 48 tokens each, one user. Not yet done: a scores-level comparison (needs host memory this server
  does not leave), several users at once, the one-card server, and prompts beyond 30K.
- **Decision:** the context experiments from here on run with this cache (interval 13,312 for the long ones, so a
  180K conversation and its states fit the pool).

## Does the cache change the standard gate or the write rate? (09:42 EDT)

Asked by the owner: "did token decode rate change as a result of this?" Controlled check, `MU_MODE=pcgate`: two
fresh two-card servers, drafting on, the shipped 33K window, the standard 12-prompt strict gate run twice on each
(the second pass on the cache server reads its prompts from the cache). Data: `data/2026-10-05-context/pcgate/`.

| Server | Gate, first pass | Write rate | Gate, second pass | Write rate |
| --- | --- | ---: | --- | ---: |
| Cache off, 4,096-token pieces (as shipped) | 12 of 12 exact | 88.5 tok/s | 12 of 12 exact | 88.7 tok/s |
| Cache on, `b70-prefix-cache-exact`, 832-token pieces | 12 of 12 exact | 89.6 tok/s | 12 of 12 exact | 89.7 tok/s |

- **The write rate did not change** (a one percent difference between two servers is inside the usual spread).
- **The answers did not change:** both servers match the standing reference on all twelve prompts, on a cold pass
  and on a pass served from the cache.
- One server each; a first look, consistent with the cache only deciding which blocks are kept.
