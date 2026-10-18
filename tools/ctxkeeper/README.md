# ctxkeeper

**Let an AI agent keep working on one long task after its conversation has grown far past what the model can read
at once, without forgetting what it was told.**

ctxkeeper is a small proxy that sits between your agent (or chat app) and your model server. Your agent keeps
sending its whole history, as agents do. The proxy shows the model a short, current view of it: the opening
instructions, a set of **notes** it keeps up to date (standing rules, current facts, open questions), and the most
recent turns. Everything older goes to an **archive** on disk, and the model gets a `recall` tool to search it. The
model and the server are not changed in any way; only what the model is shown each time changes.

```
your agent / app  --->  ctxkeeper (:18200)  --->  any OpenAI-compatible server (vLLM, llama.cpp, SGLang, ...)
  sends everything        keeps notes + archive,       sees a short, current view
                          shows a bounded view
```

Version 1.1.0 · public domain ([Unlicense](LICENSE)) · Python 3.10 or newer, standard library only (two files:
`ctxkeeper.py`, `notesdelta.py`) · in plain words: <https://skindeep.ai/context-use.html>

## Does it work?

Measured on Qwen3.8-27B (FP8, served by vLLM on two Intel Arc Pro B70 cards), with a 32K-token live window:

| Test | With ctxkeeper | Without it |
| --- | --- | --- |
| **Real code repair**: 40 bugs to fix in a real Python library, handed out one ticket at a time, with three house rules announced along the way, then questions about the earliest fixes | **40/40 fixed, 40/40 following every rule, 7/7 questions right**, in 16 min (`--recipe qwen`); 36-38 min (`--recipe agent`); both with `--recite-when` for the tickets | Sliding 32K window: 22 to 35 of 40 clean, 0/7 questions. Summarizing the history: 33 to 40 of 40, 0 to 7 of 7 |
| **The same task with a separate agent program** that manages nothing itself ([freeagent](../freeagent/freeagent.py)) | **40/40, 40/40, 7/7 in 33 min**, reading 2.9M prompt tokens; at release, with `--recipe qwen` and no other option: **40/40, 40/40, 7/7 in 31 min** | The same agent sending everything into a 262K window: same score, 55 min, 29.9M prompt tokens |
| **Memory over 1M tokens**: 228 questions about things said up to a million tokens earlier | **226/228 (99%)** in 50 min | A 200K window: 166/228 (73%), every one of 29 standing-rule questions wrong, 228 min |
| **2M tokens with planted traps** (values that change and change back, corrections, pronouns) | **351/382 (92%)**, 0 of 12 traps fell for | (not run: no window holds it) |

## Tested before release

Version 1.0.0 was installed the way a user installs it (pip into a fresh environment; the Docker image built from
the source archive; the program files are byte-identical to this release's) and run as written, against the same
Qwen server unless noted:

| Check | Result |
| --- | --- |
| The code-repair task above through freeagent, `--recipe qwen`, nothing else | 40/40 fixed, 40/40 following every rule, 7/7 questions, 31 min |
| [`long_chat.py`](examples/long_chat.py) through the Docker image, 300K tokens (more than the server's own 262K window) | 4/4, 4 min |
| The OpenAI SDK snippet below | plain reply, tool call and streaming all came back in the SDK's types |
| **Another model and server:** `long_chat.py` through `--recipe agent --budget 15360` to Gemma 4 26B (Q8) on llama.cpp, 100K tokens | 4/4, 4.5 min (a smoke test: one run) |
| **1.1.0 from the public release:** checksums, pip from both URLs, the Docker image built from the archive URL; `long_chat.py` through it to the same Gemma server with a 4K view (`--budget 4000 --inplace-fit`), 16K tokens | all OK; 4/4 in 1 min ([record](../../experiments/qwen38-27b-b70/data/2026-10-16-context-campaign22/release-1.1.0-check/)) |

Records: [`data/2026-10-14-context-campaign19/`](../../experiments/qwen38-27b-b70/data/2026-10-14-context-campaign19/).

Version 1.0.1 changes only how requests and replies are passed on ([Changes](#changes)); its program files are
byte-identical to the ones the twelve-agent test below ran. Version 1.1.0 adds options that are all off by default
([Added in 1.1.0](#added-in-110-all-off-by-default)); with them off it sends the same requests and keeps the same
state as 1.0.1 (all 1.0.1 tests pass, and a request-by-request comparison against a scripted model over five
setups came out identical).

## Tested with 12 open-source coding agents

The same code-repair task, through `--recipe qwen` and the same Qwen server, with each agent as shipped except
that its own history trimming or summarizing was turned off (set-ups:
[agentbench](../agentbench/README.md)). One run each, 60 minutes at most, sorted by time:

| Agent | Fixed (of 40) | Following every rule | Questions (of 7) | Time |
| --- | --- | --- | --- | --- |
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) 2.4.6 | 40 | 40 | 7 | 14 min |
| [Open Interpreter](https://github.com/openinterpreter/openinterpreter) 0.0.56 | 40 | 39 | 7 | 18 min |
| [freeagent](../freeagent/freeagent.py) (the lab's own, for comparison) | 40 | 39 | 7 | 21 min |
| [Cline CLI](https://github.com/cline/cline) 3.0.71 | 40 | 40 | 7 | 24 min |
| [Goose](https://github.com/aaif-goose/goose) 1.54.0 | 40 | 40 | 7 | 24 min |
| [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk) 1.54.0 | 40 | 40 | 6 | 24 min |
| [Mistral Vibe](https://github.com/mistralai/mistral-vibe) 2.26.1 | 40 | 40 | 7 | 26 min |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) 0.22.1 | 40 | 40 | 7 | 26 min |
| [pi](https://github.com/earendil-works/pi) 1.2.0 | 39 | 39 | 0 | 28 min |
| [OpenCode](https://github.com/anomalyco/opencode) 1.19.0 | 40 | 40 | 7 | 33 min |
| [Qwen Code](https://github.com/QwenLM/qwen-code) 0.25.1 | 40 | 39 | 7 | 33 min |
| [Kimi Code](https://github.com/MoonshotAI/kimi-code) 2.2.0 | 40 | 40 | 7 | 38 min |
| [ForgeCode](https://github.com/tailcallhq/forgecode) 2.14.0 | 25 | 25 | not reached | 60 min (time limit) |

Eleven of the twelve agents fixed 39 or 40 bugs. pi wrote its answers to the seven questions and then
deleted them, after a wrong line in the notes said the questions had never been asked (see [Limits](#limits)).
ForgeCode was still working, correctly, when its hour ran out. OpenCode ran later, alone, with its memory capped
at 400 MiB and swap behind it, because the test machine had too little memory free beside the server for it at
first. ForgeCode and OpenHands only work from 1.0.1 on.

Full record, every run and what went wrong: the lab note
[`2026-10-10-context-16k-baseline.md`](../../experiments/qwen38-27b-b70/notes/2026-10-10-context-16k-baseline.md)
(campaigns 10 to 20, the agents in campaign 20, data in
[`data/2026-10-15-context-campaign20/`](../../experiments/qwen38-27b-b70/data/2026-10-15-context-campaign20/)) and
[HISTORY.md](HISTORY.md). One model, one machine: see [Limits](#limits).

## Install

Pick one. All three come from the [1.1.0 release](https://github.com/steveseguin/b70-optimization-lab/releases/tag/ctxkeeper-v1.1.0)
(small files; nothing clones the lab's large repository):

```bash
R=https://github.com/steveseguin/b70-optimization-lab/releases/download/ctxkeeper-v1.1.0

# 1. pip (gives you the `ctxkeeper` command)
pip install $R/ctxkeeper-1.1.0-py3-none-any.whl

# 2. Docker (builds the image from the 90 KB source archive)
docker build -t ctxkeeper $R/ctxkeeper-1.1.0.tar.gz

# 3. just the two files (run with python3 ctxkeeper.py ...)
curl -LO $R/ctxkeeper.py
curl -LO $R/notesdelta.py
```

The source archive `ctxkeeper-1.1.0.tar.gz` also holds the demo below, the tests and this README; the release page
lists every file's SHA-256.

## Quick start

1. Run a model server that speaks the OpenAI API and accepts at least 32K tokens per request (more is fine; the
   proxy keeps each request under its window). For example vLLM on port 8000.
2. Start the proxy in front of it:

   ```bash
   ctxkeeper --upstream http://127.0.0.1:8000 --recipe agent    # any OpenAI-compatible server
   ctxkeeper --upstream http://127.0.0.1:8000 --recipe qwen     # Qwen3.x behind vLLM: the fastest measured settings
   # Docker: docker run --rm --network host -v ctxkeeper-state:/state ctxkeeper --recipe agent --upstream http://127.0.0.1:8000
   ```

3. Point your agent or app at `http://127.0.0.1:18200/v1` instead of the server.
4. See it work: [`examples/long_chat.py`](examples/long_chat.py) holds a conversation several windows long, says a
   codename, a budget and a standing rule at the start, and asks about them at the end.

   ```bash
   curl -LO $R/long_chat.py      # or examples/long_chat.py in the source archive
   python3 long_chat.py --base-url http://127.0.0.1:18200/v1
   ```

## Use it with your agent or app

Anything that can be given an OpenAI-compatible base URL works, if it:

- uses the **Chat Completions** API (`/v1/chat/completions`). Other endpoints (`/v1/responses`, `/v1/completions`,
  `/v1/models`, ...) are passed through untouched, without any context management;
- **sends its whole history** every time (most agents do) and has **its own truncation or summarizing turned
  off**: a history from which something the proxy archived has vanished is treated as a new conversation;
- asks for one reply per request (`n` = 1). Streaming works, but the reply arrives in one piece at the end (the
  proxy must first see whether the model wanted to search its archive).

Python with the official SDK:

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:18200/v1", api_key="unused")   # the key is passed on to your server
reply = client.chat.completions.create(model="your-model", messages=history)
```

Several conversations can share one proxy. Each is recognized by its model name, system messages and first user
message; to name one yourself, send the header `X-Ctx-Session: <any id>`.

If your task delivers new instructions inside **tool results** (tickets, emails, files) rather than as user
messages, tell the proxy what they look like, so it repeats the standing rules right after each one:

```bash
ctxkeeper --upstream http://127.0.0.1:8000 --recipe qwen --recite-when '(?m)^TICKET \d+'
```

On the code-repair task it was not needed: its tickets arrive in tool results, and in the release test the rules
held from the notes alone (40/40). The fastest runs used it.

## Recipes

A recipe is a set of options that were measured together. Any option given on the command line still wins.

| | `--recipe agent` | `--recipe qwen` |
| --- | --- | --- |
| For | any OpenAI-compatible server and model | Qwen3.x behind vLLM (sends `chat_template_kwargs`) |
| Live window | 32,768 tokens (`--budget`) | 32,768 |
| Notes | in place, every 15,000 tokens of new turns, changes only | same, written without thinking |
| Extra per request | nothing | `reasoning_effort: medium`, which keeps the prompt identical with thinking on or off so the server's prefix cache serves the notes calls |
| Measured (code repair) | 40/40 clean, 7/7, 36-38 min | 40/40 clean, 7/7, 16 min |

Window size: on the code-repair task 24K worked as well as 32K (13 min); at 16K one rule slipped once (39/40) and
the notes no longer had room to be written in place. Bigger windows are slower: the model reads more every turn.

## Watching it

- `GET http://127.0.0.1:18200/ctxkeeper/status`: per conversation, how many cuts, messages archived, archive
  searches, rules put back, and the token ratio learned from the server.
- State per conversation under `--state-dir` (default `~/.cache/ctxkeeper/<id>/`): `archive.jsonl` (every message
  moved out of view, verbatim), `state.json` (the current notes), `notes-history.jsonl` (every version of the
  notes), `events.jsonl` (every notes reply, and why any was rejected).

## Options you may want

| Option | What it does |
| --- | --- |
| `--upstream URL` | the model server, without `/v1` |
| `--host`, `--port` | where the proxy listens (default `127.0.0.1:18200`) |
| `--budget N` | live window in tokens, reply included |
| `--recite-when REGEX` | also repeat the rules when the newest message matches (instructions arriving in tool results) |
| `--think-when REGEX`, `--think-until REGEX` | turn thinking on only around matching messages (Qwen-style `enable_thinking`) |
| `--notes-checks near` | extra checks for ledger-like state with names such as `abcd12` (the lab's memory streams); leave it off for ordinary agent work |
| `--recall-label REGEX` | let `recall` use your content's own numbering (e.g. `'(?m)^ITEM (\d+)/'`) instead of message numbers |
| `--lookups` | with `--recall-label`: a notes line that cites an archived item and waits on it, is doubted, or works an amount out is asked again with what that item says (off by default) |
| `--state-dir DIR` | where archives and notes are kept |
| `--no-memory-note` | do not add the short paragraph that tells the model about its notes and `recall` |

Everything else: `ctxkeeper --help`.

### Added in 1.1.0 (all off by default)

| Option | What it does |
| --- | --- |
| `--notes-upstream URL`, `--notes-model NAME` | send the notes calls to a second, separate model server (a smaller keeper) |
| `--notes-system TEXT\|@file`, `--notes-kwargs JSON` | the keeper's own system message and chat-template options |
| `--notes-prefill` | start a separate keeper's reply with the notes heading, so a small model writes notes instead of carrying on the agent's work (llama.cpp continues it as is; for vLLM add `--notes-extra '{"continue_final_message":true,"add_generation_prompt":false}'`, not tested there) |
| `--notes-prepass CHARS` | for a separate keeper only: long tool results are cut to their start, end and outcome lines before it reads them |
| `--notes-extra JSON` | more fields for a separate keeper's requests; `'{"thinking_budget_tokens":0}'` turns thinking off on llama.cpp for a model whose template always starts it (LFM2.5) |
| `--notes-async wait\|defer` | write the next notes in the background right after a reply; `defer` lets requests go on with the current view while there is room. Needs a server that runs two requests at once correctly (see below) or a separate keeper |
| `--prewarm` | after background notes, have the server read the start of the view the cut will leave, so the next request finds it cached |
| `--inplace-fit` | lower the notes threshold to the room a small window actually leaves (recommended below 24K) |
| `--log-calls` | write every model call (main, notes, prewarm; tokens read, cached, written; seconds) to `calls.jsonl` |

Measured (lab campaigns 21-23, Qwen3.8-27B FP8 on two B70s unless noted; one run per setting):

- **Window size.** On a 240K-token test stream every budget from 8K to 64K kept its 39 answers (one slip at 24K);
  24K-48K was fastest (8-9 min), 64K slower (10 min). Below 16K the notes stopped fitting in place and every cut
  rewrote them in full: 24 min at 12K, 40 min at 8K. With `--inplace-fit`: 10 min at 12K, 13 min at 8K, 81 and 84 of
  85 answers over two streams. On the bug-fixing task the floor is about 16K (at 12K two fixes missed a house rule).
- **Background notes** saved 14 % (18 % with `--prewarm`) on a server running two requests at once without
  speculative decoding, same score. With MTP speculative decoding they were correct but 8 % slower (9.4 against
  8.7 min): each step is already full with one request's draft checks, and a second request slows it down. Keep the
  default (notes in line). (Our first try with MTP returned corrupted replies; that was a bug in our vLLM build with
  prefix caching, since fixed there, not in ctxkeeper.)
- **One card.** On a single B70 with a 26K view, the model keeping its own notes, the bug-fixing task came out
  40/40 fixed, 40/40 following every rule, 7/7, in 21 min (two cards: 16); the notes took 8 % of the server's time.
- **A separate, smaller keeper** (LFM2.5-24B-A2B, Q8_0 on llama.cpp on a second card, with `--notes-upstream`) did
  worse and was slower. On the 240K stream: 19/39 in 38 min (the 27B as its own keeper: 39/39 in 16). On the
  bug-fixing task, even with `--notes-prefill`: 39-40 fixed but only 20 of 40 following every rule, in 35-55 min; it
  copied the request's instructions into the notes and missed house rules. It also reads every turn afresh, while a
  model keeping its own notes reads its own cached view. Keep the main model as its own keeper; these options are
  for trying other keepers.

## How it works

1. **Notes, kept in place.** When enough new turns have gathered (15,000 tokens), the proxy sends the model the
   request it has just answered plus one message: "write what changed". Because the start of that request is the
   same as before, the server's prefix cache serves almost all of it. The reply is only the changes: new rules,
   changed facts (with the working: `stock: 120 + 49 = 169`), open items. The proxy applies them, checks them
   (a sum is recomputed, a value must start from the one held, a rule can never be dropped) and asks once more if
   a line does not hold up.
2. **Then the old turns move out.** Every turn the notes now cover goes to the archive verbatim. The model sees: the
   opening messages, the notes, and the newest exchange.
3. **Recall.** The model gets one extra tool, `recall`, a text search over the archive (and over every saved
   version of the notes). The proxy answers it itself; your agent never sees that call.
4. **Rules stay in force.** Standing rules sit in the notes, can not be dropped, and are repeated right after each
   new user message (and after messages matching `--recite-when`).

## Limits

- **Measured with one model family on one machine** (Qwen3.8-27B FP8, vLLM, Intel Arc Pro B70). Gemma 4 26B on
  llama.cpp passed one smoke test (the demo, 4/4). Other models should work if they call tools reliably and can
  follow the notes format; that has not been measured.
- **The notes are written by the model, so they can be wrong.** On the hardest test (2M tokens with traps) about
  1 in 130 notes lines was silently wrong; on the 1M test, 1 in 1,435. The archive keeps the original text, so a
  wrong note can be found and fixed by a search, but nothing guarantees the model looks. In the twelve-agent test,
  one notes line wrongly said seven questions had never been asked; the agent (pi) believed it and deleted the
  answers it had already written.
- **The opening messages are always kept**, so the system prompt and the first user message must fit well inside
  the window.
- Token counts are estimated (characters over a ratio learned from the server's reported usage), with margins.
- **No authentication, and everything is stored in plain text** under `--state-dir`. The proxy listens on
  `127.0.0.1` by default; the Docker image listens on all interfaces, so publish its port only where you mean to.
- Tested with one conversation at a time. Separate conversations have separate state and locks.

## Changes

**Unreleased** (lab, 2026-10-17): `--upstream-retries N` (default 0, off) with `--upstream-wait SECONDS` (default
900): when the model server fails a call (no answer, or HTTP 5xx), the proxy polls the server's `/health` until it
answers 200 and sends the same call again, at most N times; a refusal (HTTP 4xx) is passed on as before. For long
tasks on a server that may be restarted under them (for example by a supervisor after a GPU fault): a greedy call
to an exact server gets the answer the failed one would have had, so the task loses only the time. Not measured
yet on a real restart.

Unreleased (1.2.0.dev0, 2026-10-17), a new option, off by default: `--lookups` (with `--notes-mode inplace` and
`--recall-label`). A CHANGES line that says it waits on an archived entry (`amount not yet known, must recall item
32`) is asked again, once per cut. The question shows what that item says about the name: each sentence that names
it, with the next one, word for word. The note checks count what is shown as stated, as they do an archive
search's result. In-place notes calls cannot search the archive themselves. Lab campaign 32: such a line waited
55 items, and the model's own sum over the whole history at the end was one off.
1.2.0.dev1 (2026-10-17): a line the note checks doubt (an amount the turns do not state) that cites an archived
item gets the same question, instead of only being asked to read the item again, which it cannot do once the item
is archived. Lab campaign 33b: a reversal was written from memory with a wrong amount (10 for 28) and then left out.
1.2.0.dev2 (2026-10-17): a line that works an amount out (`a + b`, `a - b`) and cites an archived item is asked too,
and the question says that the NOTES value already counts the entries shown. Lab campaign 34 (1M, seed 0): three
of eight reversals went wrong in such lines: an amount from memory, a whole-history sum that misread a "recorded at",
and an entry added back before it was taken out. On the recorded runs the wider trigger asks at 0 of 17 cuts on the
plain streams and at 7 of 75 cuts at 1M, all of them audit lines.
1.2.0.dev3 (2026-10-18), from lab campaign 38 (2M tokens, forged notices and quiet audits, 410/423):
- `--lookups` also asks for a line that leaves the amount as a gap after a sign (`447 + (item 85 decrease reversed,
  item 473)`). Three of sixteen reversals were written that way, never asked about, and answered without the
  reversal.
- A new option, off by default: `--rule-scan REGEX`. A sentence of the turns being moved out that matches it and that
  no RULES line has (no line holds 60 % of its words or cites its unit) is shown once per cut, with a question asking
  for any rule among them in its original words. In the same run the first notes reply wrote no rule for turns that
  state two. The confidentiality rule then lived only in an OPEN line and was never repeated at a question, and 9 of
  59 questions about the confidential counter got a number.
- On the recorded runs, the wider lookup trigger adds exactly those three lines. The rule scan, with the lab's
  pattern, asks at no cut of the 1.2.0 runs that passed and at the first cut of both 2M runs.

1.2.0.dev4 (2026-10-18), from lab campaign 39 (2M, 413/423, 16/16 audits): a new option, off by default,
`--hold-open` (needs `--recite-when` and `--think-until`). While a question is open, from the message that asks it
until one matching `--think-until`, every request gets the RULES recital and the archive searches made since it
arrived, not only the request whose newest message asks it. In that run the reply that searched printed the answers
file, and the answers were written one turn later: without the two values the searches had found, and, for a
confidential counter, without the recital (it was answered with its value). In the recorded 2M runs the option
reaches about 70 of 1,310 requests.

1.2.0.dev5 (2026-10-18), from lab campaign 43 (2M, seed 2, 405/423): with `--notes-checks count` or `near`, a NOTES
line whose name has a space inside it (`voned i62`) goes to the name its parts make when joined (`vonedi62`), if the
turns mention that name or the NOTES hold it. In that run every notes reply wrote the name split. The split name became
a STATE line of its own and took every change, while the real name's line kept its first value for the whole run;
four questions were answered from that stale line. Replayed through the 973 notes replies of ten earlier sessions,
nothing changes; in the campaign 43 session, 61 replies get the join and nothing else.

1.2.0.dev6 (2026-10-18), from lab campaign 44 (2M, seed 2, 411/423): when a notes reply that was asked for (after a
check, or with the archived entries a line waits on) thinks and writes nothing, it is asked once more without
thinking before the reply before it stands; the notes call may take six replies instead of five, so the retry
leaves every check its turn. In that run the reply to the lookup that showed `penike87 went up by seventy-two` came
back empty, the reply before it stood with `638 - (item 317 increase, amount unknown) = unknown`, and that line stayed
in 95 NOTES versions: the audit and two questions about the counter were lost. Empty asked-for replies with thinking
on came 42 times in 17 recorded sessions (one to six per long run); until now each one let the earlier reply stand.

1.2.0.dev7 (2026-10-18), from lab campaign 45 (2M, seed 2, 411/423): of an archive search's result, only the lines of
tool and user messages are kept for the note checks; the model's own earlier text is not (it is still shown to the
model). In that run a search returned, besides the items, the model's own `keruba67 -128-56=-184`; a later notes line
`keruba67: -128 - 51 = -179` (the NOTES held -184) then passed as starting from a value the turns set, and the counter
stayed 56 off for 117 versions and five answers. Replayed through about 2,500 notes replies of 29 sessions, 23 get
other verdicts: the wrong lines of that run, a reversal of campaign 43 written with a wrong amount, one false alarm
(one more question) and swapped questions about the same line.

Also unreleased (1.1.1.dev1, 2026-10-17): a NOTES line whose new value states no number of its own (only item or
ticket numbers, as in `audit reversal of the entry in item 4, amount not yet known, must recall items 4/5`) no longer
replaces a number the NOTES hold: the number stays and the line is kept as a remark on it. Before, the value became the
last item number (5) and the line was asked again. Lab campaign 31: a counter that waited on an archive search was
reversed twice that way. Only for a STATE value that is a plain number; descriptions (`contains lines for tickets 10
and 11`) are written as before. A replay of 29,272 saved lines changed only those lines.

Also unreleased (1.1.1.dev0, 2026-10-17): with `--notes-checks near`, an amount the model took from an archive search
counts as stated. The proxy keeps the text of its latest searches (up to 120,000 characters, in memory) as evidence
for the amount check only, never as a mention of a name. Before, a correct line worked out from a recalled entry was
"an amount the turns do not state" and was left out. Lab campaign 30: an audit naming only the item of the entry it
reverses was lost that way. Each search is now also logged to `events.jsonl`.

**1.1.0** (2026-10-16): new options, all off by default ([Added in 1.1.0](#added-in-110-all-off-by-default)): a
separate keeper model (`--notes-upstream`, `--notes-model`, `--notes-system`, `--notes-kwargs`, `--notes-extra`,
`--notes-prefill`, `--notes-prepass`), background notes (`--notes-async`, `--prewarm`), `--inplace-fit` for small
windows and `--log-calls`. Default behaviour is unchanged (same requests, same state as 1.0.1).

**1.0.1** (2026-10-15), found by running twelve agents through it:

- Streamed replies keep the model's thinking (vLLM's `reasoning` field); 1.0.0 dropped it when the client streamed.
- Several system messages at the start of a request are joined into one (ForgeCode sends two; Qwen's chat template
  refuses that).
- A system message sent as a list of text parts keeps its form, and the memory note goes inside it instead of into
  a second system message (OpenHands).
- With `--effort` (part of `--recipe qwen`), the proxy's value replaces a `reasoning_effort` the client sent
  (OpenHands sends `high`, which Qwen3.8's template refuses).

**1.0.0** (2026-10-14): first release.

## Development

```bash
cd tools/ctxkeeper
python3 -m unittest test_ctxkeeper test_notesdelta     # against a scripted model; no server needed
python3 sync_notesdelta.py                             # the checks are a copy of the lab harness's: must match
```

`check_score.py` replays saved notes replies through the checks against a task's true ledger (how each check rule
was fitted and regression-tested); `replay_diff.py` compares two versions of the checks on saved replies.
[HISTORY.md](HISTORY.md) is the build-by-build record.
