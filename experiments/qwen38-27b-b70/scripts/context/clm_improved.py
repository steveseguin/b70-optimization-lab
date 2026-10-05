"""Proposed improved self-managing agent (NOT wired into second-comparison.sh yet).

Design and evidence: notes/2026-10-05-self-editing-first-comparison.md, section "Improved
self-editing agent (proposal)". Built from what the second comparison's first two trials showed
(ledger, 121K tokens, memory-only, seed 0):

  * B32 (unmodified CLM agent, 32K) lost 5 of 24 counters, and every loss came from FIVE batches
    (items 2, 3, 4, 5, 7) that `next` had delivered and the harness's rollback-and-retry then
    deleted from the context (a delivered item cannot be fetched again). Its answers equal the
    true state with exactly those five batches skipped. Its own bookkeeping was exact.
  * The rollbacks came from thinking: the very first call wrote 14,425 tokens of planning, which
    the chat template keeps re-sending, so one 6.9K batch already overflowed the 30,720 limit;
    ten later turns produced 10-16K tokens each (several hit max_tokens with no command).
  * Once settled, the model invented the right layout by itself: a state block between markers,
    updated by an inline python script that reads the new batch out of the mirror, then the batch
    lines are replaced by one line. Its two early failures were its own markers colliding with
    its command text, which the mirror also contains.
  * A (no budget) kept the raw lines out of its context by piping `next` into an inline script and
    carrying the state table as a JSON argument (re-typed every call: ~3K tokens per call).

So the changes below, in order of evidence:
  1. Delivery-safe budget: a rollback never deletes a delivered stream item (a turn whose output
     matches `guard_output_regex`); it drops the turns after it and asks for a fold instead.
  2. Room gate before destructive reads: a command matching `guard_command_regex` (default:
     `next`) is not executed when the context plus the largest delivery seen so far plus
     `guard_headroom` would exceed the limit; the model gets "NOT RUN: fold first".
  3. Drop old thinking (as the B32t arm; clm_baselines._setup_drop_thinking).
  4. Harness-owned pinned state: /tmp/.live_ctx/STATE.txt, re-read before every call and shown as
     the LAST message of the context (so the transcript stays nearly append-only and the server's
     prefix cache keeps working). The harness validates it (optional line regex, size cap) and
     restores the last valid version if an edit breaks it. NOTE: the memory-only grader must then
     exclude /tmp/.live_ctx/STATE.txt like the mirror (it IS context): make_kvstream_tasks.py
     GRADE_PY_V2 needs that one-line change before this agent is run on memory-only tasks.
  5. A prompt addendum that states the protocol: fold every batch into STATE.txt right after it
     arrives, delete the raw batch turn, never retype data (read it from the mirror by code).

  6. The newest-output cap never cuts a delivered item (the room check is what keeps it in budget).
  7. Optional per-turn thinking cap, think_cap=<tokens> (run-context-job.sh THINK_CAP; default off).
     Two-call protocol on vLLM chat completions (this build supports continue_final_message;
     checked in vllm/entrypoints/openai/chat_completion/protocol.py, renderers/hf.py):
       call 1: the normal request with max_tokens = think_cap;
       if it ends with finish_reason "length" and no tool call (cut inside thinking or before the
       action), call 2: the same messages + one assistant message {reasoning_content: <the partial
       thinking>, content: <the partial content, or the bridge sentence THINK_BRIDGE>}, sent with
       continue_final_message=true, add_generation_prompt=false, the same tools and
       chat_template_kwargs, max_tokens = max_tokens - call-1 completion. The Qwen3.8 template
       renders that message as `<think>\n…\n</think>\n\n<content>` and transformers cuts the
       prompt right after <content> (so the content must be non-empty: hence the bridge), so the
       model continues after a closed thinking block and must act.
       The reply given to the harness = call-2 message with reasoning = partial thinking (+ any
       call-2 reasoning), content = bridge + call-2 content, tool calls from call 2; usage =
       call-1 prompt tokens (keeps the budget calibration honest) and both completions; call 2's
       prompt tokens are reported in improved_stats.json (extra_prompt_tokens).
     Caveat: vLLM's qwen3 parser starts every reply in "reasoning" state, so call 2's text before
     <tool_call> is returned as reasoning, not content; <tool_call> itself ends reasoning, so the
     action is still parsed. Untested on the real server.

Not implemented: an "archive" of removed spans (no loss in the evidence came from pruning).

Accounting (fairness vs B32): the pinned state is an ordinary user message in the history, so the
budget gate, the readout, the rollback logic, snapshots (peak_sent_ctx) and the server all count
it exactly like any other context; only the file it is read from is new.

Use (after the stub checks): EXTRA_KWARGS may tune it; agent path clm_improved:ClmImprovedAgent.
"""
from __future__ import annotations

import json
import re
import shlex
import types
from typing import Any

from clm_harness.clm_agent import harness as _h
from clm_harness.context_env.env import ContextEnv
from clm_harness.context_env.types import StepResult
from clm_harness.utils import tokens as tk

import litellm

from clm_baselines import _as_bool, _setup_drop_thinking

THINK_BRIDGE = "(Thinking budget reached; acting now.)"
_NEXT_EXTRA: dict[str, Any] = {}
_EXTRA_PATCHED = False


def _install_extra_body_hook() -> None:
    """litellm.completion wrapper: merge one-shot top-level body fields (continue_final_message,
    add_generation_prompt) for the next call only."""
    global _EXTRA_PATCHED
    if _EXTRA_PATCHED:
        return
    orig = litellm.completion

    def completion(*a: Any, **kw: Any) -> Any:
        if _NEXT_EXTRA:
            eb = dict(kw.get("extra_body") or {})
            eb.update(_NEXT_EXTRA)
            _NEXT_EXTRA.clear()
            kw["extra_body"] = eb
        return orig(*a, **kw)

    litellm.completion = completion
    _EXTRA_PATCHED = True

STATE_PATH = "/tmp/.live_ctx/STATE.txt"
PIN_TAG = "[[PINNED STATE: this is /tmp/.live_ctx/STATE.txt; edit that file, not this turn]]"

PROTOCOL = """

## Working protocol for streamed data (read carefully)

- Keep everything you will need later in `/tmp/.live_ctx/STATE.txt`. It is part of your context:
  the harness shows its current content as the last message of every turn. It is NOT a notes file;
  it counts against your budget like everything else. Keep it compact and exact.
- After each item arrives, in your NEXT command: fold the item into STATE.txt with an inline
  `python3 - <<'EOF'` script that reads the item's lines from the mirror file by code (never
  retype data), then delete that item's turn from the mirror. One command does both.
- Before running a command that delivers a large item, make sure there is room for it: the
  harness refuses to run such a command when the item would not fit ("NOT RUN").
- Your earlier thinking is not kept between turns: write anything you must remember into
  STATE.txt.
- If STATE.txt plus the next item cannot fit in your budget, you must decide what to drop from
  STATE.txt yourself; anything dropped is lost (answer "" for it), so drop the least useful.
"""


class _ImprovedEnv(ContextEnv):
    agent: "ClmImprovedAgent"

    async def step(self, command, messages, *, environment, pending=None):
        a = self.agent
        if a._guard_cmd.search(command or ""):
            shown = messages + ([pending] if pending else [])
            now = self.budget.count(shown)
            need = a._largest_delivery + a.guard_headroom
            limit = self.budget.strict_target or 0
            if limit and a._largest_delivery and now + need > limit:
                a.n_gate_refusals += 1
                text = (f"NOT RUN: `{command.strip()[:60]}` delivers an item of up to "
                        f"~{a._largest_delivery} tokens, and only ~{max(limit - now, 0)} of the "
                        f"{limit}-token limit are free (need ~{need} incl. headroom). Fold the "
                        f"newest item into {STATE_PATH} and delete its turn first.")
                res = types.SimpleNamespace(stdout=text, stderr="", return_code=75)
                return StepResult(result=res, ctx_changed=False, stdout_block=text + "\n\n(exit_code=75)",
                                  readout=f"\n[context: ~{now}/{limit} tokens]", notes="",
                                  exec_time=0.0, touched_ctx=False)
        res = await super().step(command, messages, environment=environment, pending=pending)
        out = getattr(res.result, "stdout", "") or ""
        if a._guard_out.search(out):
            a._largest_delivery = max(a._largest_delivery,
                                      int(tk.count_tokens([{"role": "tool", "content": out}])[0]
                                          * self.budget.tok_ratio))
        return res


class _PinnedState:
    """Pre-call hook: re-read STATE.txt, validate it, and show it as the last message."""

    def __init__(self, inner: Any, agent: "ClmImprovedAgent") -> None:
        self._inner, self._agent = inner, agent

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def maybe(self, environment: Any, messages: list[dict[str, Any]]) -> bool:
        a = self._agent
        messages[:] = [m for m in messages
                       if not (isinstance(m, dict) and str(m.get("content") or "").startswith(PIN_TAG))]
        try:
            r = await environment.exec(command=f"cat {STATE_PATH} 2>/dev/null", timeout_sec=30)
            text = (getattr(r, "stdout", "") or "").strip()
        except Exception:
            text = a._last_state
        note = ""
        if text != a._last_state:
            bad = a._validate(text)
            if bad:
                a.n_state_rejected += 1
                note = f"\n[STATE.txt edit REJECTED ({bad}); the previous version was restored.]"
                q = shlex.quote(a._last_state + "\n")
                try:
                    await environment.exec(command=f"printf %s {q} > {STATE_PATH}", timeout_sec=30)
                except Exception:
                    pass
                text = a._last_state
            else:
                a._last_state = text
        if text or note:
            messages.append({"role": "user", "content": f"{PIN_TAG}\n{text}{note}"})
        return await self._inner.maybe(environment, messages)


class ClmImprovedAgent(_h.ClmAgent):
    """CLM agent + delivery-safe rollback, room gate, pinned validated state, no old thinking."""

    @staticmethod
    def name() -> str:
        return "clm-improved"

    def __init__(self, *args: Any, drop_old_thinking: Any = True,
                 guard_command_regex: str = r"(^|[;&|]\s*)next\b",
                 guard_output_regex: str = r"(?m)^ITEM \d+/\d+ \(",
                 guard_headroom: int | str = 4096,
                 state_line_regex: str = "", state_max_tokens: int | str = 8192,
                 think_cap: int | str = 0, empty_streak_limit: int | str = 2,
                 fallback_think_cap: int | str = 2048, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._guard_cmd = re.compile(guard_command_regex)
        self._guard_out = re.compile(guard_output_regex)
        self.guard_headroom = int(guard_headroom)
        self._state_line = re.compile(state_line_regex) if state_line_regex else None
        self.state_max_tokens = int(state_max_tokens)
        self._largest_delivery = 0
        self._last_state = ""
        self.n_gate_refusals = self.n_state_rejected = self.n_protected_rollbacks = 0
        self.think_cap = int(think_cap or 0)
        self.n_think_cap_continuations = 0
        self.extra_prompt_tokens = 0
        # Loop guard (2026-10-05, arm At looped for 2.5 h: 49 calls ending at max_tokens with no
        # command). After `empty_streak_limit` consecutive replies without a tool call, the next
        # call uses the think-cap continuation with `fallback_think_cap`, which forces an action.
        self.empty_streak_limit = int(empty_streak_limit)
        self.fallback_think_cap = int(fallback_think_cap)
        self._empty_streak = 0
        self.n_loop_guard = 0
        _install_extra_body_hook()
        self._ctx.__class__ = _ImprovedEnv
        self._ctx.agent = self
        self._ckpt = _PinnedState(self._ckpt, self)
        _setup_drop_thinking(self, drop_old_thinking)  # strip first, then pin the state
        self._protect_deliveries()
        orig_cap = self._budget.cap_newest_output
        guard = self._guard_out

        def cap_newest_output(messages, tool_content, *, floor=128):
            if guard.search(tool_content or ""):
                return tool_content  # never cut a delivered item; the room check budgets it
            return orig_cap(messages, tool_content, floor=floor)

        self._budget.cap_newest_output = cap_newest_output

    async def _query_with_retry(self, model: str, messages: list[dict[str, Any]]) -> Any:
        cap = self.think_cap
        if (not cap and self.empty_streak_limit
                and self._empty_streak >= self.empty_streak_limit):
            cap = min(self.fallback_think_cap, max(self.max_tokens // 2, 1))  # must be < max_tokens
            self.n_loop_guard += 1
        r = await self._query_capped(model, messages, cap)
        try:
            has_tool = bool(getattr(r.choices[0].message, "tool_calls", None))
        except Exception:
            has_tool = True
        self._empty_streak = 0 if has_tool else self._empty_streak + 1
        return r

    async def _query_capped(self, model: str, messages: list[dict[str, Any]], cap: int) -> Any:
        if not cap or cap >= self.max_tokens:
            return await super()._query_with_retry(model, messages)
        full = self.max_tokens
        self.max_tokens = cap
        try:
            r1 = await super()._query_with_retry(model, messages)
        finally:
            self.max_tokens = full
        ch = r1.choices[0]
        m1 = ch.message
        if getattr(m1, "tool_calls", None) or (ch.finish_reason != "length" and cap == self.think_cap):
            return r1
        rc1 = (getattr(m1, "reasoning_content", None) or "").strip()
        c1 = (m1.content or "").strip()
        bridge = c1 or THINK_BRIDGE
        prefill = {"role": "assistant", "reasoning_content": rc1, "content": bridge}
        u1 = r1.usage
        rest = max(full - (getattr(u1, "completion_tokens", 0) or 0), 1024)
        _NEXT_EXTRA.update(continue_final_message=True, add_generation_prompt=False)
        self.max_tokens = rest
        try:
            r2 = await super()._query_with_retry(model, list(messages) + [prefill])
        finally:
            self.max_tokens = full
            _NEXT_EXTRA.clear()
        self.n_think_cap_continuations += 1
        m2 = r2.choices[0].message
        rc2 = (getattr(m2, "reasoning_content", None) or "").strip()
        m2.reasoning_content = rc1 + (("\n" + rc2) if rc2 else "")
        m2.content = bridge + ((" " + m2.content.strip()) if (m2.content or "").strip() else "")
        u2 = r2.usage
        self.extra_prompt_tokens += getattr(u2, "prompt_tokens", 0) or 0
        try:
            u2.completion_tokens = (getattr(u1, "completion_tokens", 0) or 0) + (getattr(u2, "completion_tokens", 0) or 0)
            u2.prompt_tokens = getattr(u1, "prompt_tokens", 0) or 0
            u2.total_tokens = u2.prompt_tokens + u2.completion_tokens
            u2.prompt_tokens_details = getattr(u1, "prompt_tokens_details", None)
        except Exception:
            pass
        return r2

    def _validate(self, text: str) -> str:
        if tk.count_tokens([{"role": "user", "content": text}])[0] > self.state_max_tokens:
            return f"over {self.state_max_tokens} tokens"
        if self._state_line:
            for ln in text.splitlines():
                if ln.strip() and not self._state_line.match(ln.strip()):
                    return f"line does not match the state format: {ln[:60]!r}"
        return ""

    def _protect_deliveries(self) -> None:
        """Rollback may drop newest turns, but never a turn holding a delivered item."""
        b = self._budget
        orig = b.rollback_to_margin
        guard = self._guard_out
        agent = self

        def rollback_to_margin(messages, protect=None, margin=None):
            dropped = []
            target = max(b.strict_target - (b.rollback_margin() if margin is None else margin), 0)
            floor = b.protect_prefix if protect is None else protect
            while len(messages) > floor and b.count(messages) > target:
                m = messages[-1]
                if m.get("role") == "tool" and guard.search(str(m.get("content") or "")):
                    agent.n_protected_rollbacks += 1
                    break
                dropped.append(messages.pop())
                while (len(messages) > floor and messages[-1].get("role") == "assistant"
                       and messages[-1].get("tool_calls")):
                    dropped.append(messages.pop())
            b.n_turns_rolled_back += len(dropped)
            return list(reversed(dropped)), b.count(messages)

        b.rollback_to_margin = rollback_to_margin
        self._orig_rollback = orig

    async def run(self, instruction, environment, context) -> None:
        saved = _h._SYSTEM_TEMPLATE
        _h._SYSTEM_TEMPLATE = saved.replace("{{finish_instructions}}", PROTOCOL + "\n{{finish_instructions}}") \
            if "{{finish_instructions}}" in saved else saved + PROTOCOL
        try:
            await super().run(instruction, environment, context)
        finally:
            _h._SYSTEM_TEMPLATE = saved
            try:
                (self.logs_dir / "improved_stats.json").write_text(json.dumps({
                    "gate_refusals": self.n_gate_refusals, "state_rejected": self.n_state_rejected,
                    "protected_rollbacks": self.n_protected_rollbacks,
                    "largest_delivery_tokens": self._largest_delivery,
                    "think_cap": self.think_cap,
                    "think_cap_continuations": self.n_think_cap_continuations,
                    "loop_guard_calls": self.n_loop_guard,
                    "extra_prompt_tokens": self.extra_prompt_tokens,
                    "dropped_thinking_chars": getattr(self, "dropped_thinking_chars", 0),
                    "drop_old_thinking": _as_bool(getattr(self, "drop_old_thinking", False)),
                }, indent=1) + "\n")
            except Exception:
                pass
