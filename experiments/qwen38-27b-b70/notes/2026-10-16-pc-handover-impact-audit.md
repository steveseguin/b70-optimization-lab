# Prefix cache + drafting hand-over defect: which results and public claims it could touch (audit, 2026-10-16)

Read-only audit, written 2026-10-16 evening while `b70-spec-resume-accepted` 0.5.0 is being validated (server
`/mnt/fast-ai/bench-results/fp8-r314-A0-20261016-pcorder/`, launched 19:04 EDT). The defect itself is described in
`2026-10-04-fp8-multiuser-prereg.md`, addenda of 2026-10-16 (Q3 result, 18:56 addendum, 19:04 amendment). Nothing
was started, stopped or edited for this audit. Times are EDT unless marked UTC.

## In plain words

**What the defect needs.** Three things at once: drafting on (`--mtp` above 0), prefix caching in align mode, and a
request that starts from a cache hit and is handed the server right after every earlier request has finished. In
the 2026-10-16 tests it showed up when requests were *already waiting in the server's queue* (Q3: all 64 sent at
once to a one-sequence server, 25-27 of 64 answers changed).

**A new piece of evidence from this audit: a client that waits for each answer and then sends the next one at once
did not trigger it.** The solo ("oracle") passes of Q3 and P1 send one request, wait for the whole answer, and send
the next 0.1-0.2 ms later (measured from `request_ended_epoch_s` / `request_started_epoch_s` in their result
files). 49 of each pass's 64 requests started from a cache hit, and all 64 answers of both passes are token for token
the answers of the cache-off server Q2 (64/64 and 64/64). The 99/99 test (one request at a time, no pause) agrees.
So the real exposure is traffic where a request **waits in the queue** while another runs, not traffic that is merely
fast. The stated window "or arrives within roughly one decode step of the previous request's end" is not supported or
ruled out by a direct test (see open question 1).

**What is affected.**

- **Public wording, regardless of numbers.** Several pages say the cache is exact without the condition that was
  tested (one request at a time, never a queued one), for example "a cached answer is identical to an uncached one"
  (`skindeep/context-reuse.html:163`). The ctxkeeper README on `main` says the drafting + prefix-caching bug is
  "since fixed" (`tools/ctxkeeper/README.md:225-226`); only part of it was fixed then (0.3.0), and the hand-over
  defect was still present. Those sentences need a limit or a correction whatever the re-checks show.
- **Every context-lane result from 2026-10-05 to now that used drafting**, apart from the runs with the cache off,
  ran on an affected server without the 0.5.0 fix. That covers the context research pages, LongMemEval, the
  1M/2M streams, all ctxkeeper release tests (1.0.0, 1.0.1, 1.1.0), the twelve-agent test and the one-card result.
  These results are **task scores**, not token identity.
- **But the logs show almost no queued requests in those runs.** Every affected server's log was scanned for the
  periodic "Running: N reqs, Waiting: M reqs" line (one every 10 s). A request was waiting only in: the first
  campaign-20 launch (three agents at once; voided at the time), ForgeCode's first two requests in c20d (a title
  request sent beside its first main request), the c21b S16 smoke test with background notes (voided at the time for
  "!!!!" garbage), and the two `Aw` trials of the 2026-10-05 sixth CLM run (both ended by `CancelledError` and not
  counted). The agent request logs of campaign 20 agree: only ForgeCode ever sent two requests within 0.5 s.
  **So no published score is known to be wrong, and the logs give no reason to expect one; it is not proven.**
- **Token-identity statements made on the affected profile** (99/99; the 12-prompt gate on a cached pass; the 120K
  cold repeat; "one request at a time is exact" from the campaign 23/24 checks; "MTP5 one-sequence is still exact
  against MTP0" from campaign 23b) were all measured one request at a time. They stand as measured, but they say
  nothing about queued requests, which is where the defect lives.

**What is not affected.** The neural.download packages (FP8 TP1 and TP2 `serve.py` and `compose.yaml` pass
`--no-enable-prefix-caching`); the multi-user results (2026-10-04/15 sweeps, 630 tok/s at 64 users: prefix caching
off); every run with drafting off (the first 56/56 prefix-cache test, campaign 23b, Q1, D2) or the cache off (the
2026-10-07 r4 / semantic / sparse / history / full-source studies, c24b P0/E0, Q2, D3); the Gemma and LFM2.5 lanes.

## How the runs were found

- Every `launch.json` under `/mnt/fast-ai/bench-results/` (depth 4) written since 2026-10-05, filtered to
  `rung.mtp > 0` and `rung.prefix_cache == "align"`. Overlay versions come from `overlay_sha256` (dist-info names).
- Queued requests: count of `Waiting: [1-9] reqs` lines in each of those servers' `server.log`. The line is printed
  every 10 s while the engine is busy, so a wait of under a few seconds can be missed; a seqs-1 server makes a queued
  request wait for the running one (seconds), so repeated queueing would show.
- Notes: `2026-10-05-*.md`, `2026-10-07-context-reverify-fixed-checker.md`, `2026-10-08-longmemeval-stage2-result.md`,
  `2026-10-10-context-16k-baseline.md` (campaigns 1-24c), `2026-10-12-context-campaigns-11-12-closeout.md`,
  `2026-10-14-ctxkeeper-1.0.0-release-closeout.md`, `tools/ctxkeeper/README.md`. There is no separate 1.0.1 or 1.1.0
  closeout note; both are recorded in the 16K note (campaign 20 summary; "ctxkeeper 1.1.0 released").

## Runs on the affected profile (drafting on + align prefix cache), 2026-10-05 to now

All: Qwen3.8-27B FP8, R314 image, `b70-prefix-cache-exact` 0.1.0, async scheduling (the R314 default). SRA =
`b70-spec-resume-accepted`, loaded with `B70_SPEC_RESUME_ACCEPTED=1` in every row; no row before the 19:04 A0 server
had 0.5.0. "Waiting" = log lines with a queued request / periodic stat lines. Server folders are under
`/mnt/fast-ai/bench-results/`.

| When (EDT) | Run (server folder) | Server | SRA | What was measured | Waiting | Published |
| --- | --- | --- | --- | --- | --- | --- |
| 10-05 03:27 | 99/99 prefix-cache test (`context-pcexact-mtp-20261005/tp2-pc-cache`) | TP2, seqs 1, MTP 5, 33K, interval 6,656 | 0.2.0 | token ids, 99 cases vs a cache-off control | 0/16 | yes: context-prefix-cache, -cache, -reuse, -results, -questions, research.html, docs/claims.md |
| 10-05 04:11 | recall by length (`context-recall-20261005`) | TP2, seqs 1, MTP 5, 262K, 13,312 | 0.2.0 | recall scores (708/720) + one 120K cold repeat (token ids) | 0/69 | yes: context-results L62-75, research.html |
| 10-05 09:36 | gate with the cache (`context-pcgate-20261005/tp2-pcgate-on`) | TP2, seqs 1, MTP 5, 33K | 0.2.0 | 12-prompt strict gate tokens, cold and cached pass; write rate | 0/18 | yes: context-cache L19-25, -results L81-82, -questions L29 |
| 10-05 04:32 - 10-05 23:43 | self-editing / CLM comparisons (`context-clm-second` ... `-fourteenth`, 12 servers), edit-cost probes (`context-probes`), calibration (`context-calib`) | TP2, seqs 1, MTP 5, 262K | 0.2.0 | task scores (ledger, prose, kv), times, edit cost | 0 except clm-sixth: 426/576, 15:33-16:44 = the two `Aw` trials, both void (CancelledError) | yes: canonical export 2026-10-06; context-results, -clm*, -files*, -self-editing, -summaries ... |
| 10-06 10:06 - 21:26 | Harbor plans A-E (`context-planA-a1` ... `planE-a1`) | same | 0.2.0 | task scores (120K-1M streams; quoted events 10/10, 24/24) | 0 | yes: context-results L27-55 |
| 10-06 21:50 - 10-07 00:06 | durable context v2 / r2 / r3 (`context-durable-*-20261007`) | same | 0.2.0 | durable-store pilot scores | 0 | unknown (not found on the pages) |
| 10-07 21:10, 21:33 | re-verification (`context-reverify-20261007`, 262K then 65K) | same | 0.2.0 | repeat of the published 480K and 1M quoted-events runs: 1M call-for-call identical; 480K differs by 1 call and 102 written tokens | 0/116, 0/405 | yes: context-results L50 |
| 10-07 23:17 - 10-08 13:33 | LongMemEval stages 1-2 (`context-longmemeval-20261007`, 4 servers) | TP2, seqs 1, MTP 5, 131K / 65K | 0.2.0 | 56-question scores, 27B as judge | 0 | yes: context-retention, context.html |
| 10-08 22:08 | long-running task (`context-longrun-20261008`) | TP2, seqs 1, MTP 5, 65K | 0.2.0 | task scores | 0/1,439 | unknown |
| 10-10 19:04 | 16K baseline round 1 (`context-longrun-20261010/server/tp1-pcexact-w26624`) | **one card**, TP1, seqs 1, MTP 5, 26,624 | 0.2.0 | probe scores, times | 0/596 | yes: context-distance |
| 10-10 23:08 - 10-11 03:27 | rounds 2-3, campaign 4 (`tp2-w65536`, `-r3`, `-r4`) | TP2, seqs 1, MTP 5, 65K | 0.2.0 | probe scores, times | 0 | yes: context-distance (L272 names the profile) |
| 10-11 05:39 - 10-12 02:08 | campaigns 5-10b (`context-longrun-20261011/server/tp2-w262144-c5` ... `c10b`) | TP2, seqs 1, MTP 5, 262K | 0.2.0 | keeper, proxy, RAG; 1M 228/228 | 0 | yes: context-distance, -results, context.html |
| 10-12 03:12 - 10-14 | campaigns 11-18 (`context-longrun-20261012/server/...c11` ... `c18`) | same | 0.2.0 | proxy 1M 220/228 and 226/228, repair marathon 40/40, freeagent 33 vs 55 min, 2M 351/382 | 0 | yes: ctxkeeper README, context-use, -distance, index.html#long-tasks |
| 10-14 20:39 - 21:46 | campaign 19, ctxkeeper 1.0.0 gate (`c19`, `c19b`, `c19c`) | same | 0.2.0 | G1 40/40/40, 7/7, 31 min; G2 4/4; G3 SDK | 0 | yes: README "Tested before release", context-use L102-103 |
| 10-15 01:08 - 14:18 | campaign 20, twelve agents, 1.0.1 (`c20` void; `c20b` ... `c20f`) | same | 0.2.0 | per-agent task scores, times | c20: 106/141 (three agents at once; void). c20d: 1/1,145 (ForgeCode, 06:26). Others 0 | yes: README, context-use #agents, index.html L1365 |
| 10-16 02:22 - 06:18 | campaign 21 (`c21`, `c21b` seqs 2, `c21c` seqs 1) | TP2, MTP 5, 262K | 0.2.0 | window sweep K08-K64, repair R12/R16/R48 | c21b: 20/376 during the S16 smoke (background notes; void for garbage). Others 0 | yes: README window bullet, context-use L89-97 |
| 10-16 06:23 | campaign 23 (`tp2-w262144-s2-xp-c23`) | TP2, **seqs 2**, MTP 5, exclusive prefill | 0.2.0 | concurrency check (23/24 differ), S16, K12f/K08f scores | 0/314 | yes: README `--inplace-fit` numbers, context-use |
| 10-16 08:29 - 12:04 | campaign 22 (`tp1-w26624-c22`, `-c22b`, `-c22c`) | **one card**, TP1, seqs 1, MTP 5, 26,624 | 0.2.0 | O1 39/39 15.8 min; O1r 40/40/40, 7/7, 21.1 min; LFM2.5 keeper arms | 0 | yes: README one-card and keeper bullets, context-use L38, L111, index.html L1366 |
| 10-16 15:10 - 16:23 | campaigns 24, 24b-L33, 24c (`...-mtp5-c24`, `c24b-L33`, `...-mtp5-c24c`) | TP2, seqs 2, MTP 5 (L33: 33K) | 0.2.0; c24c 0.3.0 | concurrency checks; K32 39/39 8 min 41 s; A32dp +8 % | 0 | yes: README L223-226, context-questions L34 |
| 10-16 16:29 - now | FP8 multi-user prefix-cache runs (`fp8-r314-sweep-mtp1-s2-20261016-pc`, `-D1-`, `-P1-`, `-Q3-`, `-T1-`, `-A0-`) | TP2, seqs 2 (Q3, T1, A0: seqs 1), 33K | 0.3.0 / 0.4.0; A0 0.5.0 | token identity against solo answers: the runs that found the defect | many (requests queued by design) | no |

Same period, **not affected** (drafting off or cache off): `context-prefixcache-20261005` (MTP 0, the first 56/56),
`context-clm-first-20261005` and `context-longctx-20261005` (cache off), the 2026-10-07 r4 / semantic / sparse /
history / full-source studies (cache off; context-results L45 notes zero cached tokens), `c23b` (MTP 0), `c24b-P0`,
`c24b-E0`, the 2026-10-15 sweeps, D2, D3, Q1, Q2.

## Question 2: can ctxkeeper / agent traffic hand the server back to back?

**Yes, by the code, many times per run.** Whether that matters depends on the open question above: by the lab's
data it is the *queued* case that breaks, and ctxkeeper by default never has two requests of one conversation in
flight.

What the code does (`/home/steve/b70-optimization-lab/tools/ctxkeeper/ctxkeeper.py`, 1.1.0 on `main`):

- One client request is handled in order under the conversation's lock: `with s.lock:` (1330), then the notes
  call if one is due, `self.keep(s, body.get("model"), messages, body)` (1336), then the main call
  `resp = self.upstream(first, s)` (1398). No sleep anywhere in the file.
- Immediate re-sends to the same server, each extending a prompt the server has just read (so a cache hit): the
  recall loop `for round_ in range(self.max_recalls + 1):` (1382; 8 rounds by default, 16 in the recipes); the
  empty-reply retry "Nothing for the client at all ... Asked once more without it." (1407-1412, on unless
  `--no-empty-retry`); the think-cap re-send (1401-1405, only with `--think-cap`); in-place notes re-asks
  `for attempt in (1, 2, 3, 4):` (1051), falling through to a full rewrite (two more attempts, 861-904).
- Two requests in flight only with options that are off by default: `--notes-async` (1635: no default) starts
  `threading.Thread(target=run, name="ctxkeeper-notes", daemon=True)` (1271-1274) right after a reply (1466-1470),
  plus a `--prewarm` call (1266); with `defer` the next main call goes on while it runs (1290-1292). On a
  one-sequence server those would queue. Used only in c21b S16 (void), c23 S16 (void) and c24c S16 / A32dp (seqs 2).
- The notes calls go to the same server unless `--notes-upstream` is given (only the c22 LFM2.5 arms).
- Different conversations run in parallel: the proxy is a `ThreadingHTTPServer` (1676) with one lock per session.
  ForgeCode's title request and its first main request arrived at the same millisecond (c20d request log,
  `2026-10-15T10:26:29.205Z`, requests 1 and 2), which is the one c20d `Waiting: 1` line (10:26:44 UTC).

Clients:

- `tools/ctxkeeper/examples/long_chat.py:86-104`: `ask()` posts and returns; the loop sends the next report at
  once. Used for the smoke tests (c19 G2/G4, c21-24 S16).
- Harbor `PlainAgent` / `ClmAgent` (`/mnt/fast-ai/src/context-language-models/clm/clm_harness/clm_agent/harness.py`):
  a shell step between calls (612); a reply without a tool call gets a nudge and is re-sent at once (586-596);
  exception retries wait `random.uniform(0.0, min(60.0, 2.0 * 2**(attempt-1)))` (801-804), so possibly close to 0.
- `tools/freeagent/freeagent.py:47-94`: one `docker exec` per step, no sleep, no retry.
- The twelve agents: their own programs; per-turn pauses and side requests are not in this repo (unknown). Their
  request logs (`c20{b,d,e,f}/runs/jobs/*/trial/agent/requests.jsonl`) show one conversation each and no two requests
  starting within 0.5 s, except ForgeCode's first pair. The logs hold start times only.

Gaps measured at the proxy (`calls.jsonl`, campaigns 21-24, from a delegated read of those files): recall rounds and
empty retries under 50 ms, 422 of 458 starting from a cache hit; notes re-asks about 48 ms, 26 of 26 hits; main after
notes 2-65 ms, almost never a hit; the next client turn after a shell step 100-300 ms (55 ms at least); background
notes 5-6 ms after the reply and overlapping the next main call when enabled.

Evidence that these fast sequential hand-overs did not change answers: the 240K rules stream K32 gave the same
counts in every proxy record on MTP 5 servers (c13 X32q, c21b, c24c) and on the MTP 0 server of c23b (17 cuts, 292
archived, 10 recalls, notes 342,682 read / 17,146 written), although K32 includes recall rounds and notes re-asks
sent within 50 ms. A changed reply would almost certainly have changed those counts.

## Question 4: the 99/99 test

`experiments/qwen38-27b-b70/scripts/qwen38-fp8-prefix-cache-exactness-probe.py` is strictly one request at a time:
`ask()` (108-144) opens one blocking `urllib.request.urlopen` and reads the stream to `[DONE]`; the main loop
(284-318) sends the next variant only after the previous answer is read, compared and the report rewritten. There is
no `sleep`, no thread and no concurrency, so a request could never wait in the queue (the server log has no
`Waiting` line). The gap after each answer was not recorded; it is Python bookkeeping (comparing, rewriting the
JSON report, `expected_hit()` prefix scans), so milliseconds, not the 1 s pause of the 18:56 probe. The server was
seqs 1, MTP 5, align, exact 0.1.0, SRA 0.2.0, as in the table. All 99 answers matched a cache-off control, and the
hit cases (b, c, d, e2, f, g) did read from the cache. Since in Q3 roughly half of the hit answers changed when the
defect fired (25-27 of 64 per pass, every one a hit; the 8 `prose2k` copies never hit), 99/99 is good evidence that
it never fired there. **It shows exactness for one request at a time with
no queue, not for queued hand-overs**; the public wording drops that condition.

## Public claims (question 3)

Categories: (a) says the cache is exact / identical; (b) presents results from the affected profile; (c) recommends
prefix caching where drafting is on. "Profile" = whether the sentence names drafting, sequences or the cache.
Quotes are without HTML. Repos were clean and pushed at the time of the audit, so these files are what is live.
`content/pages.json`, `content/context-*.html`, `content/search-answers.json` and `search/answers.json` repeat the
page texts and need the same changes.

### Needs a limit or a correction whatever the re-check shows

- `/home/steve/b70-optimization-lab/tools/ctxkeeper/README.md:223-226` (a/b, `main` only; the v1.1.0 tag still
  says the replies were corrupted): "With MTP speculative decoding they were correct but 8 % slower ... (Our first
  try with MTP returned corrupted replies; that was a bug in our vLLM build with prefix caching, since fixed there,
  not in ctxkeeper.)" The fix then was 0.3.0; the hand-over defect was still there.
- `/home/steve/skindeep/context-reuse.html:163` (a, strongest): "Everything it reuses is exactly what a fresh read
  computes, so a cached answer is identical to an uncached one." Profile: no. Also L17 "This lab uses an exact
  cache instead", L183 "a resumed read does the same arithmetic as a cold one", L184 "99 of 99 cases gave identical
  output tokens with drafting on ... The standard 12-prompt check returned identical answers", L222 "Bit-identity
  can no longer be the test".
- `/home/steve/skindeep/context-prefix-cache.html:25` (a): "The matching cache test produced the same output
  tokens in 99/99 cases." L22: "The text available to the model stays the same; the server skips repeated
  computation." L29: summary "Technical details: exact reuse on this model" ... "Separate 120K cold-repeat checks
  also matched." The page never mentions drafting, users or sequences; L17 and L27 recommend the cache (c).
- `/home/steve/skindeep/context-cache.html:28` (a): "The exact-cache test returned the same output tokens in 99/99
  cases, including repeat questions, edits and later turns." L21 "All 12 answers matched the reference on both
  passes", L29 heading "How the cache stayed exact", L31 "With drafting enabled, 99/99 cases returned the same token
  sequence as the matched uncached reference" (limit there: "Matching output tokens is narrower than a
  scores-level or every-input guarantee"), L17 (c) "Prefix caching makes the next answer start sooner."
- `/home/steve/skindeep/context-results.html:80` (a): "With drafting on, the matched cache experiment produced
  identical output token sequences in 99/99 cases". L81-82 the gate 12/12 on both passes. L84 has the only partial
  limit: "Multi-user scheduling, one-card execution and disk restore were not established".
- `/home/steve/skindeep/context-reproduce.html:20, 37-39` (b/c, names the whole affected profile as the setup to
  copy): "All measurements used Qwen3.8-27B ... on two Intel Arc Pro B70 GPUs, one request at a time." ... "one
  sequence at a time." ... "Exact prefix cache: --prefix-cache align ... so a resumed read does the same arithmetic as
  a fresh one ... Add-on: b70-prefix-cache-exact." ... "Drafting on: the model's own draft head, five tokens ahead."
- `/home/steve/skindeep/context-questions.html:34` (b/c, two requests at once with MTP and the cache, from c24c):
  "With speculative decoding it was 8% slower (9.4 minutes against 8.7) ..." L54 (c): "prefix caching to avoid
  repeated reading when the engine supports it correctly." L33 (a): "Our exact cache already skips the unchanged text
  before an edit". L48 (a, with a limit): "matched output token sequences on 99 cases. That does not ... establish
  every future cache continuation." L53 (limit): "Shared-cache concurrency and other hardware need separate
  measurements".
- Smaller (a) mentions: `skindeep/docs/claims.md:84` (has a limit: "One user, matched reading chunks, token IDs"),
  `skindeep/docs/context-prefix-cache.md:7`, `skindeep/docs/research-status.md:39`, `skindeep/context-methods.html:49`
  ("Exact prefix cache: Reuses the unchanged start"), `skindeep/context-distance.html:328` ("The model's own
  arithmetic stays exact"), `skindeep/results/long-context/result.json:184` (`"cases_identical": "99 of 99"`; L204
  `"users_tested": 1`).

### Results from the affected profile (scores and times; probably unaffected, see above)

- `/home/steve/b70-optimization-lab/index.html` `#long-tasks` (1353-1367), profile named only as "Measured with
  Qwen3.8-27B FP8 on two B70s" (1356): 1359 "ctxkeeper 226 / 228 50 minutes"; 1361-1363 "40/40 fixed, every rule
  kept, 7/7", "33 min 2.9M prompt tokens read", "262K window 55 min"; 1365 "Twelve open-source coding agents ...
  eleven of the twelve fixed 39 or 40 of the 40 bugs, in 14 to 38 minutes"; 1366 "On a single B70 with a 26K view
  ... 7/7 in 21 minutes" (one-card server, not named). 1367 limit: "One model on one machine so far". No other
  prefix-cache text on the site except a generic `learn/context-length.html:106` ("lean on prompt caching") (c).
  The FP8 package row (about L1201, "one user, MTP depth 5") is not affected: the package runs with the cache off.
- `/home/steve/b70-optimization-lab/tools/ctxkeeper/README.md:23` "Measured on Qwen3.8-27B (FP8, served by vLLM on
  two Intel Arc Pro B70 cards)" and the tables after it (40/40 7/7 16 min, 226/228, 351/382, twelve agents); L172 (c)
  "keeps the prompt identical ... so the server's prefix cache serves the notes calls"; L240 (c) "the server's
  prefix cache serves almost all of it". No drafting or sequence setting named.
- `/home/steve/skindeep/context-use.html` (never names drafting, cache mode or sequences): L17 "eleven of the twelve
  fixed 39 or 40 of 40 bugs", L29-34 (40/40, 31-33 min, 226/228, 351/382), L37, L38 one card "21 minutes", L64-79
  the agents table, L84-87 recipes (L87 (c): "keeps the prompt identical, so the server's cache does most of the
  note-taking work"), L89-97 window sizes, L102-103 release checks, L111-112.
- `/home/steve/skindeep/context.html`: L17 "226 of 228 questions over a million tokens in 50 minutes", L21-37 tables,
  L40 (c) "prefix caching reuses the work of reading unchanged text". No profile named.
- `/home/steve/skindeep/context-distance.html`: keeper / proxy / repair / 2M results throughout (L18-155, L281, L305);
  cache-share lines (L44-51 "91.5% of the notes calls' reading came from the cache", L111, L135, L153); profile at
  L272: "two B70 GPUs, server window 65,536 tokens, exact prefix cache, one run at a time" (drafting not named).
- `/home/steve/skindeep/context-results.html`: L17-55 ledger / 478K / quoted-events tables ("These measurements used
  prefix caching in both methods", L49), L62-75 speed by length and recall 708/720 (L63 names the cache and drafting),
  L79 and L83 reuse times, L89-97 retention and past-the-window results; L106-107 profile: "One request ran at a
  time ... output speeds include drafting unless stated."
- Also (b): `skindeep/context-retention.html` (LongMemEval 46/56, 42/56), `context-cache-offload.html:24`,
  `context-memory.html:34`, `research.html:17` ("Recall was 708/720"), the ledger rows on `context-files*.html`,
  `context-clm*.html`, `context-summaries.html`, `context-self-editing.html`, `context-revised-editing.html`,
  `context-large-window.html`, `context-model-choice.html`; `results/long-context/result.json:1393` names the profile
  for the distance / keeper probes: "exact prefix cache, drafting on, tool calling on, one request at a time".
- Out-of-date limits seen on the way (not about this defect): `context-results.html:22` and
  `context-distance.html:26` / `context-methods.html:24` still say the proxy has not been tested under a third-party
  agent.

## Open questions

1. **Does a client that sends the next request the moment the previous answer arrives ever trigger it?** The lab's
   data says no: 98 cache-hit requests sent 0.1-0.2 ms after the previous answer (Q3 and P1 solo passes) matched a
   cache-off server 64/64 and 64/64, the 99/99 test matched, and the K32 proxy counts match MTP 0. The 19:04 probe
   compares paused runs with bursts sent 30 ms apart (queued), so it does not test this case directly. One
   unpaused one-at-a-time pass on the reset-off server (part A) would settle it; if it can fire, ctxkeeper's recall
   rounds, empty retries and notes re-asks (1-50 ms, nearly all cache hits) are exposed on every affected run.
2. **The 2026-10-07 480K re-verification differed from the original by one call and 102 written tokens**, with the
   same task bytes (window 65K instead of 262K). The server log shows no queued request, so this defect is an
   unlikely cause by the evidence above; the cause is unknown.
3. ForgeCode's queued request in c20d: whether it started from a cache hit is unknown (the title request has a
   different system message, so probably not). ForgeCode's result (25/40, time limit) is in the published table.
4. Short waits (under a few seconds) can slip between the 10-s log lines, and the agent request logs hold start
   times only. A direct check would need end times per request (the proxy's `calls.jsonl` has them only from
   campaign 21 on).
5. The clm-sixth `Aw` trials: why one request waited about 70 minutes is unknown; both trials are void.
6. Whether to re-run any published number on the 0.5.0 server: by the evidence above none is expected to change.
   The candidates, if the owner wants a check, are the ones that are cheapest and most cited: the 99/99 probe with
   queued requests added, and K32 on the 240K rules stream (its counts are a sensitive identity check).
7. Wording: which of the sentences above change, and how, is the owner's call (the site rules in AGENTS.md and the
   site check pins apply). The three that need a change whatever the result: README L223-226, context-reuse L163,
   and the unconditioned "99/99" / "exact" sentences on context-prefix-cache and context-cache.
