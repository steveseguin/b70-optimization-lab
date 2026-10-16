# Where the time goes: ctxkeeper runs (read-only analysis, 2026-10-16)

No GPU, server or git action. Large files were streamed line by line. Scripts and intermediate outputs:
``data/2026-10-16-context-campaign21/offline/`` (run.py, comp.py, srvlog.py,
gaps.py, c20.jsonl, comp.jsonl, comp-FAd.json).

Abbreviations: LAB = `/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data`, RAW =
`/mnt/fast-ai/bench-results/context-longrun-20261012`.

## Method notes (read these first)

- **Proxy timers.** `handle_s` covers the whole request inside the proxy. `upstream_s` covers every model-server call:
  main calls, notes calls, recall rounds and retries. ctxkeeper.py `complete()` adds both to state.json per request.
  "Outside" means agent seconds minus `handle_s`: the server is idle while the agent and its tools run.
- **Server metrics.** Prefill and decode seconds were sampled only in campaigns 11 to 13
  (`metrics-c12.tsv`, `RAW/metrics-c13*.tsv`). Campaigns 15, 19 and 20 have none. For those runs I added up the
  vLLM 10-second log lines (`RAW/server/tp2-w262144-<run>/server.log`, "Avg prompt/generation throughput").
  - Checked on runs where the truth is known: these sums equal the server's **uncached** prompt tokens (X32p:
    2,366,431 against 2,366,521 measured; FAp: 819,726 against 819,714) and its generated tokens (X32p: 173,040
    exact; FAp: 160,528 against 160,523).
  - Total prompt tokens including cached ones are not in those lines.
  - Prefill and decode seconds for c19 and c20 are therefore **estimates**: prefill = uncached / 2,700 tok/s, the
    rate measured on X32p (2,719), c13 XR (2,687) and XR4 (2,706); decode = upstream_s minus prefill.
- **Per-request usage** (prompt, cached) was never logged, not by the proxy, the harness or agentbench.
  - The bridge tap (`trial/agent/requests.jsonl`, c20 only) has the arrival time and full body of every request,
    but no response or timing.
  - So "re-read after a cut" comes from a regression (X32p) or a message-level replay (c20), described below.
- **Server config, all runs.** `--max-num-seqs 1` (launch.json). The attention block size is forced to **832
  tokens** (server.log: "Setting attention block size to 832 tokens"). The b70-prefix-cache-exact overlay is
  installed. Its docstring (`overlays/b70-prefix-cache-exact/b70_prefix_cache_exact.py`) says two things:
  - nothing past the prompt is cached, so each previous answer is read again as prompt;
  - with drafting, a cache hit moves back one block.

## 1. Wall clock vs proxy vs server

| run | agent wall s | handle_s | upstream_s | outside proxy (server idle) |
| --- | ---: | ---: | ---: | ---: |
| X32p 1M (c12) | 2,975 | 2,593.4 | 2,565.5 | 381.6 (12.8%) |
| G1 freeagent (c19c) | 1,851 | 1,828.8 | 1,828.3 | 22.2 (1.2%) |
| FAp freeagent via proxy (c15) | 1,989 | 1,970.2 | 1,969.7 | 18.8 (0.9%) |
| FAd freeagent direct, 262K (c15) | 3,287 | none (no proxy) | about 3,270 (wall minus tools) | 16.7 tool s (0.5%) |
| c20 mini-swe-agent | 807 | 757.7 | 757.4 | 49.3 (6.1%) |
| c20 open-interpreter | 1,050 | 1,013.2 | 1,012.9 | 36.8 (3.5%) |
| c20 freeagent | 1,253 | 1,209.0 | 1,208.6 | 44.0 (3.5%) |
| c20 goose | 1,426 | 1,378.9 | 1,378.3 | 47.1 (3.3%) |
| c20 pi | 1,657 | 1,618.5 | 1,618.1 | 38.5 (2.3%) |
| c20 qwen-code | 1,966 | 1,927.1 | 1,926.6 | 38.9 (2.0%) |
| c20 cline | 1,404 | 1,360.7 | 1,360.1 | 43.3 (3.1%) |
| c20 openhands | 1,433 | 1,308.0 | 1,307.7 | 125.0 (8.7%) |
| c20 hermes-agent | 1,516 | 1,465.5 | 1,465.0 | 50.5 (3.3%) |
| c20 kimi-code | 2,278 | 2,234.2 | 2,233.7 | 43.8 (1.9%) |
| c20 forgecode (60-min limit) | 3,600 | 3,585.4 | 3,584.3 | 14.6 (0.4%) |
| c20 mistral-vibe (c20e) | 1,520 | 1,466.2 | 1,465.8 | 53.8 (3.5%) |
| c20 opencode (c20f) | 1,973 | 1,913.6 | 1,913.1 | 59.4 (3.0%) |
| **c20, all 13** | **21,883** | | **21,231.6** | **645 (2.9%)** |

Sources:
- Proxy timers: `proxy/.../state.json`.
- c20 wall: `agentbench.json` `agent_exit.seconds`.
- X32p wall: `campaign12.log` ("49 min 35 s").
- G1: `run.out`.
- FAp/FAd: `RAW/client-repair2/runs/FA?__repair-n40-s2x.out`.

The proxy's own CPU time is 0.3 to 1.1 s per run (handle_s minus upstream_s). X32p's 27.8 s comes from the 1.0.0
checks.

X32p's 381.6 s outside the proxy splits as follows (`runs/client-1m/X32p__sparse-memory-t1000k-s0/timing.json`):
- shell commands: 67.5 s (675 steps, every one 0.1 s);
- client to proxy HTTP: 60.3 s (client llm_s 2,653.7 against handle_s 2,593.4);
- harness overhead plus container start and grading: 253.8 s (not broken down further in the records).

**Bound for "keeper work while the agent is busy":** the server is idle 1 to 9% of the time on the repair task,
in slivers of about 0.2 to 0.6 s per request (outside_s / requests). Each notes call takes about 6 to 10 s. The
server serves one sequence at a time (`--max-num-seqs 1`), so notes work running in the background would queue
behind the next main call.

## 2. Notes work

**X32p** (1.0.0 code, in-place notes, notes thinking **on**, checks near):
- 75 cuts, all in place, 0 failed. 90 notes calls: 75 first attempts and 15 asked again (`events.jsonl`).
- Notes tokens: prompt 1,577,993, cached 1,410,240 (89.4%), written 93,306. That is 54% of all 173,040 generated
  tokens.
- Notes time is not timed directly. Two estimates:
  - At the run's average decode rate: 93,306 / 103.2 tok/s + 167,753 uncached / 2,719 tok/s = **about 966 s**.
  - At the rate of the re-asked calls: those are timed exactly by consecutive reply timestamps. 15 calls took
    198.1 s for 16,960 tokens, 85.6 tok/s; applied to all calls that gives **about 1,090 s**.
  - So notes took **38 to 42% of upstream_s** (32 to 37% of wall).
- The 15 re-asks alone took 198 s (7.7% of upstream_s).

**c20** (ctxkeeper 1.0.1 `--recipe qwen`: notes thinking off).
- Keeper time per request = last notes timestamp (`notes-history.jsonl` and `events.jsonl` "at") minus that
  request's arrival in `requests.jsonl`. This is exact up to the bridge latency.

| agent | cuts (in place) | notes calls | keeper s | % of upstream | per cut median / max s | notes prompt / cached / written |
| --- | --- | ---: | ---: | ---: | --- | --- |
| mini-swe-agent | 7 (7) | 7 | 54.2 | 7.2 | 8.2 / 10.0 | 134,845 / 91.3% / 4,191 |
| open-interpreter | 5 (5) | 5 | 29.1 | 2.9 | 5.6 / 7.9 | 123,567 / 92.9% / 1,998 |
| freeagent | 8 (8) | 8 | 52.5 | 4.3 | 6.8 / 8.6 | 145,865 / 90.7% / 4,211 |
| goose | 9 (9) | 9 | 70.7 | 5.1 | 6.8 / 13.4 | 162,194 / 90.3% / 5,000 |
| pi | 9 (8) | 8 + 1 full | 59.6 | 3.7 | 7.3 / 11.2 | 151,035 / 90.3% / 3,565 |
| qwen-code | 14 (6) | 6 + 8 full | 141.9 | 7.4 | 10.1 / 21.2 | 165,050 / 93.8% / 2,900 |
| cline | 12 (11) | 12 + 1 full | 80.6 | 5.9 | 6.4 / 10.1 | 240,657 / 90.9% / 5,746 |
| openhands | 6 (6) | 6 | 50.3 | 3.8 | 8.6 / 9.4 | 142,215 / 92.4% / 3,857 |
| hermes-agent | 12 (9) | 9 + 3 full | 117.6 | 8.0 | 7.6 / 31.7 | 220,100 / 92.6% / 4,874 |
| kimi-code | 13 (12) | 13 + 1 full | 108.4 | 4.9 | 7.4 / 11.7 | 449,816 / 94.7% / 6,618 |
| forgecode | 69 (7) | 8 + 62 full | 835.2 | 23.3 | 13.0 / 26.4 | 306,156 / 95.4% / 1,570 |
| mistral-vibe | 5 (5) | 5 | 39.2 | 2.7 | 7.6 / 9.5 | 118,938 / 92.3% / 3,110 |
| opencode | 13 (12) | 12 + 1 full | 90.8 | 4.7 | 6.4 / 16.5 | 274,017 / 92.9% / 5,525 |

- All 13 runs: keeper time 1,730 s = 8.1% of upstream. Without forgecode: 895 s = **5.1%** of 17,647 s.
- "Full" means the ordinary cut path (`notes_call`). It is not prefix-aligned, and its tokens are **not** counted
  in `notes_prompt_tokens`.
- G1 (c19c): 11 in-place cuts plus 1 notes call not applied; prompt 224,647, cached 203,840 (90.7%), written
  6,949. There is no request log, so time is not recorded. Estimate: 12 × 6.6 s (c20b freeagent's measured rate)
  ≈ 79 s ≈ 4.3% of upstream.
- FAp (c15): 12 in-place cuts, prompt 233,674, cached **3.9%** (the thinking-off misalignment found in campaign
  16), written 6,264. Its notes alone read about 225K uncached tokens.

## 3. Reading: prompt vs cached, prefill vs decode

**X32p** (`metrics-c12.tsv`, deltas 09:56:10 to 10:45:41; the request delta 834 equals upstream_calls):
- Prompt 9,542,521, of which 7,176,000 cached (75.2%); **uncached 2,366,521**. Generated 173,040.
- **Prefill 870.4 s (34%), decode 1,677.3 s (66%)**; TTFT 884.6 s, queue 0.
- Uncached tokens by call type:
  - main calls 2,039,626 (from client `usage.json`: 7,130,634 prompt, 5,091,008 cached);
  - notes 167,753;
  - recall rounds and other calls 159,142 (69 calls).
- Regression of uncached tokens per 30-s window on call counts (98 windows):
  - about **2,580 uncached tokens per ordinary main or recall call** (windows with no cut: 2,612);
  - **3,270 extra on the first main call after a cut** (about 5,850 in total);
  - about 2,125 per notes call.
  - In total, re-reading after cuts ≈ 245K tokens (10% of uncached, about 90 s of prefill).

**Repair task, measured split** (proxy runs that have metrics, `RAW/metrics-c13.tsv` and `metrics-c13c.tsv`):
- XR s0: uncached 587,218 of 2,924,306 (20%); prefill 218.5 s (**10%**), decode 1,965.5 s (**90%**); 90.7 gen
  tok/s.
- XR4: prefill 196.6 s (12%), decode 1,479.2 s (88%).

**c20** (uncached and generated tokens from the server log, seconds estimated as in the method notes):
- Per-run prefill estimate: 10.3% (kimi) to 18.5% (mini-swe) of upstream. Implied decode rate 60 to 100 tok/s.
- Without forgecode: uncached 6,215,257 tokens (about 2,300 s, 13%) and generated 1,106,561 tokens.
- Decode (reasoning plus replies) is about 87% of server time.

**G1:** client prompt 3,358,370 (cached not recorded by freeagent). Server-log uncached 615,349, generated 153,452:
130,009 main, 6,949 notes, about 16.5K in retried or discarded replies. Prefill est. 228 s (12.5%).

**FAd** (direct, 262K window; `campaign15.log` server totals):
- Prompt 29,934,764, cached 29,376,256 (98.1%), uncached 558,508, generated 125,328.
- Prefill est. about 207 s, so decode is about 3,060 s, **about 41 tok/s**. The history grew to about 220K tokens
  (624,725 chars / 2.835).
- Its 10-s server log was not kept: `server/tp2-w262144-c15` holds FAp's later launch.

**What the re-read is made of** (c20, 12 agents without forgecode; message-level replay of each final history,
see section 5):

| part | tokens | share of uncached |
| --- | ---: | ---: |
| new messages per request (previous reply incl. reasoning + tool results; output is never cached) | 1,673,978 | 26.9% |
| right after a cut: NOTES + kept exchange | 262,772 | 4.2% |
| notes calls' own uncached | 175,915 | 2.8% |
| **remainder: about 1,289 tokens per upstream call** | 4,102,592 | **66.0%** |

The remainder is the same in every agent: 1,184 to 1,385 per call (qwen-code 1,644, forgecode 3,747). It matches
the cache granularity: the hit point is the last full 832-token block, moved back one block for drafting, so
832 + 832/2 ≈ 1,248 tokens are expected per call. **About two thirds of all re-reading on the repair task is block
granularity, not cuts.** Re-reading after cuts is about 4% (about 1,100 to 3,300 tokens per cut).

## 4. Gaps between requests

- **c20** (`requests.jsonl` arrivals; a gap = proxy handling + agent time):
  - median 2.0 to 4.0 s, p90 8.1 to 24.9 s, max 37.6 to 413.7 s; the total equals the run span.
  - The agent's share of the gaps (outside_s / requests) is 0.15 to 0.6 s per request.
  - Requests that carried a cut: gap median 7.4 to 13.2 s. After the keeper part, the rest of the gap had median
    2.1 to 7.6 s.
- **Long replies dominate.** Gaps over 30 s: 82 of about 3,000 requests (12 agents without forgecode), 6,334 s =
  **36% of upstream time**. Gaps over 60 s: 4,285 s (24%).
  - Per agent: qwen-code 925 s over 30 s (737 s over 60 s), kimi 1,012 (610), pi 685 (608), mistral-vibe 527 (405,
    one 405-s reply), openhands 441 (one 391-s reply), forgecode 1,825 (1,463).
- **X32p:** per-step client llm_s median 1.7 s, p90 12.0 s, max 52.2 s. Shell commands 0.1 s each. 12 steps over
  20 s took 390.8 s.
- **freeagent** (G1/FAp/FAd `timing.json`): commands median 0.0 s, p90 0.1 s, max 1.7 s, total 15.1 / 14.1 /
  16.7 s. Request timestamps were not recorded for these runs.

## 5. Repair task: what the conversation is made of (final client history, chars)

- Sources:
  - c20: the last request body in `requests.jsonl` (each request extends the previous one; whole_history_ok);
  - G1, FAp, FAd: `trajectory.json`.
- Token counts use chars / 3.5. The view simulation uses each run's learned ratio. The simulated cut counts match
  the real ones (8/8, 9/9, 6/6, 13/13, 11/12 ...), except forgecode (16 vs 69) and qwen-code (11 vs 14), whose
  ordinary cuts are not modelled.

| run | history tok (3.5) | tool % | reasoning % | asst visible % | user+system % | tool result median / p90 / max tok | old tool in final history, removable % |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| mini-swe-agent | 88K | 58.2 | 27.7 | 12.7 | 1.4 | 189 / 620 / 1,512 | 49.5 |
| open-interpreter | 76K | 71.3 | 0 | 19.1 | 9.6 | 99 / 658 / 1,973 | 62.3 |
| freeagent c20 | 119K | 43.0 | 45.2 | 11.4 | 0.4 | 66 / 435 / 1,718 | 34.6 |
| goose | 118K | 46.7 | 42.0 | 10.5 | 0.8 | 65 / 599 / 1,319 | 39.3 |
| pi | 123K | 38.4 | 49.8 | 11.0 | 0.9 | 46 / 504 / 2,332 | 32.1 |
| qwen-code | 149K | 41.0 | 43.8 | 9.7 | 5.5 | 110 / 538 / 1,964 | 33.8 |
| cline | 140K | 52.1 | 36.0 | 10.7 | 1.2 | 85 / 700 / 2,421 | 44.3 |
| openhands | 75K | 73.9 | 0 | 19.8 | 6.3 | 149 / 631 / 1,158 | 63.3 |
| hermes-agent | 135K | 48.3 | 40.4 | 7.8 | 3.6 | 176 / 633 / 2,583 | 41.1 |
| kimi-code | 148K | 34.6 | 54.6 | 8.8 | 2.0 | 51 / 527 / 2,282 | 27.9 |
| forgecode | 300K | 63.7 | 29.8 | 5.3 | 1.1 | 131 / 828 / 21,855 | 60.5 |
| mistral-vibe | 75K | 70.7 | 0 | 22.1 | 7.3 | 69 / 495 / 1,868 | 55.6 |
| opencode | 162K | 40.4 | 48.9 | 8.9 | 1.8 | 48 / 596 / 1,596 | 33.6 |
| G1 freeagent c19 | 158K | 32.3 | 55.9 | 11.5 | 0.3 | 57 / 454 / 1,081 | 25.5 |
| FAp freeagent c15 | 176K | 34.2 | 53.1 | 12.4 | 0.3 | 78 / 561 / 1,718 | 28.5 |
| FAd freeagent direct | 178K | 45.4 | 43.0 | 11.3 | 0.3 | 280 / 592 / 1,414 | 40.0 |

Notes on this table:
- 12 agents without forgecode, mean: tool 51.5%, reasoning 32.4%, assistant visible 12.7%. The three agents that
  do not send reasoning back (open-interpreter, openhands, mistral-vibe) are 72% tool.
- Reasoning is passed upstream as the client sends it: `view()` forwards `messages[h+cut:]` unchanged, and the
  Qwen3.8 template renders `reasoning_content` for every assistant turn (preserve_thinking undefined).
- "Old tool, removable" = tool results with more than 3 assistant turns after them, minus a 120-char stub.

**Inside the proxy's 32K view** (replay of the in-place cut rule: 15,000-token trigger, head + NOTES + turns
since the cut), the pre-pass could remove:
- Tool output older than 3 assistant turns is **11.6 to 30.6% of view tokens**; mean 21.7% for the 12 agents.
- Mean view size 9.5K to 18.8K tokens.
- FAd (whole history on every call): old tool output is 38.3% of all 84.9M prompt chars sent, about 11.5M of its
  29.9M prompt tokens. But 98% of those were cache hits, so the gain would be in decode attention and KV size, not
  in prefill.

**What a CPU pre-pass would do** (simulated, 12 agents):
- **Rolling stub at every request** (an output is stubbed as soon as it is 3 turns old):
  - cuts fall about 40% (freeagent 8 → 5, opencode 13 → 9, open-interpreter 5 → 1);
  - but every request then edits a message 3 exchanges back, so the cache breaks there: **+229K to +565K
    re-read tokens per run** (+85 to +210 s of prefill at 2,700 tok/s);
  - it saves 2 to 6 notes calls (about 7 s each, so 15 to 45 s). A net loss.
- **Stub only when the cut would trigger** (pre-pass in place of a notes call; cut only if still over 15K):
  - the same cut reduction, with 12 to 28 stub events per run;
  - +35K to +206K re-read tokens (13 to 76 s), and views 8 to 22% larger (cached);
  - about break-even against the notes calls it saves (for example freeagent: 3 cuts saved ≈ 22 s, 17 stub events
    ≈ 39 s of re-read).

## 6. Other places the time goes

- **Decode of long replies is the main cost on the repair task.** It is about 87 to 90% of server time, and 3% of
  requests (over 30 s) take 36% of upstream time.
- **Block-granularity re-read:** about 1,250 tokens per upstream call, about 0.46 s per call, about 130 to 140 s
  per 300-call run (66% of uncached tokens). It is larger than cuts and notes reads combined.
- **forgecode:** 62 ordinary (full-rewrite) cuts, keeper time 835 s (23% of upstream), 1.56M uncached tokens. One
  tool result was 21,855 tokens. It hit the 60-min limit at ticket 29.
- **Recall rounds** (upstream_calls minus requests, notes calls and retries):
  - X32p: 69 rounds for 112 searches, about 25K generated + 159K uncached, about 300 s (12% of server time);
  - c20: goose 18 rounds (22 searches), cline 10, pi 8, hermes 8, freeagent 4, others 0 to 2.
- **Notes re-asks:** X32p 15, costing 198 s. c20 0 (checks off in recipe qwen).
- **Notes not applied:** G1 1, cline 1, kimi 1. forgecode had 1 reply rejected.
- **Retries:** empty replies retried: G1 2, FAp 2, c20 freeagent 2. Think-cap retries: none recorded.
- **Context length (FAd vs FAp):** the same agent reached about 41 tok/s decode at 200K+ context against about
  80 to 100 tok/s inside the 32K view. That is most of FAd's 55 min against FAp's 33.
- **Not recorded:** per-request prompt and cached usage (all runs); prefill and decode seconds for c15, c19 and c20;
  FAd's 10-s server log; request timestamps for G1, FAp and FAd; notes timing for G1.
