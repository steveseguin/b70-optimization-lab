"""Arm B32iraR: archive-and-recall with pinned RULE lines (2026-10-11).

Why: on the `--rules` stream (campaign 4, notes/2026-10-10-context-16k-baseline.md) B32ira kept every current
value, old value, narrative detail and the house method (5/5 each) but lost the standing rule of item 1 completely
(0/5 rule probes and the confidential counter of the final query). The model saw the rule (its thinking at item 1
says so), but STATE.txt accepts only `name value` lines, earlier thinking is dropped and item 1 goes to the archive,
so the rule had nowhere to stay in view; a question about a confidential counter looks like any other value question,
so nothing prompted a search either. The method survived only because its questions name it ("using the house
method"), which sends the model to the archive.

Change (everything else is B32ira: clm_improved.ClmImprovedAgent, fold_mode=read, archive=true): STATE.txt may also
hold lines `RULE: <text>` for standing rules and methods. A RULE line is permanent (an edit that removes or rewords
one is rejected and the previous file restored), there are at most `rule_max_lines` of at most `rule_max_chars`
characters, so they cannot become a notes file, and the protocol tells the model to read them before answering.
Counter lines keep their format and guards. Nothing in clm_improved.py, ctxfold.py or recall.py is modified;
second-comparison.sh runs this class for arm B32iraR with `-a clm_rules:ClmRulesAgent`.
"""
from __future__ import annotations

from typing import Any

import clm_improved as _ci
from clm_improved import ClmImprovedAgent

STATE_LINE = r"^(?:[a-z]+\d\d\s+(?:-?\d+|removed)|RULE: \S.*)$"
ONLY_COUNTERS = "(nothing else in the file)"
RULES_NOTE = """- Standing rules and methods: when an item states a rule or a method that holds from then on (how certain
  counters must be reported, how a figure is worked out, and the like), add it to STATE.txt in the same command as
  that item's update, as ONE line `RULE: <the rule or method, complete, in the item's own words>`. Keep RULE lines
  at the top of the file. A RULE line is permanent: never remove or reword it (the harness rejects that). RULE
  lines are for standing rules and methods only, never for values or notes.
- Before you answer any question (a PROBE item or the final item), read the RULE lines and apply every one that
  covers the question.
"""


def rule_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("RULE:")]


def rules_problem(old: str, new: str, max_lines: int, max_chars: int) -> str:
    """Why the RULE lines of `new` are not acceptable after `old` ('' if they are)."""
    now = rule_lines(new)
    gone = [r for r in rule_lines(old) if r not in now]
    if gone:
        return f"a RULE line was removed or reworded (RULE lines are permanent): {gone[0][:80]!r}"
    if len(now) > max_lines:
        return f"more than {max_lines} RULE lines (they are for standing rules and methods only, not notes)"
    long = [r for r in now if len(r) > max_chars]
    if long:
        return f"a RULE line is longer than {max_chars} characters: {long[0][:60]!r}"
    return ""


class ClmRulesAgent(ClmImprovedAgent):
    """Improved agent, read mode + archive/recall, counter lines plus permanent RULE lines in STATE.txt."""

    @staticmethod
    def name() -> str:
        return "clm-rules"

    def __init__(self, *args: Any, rule_max_lines: int | str = 12, rule_max_chars: int | str = 400,
                 **kwargs: Any) -> None:
        kwargs["fold_mode"] = "read"
        kwargs["archive"] = True
        kwargs["quoted"] = False
        kwargs["state_line_regex"] = STATE_LINE
        super().__init__(*args, **kwargs)
        self.rule_max_lines, self.rule_max_chars = int(rule_max_lines), int(rule_max_chars)

    def _validate(self, text: str) -> str:
        bad = super()._validate(text)
        if bad:
            if "does not match the state format" in bad:
                bad += " (a counter line is `name value` or `name removed`; a rule or method is one line `RULE: ...`)"
            return bad
        return rules_problem(self._last_state, text, self.rule_max_lines, self.rule_max_chars)

    async def run(self, instruction, environment, context) -> None:
        saved = _ci.PROTOCOL_READ
        if ONLY_COUNTERS not in saved:
            raise RuntimeError("clm_rules: PROTOCOL_READ changed; update ONLY_COUNTERS")
        _ci.PROTOCOL_READ = saved.replace(ONLY_COUNTERS, "(nothing else in the file except RULE lines, see below)") + RULES_NOTE
        try:
            await super().run(instruction, environment, context)
        finally:
            _ci.PROTOCOL_READ = saved
            try:
                (self.logs_dir / "rules_stats.json").write_text(__import__("json").dumps(
                    {"rule_lines": rule_lines(self._last_state), "rule_max_lines": self.rule_max_lines,
                     "rule_max_chars": self.rule_max_chars}, indent=1) + "\n")
            except Exception:
                pass
