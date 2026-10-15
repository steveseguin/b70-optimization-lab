# agentbench: well-known open-source coding agents on the repair task, through ctxkeeper

Runs well-known open-source coding agents, pinned and unchanged (one exception: a one-line timeout patch in Kimi
Code), on the lab's real-code repair marathon (`repair-n40-s2x`: 40 bugs in more-itertools, 44 tickets fetched one at
a time with `next`, three house rules, a final audit) behind the [ctxkeeper](../ctxkeeper/README.md) proxy. Each
agent gets the task's `instruction.md` word for word, runs in its own locked-down container, and is graded by the
task's own verifier exactly like [freeagent](../freeagent/run-freeagent-job.sh), so the scores compare.

**Status (2026-10-15): plumbing only.** Every agent below was run against a scripted fake model through a real
ctxkeeper 1.0.0 instance, on the CPU. None has been run on a real model yet.

## Run one agent

The campaign session starts the model server and ctxkeeper (fresh state directory per run: ctxkeeper recognizes a
conversation by its system prompt and first message, so a second run of the same agent on the same state directory
would land on the first run's archive):

```bash
/mnt/fast-ai/venvs/ctxkeeper-1.0.0/bin/ctxkeeper --upstream http://127.0.0.1:8000 --recipe qwen --port 18200 \
  --state-dir /mnt/fast-ai/bench-results/<campaign>/ctxkeeper-<job>
```

then runs, for example:

```bash
cd /home/steve/b70-optimization-lab/tools/agentbench
./run-agent-job.sh goose \
  /mnt/fast-ai/bench-results/context-longrun-20261012/client-repair2/tasks/repair-n40-s2x \
  /mnt/fast-ai/bench-results/<campaign> AB-goose__repair-n40-s2x http://127.0.0.1:18200/v1 3300
```

`run-agent-job.sh AGENT TASK_DIR OUT_DIR JOB_NAME PROXY_URL [TIME_LIMIT]` builds the images if they are missing
(needs the network; all images for repair-n40-s2x are already built), runs the agent, grades it, and writes
`OUT_DIR/jobs/JOB_NAME/trial/{agent,verifier}` like the freeagent runner (`verifier/details.json`: fixed, clean,
rules, audit). Env: `MODEL_NAME` (default `qwen38-27b-fp8`), `AGENT_MEM` (container memory cap, default `768m`),
`TAP=full` (keep every request body; default `summary`). AGENT is a folder name under `agents/`: `freeagent`,
`goose`, `mini-swe-agent`, `openhands`, `qwen-code`, `pi`, `forgecode`, `open-interpreter`, `hermes-agent`,
`kimi-code`, `cline`, `mistral-vibe`, `opencode`. Use `AGENT_MEM=1g` for Cline and Mistral Vibe and `AGENT_MEM=1536m`
for OpenCode (see memory below). The runner does not check host memory: check free RAM before
starting an agent beside the model server.

`trial/agent/` holds the agent's own logs and session files (`home/`), `requests.jsonl` (one line per request the
agent sent: size, message count, tools, whether it extended the previous request), `history-check.json`,
`memory.json` (peak memory of the container), `exit.json`, and `agentbench.json` (a summary of the run).

## The agents

Twelve agents plus the freeagent control, all passing every plumbing test (below). Memory is the agent container
(agent + task) in MiB, "non-file / total peak": non-file (anon + kernel) cannot be dropped as page cache and is the
number to hold against free host RAM. Columns: at the start of a run, with a ~1 MB history (about what this task
reaches: freeagent's real runs ended at 0.75 MB), and with a 4M+ character history.

| agent | version | license | image | plumbing: basic / slow / stress | memory at start | ~1 MB history | 4M+ history | fixed prompt (tokens) | streams | sends thinking back |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| freeagent (control) | lab | lab | 190 MB | pass / pass / pass* | 32 / 34 | 53 / 56 | 44 / 92* | ~170 | no | yes |
| Goose | 1.54.0 | Apache-2.0 | 402 MB | pass / pass / pass | 71 / 107 | 111 / 192 | 122 / 201 | ~1,600 | no | yes |
| mini-swe-agent | 2.4.6 | MIT | 1.1 GB | pass / pass / pass | 241 / 257 | 252 / 347 | 271 / 301 | ~90 | no | yes |
| OpenHands SDK | 1.54.0 | MIT | 1.11 GB | pass / pass / pass | 288 / 430 | 294 / 423 | 340 / 390 | ~9,000 | no | no |
| Qwen Code | 0.25.1 | Apache-2.0 | 516 MB | pass / pass / pass | 204 / 215 | 301 / 395 | 322 / 358 | ~10,300 | yes | no |
| pi | 1.2.0 | MIT | 546 MB | pass / pass / pass | 118 / 129 | 134 / 204 | 175 / 231 | ~1,600 | yes | no |
| ForgeCode | 2.14.0 | Apache-2.0 | 254 MB | pass / pass / pass | 32 / 38 | 34 / 106 | 74 / 107 | ~11,600 | yes | no |
| Open Interpreter | rust-v0.0.56 | Apache-2.0 | 708 MB | pass / pass / pass | 72 / 88 | 74 / 126 | 136 / 197 | ~7,900 | yes | no |
| Hermes Agent | 0.22.1 | MIT | 1.23 GB | pass / pass / pass | 337 / 354 | 364 / 504 | 404 / 438 | ~8,400 | yes | no |
| Kimi Code | 2.2.0 (+1-line patch) | MIT | 438 MB | pass / pass / pass | 324 / 326 | 352 / 463 | 425 / 461 | ~20,800 | yes | no |
| Cline CLI | 3.0.71 | Apache-2.0 | 372 MB | pass / pass / pass | 317 / 411 | 407 / 454 | 729 / 783 (7.1 MB) | ~3,600 | yes | no |
| Mistral Vibe | 2.26.1 | Apache-2.0 | 711 MB | pass / pass / pass | 141 / 181 | 191 / 268 | 533 / 605 | ~8,400 | yes | no |
| OpenCode | 1.19.0 | MIT | 446 MB | pass / pass / pass | 578 / 597 | 704 / 825 | 869 / 911 | ~6,700 | yes | no |

Image sizes are unpacked (`docker images`) and include the 189 MB task image. "Fixed prompt" is the system prompt
plus tool definitions sent on every request, at ~3.6 characters per token. The ~1 MB column is 0.8 MB for ForgeCode
and Mistral Vibe (they shorten each command output). \* freeagent shortens each long command output too, so its
170-step stress run reached 1.2 MB, not 4 MB; its history never shrank and every request carried all of it, and its
real runs on this task are on record.

**Memory beside the two-card server** (~2.5 GiB free, 1.6 GiB kill floor, so roughly 450 MiB for an agent):

- **Fit** (under ~450 MiB non-file at this task's ~1 MB history, and at 4 MB): freeagent, Goose, mini-swe-agent,
  OpenHands, Qwen Code, pi, ForgeCode, Open Interpreter, Hermes Agent (364 at 1 MB, 404 at 4 MB: close), Kimi Code
  (352 at 1 MB, 425 at 4 MB: close).
- **Fit at this task's size, not at long histories**: Cline (407 at 1 MB, 729 at 7 MB), Mistral Vibe (191 at
  0.8 MB, 533 at 4.6 MB). Run them with `AGENT_MEM=1g`.
- **Does not fit: OpenCode** (~580 MiB before the first request, ~700 at 1 MB, ~870 at 4 MB). Run it only when the
  host has room, with `AGENT_MEM=1536m`; the default 768m cap would kill it on a long run.

## What every agent has in common

- **Pinned and checked.** npm packages through a committed `package-lock.json` and `npm ci` (each package checked
  against its registry integrity hash), no install scripts; PyPI packages through `requirements.txt` with SHA-256
  hashes (`pip install --require-hashes --no-deps`, from `uv pip compile --generate-hashes`); GitHub release files
  checked against the SHA-256 in the Dockerfile; Debian packages at exact versions; base images by digest
  (`node:22-trixie-slim@sha256:154ba2f4…` for Node 22.23.3, `python:3.12-slim@sha256:02108f5d…`, the task's own
  Python). Each image carries the agent's version and hash in its `agentbench.agent.version` label.
- **Its own context management off, or out of reach.** Auto-compaction, summarizing condensers, old-tool-output
  pruning and history budgets are switched off where a switch exists; where only a threshold exists, the declared
  context window is 10,000,000 tokens and the threshold is pushed to its maximum. The stress test proves it: every
  agent's history passed 4M characters (over 1M tokens by any count) with every request still starting with the
  whole previous request.
- **Limits that would end a 900-step, one-hour run raised** (step, turn, iteration and cost caps); request timeouts
  of an hour (through ctxkeeper a reply arrives in one piece after the model has finished, so a client sees nothing
  for the whole generation; the slow-reply test proves a 330-second silence is waited out without a retry).
- **No telemetry, update checks, model-catalog fetches, cloud or sharing features**, each turned off by its own
  setting; with `--network none` nothing could leave the container anyway.
- **No sub-agent or web tools** (a sub-agent is a separate conversation: the agent managing its own context), no
  title or summary side calls (except ForgeCode's title call, which has no switch). Every other default (prompts,
  tools, per-output size caps, loop guards, sampling) is left as shipped.
- **The task prompt** is `TASK_DIR/instruction.md`, word for word, as the agent's task (`run.sh` gets the file).

## Each agent

### freeagent (control arm)

The lab's own agent (`tools/freeagent/freeagent.py`, unmodified; sha256 recorded in the image), run here so that the
same plumbing carries a known-good agent: freeagent through ctxkeeper `--recipe qwen` scored 40/40 clean, audit 7/7 on
repair-n40-s2x. One `shell` tool; a ~170-token system prompt; never trims anything. Its `docker exec` calls are
pointed at the container itself by a two-line shim (`agents/freeagent/docker-shim`), so it runs inside the container
like the others. Sends `max_tokens 8192`, `temperature 0.0`, `chat_template_kwargs.enable_thinking`; not streamed;
sends its thinking back. It shortens each long command output (its own design, kept), so the 170-step stress run
reached 1.2 MB rather than 4 MB; its history still never shrank and every request carried all of it. Launch:
`python3 -I /opt/agent/freeagent.py --api-base URL --model MODEL --container local --instruction PROMPT
--out /logs/agent/freeagent --max-steps 900 --time-limit TIME_LIMIT`, with the shim first on `PATH`.

### Goose 1.54.0

`goose` 1.54.0 (Apache-2.0, AAIF / Linux Foundation, formerly Block; GitHub release
`goose-x86_64-unknown-linux-musl.tar.gz`, sha256 `777e49b6ae128fae06600f94bf51ff05c81572fce63c1581e9ea94bc49d64e42`).
Launch: `goose run --name agentbench-run --no-profile --with-builtin developer --max-turns 100000 --output-format
stream-json -i PROMPT`.
Settings: a declarative custom provider (`agents/goose/custom_provider.json`: engine `openai` = Chat Completions,
`context_limit 10000000`, `timeout_seconds 3600`, `supports_streaming false`: Goose's streaming parser drops text
that arrives with a tool call), and environment in the Dockerfile:
- `GOOSE_AUTO_COMPACT_THRESHOLD=0` (auto-compaction off), `GOOSE_CONTEXT_LIMIT=10000000`,
  `GOOSE_TOOL_PAIR_SUMMARIZATION=false` (it would otherwise summarize old tool call/result pairs).
- `GOOSE_MAX_TURNS=100000`; `GOOSE_DISABLE_SESSION_NAMING` (no naming side call); `GOOSE_TELEMETRY_OFF`,
  `GOOSE_TELEMETRY_ENABLED=false`, `GOOSE_DISABLE_KEYRING`; only the built-in `developer` extension.
Not streamed; sends no sampling settings at all (the server's defaults apply); sends thinking back as
`reasoning_content`. Left on: it summarizes if the server ever answers "context too long" (ctxkeeper never does), and
it ends on the first reply without a tool call.

### mini-swe-agent 2.4.6

`mini-swe-agent` 2.4.6 (MIT, Princeton/Stanford SWE-agent team; wheel sha256 `0532c819…` / `a35463c5…`) with
`litellm` 1.105.1, the full 80-package closure pinned with hashes in `agents/mini-swe-agent/requirements.txt`.
Launch: `mini -c mini.yaml -c overrides.yaml -t "PROMPT" --yolo --exit-immediately -o /logs/agent/mini.traj.json`.
It never trims or summarizes history (nothing to turn off). `overrides.yaml` only sets `cost_limit 0` (no cost cap),
cost tracking errors ignored (the model is not in litellm's price list), the API base, `timeout 3600`;
`MSWEA_CONFIGURED=true`, `LITELLM_LOCAL_MODEL_COST_MAP=True` (no price-list download), `HF_HUB_OFFLINE=1`. Its stock
prompts are kept: the task goes in a user message wrapped in its instance template, each command output is shown up to
10,000 characters (head and tail beyond that), each command has a 30-second limit. One `bash` tool, commands run with
`sh` (so the task's `BASH_ENV` limit does not apply). Ends when the model runs
`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`; three replies in a row without a tool call also end it. Not streamed;
sends no sampling settings; sends thinking back.

### OpenHands (software-agent-sdk 1.54.0)

`openhands-sdk` and `openhands-tools` 1.54.0 (MIT, All Hands AI; sdk sha256 `431e7bc6…` / `647bf83c…`, tools
`07072ec3…` / `ca6957c1…`), 185-package closure pinned with hashes; Debian `tmux 3.5a-3` (its terminal tool).
The OpenHands CLI is not used (see Excluded): `agents/openhands/oh_run.py` (a 30-line script) builds the CLI's own
default agent, `get_default_agent(llm, cli_mode=True)` (terminal, file editor, task tracker, finish, think), and runs one
conversation. Launch: `/opt/agent/bin/python -I /opt/agentbench/oh_run.py PROMPT`.
- `condenser=None` (the default agent comes with a summarizing condenser), `max_iteration_per_run=100000`
  (default 500), LLM `timeout 3600` (default 300 s); stuck detection left on.
- No telemetry or cloud calls in the SDK path used; `ANONYMIZED_TELEMETRY=false`, `LITELLM_LOCAL_MODEL_COST_MAP=True`
  and `LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS=True` (no downloads at start), `HF_HUB_OFFLINE=1`.
Not streamed; sends `reasoning_effort high` and a `prompt_cache_key`; tool outputs as content lists; does not send
thinking back. Its terminal is a tmux shell, so the task's `BASH_ENV` limit does not apply to its commands.

### Qwen Code 0.25.1

`@qwen-code/qwen-code` 0.25.1 (Apache-2.0, Alibaba Qwen team; npm integrity
`sha512-6cEbtfx4Ugl1d3FdFLa8fcsG6knHuUUHqvDseLxGY06Xan8p7Fcd7+g5KlX694zX4mo/+Vh56AHxT/4R15zpYA==`), installed with
`npm ci --omit=optional --ignore-scripts`, run on Node 22.23.3.
Launch: `node .../cli-entry.js --yolo --output-format stream-json --session-id UUID "PROMPT" < /dev/null`.
Settings (`agents/qwen-code/settings.json`):
- Compaction has no off switch, only a threshold: `model.contextWindowSize 10000000` and
  `context.autoCompactThreshold 1` (it would compact at ~70% of the declared window, so never before 7M tokens; the
  shipped window is ~223K tokens).
- `context.clearContextOnIdle.toolResultsTotalCharsThreshold -1` and `toolResultsThresholdMinutes -1`: off (by
  default it blanks old tool outputs once they pass 500K characters).
- `model.maxToolCallsPerTurn -1` (default: an adaptive cap of 100 tool calls per user turn, which this one-prompt run
  would hit), `maxSessionTurns`, `maxWallTimeSeconds`, `maxToolCalls` `-1`, `skipLoopDetection true`,
  request `timeout 3600000`, `streamIdleTimeoutMs 0`, `approvalMode yolo`.
- Off: usage statistics, telemetry, auto-update, auto memory; models.dev fetch (`QWEN_CODE_MODELS_DEV=off`).
- Tools disabled: `agent` (sub-agents), `cron_*`, `loop_wakeup`, `web_fetch`, `web_search`, `advisor`, `workflow`,
  `ask_user_question`.
Streams; `max_tokens 32768`; does not send thinking back (see the reasoning decision below).
Left on: it stops after 5 identical consecutive tool calls (no setting), and it compacts if the server ever answers
"context too long" or 413 (ctxkeeper never does).

### pi 1.2.0

`@earendil-works/pi-coding-agent` 1.2.0 (MIT, Mario Zechner / Earendil; npm integrity
`sha512-h/4WaVWv1VlCaY8x8qEN5U+7jbF/e7+Ck6moPeEOFn5juMTWwNAXjwgYM7gRgbBYh8Zppwt6qWvJDzNTf4GNEQ==`, git tag v1.2.0 =
`06a46693`), 119 locked packages, no optional or platform modules.
Launch: `node .../pi-coding-agent/dist/bundle/cli.js --mode json --offline --no-extensions --provider agentbench
--model MODEL -- "PROMPT"` (`--no-extensions` drops its built-in MCP, llama.cpp, codemode and tool-search
extensions; the default tools read, bash, edit, write stay).
Settings (`agents/pi/settings.json`, `models.json`):
- `compaction.enabled false` (this also covers its overflow recovery); model `contextWindow 10000000`.
- `httpIdleTimeoutMs` and `retry.provider.timeoutMs` 3,600,000 (default 300,000).
- `enableInstallTelemetry false`, `enableAnalytics false`, `cacheWarming "off"` (a side call);
  `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `--offline`.
- No step or turn limit exists; no sub-agent or web tools exist.
Streams; `max_completion_tokens 16384`, `store false`; does not send thinking back. Bash output beyond 2,000 lines or
50 KB goes to a temp file (default, kept).

### ForgeCode 2.14.0

ForgeCode v2.14.0 (Apache-2.0, Tailcall; tag commit `6ab58df3d8f11ce52c8d182359f4c76e74f29c0f`; static musl binary
`forge-x86_64-unknown-linux-musl` from the GitHub release, sha256
`64832f828bf08961322e302243f352ee7c27e88d76f972574a3628c7b70cb1be`: npm stops at 2.13.21).
Launch: `forge --agent forge -p PROMPT` (one turn of the default `forge` agent; ends when the model stops calling
tools). Settings (`agents/forgecode/forge.toml` as `~/.forge/.forge.toml`; a custom provider, `response_type
"OpenAI"`, with a static model list, so it never fetches `/models`):
- `[compact]`: `token_threshold 1000000000`, `token_threshold_percentage 1.0`, `message_threshold 1000000000`,
  `turn_threshold 1000000000`, `on_turn_end false` (defaults compact at 100K tokens or 200 messages); model context
  10,000,000, so the effective trigger is 10M tokens.
- `max_requests_per_turn 100000` (default 100: in `-p` mode the whole run is one turn), `max_tool_failure_per_turn
  100000` (default 3 consecutive failures of one tool, such as a failing test, end the run),
  `[http] read_timeout_secs 7200` (default 900).
- `subagents false` (removes the `task` and `sage` tools); the `fetch` web tool removed by a global agent file
  (`forge-agent.md`: the built-in `forge.md` minus that line).
- `[updates] frequency "never"`, `auto_update false` (it would otherwise run `curl forgecode.dev/cli | sh`).
- `services_url = "http://127.0.0.1:9/"`: every file write and patch otherwise sends the file to `api.forgecode.dev`
  for a syntax check (and failed patches for a fuzzy match). Without a network each call stalled 5 s; pointed at a
  closed local port it fails at once and the agent carries on without those checks.
- `SHELL=/bin/bash` (it would use `/bin/sh`, which skips the task's `BASH_ENV` limit), `FORGE_TRACKER=false`.
Streams; `max_completion_tokens 20480`, `parallel_tool_calls true`; does not send thinking back. One side request per
run: a title call (no tools, temperature 1.0) that cannot be switched off. It keeps the first and last 100 lines of
each command output (its default, kept).
**Telemetry cannot be switched off in 2.14.0**: usage events and info-level logs (including commands and the prompt)
go to PostHog for any release build. Here they cannot leave the container (`--network none`).

### Open Interpreter rust-v0.0.56

Open Interpreter rust-v0.0.56 (Apache-2.0; tag commit `cc054cf52fa3585a3de50e0d4e0be6f9ee6677e8`; the asset its
official installer picks, `open-interpreter-package-x86_64-unknown-linux-musl.tar.gz`, sha256
`9e859353d6e2af28381489570d3ecf02060f7c73df5a652f3ca60c196835ccac`). This is the new Rust Open Interpreter, built on
the Codex CLI code base, which kept Chat Completions (`wire_api = "chat"`).
Launch: `interpreter exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --json -C /app - < PROMPT`
(the container is the sandbox; the prompt on stdin arrives byte for byte).
Settings (`agents/open-interpreter/config.toml`):
- It compacts at 90% of the model's window, and an unknown model's window is capped at 272K tokens. A one-entry
  model catalog (`model-catalog.json`, made by `make_model_catalog.py`: its own fallback entry with the window set
  to 10,000,000) plus
  `model_context_window = 10000000` pushes that to 9M tokens. Turn-end compaction is off by default.
- `stream_idle_timeout_ms = 7200000` (default 300,000 would kill a long silent reply); no step limit in `exec`.
- `[features]` multi_agent, memories, browser_use, in_app_browser, computer_use, plugins off (plugins would sync from
  github.com and chatgpt.com at start); `web_search "disabled"`, `check_for_update_on_startup false`, analytics and
  feedback off.
- `harness = ""` pins its own prompt and tools; left unset, a model name containing "qwen" switches it to its
  imitation of Qwen Code.
Streams; `parallel_tool_calls true`, `store false`; does not send thinking back. Each tool output is cut to 10,000
bytes (its default, kept). Its goal tools are on by default: if the model sets a goal, it carries on by itself.
**Its task prompt is not in ctxkeeper's kept head**: the opening messages are system, a skills block, an environment
block, then the task, and ctxkeeper always keeps only the system messages and the first user message. In a long run
the task text can leave the live window, leaving only ctxkeeper's notes of it (see decisions).

### Hermes Agent 0.22.1

Hermes Agent v0.22.1 (MIT, Nous Research; GitHub tag commit `297552a9d646119871391d202509822cd86330df`, source
tarball sha256 `45ebe864dbf65ecd31693a811ddd6e2e449b1878b835b563cf0a28d6a9c4bf38`: PyPI stops at 0.19.0). 66
dependencies hash-pinned from the tag's `uv.lock` (`--require-hashes --only-binary :all: --no-deps`). Hermes needs
Python 3.14: the interpreter is the one Hermes itself pins, python-build-standalone cpython 3.14.7+20260901 (sha256
`0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0`).
Launch: `python -P -m hermes_cli.main chat --oneshot --yolo --query-file PROMPT --format stream-json --toolsets
terminal,file,todo,code_execution,skills` (its own finite-run path: it starts its local gateway inside the container
and runs the turn there, so two Python processes run).
Settings (`agents/hermes-agent/config.yaml`):
- `compression.enabled false`, `micro_compact false`, `proactive_prune_tokens 0`, `idle_compact_after_seconds 0`,
  `hygiene_hard_message_limit 1000000`; context length 10,000,000 on the model and provider. With compression off,
  its overflow recovery refuses to compress (`agent/turn_recovery.py`).
- `max_turns 100000` (already unlimited by default); every request, stream and stale timeout 7,200 s; the gateway
  inactivity kill and the turn watchdog off.
- `updates.check false`, `model_catalog.enabled false`, shared metrics off, no lazy installs
  (`HERMES_DISABLE_LAZY_INSTALLS=1`, `lsp.install_strategy manual`); memory, user profile, curator, title generation
  and background review off.
- Toolsets left out: web, browser, memory, session search, delegation, cron, kanban, clarify, vision/image/TTS,
  computer use, connectors.
Streams; sends `reasoning_effort medium` on every request (its provider default); does not send thinking back. Each
command keeps its 180-second default limit.

### Kimi Code 2.2.0 (one-line patch)

`@moonshot-ai/kimi-code` 2.2.0 (MIT, Moonshot AI; npm integrity
`sha512-I1w2l6JGYEUSwA1DTvYrw/kDJYjJQKHFON+RON61epDeTITvwpXoDn4Kgl4atA82RfwcsMp3KG6k8Yaoj6LT0A==`, tag `472192c3`),
installed with `npm ci --omit=dev --omit=optional --ignore-scripts`. The successor of the archived Kimi CLI.
Launch: `node .../kimi-code/dist/main.mjs --model agentbench --output-format stream-json --prompt="PROMPT"` (print
mode always runs in the never-ask permission mode and has no step cap).
**The one change to the shipped program**: Kimi Code builds its OpenAI client without a timeout, so the bundled SDK's
fixed 10-minute limit applies to every request, and no setting reaches it. Behind ctxkeeper the reply arrives only
when it is finished, so any reply that takes over 10 minutes would be cut off and sent again. The Dockerfile changes
that one constant (`OpenAI.DEFAULT_TIMEOUT` 600,000 to 3,600,000 ms; the build fails unless exactly one line
matches), the image label records it, and a 660-second slow test passed with it. Deleting one `RUN` block removes it.
Settings (`agents/kimi-code/config.toml`, `tui.toml`):
- No compaction switch: `max_context_size = 10000000` pushes it to 8.5M tokens (it compacts at 85%); it also
  compacts if the server answers "context too long" (ctxkeeper never does).
- `[loop_control] max_steps_per_turn = 0` (unlimited); `KIMI_CODE_LLM_HEADERS_TIMEOUT_MS=3600000`.
- `telemetry = false`, `KIMI_DISABLE_TELEMETRY=1` (crash reports go through the same client),
  `KIMI_CODE_NO_AUTO_UPDATE=1`, `[upgrade] auto_install = false`, `auto_session_title = false`.
- `[tools] disabled = Agent, AgentSwarm, WebSearch, FetchURL`; `capabilities = ["tool_use"]` (the model name is
  unknown to it).
Streams; sends `prompt_cache_key`, no `max_tokens`; adds `reasoning_effort medium` once its history holds thinking
(not the case through ctxkeeper 1.0.0's streaming). **Its fixed prompt is the largest here: ~20,800 tokens** (22
tools, 66K characters of tool definitions, plus two reminder messages after the prompt), about two thirds of
ctxkeeper's 32K window. A command runs 60 s in the foreground, then moves to the background (default, kept).

### Cline CLI 3.0.71

`@cline/cli-linux-x64` 3.0.71 (Apache-2.0, Cline Bot Inc.; npm integrity
`sha512-3bDa8a9KLAhj7UaoLYgXHl6wNpLp3t3REp37orGv9LMmGktqXw4z0wmHHgR7CApzwUVogaT93DowuW+vXvuEPw==`, binary sha256
`8562eda595d5766d253154053a0b386e0cfa1ef3abce928ae6ff63f594a61047`).
Launch: `cline --yolo --json --compaction off -P openai-compatible -m MODEL --data-dir DIR -c /app "PROMPT"`.
- `--compaction off` and `compactionEnabled false`; provider `contextWindow 10000000` (`providers.json`).
- Its message builder trims history on its own unless told not to: `CLINE_MESSAGE_BUILDER_MAX_TOOL_RESULT_CHARS=
  1000000000` (default 8,000-character cap on each old tool result), `..._MIN_OUTDATED_REWRITE_BYTES=disable`
  (default rewrites stale file reads), `..._MAX_TOTAL_TEXT_BYTES=1000000000000` (default 6 MB budget). The stress
  test (7.1 MB, 280 steps) confirms all three are off.
- `telemetryOptOut`, `autoUpdate false`, `CLINE_NO_AUTO_UPDATE`, `IS_TEST=true` (no PostHog feature-flag fetches),
  `CLINE_SESSION_BACKEND_MODE=local`, `BUN_CONFIG_HTTP_IDLE_TIMEOUT=0` (no idle timeout on the request).
Streams; `max_tokens 32000`; does not send thinking back. Left on (no setting): a hard stop after 5 identical
consecutive tool calls, a 30-second limit on each command, a stop after 3 consecutive failed tool calls (resets on
success). Ends only through its `submit_and_exit` tool; a text-only reply gets a reminder to use a tool.
**Memory: ~410 MiB non-file at a ~1 MB history, ~730 at 7 MB**: borderline beside the two-card server.

### Mistral Vibe 2.26.1

`mistral-vibe` 2.26.1 (Apache-2.0, Mistral AI; wheel `mistral_vibe-2.26.1-cp312-abi3-manylinux_2_28_x86_64.whl`, sha256
`1ceb43e38a2e82cb8c54e1032b011874f8422e998cf87b4a3fdf58704133de55`; git tag v2.26.1 = `4ae5c595`), 97 packages
hash-pinned (`--no-deps --require-hashes --only-binary :all:`).
Launch: `vibe --prompt-file PROMPT --auto-approve --trust --max-turns 100000 --output streaming --output-dir
/logs/agent/vibe-run`.
Settings (`agents/mistral-vibe/config.toml`):
- `auto_compact_threshold = 0` at the global and the model level ("0 stays the documented way to disable
  compaction").
- `--max-turns 100000` (default 1,000 model calls per run); `api_timeout 3600` (default 720).
- Off: `enable_telemetry`, `enable_update_checks`, `enable_auto_update`, `enable_connectors`, `enable_subagents`,
  experiments, title generation (`VIBE_TEST_DISABLE_AUTO_TITLE=1`); `disabled_tools = task, web_fetch, web_search`;
  `VIBE_CLI=python` (the Python CLI, not the bundled Rust TUI).
Streams; `temperature 0.2`; does not send thinking back. Its bash tool cuts stdout and stderr at 16,000 bytes each
(default, kept). API retries give up after 300 s (default).
**Memory grows with the history inside its Python process: ~190 MiB non-file at 0.8 MB, ~530 at 4.6 MB.** Fine for
this task's ~1 MB histories; give it `AGENT_MEM=1g` to be safe on long ones.

### OpenCode 1.19.0

`opencode-linux-x64` 1.19.0 (MIT, Anomaly/SST; npm integrity
`sha512-+UFxn2AbOqKEISBDqrWk5nHsZrPWBMVZ4H9R7tbnrt1+nYvEGejpg9tyt+QMrpBPYZP7F+D3Ym0vZbZcF7gSSw==`, binary sha256
`135ac3f86c43f2a22328a3554fec5f0bc57d71576077902661bc38dac34871fd`), plus Debian `ripgrep 14.1.1-1+b4` (its search
tools need it).
Launch: `opencode run --format json --thinking --dangerously-skip-permissions --model ctxkeeper/MODEL --agent build
--title agentbench-run < PROMPT`.
Settings (`agents/opencode/opencode.json`, a custom `@ai-sdk/openai-compatible` provider named `ctxkeeper`):
- `compaction.auto false`, `compaction.prune false`, plus `OPENCODE_DISABLE_AUTOCOMPACT` and
  `OPENCODE_DISABLE_PRUNE`; model `limit.context 10000000`.
- Provider `timeout false` (no request timeout); `autoupdate false`; `share disabled`; `snapshot`, `lsp`,
  `formatter` off; `OPENCODE_DISABLE_MODELS_FETCH`, `_AUTOUPDATE`, `_LSP_DOWNLOAD`, `_DEFAULT_PLUGINS`, `_SHARE`,
  `_CLAUDE_CODE`, `_EXTERNAL_SKILLS` (Dockerfile).
- Permissions: everything allowed except `task` (sub-agents), `webfetch`, `websearch`, `skill`, `question` (denied);
  the session-title side call is disabled (`--title`).
Streams; `max_tokens 32000`; does not send thinking back.
**Memory: ~580 MiB at the start, ~700 MiB non-file at a ~1 MB history, ~870 at 4 MB.** It cannot run beside the
two-card server, and the default `AGENT_MEM=768m` would kill it on a long run: give it `AGENT_MEM=1536m` and run it
only where the host has room (`BUN_OPTIONS=--smol` did not help).

## Excluded

| agent | why not |
| --- | --- |
| Codex CLI 0.162.1 (OpenAI, Apache-2.0) | Speaks only the Responses API. `wire_api = "chat"` is a hard config error (`codex-rs/model-provider-info/src/lib.rs`); Chat Completions was deprecated in 0.72.0 (2025-12-13) and removed in 0.95.0 (2026-02-04, "nuke chat/completions API"). ctxkeeper serves Chat Completions only. The last version that could talk to it is 0.94.0 (npm `sha512-GKOU2ty3NXls2aeiFSCnSSB6zQBtENqC5OnPa8s79Z576YP1r2DIfUrhQZzVDKmFei852E1SG4TNljFL/081gg==`), eight months old: possible, not recommended. |
| Gemini CLI (Google, Apache-2.0) | Talks only Google's Gemini API format; no OpenAI-compatible base URL. |
| Aider 0.86.2 (Apache-2.0) | Not an autonomous loop: it edits files from the model's replies, and commands the model suggests are answered "no" even with `--yes-always` (`base_coder.py`, `io.py`), so it cannot run `next` and `t` by itself. |
| SWE-agent 1.1.0 (MIT) | Its README says it is superseded by mini-swe-agent (included). It also deep-copies and re-saves the whole history every step (about 1.7 GB of JSON per save at 900 steps). |
| OpenHands CLI 1.16.0 (MIT) | Its README says it is no longer maintained; it pins SDK 1.21.0, a fixed 500-iteration cap, and a forced security-analyzer and sub-agent tool. OpenHands is tested through its maintained SDK instead (above). `openhands-ai` is the server/GUI, not a CLI. |
| Continue CLI `cn` 1.5.47 (Apache-2.0) | Its repository says it "is no longer actively maintained and is read-only". It would also need a resume loop to run unattended, drops thinking, and calls api.continue.dev at start. |
| Kimi CLI (Moonshot, Python) | Archived 2026-09-22; its successor Kimi Code is the one considered here. |
| Roo Code | Archived; VS Code extension only. |
| Kilo Code CLI | A fork of OpenCode (included) on an older base, with its own gateway and telemetry: a near-duplicate that adds nothing to the comparison. |
| Crush (Charm) | FSL-1.1-MIT license: source-available, not OSI open source. |
| Plandex | Dormant, and a plan-then-apply tool rather than a shell loop. |
| Trae Agent (ByteDance) | No release, no commit since 2026-02-05. |
| Nanocoder | Small project (~2.5k stars), not yet a well-known agent. |
| Letta Code | Needs a running Letta server that keeps its own memory (its own context management, by design). |
| smolagents | A library for building agents, not a coding agent. |
| Warp | Requests go through Warp's servers and need an account. |
| Amazon Q Developer CLI | Unmaintained (replaced by Kiro). |
| Kiro, GitHub Copilot CLI, Claude Code, Cursor CLI, Amp, Factory Droid, Junie, Augment Auggie | Not open source. |

## Needs the owner's decision

1. **Which agents run beside the two-card server.** OpenCode cannot (memory, above); Cline and Mistral Vibe only at
   this task's history size. Run OpenCode only when the cards are not serving, or leave it out.
2. **Thinking is lost for streaming agents.** vLLM returns the model's thinking in a `reasoning` field. ctxkeeper
   1.0.0 passes a non-streamed reply through whole, but when a client streams it re-sends the finished reply as one
   event carrying only `content`, `reasoning_content` and tool calls (`as_stream`, ctxkeeper.py:1120). So the
   streaming agents (Qwen Code, OpenCode, Cline, pi, ForgeCode, Open Interpreter, Hermes, Kimi Code, Mistral Vibe)
   never see the thinking. The non-streaming ones get it, and freeagent, Goose and mini-swe-agent send it back on
   every request (OpenHands does not), which makes their histories larger and their model calls different. Options:
   accept it as how ctxkeeper 1.0.0 behaves, or a one-line ctxkeeper fix (also copy `reasoning`), which would be a
   new ctxkeeper release.
3. **Sampling differs by agent, as shipped.** freeagent sends `temperature 0`, `max_tokens 8192`, thinking on;
   Qwen Code `max_tokens 32768`; OpenCode and Cline `max_tokens 32000`; ForgeCode `max_completion_tokens 20480`; pi
   `max_completion_tokens 16384`; Mistral Vibe `temperature 0.2`; Hermes `reasoning_effort medium`; OpenHands
   `reasoning_effort high`; Goose and mini-swe-agent nothing (the server's defaults apply). `--recipe qwen` adds
   `reasoning_effort medium` to every call. Recommendation: leave as shipped and report it. The server needs a
   context length of at least ~64K (a ~31K view plus up to 32,768 reply tokens); the lab's usual 262,144 is fine.
4. **Fixed prompt size eats the 32K live window.** System prompt plus tool definitions, sent on every call: from
   ~90 tokens (mini-swe-agent) and ~170 (freeagent) to ~9,000 (OpenHands), ~10,300 (Qwen Code), ~11,600
   (ForgeCode) and ~20,800 (Kimi Code), out of ctxkeeper's 32,768-token window. Heavy agents get much less room for
   the work. Options: keep one window for all (the cost of a heavy prompt is part of the result), or give each
   agent its fixed size on top (`--budget` 32768 plus its fixed size).
5. **How runs end.** Most agents stop at the first reply without a tool call (freeagent does too); Cline only stops
   through its submit tool; mini-swe-agent after three text replies in a row. No "keep going" loop has been added to
   any agent. If the model stops early on the real task, that agent scores low.
6. **Kimi Code's one-line patch** (its 10-minute request limit raised to an hour, above). Without it, any reply
   slower than 10 minutes is cut off and sent again. Keep the patch, run it unpatched, or leave Kimi Code out.
7. **ForgeCode's usage tracking** cannot be switched off in 2.14.0 (events, including commands and the prompt, to
   PostHog). In these containers it cannot leave (`--network none`). Accept that, or leave ForgeCode out.
8. **Open Interpreter's task prompt can leave the live window** (it comes after a skills block and an environment
   block, and ctxkeeper always keeps only the first user message). Run it as shipped, or set `[skills]
   include_instructions = false` and `include_environment_context = false` so the task is the first user message.
9. **Hermes Agent runs on Python 3.14** (it requires it), installed beside the task's Python 3.12 in `/opt/agent`.
   Noted, no action needed.
10. **Codex CLI.** Only its eight-month-old 0.94.0 can talk Chat Completions. Recommendation: leave it out.
11. **Order and time.** Each run is up to 55 minutes (`3300` s, as freeagent's), one at a time behind one ctxkeeper.
   A pilot of the control arm plus two or three small agents first (suggested: freeagent, Goose, mini-swe-agent,
   Qwen Code), then the rest, keeps each sitting to a few hours.

## How a run is isolated

```
host                                                     agent container (image agentbench-AGENT:TASK)
ctxkeeper 127.0.0.1:18200  <-  bridge.py (host side)  <-  /run/agentbench/proxy.sock  <-  bridge.py  <-  agent
  (tap: one JSON line per request)       read-only mount, holds only the socket          127.0.0.1:18200
```

- **One container per run, built FROM the task's own image** (`agentbench-task:TASK`, built from
  `TASK/environment` as the freeagent runner builds it), so `/app`, `next` and `t` are the task's, unchanged. The
  pinned agent is added on top, plus `bridge.py` and `common/entry.sh`.
- **No network**: `--network none`. The only way out is one Unix socket, in a directory that holds nothing else and
  is mounted read-only. On the host, `bridge.py` forwards it to the proxy's TCP port; inside, a second `bridge.py`
  listens on `127.0.0.1:PORT`, so the agent uses the same URL as on the host. The agent reaches the proxy (and
  through it the model) and nothing else: not the LAN, not the internet, not other host ports.
- **No host files**: no home directory, SSH keys, tokens or Docker socket. Nothing is mounted except the socket
  directory. The task prompt is streamed in with `docker exec -i`; logs leave with `docker cp` after the run.
- **Unprivileged**: the agent runs as user `agent` (uid 10001), which owns only `/app`, `/opt/repair` (where `next`
  keeps its place) and `/logs/agent`; `--cap-drop ALL`, `no-new-privileges`, `--pids-limit 1024`, `--memory` =
  `--memory-swap` = `AGENT_MEM` (default 768m: the task's 256 MiB plus ~512 MiB for the agent). Docker on this host
  is rootful, so these matter.
- **Dummy key only** (`sk-agentbench-dummy`); ctxkeeper passes it on and vLLM ignores it.
- **Time limit** inside the container (`timeout -k 30 TIME_LIMIT`), with a host-side guard five minutes later. When
  the agent stops, every process of user `agent` is killed before grading.
- **Grading** is freeagent's: the task's `tests/` copied in, `python3 /tests/grade.py` as root in the same container,
  `/logs/verifier/` copied out.
- The task image's `BASH_ENV` (`ulimit -v 163840`) still applies to an agent's own `bash -c` commands, as it does to
  freeagent's (agents that keep an interactive shell, OpenHands, do not read it); `entry.sh` and every `run.sh` are
  POSIX `sh` so the limit never lands on the agent program itself. The image's `http_proxy=127.0.0.1:9` stays;
  `NO_PROXY=127.0.0.1,localhost` lets the agent reach the bridge.

## Plumbing tests (CPU only)

```bash
./plumbing-test.sh AGENT [SLOT]                 # basic: the definition of done
MODE=slow ./plumbing-test.sh AGENT [SLOT]       # a 330 s silent reply must be waited out
MODE=stress ./plumbing-test.sh AGENT [SLOT]     # history past 4M characters without the agent compacting
MODE=stress RUN_TAG=1mb BIG_STEPS=42 ./plumbing-test.sh AGENT [SLOT]   # memory at a ~1 MB history
python3 summarize_plumbing.py                   # the table above
```

Each starts `fake_agent_server.py` (a scripted model, port 18310+SLOT) and a real ctxkeeper 1.0.0
(`--recipe agent`, port 18320+SLOT), then runs the agent through `run-agent-job.sh` (`AGENT_MEM=2g`, so memory is
measured, not capped). The fake finds the agent's shell tool from the request's `tools` (by name, or any tool with a
`command`/`cmd`/`commands` argument), fills its required arguments from the JSON schema, and plays: `next`,
`t SplitAtTests`, `next`, then finishes the way the agent expects (its finish tool, mini-swe-agent's
`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`, or a plain text reply). Its replies look like vLLM's (content null with
tool calls, a `reasoning` field). `plumbing_check.py` then checks:

| check | how |
| --- | --- |
| requests reach the proxy as Chat Completions, with tools, no chunked bodies | the host bridge's tap of the agent's own requests |
| the fake model received them through ctxkeeper | the fake's request log |
| `next` ran in /app; the ticket text and the `t` output came back to the model | `/opt/repair/.log` (verifier `tickets_fetched`), the tap |
| the agent ended by itself when told the job was done | exit code 0, before the time limit |
| the verifier wrote `details.json` | the trial folder (score ~0, as expected) |
| whole history every time | each request starts with every message of the previous one, compared as ctxkeeper compares (role, text, tool calls; thinking and call ids ignored) |
| one ctxkeeper conversation, no restart | `/ctxkeeper/status` |
| stress: the history passed 4M characters, never shrank, ctxkeeper cut it without a restart | tap sizes, `/ctxkeeper/status` |
| slow: no request sent during a 330 s silent reply, run still finished | tap timestamps against the fake's delay window |

Results: `/mnt/fast-ai/bench-results/agentbench-plumbing-20261014/<agent>[-slow|-stress|-stress-1mb]/`
(`plumbing-result.json`, the fake's and ctxkeeper's logs, the whole trial folder).

## Files

| file | what |
| --- | --- |
| `run-agent-job.sh` | the runner (one agent, one task, graded) |
| `build-agent-image.sh` | builds `agentbench-task:TASK` and `agentbench-AGENT:TASK` (context: `tools/`) |
| `bridge.py` | TCP to Unix socket forwarder, both ends; `--tap` records the agent's requests (host side) |
| `memwatch.py` | samples the container's cgroup from the host: peak, non-file, anon |
| `check_history.py` | whole-history check over the tap |
| `common/entry.sh`, `common/finalize.sh` | in-container launcher (bridge, time limit, exit record); image user setup |
| `agents/AGENT/` | `Dockerfile`, `run.sh` (the exact launch command), config templates, lockfile or hashed requirements |
| `fake_agent_server.py`, `plumbing-test.sh`, `plumbing_check.py`, `summarize_plumbing.py` | the plumbing tests |
| `cleanup.sh` | removes `agentbench-*` containers (`--images`: and images) |
