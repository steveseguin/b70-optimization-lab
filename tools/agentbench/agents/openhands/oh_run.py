#!/usr/bin/env python3
"""OpenHands, headless, through its maintained SDK (openhands-sdk / openhands-tools 1.54.0).

The OpenHands CLI (PyPI `openhands` 1.16.0) is no longer maintained (its README says so; it pins SDK 1.21.0 and a
fixed 500-iteration cap). This is the SDK's own default agent in CLI mode, `get_default_agent(llm, cli_mode=True)`
(tools: terminal, file_editor, task_tracker, plus the built-in finish and think; no browser, no sub-agents), with
only these changes for a long run behind ctxkeeper:
  - condenser=None: the default LLMSummarizingCondenser would summarize the history;
  - max_iteration_per_run=100000: the default 500 would stop a 900-step run;
  - timeout=3600: the default 300 s per request is too short for one long-context reply.
Everything else (prompt, tools, stuck detection, retries, no streaming) is the SDK's default.
Usage: oh_run.py PROMPT_FILE   (env AB_PROXY_URL, AB_MODEL)
"""
import os
import sys
from pathlib import Path

from openhands.sdk import LLM, Conversation
from openhands.tools.preset.default import get_default_agent

task = Path(sys.argv[1]).read_text(encoding="utf-8")
llm = LLM(model="openai/" + os.environ["AB_MODEL"], base_url=os.environ["AB_PROXY_URL"],
          api_key="sk-agentbench-dummy", usage_id="agent", timeout=3600)
agent = get_default_agent(llm, cli_mode=True).model_copy(update={"condenser": None})
conv = Conversation(agent=agent, workspace="/app", persistence_dir="/logs/agent/openhands",
                    max_iteration_per_run=100000)
conv.send_message(task)
conv.run()
print("OPENHANDS_EXIT", conv.state.execution_status, "conversation", conv.id, flush=True)
