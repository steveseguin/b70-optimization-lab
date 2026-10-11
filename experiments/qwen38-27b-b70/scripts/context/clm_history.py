"""Arm B32iraRH: B32iraR plus a history of the pinned state (2026-10-11).

Why: on the 1M stream (campaign 5) B32iraR answered what is true now (current values), what was said (who did what),
the standing rule and the house method at about nine in ten or better, but only about half of the questions "what
value did X hold at the end of item N". Answering those from the archive means replaying every sentence about X up to
item N in the model's head. The model had already worked that value out once, when item N arrived: it was in
STATE.txt then, and was overwritten later.

Change: the harness keeps every accepted version of STATE.txt, keyed by the last item folded into it, in its own
memory (nothing is written in the sandbox), and answers one extra command itself:

    recall --state-at N [NAME ...]

prints the counter lines (all, or only the named ones) as they stood at the end of item N, or at the last item
before N that changed the state. Everything else is B32iraR (clm_rules.ClmRulesAgent).

Rule class: this is "archive allowed" plus a version history of the model's own pinned state. No stream text is kept
that the archive does not already hold, but the history is a store outside the context, so results of this arm are
reported under their own label and never pooled with B32ira / B32iraR.
"""
from __future__ import annotations

import re
import types
from typing import Any

import clm_improved as _ci
import clm_rules as _cr
from clm_harness.context_env.types import StepResult
from clm_rules import ClmRulesAgent

STATE_AT = re.compile(r"^\s*recall\s+--state-at\s+(\d+)((?:\s+[A-Za-z]+\d\d)*)\s*$")
REMOVED = re.compile(r"ctxfold: removed items \[([\d, ]+)\]")
HISTORY_NOTE = """- A question about the value a counter held at the end of an EARLIER item: `recall --state-at N NAME` (a command of
  its own) prints that counter's line as it stood in your STATE.txt at the end of item N; the harness keeps every
  version. Use it instead of replaying the archive, and never answer such a question with the current value.
"""


def state_at(history: dict[int, str], n: int, names: list[str]) -> str:
    """The reply to `recall --state-at N [NAME ...]` from {item: STATE.txt text after that item was folded}."""
    keys = [k for k in history if k <= n]
    if not keys:
        first = min(history) if history else None
        return (f"recall: no saved state at or before item {n}"
                + (f" (the first saved state is after item {first})" if first is not None else " (nothing saved yet)"))
    k = max(keys)
    lines = [ln.strip() for ln in history[k].splitlines() if ln.strip() and not ln.strip().startswith("RULE:")]
    if names:
        want = {x.lower() for x in names}
        got = [ln for ln in lines if ln.split()[0].lower() in want]
        missing = sorted(want - {ln.split()[0].lower() for ln in got})
        lines = got + [f"{m}: no line at that time (not yet opened)" for m in missing]
    head = f"STATE at the end of item {n}" + ("" if k == n else f" (unchanged since item {k})") + ":"
    return head + "\n" + "\n".join(lines)


class _HistoryEnv(_ci._ImprovedEnv):
    """Answers `recall --state-at` from the agent's saved states; notes which items a successful drop folded."""

    async def step(self, command, messages, *, environment, pending=None):
        a = self.agent
        m = STATE_AT.match(command or "")
        if m:
            a.n_state_at += 1
            text = state_at(a.state_history, int(m.group(1)), m.group(2).split())
            res = types.SimpleNamespace(stdout=text, stderr="", return_code=0)
            return StepResult(result=res, ctx_changed=False, stdout_block=text + "\n\n(exit_code=0)",
                              readout="", notes="", exec_time=0.0, touched_ctx=False)
        res = await super().step(command, messages, environment=environment, pending=pending)
        hit = REMOVED.search(getattr(res.result, "stdout", "") or "")
        if hit:
            a._folded_now = [int(x) for x in re.findall(r"\d+", hit.group(1))]
        return res


class _HistoryGuard:
    """After the pinned-state check has accepted (or restored) STATE.txt, save it under the items just folded."""

    def __init__(self, inner: Any, agent: "ClmHistoryAgent") -> None:
        self._inner, self._agent = inner, agent

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def maybe(self, environment: Any, messages: list[dict[str, Any]]) -> bool:
        r = await self._inner.maybe(environment, messages)
        a = self._agent
        if a._folded_now:
            for n in a._folded_now:
                a.state_history[n] = a._last_state
            a._folded_now = []
        return r


class ClmHistoryAgent(ClmRulesAgent):
    """B32iraR + every accepted STATE.txt version kept by the harness and readable with `recall --state-at N`."""

    @staticmethod
    def name() -> str:
        return "clm-history"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.state_history: dict[int, str] = {}
        self._folded_now: list[int] = []
        self.n_state_at = 0
        self._ctx.__class__ = _HistoryEnv
        self._ckpt = _HistoryGuard(self._ckpt, self)   # outside the pinned-state guard: runs after its validation

    async def run(self, instruction, environment, context) -> None:
        saved = _cr.RULES_NOTE
        _cr.RULES_NOTE = saved + HISTORY_NOTE
        try:
            await super().run(instruction, environment, context)
        finally:
            _cr.RULES_NOTE = saved
            try:
                (self.logs_dir / "history_stats.json").write_text(__import__("json").dumps(
                    {"states_saved": len(self.state_history), "state_at_calls": self.n_state_at}, indent=1) + "\n")
            except Exception:
                pass
