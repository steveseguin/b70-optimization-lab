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

## Result, campaign 27 agent arms (04:23-04:40 EDT, one server; `data/2026-10-17-context-campaign27/`)

| Arm | c26a | c27a (tail) | change | score | calls equal (all fields but time and cached) | calls gaining a block |
| --- | ---: | ---: | ---: | --- | --- | --- |
| K32 | 7 min 51 s | 6 min 58 s | **-11.3 %** | 39/39 | 182 / 182 | 181 (+150,592 cached tokens) |
| K64 | 8 min 21 s | 7 min 24 s | **-11.4 %** | 39/39 | 174 / 174 | 174 (+144,768) |

- **Exact:** every call equal to c26a's in messages, prompt tokens, written tokens and finish; the server's prompt and
  generated totals are equal after each arm (K32 1,932,094 / 30,313; after K64 5,210,811 / 60,132), only the cached
  count is higher (1,413,568 -> 1,564,160; 4,198,272 -> 4,493,632).
- **Every hit gained exactly one block** (832 tokens; the first call of the run has nothing to hit).
- **Faster than predicted** (5-10 % / 4-9 %). Model time per kind: main calls -16.9 % (K32) and -18.1 % (K64), notes
  calls -4.2 % and -2.5 % (they are mostly writing). The re-read block cost about 0.28 s a call, more than the 0.22 s
  estimated from the least-squares split.

## Result, edit-cost probe on the same server (04:50-05:01 EDT; `data/2026-10-17-context-campaign27/edit-c27a.json`)

All 30 answers equal to `edit-K832.json`'s and `edit-K832b.json`'s (`scripts/compare-edit-probe.py`). Wait for the
first token, 2026-10-16's K832 server -> this one (cached tokens in brackets):

| Request | 30K | 120K | 200K |
| --- | --- | --- | --- |
| cold read | 11.50 -> 11.27 s | 69.43 -> 69.38 s | 152.11 -> 152.20 s |
| same text again | 0.75 -> **0.37 s** (29,120) | 1.57 -> **0.88 s** (118,976) | 1.77 -> **0.78 s** (199,680) |
| four lines removed 203 tokens from the end | 0.66 -> 0.29 s | 1.49 -> 0.80 s | 15.80 -> **1.22 s** (186,368 -> 198,848) |
| edit at 90 % | 6.66 -> **1.35 s** (13,312 -> 26,624) | 10.94 -> 10.97 s | 30.61 -> 30.63 s |
| edit at 50 % / 10 % | unchanged | unchanged | unchanged |
| any edited text sent again | 0.66 -> 0.29 s | 1.50 -> 0.81 s | 2.21 -> 1.23 s |

- Repeats land on the end-of-prompt boundary, as predicted (29,120 / 118,976 / 199,680), at half the wait or less.
- The near-end edit at 200K resumes from the state one block before the edit (198,848) instead of the periodic one
  13,138 tokens back: 13x faster, inside the 5 s gate that 2026-10-16's study missed with every piece size.
- Not predicted: an edit just past a periodic kept state (30K at 90 %: the edit at about 26,800, a periodic state at
  26,624) also lost a whole interval to the dropped block; it now resumes at 26,624 (6.66 -> 1.35 s). Edits further
  from a kept state (120K and 200K at 90 %, and every 50 % / 10 % edit) are unchanged: they still resume from the
  last periodic state before the edit.
- Cold reads unchanged.

**Decision (as registered): adopt for the context lane.** Every context-lane server adds
`B70_PREFIX_CACHE_EXACT_TAIL=1` (campaign 27's runner defaults to it). The packages run without the prefix cache, so
nothing changes there. Agent-run figures measured before today (campaigns 1-26) are without it.

## Review finding and 0.3.0 (06:25-06:45 EDT, CPU only; the cards were down after the 06:23 fault)

A read-only Codex review of the tail switch (prompt and output in the session scratchpad; the review read the
overlay against the R314 sources) found one real hole, in the stock engine too: **only the hit's last block was
checked for the following token.** The engine keeps duplicate copies of a block hash (every drafting hit recomputes
the block it drops) and its lookup returns the first copy. When two texts agree up to a block's end and then differ,
there are two copies of that block whose drafter values at the last position differ (each made from its own next
token); a later request following the second text can be handed the first text's copy as an interior block. Codex
reproduced it on CPU with the stock lookup code: in a case with the first boundary's state evicted, stock hit 0, tail
hit 1,664 tokens containing the other text's block. Also unchecked before: a block whose prompt ended exactly at its
end (its drafter value comes from the sampled token) could sit inside a later hit.

What it can and cannot have changed: only the drafter's values (the main model's values in a block depend only on the
tokens up to it), so drafts, accepted counts and step counts, not answers (campaign 28c: no drafting gives the same
answers as depth 5 on all 182 agent calls). It needs a divergence exactly at a block boundary (about 1 in 832 per
divergence) followed by reuse of that block. No measured run is known to have hit it: campaigns 27 and 28 compared
every call with campaign 26 (no tail) in everything but time and cache counts, all equal.

**0.3.0** (same switch, `B70_PREFIX_CACHE_EXACT_TAIL=1`): every block of a drafting group in the hit must carry this
request's own following token(s): the engine's copy if it does, otherwise another copy of the same hash that does;
where none does, the hit stops at the furthest earlier boundary with a kept state, and with no boundary left the
request reads from the start. A block with no recorded token is never part of a hit. Tests:
`tests/test_b70_prefix_cache_exact_tail.py` (7 cases with stand-ins shaped like the R314 pool, coordinator and
manager; 4 of them fail on 0.2.0, all pass on 0.3.0); installs in the R314 image on CPU (all three wraps in place,
the pool's duplicate table found). A check against the image's real classes is being written
(`tests/r314_tail_engine_check.py`).

Before any public use of "exact cache" with drafting: a GPU run of 0.3.0 on the agent streams (calls equal to c27a's;
hit counts equal or a few blocks lower), after the reboot.

## Test of 0.3.0 (registered 06:38 EDT, before any run): campaign 28f, after the reboot

`scripts/run-20261017-after-reboot.sh` (refuses on the faulted boot; one bounded health probe first): c27a's server
(R314, piece 832, one sequence, MTP5, one-launch verify, tail switch) now with 0.3.0; queue `QUEUE28f.txt`: K32 on the
240K rules stream seed 0, then the repair task K32 2x (the re-measure of `2026-10-17-context-lane-public-remeasure.md`).

- **Must hold:** every K32 call equal to c27a's in everything but time and cached count (`compare-campaign-calls.py`),
  39/39; server prompt and generated totals after K32 equal to c27a's (1,932,094 / 30,313). Any difference stops
  0.3.0: traced before anything else.
- **Prediction:** cached counts equal to c27a's on every call (an agent conversation only grows, so no divergence at a
  block boundary is expected on this stream); the overlay's log shows `replaced 0` or a handful, `shortened` 0 or a
  handful; wall time within noise of 6 min 58 s. A lower cached count on a few calls would be the hole showing up.
- **Decision:** all equal: 0.3.0 replaces 0.2.0 for the context lane and the "exact cache with drafting" claim rests
  on it. Repair figures go to the owner as registered in the remeasure note.
