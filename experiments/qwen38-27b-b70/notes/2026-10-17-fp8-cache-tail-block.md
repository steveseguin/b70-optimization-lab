# Exact cache: the block a drafting hit gives up (2026-10-17, context lane)

## Finding (from campaign 26's call log, CPU only)

Every agent call re-reads about 830 more tokens than it has to. In `calls-c26a-K32.jsonl` the cached count of each
call is exactly one block short of the end-of-prompt boundary of the call before it: the previous prompt P gives a
hit of `(floor(P/832) - 1) x 832` (5,313 -> 4,160; 7,103 -> 5,824; 16,022 -> 14,976 on a notes call), on all 162
main calls and all 20 notes calls. The edit probe of 2026-10-16 shows the same on a repeated prompt (30K: 28,288 of a
possible 29,120; 200K: 198,848 of 199,680).

A least-squares split of c26a's calls: K32 420 s of model time = 50 s fixed + 138 s reading (0.27 ms per uncached
token) + 232 s writing; notes calls are 146 s of it, almost all writing. 162 main calls x 832 tokens = 135K of the
481K uncached tokens, about 36 s (8 % of the run); more at long context, where re-reading a block costs more.

**Why the block is dropped** (R314 source, `kv_cache_coordinator.py`, the comment before the multi-module MTP check;
`scheduler.py` `_mamba_block_aligned_split`): when the drafter reads a prompt piece, the KV it writes at the piece's
last position is made from that position's hidden state and the *next* token, the first token of the following
piece. The block hashes up to the boundary do not cover that token, so the engine requires one more matching block
and then drops it. The recurrent state at the end-of-prompt boundary is kept (the "replay boundary"), but the hit
never reaches it; our exact-cache overlay keeps one more state a block earlier (`B70_PREFIX_CACHE_EXACT_BACK=1`) so
that the dropped hit has somewhere to land.

A second cost from the same rule: an edit just before the end of a long text resumes from the last *periodic* kept
state (every 13,312 tokens), not from the end-of-prompt state before the edit. At 200K, "edit@last" (four lines
203 tokens from the end) waited 15.8 s (cached 186,368, re-read 13,138 tokens) where 2.2 s was possible.

## Change: `b70-prefix-cache-exact` 0.2.0, `B70_PREFIX_CACHE_EXACT_TAIL=1` (off by default; off = 0.1.0)

The overlay records, for every block cached while a prompt is read, the token after its end (one token: a single MTP
module, `num_prefill_lookahead` 1). After the engine's own search it walks the attention blocks past the engine's
hit (hash-chain order, while every attention group holds them) and takes the furthest block boundary where every
recurrent-state group has a kept state and the new request's token after the boundary equals the recorded one.

Why that is exact by the same construction as 0.1.0: the request then reads only values a cold read of the same
prompt computes, in the same pieces. The hash chain covers every token before the boundary; the recorded token
covers the one after it (the only input outside the chain, the drafter's last slot); the kept state is a prompt-path
state (nothing past the prompt is cached); the request goes on from a block boundary in 832-token pieces, as a cold
read does. So answers, drafts, accepted counts and step counts stay those of a cold read. Never past the prompt or
`num_tokens - 1`.

Checked before any GPU run: compiles; installs in the R314 image on CPU (`register()` with both switches; the three
wrapped functions are in place).

## Test (registered 04:22 EDT, before any run): campaign 27, `scripts/longrun-campaign27.sh`

One server: campaign 26's (R314, piece 832, one sequence, MTP5, one-launch verify, every other flag the same) plus
`B70_PREFIX_CACHE_EXACT_TAIL=1`. Queue: K32 and K64 on the 240K rules stream, seed 0 (as c26a). Then on the same
server, the edit-cost probe at 30K / 120K / 200K (as 2026-10-16's K832 servers).

- **Must hold:** every call of both arms equal to c26a's in everything but time and cached count (messages, prompt
  tokens, written tokens, finish), 39/39 both; the server's prompt and generated totals equal to c26a's. The edit
  probe's 30 answers equal to `edit-K832.json`'s and `edit-K832b.json`'s. Any difference stops the change; it is
  traced call by call before anything else.
- **Predictions:** cached count one block higher on nearly every main and notes call after the first of a window
  (162 + 20 hits gaining 832 each); wall time K32 7 min 51 s -> 7 min 05 s to 7 min 30 s (5-10 % less), K64
  8 min 21 s -> 7 min 35 s to 8 min 00 s (4-9 %). Edit probe: repeats cached at the end-of-prompt boundary (30K
  29,120, 120K 118,976, 200K 199,680) and faster (200K 1.77 s -> about 1 s); edit@last at 200K cached 198,848 and
  about 2 s instead of 15.8 s; cold reads unchanged.
- **Decision:** all equal and both arms at least 4 % faster: adopt for the context lane (every context-lane server
  adds `B70_PREFIX_CACHE_EXACT_TAIL=1`). Equal but under 4 % on either arm: keep it off, record. Neither TP2 nor
  one-card package ships the prefix cache, so no package change follows.
