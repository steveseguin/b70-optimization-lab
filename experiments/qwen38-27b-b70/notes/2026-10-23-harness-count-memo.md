# The harness counts the whole history four times a step: an exact memo, and campaign 58 to measure it (2026-10-23)

**Written 02:53 EDT, before any run. CPU only so far.**

## Where a 2M hostile seed's time goes

Campaign 57's time budget (seed 0, `calls.jsonl` of the proxy and `timing.json` of the client; wall between the
first and last main call 4,800 s):

| Part | Seconds | Share |
| --- | --- | --- |
| Model, main calls (1,476 upstream calls) | 2,603 | 54 % |
| Model, notes calls (231) | 1,112 | 23 % |
| Tool runs (`bash_s`, 1,320 steps) | 132 | 3 % |
| Proxy and client around the calls (handle − upstream, llm_s − handle) | 146 | 3 % |
| **Between steps, in the client** (wall − llm_s − bash_s) | **807** | **17 %** |

Campaign 55 seed 0 (thinking on): the same part is 898 s of 5,524. The between-step time grows with the run: the
gaps between consecutive main calls that hold no notes call average 0.20 s over the first 250 calls and 1.24 s
over the last 250 (c57 seed 0), uncorrelated with the request size (the proxy's view is a constant ~11K tokens)
and with the reply size. So it is work proportional to the whole retained history, which for the plain agent is
the entire 2M-token stream (2,642 messages, 10.4 MB of JSON at the end).

## What the client does there

`clm_harness/clm_agent/harness.py` (upstream CLM code, unmodified) at every step: `tk.record` (a snapshot of the
full history: tiktoken count + a 10 MB write), the budget gate (disabled at `CONTEXT_BUDGET=0`), `tk.annotate`
(another full count, read and rewrite of the snapshot), `_snap` (count + write again) and, after the reply,
`budget.calibrate` (a fourth full count). On the final history one `count_tokens` is 0.25-0.36 s and one write
0.03 s, so the counting is the cost: four encodes of 2M tokens a step. The snapshot files are 6.4 GB a seed
(1,322 files; the campaign disk holds 43 GB of them, which is what filled it before campaign 54b).

## The fix: an exact per-message memo (`clm_baselines.py`, `COUNT_MEMO=1` by default)

Importing the lab's agent module replaces `tokens.count_tokens` with a memo: a message's count is reused only
when every text piece the upstream `_iter_text` yields for it (content, reasoning, tool-call names and
arguments) is the very same string object as at the last call; strings are immutable, so the encoder would
return the same ids. Anything else is re-encoded with the upstream code. The numbers are therefore the upstream
numbers; nothing written changes. `COUNT_MEMO=0` restores the upstream function.

Checks (receipts under [data/2026-10-23-count-memo](../data/2026-10-23-count-memo/)):
- `count_memo_check.py` on campaign 57 seed 0's final history (2,642 messages): the memo equals the upstream
  count on 60 random prefixes, the full list, a replaced content string, replaced tool-call arguments, an
  inserted, a removed and a reordered message, list content and an empty list (69 cases). One simulated run
  (four counts of every prefix in turn, 2,642 steps) takes 14.6 s with the memo; the upstream path is
  estimated at 1,250 s from 12 timed prefixes.
- `count-memo-check.sh`: one plain-agent Harbor job on a small sparse-memory task against the recording fake
  server, `COUNT_MEMO=0` and `=1` under one hash seed: all 26 request bodies, the trajectory, usage, the
  grader's output and all 28 context snapshots byte-identical.

Not changed: the duplicate snapshot writes (the top-of-step file is overwritten by the next step's sent
snapshot, and the annotation with it); that is 0.1-0.2 s a step at the end of a run and the on-disk result of a
deferred write is harder to keep identical in every exit path, so it stays as a later lever, with the 6.4 GB.

## Campaign 58: campaign 55 again with the memo, both seeds, registered 02:53 EDT (before any run)

Arm **K32V** on ctxkeeper **1.3.0** (the release candidate), queue `QUEUE58.txt` (`K32V hostile2mk 0 14400`, then
seed 2), unit `ctx-campaign58`, `RUN=c58`, `COUNT_MEMO=1` in the environment (the default), everything else as
campaign 57's launch. Nothing else runs on this host; cards empty before and after (`RESTORE=0`).

**Predictions:**
- **Nothing the model sees changes:** seed 0's NOTES versions identical in text to campaign 55 seed 0's (153
  versions, which campaigns 52, 53 and 55 reproduced byte for byte) and 423/423 with 0 wrong STATE lines; seed 2
  419-421/423 with at most 4 wrong lines (campaign 55: 420 and 2; campaign 54d: 421 and 4); 16/16 audits and
  every forgery target kept on both seeds; audits PASS.
- **Time:** between-step time (gaps between main calls holding no notes call) at most 150 s a seed (campaign
  55: 1,000 s; campaign 57: 929 s); wall 76-82 min for seed 0 (campaign 55: 92.7) and 77-84 min for seed 2
  (93.2), a 10-16 % cut; model time unchanged within 5 % (main 2,600-2,700 s, notes 1,650-1,900 s a seed).
- **Not claimed:** anything about the model, the keeper or the answers; this is harness time.

**Decision:** both seeds as predicted → the public 2M wall figures are re-quoted from campaign 58 with the memo
named as the reason, and the memo stays the lab default. A seed with a different NOTES text or score → the memo
is withdrawn from the default (`COUNT_MEMO=0`) until the difference is explained, since the checks above say
there can be none.
