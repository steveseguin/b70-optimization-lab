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

Version 1.0.1 · public domain ([Unlicense](LICENSE)) · Python 3.10 or newer, standard library only (two files:
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

Records: [`data/2026-10-14-context-campaign19/`](../../experiments/qwen38-27b-b70/data/2026-10-14-context-campaign19/).

Version 1.0.1 changes only how requests and replies are passed on ([Changes](#changes)); its program files are
byte-identical to the ones the twelve-agent test below ran.

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

Pick one. All three come from the [1.0.1 release](https://github.com/steveseguin/b70-optimization-lab/releases/tag/ctxkeeper-v1.0.1)
(small files; nothing clones the lab's large repository):

```bash
R=https://github.com/steveseguin/b70-optimization-lab/releases/download/ctxkeeper-v1.0.1

# 1. pip (gives you the `ctxkeeper` command)
pip install $R/ctxkeeper-1.0.1-py3-none-any.whl

# 2. Docker (builds the image from the 80 KB source archive)
docker build -t ctxkeeper $R/ctxkeeper-1.0.1.tar.gz

# 3. just the two files (run with python3 ctxkeeper.py ...)
curl -LO $R/ctxkeeper.py
curl -LO $R/notesdelta.py
```

The source archive `ctxkeeper-1.0.1.tar.gz` also holds the demo below, the tests and this README; the release page
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
| `--state-dir DIR` | where archives and notes are kept |
| `--no-memory-note` | do not add the short paragraph that tells the model about its notes and `recall` |

Everything else: `ctxkeeper --help`.

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
