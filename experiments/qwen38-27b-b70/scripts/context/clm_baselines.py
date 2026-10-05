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
                Since 2026-10-05 (after the first comparison): the summary call's output cap is
                max(summary_max_tokens, max_tokens) and an empty reply (thinking used up the
                cap) is retried once with thinking off; if the context is already over the
                enforced limit right before a model call, the summary runs there too, instead
                of the gate's final-turn notice (_SummaryGuard). summary_calls.json records
                each attempt (finish_reason, reasoning_chars, summary_chars, reason).

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


# ---------------------------------------------------------------------------------------
# "Drop old thinking" switch (2026-10-05, owner request; run-context-job.sh DROP_OLD_THINKING=1).
# The served Qwen3.8 chat template re-sends every earlier turn's thinking
# (preserve_thinking undefined = true). With drop_old_thinking=true an agent
#   1. sends chat_template_kwargs.preserve_thinking=false on EVERY model call (agent calls and
#      summary calls), via a wrapper around litellm.completion (one Harbor job = one process);
#   2. removes reasoning_content (and the provider "reasoning" copy) from all earlier assistant
#      turns in its own history right before each call, logging the removed text to
#      agent/dropped_thinking.jsonl. The template alone would still keep the thinking of
#      assistant turns after the last user message; stripping it in the harness makes what is
#      sent, what the budget gate counts (it counts reasoning_content) and what the self-editing
#      mirror shows all the same thing: no earlier thinking at all.
def _as_bool(v: Any) -> bool:
    return v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "yes", "on")


_PATCHED = False


def _install_preserve_thinking_false() -> None:
    global _PATCHED
    if _PATCHED:
        return
    orig = litellm.completion

    def completion(*a: Any, **kw: Any) -> Any:
        eb = dict(kw.get("extra_body") or {})
        ctk = dict(eb.get("chat_template_kwargs") or {})
        ctk["preserve_thinking"] = False
        eb["chat_template_kwargs"] = ctk
        kw["extra_body"] = eb
        return orig(*a, **kw)

    litellm.completion = completion
    _PATCHED = True


class _PreCall:
    """Wraps the agent's checkpointer (its maybe() runs every iteration right before the
    budget gate and the model call) and runs `cb(messages)` first."""

    def __init__(self, inner: Any, cb: Any) -> None:
        self._inner, self._cb = inner, cb

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def maybe(self, environment: Any, messages: list[dict[str, Any]]) -> bool:
        self._cb(messages)
        return await self._inner.maybe(environment, messages)


def _setup_drop_thinking(agent: Any, flag: Any) -> None:
    agent.drop_old_thinking = _as_bool(flag)
    agent.dropped_thinking_chars = 0
    if not agent.drop_old_thinking:
        return
    _install_preserve_thinking_false()

    def strip(messages: list[dict[str, Any]]) -> None:
        out = []
        for i, m in enumerate(messages):
            if not isinstance(m, dict) or m.get("role") != "assistant":
                continue
            rc = m.pop("reasoning_content", None)
            m.pop("reasoning", None)
            psf = m.get("provider_specific_fields")
            if isinstance(psf, dict):
                psf.pop("reasoning", None)
                psf.pop("reasoning_content", None)
            if rc:
                agent.dropped_thinking_chars += len(rc)
                out.append({"index": i, "chars": len(rc), "text": rc})
        if out:
            try:
                agent.logs_dir.mkdir(parents=True, exist_ok=True)
                with open(agent.logs_dir / "dropped_thinking.jsonl", "a") as f:
                    for r in out:
                        f.write(json.dumps(r) + "\n")
            except Exception:
                pass

    agent._ckpt = _PreCall(agent._ckpt, strip)


class ClmAgentT(_h.ClmAgent):
    """The unmodified CLM agent plus the drop-old-thinking switch (nothing else differs)."""

    @staticmethod
    def name() -> str:
        return "clm-drop-thinking"

    def __init__(self, *args: Any, drop_old_thinking: Any = True, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _setup_drop_thinking(self, drop_old_thinking)


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

    def __init__(self, *args: Any, drop_old_thinking: Any = False, **kwargs: Any) -> None:
        super().__init__(*args, **_baseline_defaults(kwargs))
        self._ctx.__class__ = _NoMirrorEnv
        _setup_drop_thinking(self, drop_old_thinking)

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


class _SummaryGuard:
    """Wraps the agent's checkpointer, whose maybe() runs right before the budget gate of
    every iteration. If the context is already over the enforced limit there (a large tool
    output landed on a context just under the trigger), summarize now instead of letting the
    gate hand out the final-turn notice. In the first comparison the gate issued that notice
    once because summaries had failed; this keeps "summary" from being judged by the plain
    arm's stop policy."""

    def __init__(self, inner: Any, agent: "SummaryAgent") -> None:
        self._inner, self._agent = inner, agent

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def maybe(self, environment: Any, messages: list[dict[str, Any]]) -> bool:
        r = await self._inner.maybe(environment, messages)
        a = self._agent
        lim = a._budget.strict_target
        if lim and a._budget.count(messages) > lim:
            await a._maybe_summarize(messages, reason="over_limit_before_call")
        return r


class SummaryAgent(_h.ClmAgent):
    """Codex-style harness-triggered summary compaction (see module docstring)."""

    @staticmethod
    def name() -> str:
        return "summary-baseline"

    def __init__(self, *args: Any, summary_trigger_ratio: float | str = 0.75,
                 summary_max_tokens: int | str = 4096, drop_old_thinking: Any = False,
                 **kwargs: Any) -> None:
        super().__init__(*args, **_baseline_defaults(kwargs))
        self.summary_trigger_ratio = float(summary_trigger_ratio)
        self.summary_max_tokens = int(summary_max_tokens)
        self._ctx.__class__ = _SummaryEnv
        self._ctx.agent = self
        self._ckpt = _SummaryGuard(self._ckpt, self)
        _setup_drop_thinking(self, drop_old_thinking)  # wraps outside: strip, then summary guard
        self.summary_calls: list[dict[str, Any]] = []
        self.n_summary_calls = 0

    async def run(self, instruction, environment, context) -> None:
        _h._SYSTEM_TEMPLATE = BASELINE_SYSTEM
        try:
            await super().run(instruction, environment, context)
        finally:
            (self.logs_dir / "summary_calls.json").write_text(
                json.dumps(self.summary_calls, indent=2) + "\n")

    def _summary_call(self, req: list[dict[str, Any]], thinking: bool):
        model = self.model_name or ""
        kw: dict[str, Any] = {
            "model": model, "messages": req,
            token_cap_key(model): max(self.summary_max_tokens, self.max_tokens),
            "api_base": self.api_base, "timeout": _h._LLM_TIMEOUT_SECONDS,
            "num_retries": 2, "drop_params": True,
        }
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        if self.top_p is not None:
            kw["top_p"] = self.top_p
        if self.send_chat_template_kwargs:
            kw["extra_body"] = {"chat_template_kwargs": {"enable_thinking": thinking}}
        self.n_lm_calls += 1
        self.n_summary_calls += 1
        try:
            return litellm.completion(**kw)
        except Exception as exc:  # summary failure: keep going uncompacted
            logger.warning("summary call failed: %s: %s", type(exc).__name__, exc)
            return exc

    async def _maybe_summarize(self, messages: list[dict[str, Any]], reason: str = "trigger") -> None:
        limit = self._budget.strict_target
        if not limit or len(messages) <= self._protect + 1:
            return
        before = self._budget.count(messages)
        if before < self.summary_trigger_ratio * limit:
            return
        if getattr(self, "_fail_at", None) == len(messages):
            return  # the last attempt on this very context failed; do not loop
        req = list(messages) + [{"role": "user", "content": SUMMARY_PROMPT}]
        self._snap(req, "summary")
        rec: dict[str, Any] = {"before": before, "reason": reason, "prompt_tokens": 0,
                               "completion_tokens": 0, "attempts": []}
        text = ""
        # First comparison (2026-10-05): with thinking on, a 4,096-token summary cap was used up
        # by the thinking in 3 of 5 calls and the summary came back empty. So: cap = the larger
        # of summary_max_tokens and the agent's max_tokens, and if the reply is still empty,
        # retry once with thinking off (recorded as attempt 2).
        for thinking in ([self.enable_thinking, False] if self.enable_thinking else [False]):
            resp = await asyncio.to_thread(self._summary_call, req, thinking)
            if isinstance(resp, Exception):
                rec["attempts"].append({"thinking": thinking, "error": f"{type(resp).__name__}: {resp}"})
                continue
            usage = getattr(resp, "usage", None)
            choice = resp.choices[0]
            text = (choice.message.content or "").strip()
            rc = getattr(choice.message, "reasoning_content", None) or ""
            rec["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
            rec["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
            ptd = getattr(usage, "prompt_tokens_details", None)
            rec["cached_tokens"] = rec.get("cached_tokens", 0) + (
                (getattr(ptd, "cached_tokens", 0) if ptd is not None else 0) or 0)
            rec["attempts"].append({"thinking": thinking, "finish_reason": choice.finish_reason,
                                    "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                                    "reasoning_chars": len(rc), "summary_chars": len(text)})
            if text:
                break
        rec["summary_chars"] = len(text)
        if not text:
            rec["error"] = "empty summary"
            logger.warning("summary call(s) returned no text; continuing uncompacted")
            self._fail_at = len(messages)
            self.summary_calls.append(rec)
            return
        messages[:] = messages[: self._protect] + [
            {"role": "user", "content": SUMMARY_PREFIX + text}]
        rec["after"] = self._budget.count(messages)
        self.summary_calls.append(rec)
        self._budget.note_compaction()
        logger.info("summary compaction %d -> %d tokens", before, rec["after"])
