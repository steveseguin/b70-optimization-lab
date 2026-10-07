# Context Language Models (CLM) harness against our local server

The original Harbor harness below was prepared on 2026-10-05. Its clients do
not start a server. The later, explicitly invoked `*_host_runner.py` coordinators
own bounded GPU experiments and graceful cleanup; consult [CURRENT.md](../../../../CURRENT.md)
for host ownership before any live action.

[Follow-up experiment ideas](../../notes/2026-10-05-context-followup-ideas.md): verify every delivered update, test historical recall, separate file I/O from decode speed, validate cache save/restore, and measure when prefix reuse pays off. These proposals build on the current queued runs; they do not launch additional work.

## Evidence and experiment index

The [canonical trial exporter](evidence/README.md) generates historical tables
from native grader records. The later durable experiments use a separate
persistent source archive and transactional event application. Keep their
versions distinct: prompt, retry, answer and cache policies changed between
experiments, so pooled scores or direct timing comparisons would be misleading.

| Version | Evidence and scope |
| --- | --- |
| [Original durable pilot](durable/README.md) | Preserved initial harness and protocol; CPU/stub checks are software validation. |
| [Revision 2](durable_v2/README.md) | Answer/retrieval protocol repair; six development trials completed but its quality gate failed. |
| [Revision 3](durable_v3/README.md) | Final-answer reasoning enabled; structured methods exact, summary inaccurate. [Result](../../notes/2026-10-07-durable-context-r3-result.md). |
| [Revision 4](durable_v4/README.md) | Cache-disabled prospective comparison; five trials completed, one capped, six unstarted. [Result](../../notes/2026-10-07-durable-context-r4-result.md). |
| [Semantic development](semantic_v1/README.md) | All 36 trials complete: quoted and summary 84/84, archive 82/84. [Audited result](../../notes/2026-10-07-context-semantic-result.md); short authored pairs, not external validation. |
| [Sparse-state development](sparse_v1/README.md) | Four trials complete. At 128 counters both methods are exact; quoted uses 21.7% less elapsed time on one server. [Result and limits](../../notes/2026-10-07-sparse-state-result.md); [replication plan](../../notes/2026-10-07-sparse-state-replication-plan.md). |
| [Sparse replication and transfer](sparse_replication_v1/README.md) | Four trials complete, all final answers 24/24. Original task repeats its exact 21.6% elapsed signal; dispatch archive fails seven early checkpoints. [Audited result](../../notes/2026-10-07-sparse-state-replication-result.md). |
| [Historical state retrieval](history_v1/README.md) | Frozen engine used by the active study below: each method saves its own accepted states; source-only/history modes isolate lookup access. Engine wiring and snapshot integrity alone do not establish model quality. |
| [Historical-state study](history_study_v1/README.md) | Active supervised eight-trial comparison on two temporal documents, crossing bookkeeping and source-only/history access. CPU preparation and host preflight passed. [Prospective plan](../../notes/2026-10-07-history-state-study-plan.md). |

The [temporal source packet](../../data/2026-10-07-temporal-development/authoring-note.md)
is separate CPU preparation: four short narratives with earlier-value questions.
Its [two independent assistant annotations and source replay](../../data/2026-10-07-temporal-development/review-note.md)
agree on all 96 answers and 48 closing states. Its first two documents feed the
active study above; the other two remain unused development cases. All use a
shared controlled posting grammar.

Each temporal document fits within the prompt limit with all its batches supplied
together. These cases
test correctness and costs inside this streaming/retrieval protocol; they do not
show that external memory is necessary for such short documents. Before making a
broader efficiency claim, compare against direct full-source answering where it
fits, and separately test realistic streams longer than the available context.
The [CPU full-source fit receipt](../../data/2026-10-07-full-source-feasibility/README.md)
reproduces exact candidate requests. The [research priorities](../../notes/2026-10-07-context-research-priorities.md)
and [separate two-call screen plan](../../notes/2026-10-07-full-source-screen-plan.md)
make that next check explicit; they do not change the active experiment.

The revision 2, 3 and 4 holdouts remain unused. Frozen versions and negative outcomes are
preserved; new experiments do not retrospectively complete or repair them.
The remainder of this document describes the original Harbor integration,
not the current host status or a statement that its queued jobs remain active.

## What is where

| item | location |
|---|---|
| upstream code | `/mnt/fast-ai/src/context-language-models` = github.com/facebookresearch/context-language-models, commit `18dc11115f50f261233c5bba7937834491e307e8` (2026-09-30), licence CC BY-NC 4.0 (non-commercial) |
| Python env | `/mnt/fast-ai/venvs/clm` (Python 3.12, `pip install -e` of the repo: harbor 0.16.1, litellm 1.104.0, tiktoken 0.14.0, openai 2.54.0; no torch, no transformers) |
| tiktoken vocab cache | `/mnt/fast-ai/cache/tiktoken` (o200k_base, cl100k_base; scripts set `TIKTOKEN_CACHE_DIR`, so runs need no internet) |
| scripts | this directory |

Upstream contents: `clm/clm_harness` (the CLM agent for the Harbor framework), `clm/clm_icl`
(instruction evolution), `clm/clm_rl` (two patches + README), `suffix_cache_reuse` (SGLang
patch). **Not in the repo:** ContextBench (README "Coming soon", upstream issue #2 asks to
publish it), any benchmark task data, and every baseline from the paper (Mini-SWE-Agent,
Codex-style Summary, Context Folding, RLM, Self-Compact, ACM). The two configs
(`configs/bcp.yaml`, `configs/edgebench.yaml`) need BrowseComp-Plus / EdgeBench Harbor tasks
that are not shipped either.

So this directory adds, without patching upstream:

| file | what |
|---|---|
| `make_kvstream_tasks.py` | generator of "kvstream" Harbor tasks, our stand-in for ContextBench's KV Store task as the paper describes it (batches of 100 `SET key = <24 words>`, then 24 GETs, exact-value accuracy, pressure = stream tokens / 32,768). Not the paper's data or grader; scores are not comparable to the paper. |
| `clm_baselines.py` | `PlainAgent` (no management) and `SummaryAgent` (Codex-style harness summary at 75 % of the limit). Both subclass the upstream `ClmAgent`, so the loop, bash tool, task prompt, budget gate, token counting and output files are identical; only the context policy differs. |
| `run-context-job.sh` | common runner (one Harbor job, one agent); all settings via env vars, see its header |
| `run-contextbench-clm.sh` | zero-shot CLM (`ClmAgent`, unmodified) |
| `run-contextbench-baseline.sh` | `BASELINE=summary` (default), `plain`, or `both` |
| `smoke.sh` | one tiny task (1 batch of 8 SETs, 3 GETs) for each agent; `STUB=1` runs it against the fake server |
| `fake_openai_server.py` | ~90-line stub OpenAI server (scripted `next`/answer/submit tool calls), for wiring tests only |
| `summarize_results.py` | per-trial score + token/turn table for one or more job dirs |

## How the harness talks to the model

- **API:** OpenAI **chat completions with tool calling** through litellm
  (`litellm.completion(model="openai/<served name>", api_base=..., tools=[bash], ...)`,
  `clm/clm_harness/clm_agent/harness.py:749-790`). One tool, `bash(command)`. The legacy
  completions endpoint is not used.
- **Endpoint:** agent kwarg `api_base`, else env `OPENAI_BASE_URL` / `OPENAI_API_BASE`
  (`harness.py:750`). Key: `OPENAI_API_KEY` (any value; scripts set `EMPTY`).
- **Request fields:** `max_tokens` (default 16384, `harness.py:188`), `temperature` 0.7 and
  `top_p` 0.95 by default (`harness.py:186-187`; `"none"` omits a field), and
  `extra_body.chat_template_kwargs.enable_thinking` (default true, `harness.py:219,784-787`;
  `send_chat_template_kwargs=false` omits it). No seed, no stop strings. Retries: 5
  (`CLM_LLM_MAX_RETRIES`), 600 s per-call timeout (`harness.py:98,101`).
- **Greedy:** our scripts default to `temperature=0`, `top_p=none` (verified on the stub: the
  request carries `"temperature": 0.0` and no `top_p`). The paper sampled at 0.7/0.95; the
  harness has no seed option. SummaryAgent's summary call uses the same sampling settings.
- **Tokenizer:** no model tokenizer. All budget decisions count tokens with tiktoken
  `o200k_base` (`utils/tokens.py:31-53`), then scale by a ratio learned from the server's
  reported `usage.prompt_tokens` (`utils/budget.py:143-169` `calibrate`, clamp 0.5-3.0; `CLM_TOK_RATIO=0`
  disables). Offline without the vocab cache it falls back to chars/4. `transformers` is only
  an optional extra for exact FLOPs counting (not installed).
- **Server requirements:** tool calling must be on. The upstream README's vLLM line is
  `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`. Our
  `packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py` (lines 241-247) has none of these and
  runs `--no-enable-prefix-caching --max-num-seqs 1`, so a request with `tools` will be
  refused (vLLM needs `--enable-auto-tool-choice` + a parser for automatic tool choice) and
  every call re-reads the whole prompt. The server for these runs must be launched with
  the tool flags (via a separate launcher or override, not by editing the pinned serve.py).
  Which parser fits Qwen3.8's chat template (`qwen3_coder` vs `hermes`) is unverified.
  Without `--reasoning-parser`, the thinking text comes back inside `content`. It stays in
  the context and in the mirror file, and costs budget.
- **Window:** the server window must hold `context_budget_tokens + max_tokens`
  (clm_harness README). Default here: budget 28,672 + max_tokens 4,096 = 32,768, which
  fits the default 33,024 window. This is the paper's own BrowseComp-Plus setting for a
  32,768 window (`configs/bcp.yaml`: "32768-token window minus max_tokens"). The enforced
  limit is budget minus reserve (2,048) = 26,624 tokens. For the paper's ContextBench
  setting (32,768 limit, 2,048 reserved), use `CONTEXT_BUDGET=32768 MAX_TOKENS=8192` on a
  server with `--max-model-len` of at least 40,960. `run-context-job.sh` reads
  `max_model_len` from `/v1/models` and refuses to start when the request cannot fit.

## How the context file works (sandbox)

- Harbor runs each task in a **Docker container** built from the task's
  `environment/Dockerfile` (plain `docker compose`, no GPU, no `--device`). The agent loop
  runs **on the host**, so `api_base=http://127.0.0.1:<port>/v1` works unchanged. The
  container needs no network for kvstream.
- Before every command the harness renders all turns after the pinned system+task prompt
  as `[[CTX_TURN i role=...]]` blocks and uploads them to `/tmp/.live_ctx/LIVE_CTX_MAIN.txt`
  in the container (`context_env/env.py` `write_mirror`, `context_utils/context_string.py:90-101`).
  After the command it downloads the file; if it changed it is parsed back into messages
  (`parse_back`, `context_string.py:104-139`: protected prefix re-pinned, other roles fold
  to user, tool-call structure is dropped, empty turns removed, same-role turns merged),
  subject to the edit gate (`context_env/edit_gate.py`; `fit` default, `shrink` with
  `CLM_EDIT_GATE=shrink` as in bcp.yaml). A turn that only edits the file and prints nothing
  does not count as a task step (`harness.py:127-130`).
- Persistent shell: cwd/env are saved to `/tmp/.bash_ctx_state` between commands
  (`env.py` `wrap`).
- Host prerequisites found here: Docker 29.1.3 + compose 2.40.3 work. **docker buildx is not
  installed**, so Harbor's egress-control sidecar cannot build. Any task with
  `network_mode = "no-network"` or `"allowlist"` fails at start ("unknown flag: --file").
  kvstream tasks therefore use `network_mode = "public"`. Base image `python:3.12-slim` is
  pulled (about 45 MB). Each trial rebuilds its tiny image and removes it after.

## Exact instructions the CLM harness gives the model

System prompt, `clm/clm_harness/clm_agent/prompts.yaml:5-58` (`{{context_budget}}` becomes
"26624 tokens" with our defaults, `harness.py:456-466`; `{{finish_instructions}}` becomes the
submit paragraph, `utils/finish_policy.py:31-35`):

```
You are a helpful assistant that can interact with a computer.

Your response must include a THOUGHT section before your action where you
explain your reasoning. After the THOUGHT, you must call the `bash` tool
with EXACTLY ONE bash command (multiple commands chained with `&&` or `||`
count as a single action).

Failure to follow these rules — calling no tool, calling a tool other than
`bash`, or omitting the THOUGHT — will cause your response to be rejected.

## Managing your context

**Goal: maximize task success** — keep going until the task is done or you run out of
budget (no penalty for extra turns). Your context budget is {{context_budget}}; each
result shows your current size.

Your conversation is mirrored to `/tmp/.live_ctx/LIVE_CTX_MAIN.txt` (refreshed before
every command). **Free up context by editing that file** — replace stale regions (big
outputs, dead ends, superseded notes) with a concise, specific summary. A bloated
transcript wastes budget and dulls your reasoning, so compact as it grows. An editing
turn is free only when its command applies a real edit and prints nothing — any
stdout/stderr, a non-zero exit, or an edit that matches nothing costs a normal turn.

**Locate text with code — never paste or retype it** (context is long: retyping wastes
tokens and usually mis-matches). Turns are numbered `[[CTX_TURN 1 …]]`, `[[CTX_TURN 2 …]]`,
… in order from the top of the editable region (the hidden system/task prefix is NOT
counted, so the first turn you can edit is 1). Match a turn by its `[[CTX_TURN <i> role=…]]`
header, a block by a short unique first/last line, or slice on the headers:
    python3 - <<'PY'
    import re; p="/tmp/.live_ctx/LIVE_CTX_MAIN.txt"; s=open(p).read()
    # collapse turn 7 (its header -> the next header); its body is never retyped:
    s=re.sub(r"(\[\[CTX_TURN 7 [^\]]*\]\]).*?(?=\n\[\[CTX_TURN|\Z)",
             r"\1\n[grep done: parser.py:142 drops quoted commas; fix=csv.reader]", s, flags=re.S)
    open(p,"w").write(s)
    PY

**Rules:** don't `cat` this file (its text is already in your context). Keep the
`[[CTX_TURN …]]` header of any turn you keep — emptying its text drops that turn; the
system/task prefix is protected for you. Each result says whether the file changed or
matched nothing.

**Compact cheaply** — an edit forces everything *after* it to be re-read, so cost grows
with how much text FOLLOWS the edit:
- **Batch**: one large compaction beats many small edits.
- **Mind what's below your edit** — it all gets re-read, so don't compact a small early
  region while a long, still-useful tail sits beneath it (that re-reads the whole tail
  for little gain). Keep a useful tail; if it's much larger than what you'd compact,
  wait and compact head + tail together — UNLESS you expect to hit the context limit
  soon, then compact now.
- **Be generous in the summary**: the tail is re-read regardless, so a detailed
  replacement is essentially free.

When you are finished, submit by running the standalone command
`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` (with nothing else in that command).
After it runs you cannot continue.
```

The task is wrapped in the `terminal_agent_tasks` template (`task_templates/terminal_agent_tasks.yaml`,
mini-swe-agent style workflow + rules) unless `task_template=open_problems` (task text only)
or `edgebench` is set.

Other text the model sees:

- After every command: `[context: ~N/26624 tokens]`, plus ` — OVER; compact /tmp/.live_ctx/LIVE_CTX_MAIN.txt now`
  when over (`context_env/env.py:232-248`); edit receipts / rejections (`env.py` `_apply_edit`,
  `edit_gate.py:67-73`).
- Compaction hint appended to nudges (`harness.py:284-289`): "Compact /tmp/.live_ctx/LIVE_CTX_MAIN.txt by
  locating stale regions with code (match a turn by its [[CTX_TURN i ...]] header or a block by
  short start/end anchors) and replacing them with summaries — do not retype the text you
  remove. Compact settled spans; keep anything you have not finished using."
- Nudge texts: `utils/budget.py:363-399` (25 % informational; 50 % "finish the unit of work,
  then tidy ONCE" + note contract `budget.py:356-361`; 75 % "close to the limit. Compact
  settled spans now — but do NOT wipe ..."), urgent nudge `budget.py:342-353`, rollback notice
  `budget.py:310-331`, final-turn notice `budget.py:333-340`, finalize notice near the step cap
  `harness.py:725-747`.

## Default triggers and budgets (ClmAgent class defaults, `harness.py:181-245`)

| setting | default | ref | our scripts |
|---|---|---|---|
| `context_budget_tokens` | required (clm-harbor adds 32000) | `harness.py:395-408`, `cli.py` | 28672 |
| `context_budget_reserve_tokens` | 2048 → limit = budget - 2048 | `harness.py:194`, `budget.py:83` | 2048 |
| `nudge_ratios` | 0.25, 0.5, 0.75 of the **budget**, once each, re-arm after shrinking | `harness.py:196`, `budget.py` evaluate | same (CLM); off (baselines) |
| `persistent_nudge_ratio` | `adaptive`: nag every turn while room left < max(10 % of limit, 2 × largest of last 3 tool outputs), band never below 50 % of limit | `harness.py:202`, `budget.py:240-265` (`adaptive_persistent_trigger` at 246) | same (CLM); off (baselines) |
| `max_num_retry_on_limit` | 50 rollback-and-compact retries, rolling back until 2048 tokens free (`retry_edit_margin_tokens`) | `harness.py:207-208` | same (CLM); 0 (baselines) |
| over-limit after retries | one final turn, then stop and grade | `budget.py` evaluate | same |
| edit gate | `fit` (accept if result fits the limit); `CLM_EDIT_GATE=shrink` | `edit_gate.py:38-46` | fit unless you export `CLM_EDIT_GATE` |
| `max_steps` | 64 task steps; `lm_call_cap` 2·max_steps+24 | `harness.py:185,311` | 3 × items + 20 for kvstream |
| `finalize_nudge_turns` | 3 | `harness.py:209` | same |
| `observation_max_chars` | 10000 (head 5000 + tail 5000 kept) | `harness.py:192`, `prompts.yaml:63-70` | 60000 (one 100-SET batch is ~16k chars) |
| newest-output cap | newest tool output head/tail-truncated to fit under the limit | `budget.py:400-412` | same |
| `max_tokens` / sampling | 16384 / 0.7 / 0.95 / thinking on | `harness.py:186-188,219` | 4096 / 0 / none / on |
| trivial edit | < 32 tokens or < 1 % of editable region not counted as a real edit | `env.py:35-36` | same |

## Baselines here (not the paper's code)

- `PlainAgent` (`clm_baselines:PlainAgent`): the system prompt above without "Managing your
  context", no mirror file, no per-turn token readout, no nudges, no rollback. When the
  context crosses the limit the model gets the final-turn notice, then the run stops and is
  graded. This is the paper's "Mini-SWE-Agent, base harness without context management".
  With a big budget (e.g. `CONTEXT_BUDGET=0` = unlimited, or 262144 on a 262K server) it
  is the "just use a bigger window" arm.
- `SummaryAgent` (`clm_baselines:SummaryAgent`): same prompt as Plain. Before running a command, if
  the context is at least `summary_trigger_ratio` (0.75) of the limit, the harness makes one
  tool-less call: history + a compaction prompt (paraphrase of the Codex CLI compaction prompt,
  `clm_baselines.py` `SUMMARY_PROMPT`, `summary_max_tokens` 4096). Everything after the pinned
  prefix is then replaced by "Another language model started ... [SUMMARY] <text>". The command being
  run and its output stay verbatim after it. Records go to `agent/summary_calls.json`,
  and the call is snapshotted as `kind=summary`.

## Commands

Prerequisite: a server with tool calling (see above) at `$API_BASE`, serving `qwen38-27b-fp8`.

```bash
D=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context

# wiring check without a model (starts and kills its own stub; ~1 min)
STUB=1 $D/smoke.sh /mnt/fast-ai/bench-results/context-stub-smoke

# cheapest real run: one tiny task per agent (CLM, summary, plain)
API_BASE=http://127.0.0.1:18124/v1 $D/smoke.sh /mnt/fast-ai/bench-results/context-smoke-$(date +%Y%m%d)

# real comparison, 32K-window setting, pressures 1x/2x/4x, seed 0 (same task dir for all arms)
OUT=/mnt/fast-ai/bench-results/context-kv-32k-$(date +%Y%m%d)
export API_BASE=http://127.0.0.1:18124/v1
$D/run-contextbench-clm.sh "$OUT"                      # generates $OUT/tasks on first use
BASELINE=both $D/run-contextbench-baseline.sh "$OUT"   # summary, then plain
$D/summarize_results.py "$OUT"/jobs/*                  # one table over all arms

# variants
PRESSURES="1 2 4 8" SEEDS="0 1 2" ...                  # more tasks (only when $OUT/tasks is new)
CLM_EDIT_GATE=shrink $D/run-contextbench-clm.sh ...    # the paper's BCP edit gate
CONTEXT_BUDGET=32768 MAX_TOKENS=8192 ...               # paper ContextBench limit; needs window >= 40960
ENABLE_THINKING=false ...                              # roughly halves generation time
TASKS=/path/to/any/harbor/task-or-dataset ...          # any Harbor task (e.g. Terminal-Bench) instead
```

Outputs: `$OUT/jobs/<job>/<trial>/agent/{usage.json,timing.json,trajectory.json,trajectory.ctx.json,context_snapshots/}`,
`.../verifier/{reward.txt,details.json}`, plus `$OUT/<job>.{settings.txt,log,summary.txt}`.
The summary table gives the reward, LM calls, bash turns, free edit turns, real edits, summaries,
nudges, rollbacks, prompt/completion tokens (summary calls included), peak sent context, the harness's
prefix-cache-aware and naive prefill token counts and PFLOPs (Qwen3.6-27B constants,
`flops_model_key=27b`; whether they match Qwen3.8-27B is unverified), wall seconds, and a
rule-violation flag (any command naming `/opt/kvstream`).

## Rough cost (kvstream, 26,624-token enforced limit, thinking on, greedy)

One SET batch is ~5.9k o200k tokens (~6-7k Qwen tokens, estimate). These are planning estimates
at ~90 tok/s decode and ~3,400 tok/s prefill, with **no prefix caching**, because our server
disables it, so every call re-reads its whole prompt:

| run | LM calls | prompt tokens read | generated | wall |
|---|---|---|---|---|
| smoke (1 tiny task, per agent) | 4-8 | 10-20k | 2-5k | 1-2 min |
| pressure 1x (5 batches) per agent | 8-15 | 100-200k | 5-12k | 2-4 min |
| pressure 2x (11 batches) per agent | 15-30 | 300-500k | 10-25k | 4-8 min |
| pressure 4x (22 batches) per agent | 30-60 | 0.7-1.3M | 20-45k | 8-15 min |
| full default comparison (3 pressures × 3 arms) | ~150-300 | ~3-6M | ~100-250k | ~45-90 min |

The plain arm stops early once it overflows, so it is cheaper and scores low at ≥1x pressure.
The summary arm cannot carry 100s of 24-word values through a 4,096-token summary. Both
arms do better if the model offloads batches to files (`next > b1.txt`), which the task
allows, as in the paper's KV Store task. CLM editing turns force a re-read of everything
after the edit. Without prefix caching every call re-reads everything anyway.

## Second comparison (2026-10-05)

Why and how: `../../notes/2026-10-05-self-editing-first-comparison.md`. The first run's losses
all came from the model's own `next | tee file | head` (broken pipe), not from any context
policy. New pieces:

| file | what |
|---|---|
| `make_kvstream_tasks.py --tokens N --mode memory\|notes` | v2 kv tasks at absolute sizes (served-model tokens via `tokenizers` + the model's tokenizer.json), storage rule, delivery log, shared v2 grader (correct/blank/stale/wrong, file scan, void). `--pressure` still builds the first comparison's tasks byte for byte. |
| `make_ledger_tasks.py` | running-ledger task (SET/ADD/DEL on ~160 counters + noise memos), same modes and grader |
| `second-comparison.sh` | arms A, B32, B131, C32, C131, D32, E32 over both tasks; SUBSET full/core/quick; DRY_RUN=1; STUB=1 (+ rule probes) |
| `run-context-job.sh` | v2 caps: steps 4 × items + 40, call cap 3 × steps, OBS_MAX_CHARS ≥ 2 × largest item; TASK_TEMPLATE, SUMMARY_MAX_TOKENS |
| `clm_baselines.py` | summary cap max(4096, max_tokens), empty-reply retry with thinking off, over-limit summary before a call |
| `summarize_results.py` | arm/kind/mode/size/seed, ended_by, rule (VOID/suspect), diagnostics table, `--check` |
| `fake_openai_server.py` | answers correctly from the stream it saw; FAKE_PLAN=violate / inline probes |
| `DROP_OLD_THINKING=1` (runner) / arms `At B32t C32t E32t` | every model call (agent and summary) sends `chat_template_kwargs.preserve_thinking=false`, and earlier turns' reasoning is stripped from the history before each call (logged to `agent/dropped_thinking.jsonl`), so what is sent, what the budget gate counts and the self-editing mirror agree; CLM uses `clm_baselines:ClmAgentT` (the unmodified agent plus this switch). Summary table: `cached_tokens`, `think_share` |
| `stub-checks.sh <dir>` | smoke + tiny-budget summary/self-edit trials (summary must fire; container file list) + the drop-thinking request checks; PASS/FAIL lines |
| `clm_improved.py` (`run-context-job.sh improved`, arms `B32i B131i`) | improved self-editing agent: a delivered item is never rolled back or cut, a room check refuses `next` when the item cannot fit, harness-owned `/tmp/.live_ctx/STATE.txt` shown as the last message each call (counted in the budget like any message; validated, restored if broken; excluded by the memory-only grader like the mirror), old thinking dropped, optional `THINK_CAP` (two-call `continue_final_message` protocol) |
| `ctxfold.py` (installed as `ctxfold` by the improved agent) | folds every delivered item still in context into STATE.txt with the model's own `/tmp/.live_ctx/FOLD.py` (`fold()` + `selftest()`), after checking the selftest covers every line kind and the per-kind tally matches the item; refuses and changes nothing otherwise. FOLD.py is pinned with STATE.txt; arms `B32ik B131ik` add a per-turn thinking cap (THINK_CAP_K, 8192) |
| v3 arms `B32in B32io E32o`, `STABLE_RENDER`, `THINKING_POLICY` | B32in: improved agent with thinking off on routine fetch/fold calls and on where judgement is needed (until FOLD.py has folded once, after a ctxfold refusal / room-check refusal / state rejection / tool error / budget notice, and for the final item; `ClmImprovedAgent._wants_thinking`), reasoning_effort=medium so the system message is the same with thinking on or off; B32io: thinking off on every call; E32o: plain, files allowed, thinking off. Improved arms render earlier turns stably (preserve_thinking=true with thinking stripped, mirror edits keep untouched turns byte-identical, rollback notices appended); `STABLE_RENDER=1` gives plain drop-thinking arms the same. Summary columns: think_tok_est / other_tok_est, thinking_off_calls, prefix_stable_share |
| arm `Aw`, `SHOW_WINDOW=1` (plain agent) | every tool result ends with "[context: N of M tokens used; K left]" (M = server window minus max_tokens) and a `next` that cannot fit (context + largest item so far + max_tokens > window) is refused with a request to write down what is needed first; `window_stats.json` counts refusals |
| `second-comparison.sh` extras | explicit `ARMS` run arm by arm in the given order; `$OUT_DIR/STOP` stops cleanly before the next trial; graders of existing tasks refreshed (`make_kvstream_tasks.py DIR --refresh-graders`); estimate from the measured speeds |
| `summarize_results.py <OUT_DIR>/runs` | accepts trial, job, `jobs/` or `runs/` dirs; `items_lost` (delivered items that never reached any context), improved-agent counters; suspect check judges shell text and embedded code separately and ignores writes to the mirror/STATE.txt |

```bash
D=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context
OUT_DIR=/tmp/x API_BASE=http://unused DRY_RUN=1 SUBSET=core $D/second-comparison.sh    # plan + estimate
STUB=1 SIZES=4000 OUT_DIR=/mnt/fast-ai/bench-results/context-stub-second $D/second-comparison.sh
API_BASE=... OUT_DIR=/mnt/fast-ai/bench-results/context-clm-second-$(date +%Y%m%d) SUBSET=core $D/second-comparison.sh
```

## Validation done (stub only)

- `clm-harbor --help`, `harbor trial start --help`, and `import clm_harness.clm_agent.harness` work.
- `STUB=1 smoke.sh`: all three agents ran end to end. Docker build → `next` items → answers
  file → submit → verifier → summary table. Oracle agent (`harbor run -a oracle`) scores 1.0, so the
  grader works.
- Small-budget stub run (`CONTEXT_BUDGET=4096 BUDGET_RESERVE=512`): SummaryAgent compacted
  2,994 → 662 tokens; ClmAgent fired 4 nudges and 1 rollback (the stub never edits).
- Request body seen by the stub: `max_tokens`, `temperature: 0.0`, `chat_template_kwargs.enable_thinking`,
  `tools` present, no `top_p`.

## Limits

- kvstream is one of ContextBench's four tasks, re-created from the paper text. Needle
  Retention, Sudoku Sketchpad and Log Triage are not built. Needle Retention grades the final
  context, which a Harbor verifier cannot see. It could be graded from `trajectory.json`.
- The task's "do not read /opt/kvstream" rule is checked after the run, not enforced.
- Only the Harbor `docker` environment was tested. No-network task modes need docker buildx.
- Upstream code is CC BY-NC 4.0.
