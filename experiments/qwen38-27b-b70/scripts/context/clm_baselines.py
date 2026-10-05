"""Baseline agents for comparing against ClmAgent on the same Harbor tasks.

The CLM repo (facebookresearch/context-language-models @ 18dc111) ships ONLY the CLM agent.
The paper's baselines (Mini-SWE-Agent, Codex-style Summary, Context Folding, RLM,
Self-Compact, ACM) are not released. These two subclasses reuse ClmAgent's loop, bash
tool, task template, budget gate, token accounting and output files, and change only the
context-management policy, so a comparison isolates that policy:

  PlainAgent    "no management" (like the paper's Mini-SWE-Agent base harness): no context
                file, no mention of one in the prompt, no nudges, no rollback-retry. When the
                context crosses the budget the model gets one final turn, then the run stops
                and the sandbox is graded as is (ClmAgent's own error_finalize policy).
  SummaryAgent  "Codex-style summary": the harness compacts. When the retained context
                reaches `summary_trigger_ratio` (default 0.75) of the enforced limit, the
                harness asks the model (no tools) for a hand-off summary, then replaces
                everything after the pinned system+task prefix with that summary. The
                prompt wording paraphrases the Codex CLI compaction prompt; it is not a copy
                of the paper's baseline code.

Use with Harbor (the scripts directory must be on PYTHONPATH):
  -a clm_baselines:PlainAgent    or    -a clm_baselines:SummaryAgent

Extra outputs in the agent log dir: summary_calls.json (SummaryAgent: one record per
summary call with prompt/completion tokens and before/after context size). The summary
calls are also recorded as context_snapshots with kind="summary". Their tokens are NOT in
usage.json's prompt_tokens/completion_tokens (ClmAgent keeps those in a local variable);
summarize_results.py adds them.

Note: baselines rebind clm_harness.clm_agent.harness._SYSTEM_TEMPLATE when they run, so do
not mix ClmAgent and a baseline inside one Harbor job process.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import litellm

from clm_harness.clm_agent import harness as _h
from clm_harness.context_env.env import ContextEnv
from clm_harness.utils import tokens as tk
from clm_harness.utils.lm_compat import token_cap_key

logger = logging.getLogger(__name__)

# ClmAgent's system prompt (clm/clm_harness/clm_agent/prompts.yaml lines 6-14) without the
# "## Managing your context" section (lines 16-56).
BASELINE_SYSTEM = """\
You are a helpful assistant that can interact with a computer.

Your response must include a THOUGHT section before your action where you
explain your reasoning. After the THOUGHT, you must call the `bash` tool
with EXACTLY ONE bash command (multiple commands chained with `&&` or `||`
count as a single action).

Failure to follow these rules — calling no tool, calling a tool other than
`bash`, or omitting the THOUGHT — will cause your response to be rejected.

{{finish_instructions}}
"""

# Paraphrase of the Codex CLI compaction prompt (codex-rs core/templates/compact).
SUMMARY_PROMPT = """\
You are performing a CONTEXT CHECKPOINT COMPACTION. Do not call any tool. Write a hand-off \
summary for another language model that will resume this task with only the original task \
statement and your summary. Include:
- current progress and key decisions made;
- important context, constraints and facts (copy exact values, identifiers, file paths and \
data verbatim when they may be needed later);
- what remains to be done (clear next steps).
Be structured and specific; anything you leave out is lost."""

SUMMARY_PREFIX = (
    "Another language model started to solve this task and produced the summary below "
    "of its progress. The state of the sandbox it used is unchanged. Build on that work "
    "and avoid repeating it.\n\n[SUMMARY]\n"
)


class _NoMirrorEnv(ContextEnv):
    """ContextEnv without the context file: nothing is mirrored or read back, and the
    per-turn '[context: ~N/M tokens ...]' readout is not shown."""

    async def setup_dirs(self, environment: Any) -> None:  # keep persistent-bash state dir
        await super().setup_dirs(environment)

    async def write_mirror(self, environment: Any, messages: list[dict[str, Any]]) -> str:
        return ""

    async def read_mirror(self, environment: Any) -> str | None:
        return None

    async def step(self, command, messages, *, environment, pending=None):
        res = await super().step(command, messages, environment=environment, pending=pending)
        res.readout = ""
        res.notes = ""
        res.touched_ctx = False
        return res


def _baseline_defaults(kwargs: dict[str, Any]) -> dict[str, Any]:
    kwargs.setdefault("nudge_ratios", "")
    kwargs.setdefault("persistent_nudge_ratio", "none")
    kwargs.setdefault("max_num_retry_on_limit", 0)
    return kwargs


class PlainAgent(_h.ClmAgent):
    """No context management (see module docstring)."""

    @staticmethod
    def name() -> str:
        return "plain-baseline"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **_baseline_defaults(kwargs))
        self._ctx.__class__ = _NoMirrorEnv

    async def run(self, instruction, environment, context) -> None:
        _h._SYSTEM_TEMPLATE = BASELINE_SYSTEM
        await super().run(instruction, environment, context)


class _SummaryEnv(_NoMirrorEnv):
    """Before running each command, compact the history with a model-written summary
    once it reaches the trigger size. The pending assistant turn and its output are
    appended after the summary by the agent loop, so the newest step stays verbatim."""

    agent: "SummaryAgent"

    async def step(self, command, messages, *, environment, pending=None):
        await self.agent._maybe_summarize(messages)
        return await super().step(command, messages, environment=environment, pending=pending)


class SummaryAgent(_h.ClmAgent):
    """Codex-style harness-triggered summary compaction (see module docstring)."""

    @staticmethod
    def name() -> str:
        return "summary-baseline"

    def __init__(self, *args: Any, summary_trigger_ratio: float | str = 0.75,
                 summary_max_tokens: int | str = 4096, **kwargs: Any) -> None:
        super().__init__(*args, **_baseline_defaults(kwargs))
        self.summary_trigger_ratio = float(summary_trigger_ratio)
        self.summary_max_tokens = int(summary_max_tokens)
        self._ctx.__class__ = _SummaryEnv
        self._ctx.agent = self
        self.summary_calls: list[dict[str, Any]] = []

    async def run(self, instruction, environment, context) -> None:
        _h._SYSTEM_TEMPLATE = BASELINE_SYSTEM
        try:
            await super().run(instruction, environment, context)
        finally:
            (self.logs_dir / "summary_calls.json").write_text(
                json.dumps(self.summary_calls, indent=2) + "\n")

    async def _maybe_summarize(self, messages: list[dict[str, Any]]) -> None:
        limit = self._budget.strict_target
        if not limit or len(messages) <= self._protect + 1:
            return
        before = self._budget.count(messages)
        if before < self.summary_trigger_ratio * limit:
            return
        req = list(messages) + [{"role": "user", "content": SUMMARY_PROMPT}]
        self._snap(req, "summary")
        model = self.model_name or ""
        kw: dict[str, Any] = {
            "model": model, "messages": req,
            token_cap_key(model): self.summary_max_tokens,
            "api_base": self.api_base, "timeout": _h._LLM_TIMEOUT_SECONDS,
            "num_retries": 2, "drop_params": True,
        }
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        if self.top_p is not None:
            kw["top_p"] = self.top_p
        if self.send_chat_template_kwargs:
            kw["extra_body"] = {"chat_template_kwargs": {"enable_thinking": self.enable_thinking}}
        self.n_lm_calls += 1
        try:
            resp = await asyncio.to_thread(litellm.completion, **kw)
        except Exception as exc:  # summary failure: keep going uncompacted
            logger.warning("summary call failed: %s: %s", type(exc).__name__, exc)
            self.summary_calls.append({"error": f"{type(exc).__name__}: {exc}", "before": before})
            return
        text = (resp.choices[0].message.content or "").strip()
        usage = getattr(resp, "usage", None)
        rec = {
            "before": before,
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "summary_chars": len(text),
        }
        if not text:
            rec["error"] = "empty summary"
            self.summary_calls.append(rec)
            return
        messages[:] = messages[: self._protect] + [
            {"role": "user", "content": SUMMARY_PREFIX + text}]
        rec["after"] = self._budget.count(messages)
        self.summary_calls.append(rec)
        self._budget.note_compaction()
        logger.info("summary compaction %d -> %d tokens", before, rec["after"])
