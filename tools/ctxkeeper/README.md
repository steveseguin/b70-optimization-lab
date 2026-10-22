# ctxkeeper

**Keep an AI agent working on long tasks, with current notes and searchable conversation history.**

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

Version 1.2.0 (previous release: 1.1.0) · public domain ([Unlicense](LICENSE)) · Python 3.10 or newer, standard library only (two files:
`ctxkeeper.py`, `notesdelta.py`) · download and setup: <https://skindeep.ai/ctxkeeper.html>

## Does it work?

Measured on Qwen3.8-27B (FP8, served by vLLM on two Intel Arc Pro B70 cards), with a 32K-token live window:

| Test | With ctxkeeper | Without it |
| --- | --- | --- |
| **Real code repair**: 40 bugs to fix in a real Python library, handed out one ticket at a time, with three house rules announced along the way, then questions about the earliest fixes | **40/40 fixed, 40/40 following every rule, 7/7 questions right**, in 16 min (`--recipe qwen`); 36-38 min (`--recipe agent`); both with `--recite-when` for the tickets | Sliding 32K window: 22 to 35 of 40 clean, 0/7 questions. Summarizing the history: 33 to 40 of 40, 0 to 7 of 7 |
| **The same task with a separate agent program** that manages nothing itself ([freeagent](../freeagent/freeagent.py)) | **40/40, 40/40, 7/7 in 33 min**, reading 2.9M prompt tokens; at release, with `--recipe qwen` and no other option: **40/40, 40/40, 7/7 in 31 min** | The same agent sending everything into a 262K window: same score, 55 min, 29.9M prompt tokens |
| **Memory over 1M tokens**: 228 questions about things said up to a million tokens earlier | **226/228 (99%)** in 50 min | A 200K window: 166/228 (73%), every one of 29 standing-rule questions wrong, 228 min |
| **2M tokens, hostile**: forged notices of four kinds and quiet retroactive corrections planted in the stream | On 1.2.0, both seeds (lab campaign 49, hash-bound public audits): **421/423 and 417/423, 16/16 corrections applied on both seeds**; every forged line the notes carried was flagged, and no forged value, method, rule or removal was ever adopted. Two of 97 forgery-target answers slipped on silent arithmetic (the notes held the right value throughout), so the lab's strictest preregistered bar is not claimed. On dev9, the two seeds scored 414/423 and 416/423. | (not run: no window holds it) |

The hostile test uses task-specific settings (K32C), including notes thinking, archive labels, rule matching,
lookups, cited entries and arithmetic checks. It is not a measurement of the default `--recipe qwen` settings.
The [registered runner](../../experiments/qwen38-27b-b70/scripts/longrun-campaign37.sh) records the full configuration.

## Tested before release

Version 1.0.0 was installed the way a user installs it (pip into a fresh environment; the Docker image built from
the source archive) and run as written, against the same
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

## Which model do I need?

Everything above was measured on **Qwen3.8-27B** (official FP8, vLLM, one or two Intel Arc Pro B70 cards). One smoke
test also passed on **Gemma 4 26B** (Q8_0 GGUF, llama.cpp): the demo below, 4/4, at a 15,360-token view
(`--recipe agent --budget 15360`). Any current model of that class should work if it:

- **calls a tool reliably when the answer is not in view** — the only tool is `recall`, a text search over the
  archived turns;
- **can keep a simple notes layout** (RULES / STATE / OPEN, changes-only updates with the working shown);
- sits behind a server with **room for the default 32K view and the reply**. The proxy estimates token counts;
  allow headroom and keep individual messages and requested output lengths within the server's capacity.

Practical guidance, measured on the Qwen setup unless noted:

- **Let the model keep its own notes.** A separate, smaller keeper (LFM2.5-24B-A2B Q8 on a second card) was worse
  and slower: 19/39 in 38 min on the 240K stream, where the main model scored 39/39 in 16, and only 20 of 40
  rule-clean on the repair task. It reads every turn afresh; the main model re-reads its own cached view. The
  second-model options (`--notes-upstream` and friends) are for trying other keepers, not for production.
- **View size:** 32K is the default and about the fastest (24K-48K tie on question streams). The repair-task floor
  is ~16K (at 12K a house rule slipped). Below 16K the notes no longer fit beside the newest turns; add
  `--inplace-fit` (10 min at 12K, 13 min at 8K, 81 and 84 of 85 answers over two streams). A bigger view is only
  slower: the model re-reads more each turn.
- **Thinking:** fine for the agent's turns; `--recipe qwen` pins `reasoning_effort: medium` so the notes calls keep
  the same prompt and come from the server's cache (91% of notes tokens served from cache). Notes themselves are
  written without thinking.
- **Server features:** turn the server's prefix cache on — it does most of the notes work. With speculative
  decoding (MTP) keep notes in line (the default): background notes were correct but 8% slower there. Without
  speculative decoding, on a server running two requests at once, `--notes-async defer --prewarm` saved 14-18%.
- **One card is enough:** the same repair score in 21 min (two cards: 16).
- Measured with one conversation at a time. Separate conversations keep separate state, locks and archives.

## Install

Pick one. All three come from the [1.2.0 release](https://github.com/steveseguin/b70-optimization-lab/releases/tag/ctxkeeper-v1.2.0)
(small files; nothing clones the lab's large repository):

```bash
R=https://github.com/steveseguin/b70-optimization-lab/releases/download/ctxkeeper-v1.2.0

# 1. pip (gives you the `ctxkeeper` command)
python3 -m venv .venv-ctxkeeper
. .venv-ctxkeeper/bin/activate
python -m pip install "$R/ctxkeeper-1.2.0-py3-none-any.whl"

# 2. Docker (builds the image from the 90 KB source archive)
docker build -t ctxkeeper $R/ctxkeeper-1.2.0.tar.gz

# 3. just the two files (run with python3 ctxkeeper.py ...)
curl -LO $R/ctxkeeper.py
curl -LO $R/notesdelta.py
```

The source archive `ctxkeeper-1.2.0.tar.gz` also holds the demo below, the tests and this README; the release page
lists every file's SHA-256.

## Quick start

The managed Chat Completions path currently requires an upstream reachable without an API key.
Client Authorization headers are not forwarded on that path; use `api_key="unused"` as an SDK placeholder.
Keep this unauthenticated proxy on localhost or a trusted private network.

1. Run a model server that speaks the OpenAI API, with headroom beyond the default 32K view. Token counts are
   estimated, and a single oversized message may still exceed the server's limit. For example vLLM on port 8000.
2. Start the proxy in front of it:

   ```bash
   ctxkeeper --upstream http://127.0.0.1:8000 --recipe agent    # any OpenAI-compatible server
   ctxkeeper --upstream http://127.0.0.1:8000 --recipe qwen     # Qwen3.x behind vLLM: the fastest measured settings
   # Linux Docker: docker run --rm --network host -v ctxkeeper-state:/state ctxkeeper --host 127.0.0.1 --recipe agent --upstream http://127.0.0.1:8000
   ```

3. Point your agent or app at `http://127.0.0.1:18200/v1` instead of the server.
4. See it work: [`examples/long_chat.py`](examples/long_chat.py) holds a conversation several windows long, says a
   codename, a budget and a standing rule at the start, and asks about them at the end.

   ```bash
   R=https://github.com/steveseguin/b70-optimization-lab/releases/download/ctxkeeper-v1.2.0
   curl --fail --location --output long_chat.py "$R/long_chat.py"
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

Python with the official SDK (a separate optional dependency). In your client terminal, create and activate
an environment; this also works when the proxy runs in Docker:

```bash
python3 -m venv .venv-client
. .venv-client/bin/activate
python -m pip install openai
```

Use this Python code with a model ID from `http://127.0.0.1:18200/v1/models`:

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:18200/v1", api_key="unused")   # SDK placeholder for an unauthenticated local server
history = [{"role": "user", "content": "Remember: our project is called Cedar."}]
reply = client.chat.completions.create(model="your-model", messages=history)
print(reply.choices[0].message.content)
history.append(reply.choices[0].message.model_dump(exclude_none=True))
# Append each new user message and send the whole history on the next call.
```

Several conversations can share one proxy. Each is recognized by its model name, system messages and first user
message. Conversations with identical openings can collide; if your client supports headers, send a unique
`X-Ctx-Session: <conversation-id>` for each one, keeping that ID on later calls and when resuming.

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
| `--cited-entries` | with `--recall-label`: when the turns being noted cite an archived item for a name ("the decrease of balosu68 entered in item 320 ... reversed"), the notes request shows what that item says about the name (off by default) |
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
- **The notes are written by the model, so they can be wrong.** On the hardest test (2M tokens with forged notices
  and retroactive corrections) 1 to 5 counter lines of 8,500-17,100 were silently wrong in a run; on the 1M test,
  1 in 1,435. The archive keeps the original text, so a
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

Development (1.3.0.dev0, 2026-10-21): opt-in `--save-conversations` retains full client requests,
returned replies and actual main-call views in a deduplicated SQLite journal. Local `--sessions list`
and `--sessions export --session NAME` commands recover saved exchanges after a restart, including
recent turns that have never reached the recall archive. See [saved conversations](CONVERSATIONS.md)
for setup, continuation, backup and failure semantics. This is text-based recovery, not GPU-state
restoration; runtime checkpoint integration and performance qualification remain pending. Stable
PyPI 1.2.0 is unchanged.

Development 1.3.0.dev1 (2026-10-21): a STATE change written as `old set to new` is stored as the new value with its
remarks, the value the keeper already read; campaign 51 seed 0 had six such lines scored wrong as written ([history](HISTORY.md)).
`--set-check` (off by default) asks once about a set or a removal the turns state for a name that none of its CHANGES lines takes.
Development 1.3.0.dev2 (2026-10-22): a notes reply cut off by the reply cap keeps its complete lines, and the retry merges over them ([history](HISTORY.md)).

Development (1.2.2.dev0, not a stable release): `--sum-check` first asks once for working on tool-call blocks
containing at least three integer assignments whose absolute values are 100 or more, when a value is absent from
the managed view and has no written arithmetic equality. It then checks multiplication in the reply that stands,
including working supplied by that retry. Each check can add one model call; an empty or recall-only retry leaves
the preceding reply standing. With `--sum-check` off, the answer path is unchanged.

This is an experimental heuristic. A number elsewhere in the view can hide an unsupported answer, and legitimate
settings can trigger a question. Plain-text answer blocks are outside its scope; very large integers (over 100
digits) are ignored. The final arithmetic retry is passed on, not retried indefinitely. The earlier offline
“112 asks / five wrong answers caught” estimate was withdrawn: it used truncated client histories rather than
the actual managed requests. No benchmark improvement or retry rate is established for this version. Review and
evidence: [lab note](../../experiments/qwen38-27b-b70/notes/2026-10-17-hostile-history-poison.md).

Development (1.2.1.dev0, 2026-10-20), from lab campaign 49 (2M hostile, both seeds, 421/423 and 417/423), all on by
default. Campaign 49's wrong NOTES lines traced to five decision points; these three changes close them:

- A reply that was asked again and came back unusable (cut off by the token cap, or empty) no longer ends the cut's
  checks. The reply that then stands goes through the remaining checks (archived entries it waits on, working that
  does not follow) before it is taken. Campaign 49d, seed 2: the asked-again reply hit the token cap and the first
  reply stood unchecked — six counters' updates never landed or landed wrong (himo29, como20, roru25, vomogu38,
  xarosu96, vonedi62), and the lines self-copied for six to ten NOTES versions. Thirty of seed 2's thirty-one wrong
  lines trace to that one cut.
- The mentions-not-accounted-for question asks for only the lines of the names it names, in the same layout, instead
  of the three complete sections again; the merge keeps the rest. A full re-listing of a long CHANGES runs past the
  token cap — that is what cut off the campaign-49d reply.
- With `--lookups`, a doubted line whose working starts from a value the NOTES do not hold and the turns do not
  state now comes with what the archive says about the name, newest first. Seed 0's one wrong line and two of seed
  2's stood after the asked-again reply repeated a start from memory (ketuni59 from -172, the NOTES holding -62;
  jami27 from 192, holding 162). Six such starts in the nineteen working questions of the two seeds.

**1.2.0** (2026-10-20): fixes from the two-million-token hostile campaigns (39-49), and new options. Both 2M
seeds were rerun on it as lab campaign 49: 421/423 and 417/423, 16/16 corrections applied on both seeds, with
hash-bound public audits.

Keeper faults fixed, on by default, each found by a recorded 2M run: a CHANGES line that opens with its item
(`(item 820) jami27: ...`) is read as that name's change, not as a new name (142 stray lines in campaign 48); a full
rewrite that drops a STATE name the moved-out turns do not mention puts it back; a CHANGES line listing several
entries of its own is no longer questioned part by part (the answer-list flood of campaign 47); a NOTES line that
states no number of its own no longer replaces a number the NOTES hold; and with `--notes-checks near`, an amount
found by an archive search counts as stated.

New options, off by default: `--lookups` (a notes line that waits on an archived item, is doubted, or works an
amount out from one is asked again with what the item says), `--cited-entries` (a turn that cites an archived item
for a name gets what the item says shown in the notes request), `--notes-upto` (the NOTES heading says up to which
item the STATE runs), `--rule-scan` (ask about uncovered rule-like turns), `--hold-open` (repeat rules and recent
searches while a question is open), `--sum-check` (a reply whose working has a false multiplication step is asked for once more,
with the step named), `--upstream-retries` with `--upstream-wait` (send a failed call again once the server is
healthy, for servers a supervisor restarts). The per-step record of each is kept below.

Default behaviour otherwise is unchanged: with the new options off, the only differences from 1.1.0 are the fault
fixes above.

**1.2.0 development** (lab, 2026-10-17): `--upstream-retries N` (default 0, off) with `--upstream-wait SECONDS` (default
900): when the model server fails a call (no answer, or HTTP 5xx), the proxy polls the server's `/health` until it
answers 200 and sends the same call again, at most N times; a refusal (HTTP 4xx) is passed on as before. For long
tasks on a server that may be restarted under them (for example by a supervisor after a GPU fault): a greedy call
to an exact server gets the answer the failed one would have had, so the task loses only the time. Not measured
yet on a real restart.

Development (1.2.0.dev0, 2026-10-17), a new option, off by default: `--lookups` (with `--notes-mode inplace` and
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

1.2.0.dev8 (2026-10-18), from lab campaigns 39-46 (2M): a new option, off by default, `--notes-upto` (needs
`--recall-label`). The NOTES heading then says up to which unit the STATE runs ("as of the end of item K"), that what
the turns after it say is newer, and that a value at an earlier unit is not the STATE's (search the archive, or
`notes_at`). In the recorded 2M runs seven answers read a NOTES value for a point it did not cover: the value as of
item 1211 for "the end of item 1207", or "removed" as of item 1003 for a counter reopened in view at item 1004.

1.2.0.dev9 (2026-10-19), from lab campaigns 43-46 (2M, seed 2): a new option, off by default, `--sum-check`. A reply
for the client whose working has a false multiplication step (`saru45 tally = 145×5+11 = 726`) is not passed on: the
same request goes again with a note naming the step and its value ("145×5+11 is 736, not 726. That reply was not
sent. Work it out again"), and the second reply is passed on as it is (unless it is empty or an archive search: then
the first). Only a step with a multiplication on its left is checked. A sum with a leading sign is often a list of
changes to a value named before it, and a chain that is a piece of a longer expression on its line, or a number with
commas, is left alone. In four 2M runs on seed 2, 11 of 25 wrong tallies came from such a step. Across 183
recorded keeper sessions (1,426 multiplication chains in the model's replies, coding and agent sessions among them),
the check finds 18 steps, each a real slip, and no other.

Also in 1.2.0.dev9, two fixes from lab campaign 47 (2M, seed 2, 410/423), on by default:
- A CHANGES line that lists several entries of its own (`/app/answers.json: created with p1_1: 544, p1_2: −74, ...`)
  is no longer asked about "part by part". The model kept one such line for its answers file. Asked to write each
  change on a line of its own, it wrote one STATE line per answer, seven a batch. At item 680 the NOTES were over
  twice their cap, an in-place cut failed, and the ordinary cut's full rewrite kept 1 of 60 STATE lines. A replay of
  26,651 saved lines from nine 2M sessions changes only those 108 answer-list lines.
- A full rewrite (the ordinary cut) is checked against the STATE it replaces, for the names of things (one word with
  a digit or an underscore, such as `saru45`). A line it lost whose name the turns moved out do not mention is put
  back as it was: its value cannot have changed in them. A lost name that the turns do mention is asked about once
  ("write a STATE line for each of them: its value now"). Other lines (a list of answers, notes in words) may still be
  dropped: that is how NOTES that have grown are written shorter. On campaign 47's seed-2 rewrite this puts back 46
  lines, asks about 14, and leaves out the 148 answer lines. RULES lines lost in a rewrite were already put back.

1.2.0.dev10 (2026-10-19), from lab campaign 48 (2M, seed 2, 414/423), on by default: a CHANGES line that opens with
the item it is from, `(item 820) jami27: 11 - 90 = -79`, is jami27's change: the reference goes to the end of the
value, as one written after it always did. A line that is only such a remark, `(item 818: no counter changes)`,
changes nothing. The model wrote every change of 14 notes replies that way. Each became a STATE line of its own
("(item 820) jami27"), 142 of them. The counters' own lines were put right only by the question that follows a reply
leaving mentions unaccounted for, and the stamped lines stayed. Five answers about an earlier item then read them,
though they hold only some of an item's changes. A replay of 26,922 saved lines from eight 2M sessions changes 260
names, all in that run and all from such lines.

Also in 1.2.0.dev10, from lab campaigns 47 and 48 (2M, seed 0), a new option, off by default: `--cited-entries`
(with `--recall-label`). A sentence of the turns being noted that cites an archived item for a name, and is not a
question, gets what that item says about the name shown in the notes request itself, word for word. An audit,
"the decrease of balosu68 entered in item 320 was a mistake, and it has now been reversed", came in long after item
320 ("balosu68 went down by seventy-two") was archived. The reply put it on balo88, which had gone down by 72 eight
items before, wrote no balosu68 line, and asked about balosu68 wrote the same; balosu68 stayed 72 off for 118
versions of the NOTES, in both campaigns. `--lookups` could not help: it asks about a line that waits on an entry,
and there was no such line. On the two campaign-48 runs the option would show 16 entries per run, one for each
audit and each the one the audit cites, about 1,700 characters in all.

Also in 1.2.0 (1.1.1.dev1, 2026-10-17): a NOTES line whose new value states no number of its own (only item or
ticket numbers, as in `audit reversal of the entry in item 4, amount not yet known, must recall items 4/5`) no longer
replaces a number the NOTES hold: the number stays and the line is kept as a remark on it. Before, the value became the
last item number (5) and the line was asked again. Lab campaign 31: a counter that waited on an archive search was
reversed twice that way. Only for a STATE value that is a plain number; descriptions (`contains lines for tickets 10
and 11`) are written as before. A replay of 29,272 saved lines changed only those lines.

Also in 1.2.0 (1.1.1.dev0, 2026-10-17): with `--notes-checks near`, an amount the model took from an archive search
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
python3 -m unittest test_ctxkeeper test_notesdelta test_conversations  # scripted models; no server needed
python3 sync_notesdelta.py                             # the checks are a copy of the lab harness's: must match
```

`check_score.py` replays saved notes replies through the checks against a task's true ledger (how each check rule
was fitted and regression-tested); `replay_diff.py` compares two versions of the checks on saved replies.
[HISTORY.md](HISTORY.md) is the build-by-build record.
