"""Arm N32 (clm_keeper.KeeperAgent): a sliding window that loses nothing and keeps its instructions (2026-10-11).

Why: campaign 4 (notes/2026-10-10-context-16k-baseline.md). The archive arm B32ira is the most accurate method at
32K, but it works through a per-item protocol the model must follow (fold every item into a state file, then drop
it), which is specific to this stream and costs two or more model calls per item. No arm kept a standing rule.
A method meant for real agents has to work without asking the agent to manage anything.

What this is: the plain agent of the sliding-window baseline (W32: no context file, no folding commands), plus three
things the HARNESS does when the context goes over the limit, right before it cuts the oldest turns:
  1. every delivered stream item in the turns being cut is written verbatim to the read-only archive
     (/tmp/.live_ctx/archive/item-NNN.txt, the files `recall` searches and the grader's archive rule allows);
  2. the model is asked once, without tools, to rewrite a NOTES block from the old NOTES and the turns being cut:
     RULES (standing rules and methods, permanent), STATE (current facts later work depends on), OPEN;
     a RULES line can never disappear: one the model leaves out is put back by the harness;
  3. the cut turns are replaced by one pinned user message holding the NOTES, right after the task statement, so
     everything before the recent turns is byte-identical between cuts and the server's prefix cache keeps working.
The cut is made as soon as there is no longer room for the largest item seen so far (plus a margin) and goes down to
60 % of the limit, so an arriving item is never head/tail-truncated to fit, as it can be in W32. Answers already
written to /app/answers.json are never lost: if a later write drops earlier keys the harness puts them back and says so.
The system prompt gains a short Memory section (NOTES, `recall`). When a delivered item asks questions and NOTES holds
rules, the harness also appends the RULES lines as a reminder right after that item (recite_rules, on by default).
Nothing else differs from W32.

This is the policy a serving-side proxy could apply to any tool-calling agent: the agent keeps sending its history,
the proxy archives, keeps notes at each cut and offers `recall`. Cost over W32: one extra model call per cut (about
one per 8K tokens of history at a 32K budget with the default 0.75 target).

Outputs in the agent log dir: keeper_calls.json (one record per cut: sizes, items archived, the notes call's tokens,
rules put back), notes_final.txt. The notes calls are context snapshots of kind "keeper"; like summary calls, their
tokens are not in usage.json.

Use: second-comparison.sh arm N32, or `run-context-job.sh truncate <out> -a clm_keeper:KeeperAgent`.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
import re
import types
from typing import Any

import litellm

from clm_harness.clm_agent import harness as _h
from clm_harness.context_env.types import StepResult
from clm_harness.utils.lm_compat import token_cap_key

import clm_baselines as _cb
from clm_baselines import TruncateAgent
import rag_retrieve as _rag

logger = logging.getLogger(__name__)

ARCH = "/tmp/.live_ctx/archive"
RECALL_SRC = Path(__file__).with_name("recall.py")
PIN_HEAD = "[[NOTES kept by the harness: {n} earlier turns are in the archive (search it with `recall`)]]"
PIN_PLAIN = "[[{n} earlier turns were moved out of view and are kept in the store]]"   # notes_mode=none (arm R32)
PIN_RE = re.compile(r"\[\[(?:NOTES kept by the harness: )?(\d+) earlier turns")
ITEMS = re.compile(r"(?m)^ITEM (\d+)/(\d+) \((\w+)\)\n")
ONLY_NEXT = re.compile(r"\s*next(?:\s*&&\s*next)*\s*")   # a delivery whose output is the items and nothing else
FINAL_KINDS = ("QUERY", "GET")

MEMORY_NOTE = """
## Memory (read carefully)

- This task is long. Older turns are moved out of view automatically; you do not manage that.
- A NOTES message near the top of the conversation is kept by the harness and rewritten whenever turns are moved
  out. It holds the standing RULES and methods stated so far and the current STATE. Read the RULES before you answer
  any question, and apply every one that covers it.
- Everything moved out of view is kept verbatim in a read-only archive. `recall PATTERN` prints the archived
  sentences that match (as `item N: ...`); `recall --item N` prints item N. Use it whenever a question is about
  something no longer in view: an earlier item, a value something held earlier, who did something. Its output enters
  your context, so search narrowly.
- Fetch each item with `next` as a command of its own (nothing chained to it), so it can be archived word for word.
"""

MEMORY_RETRIEVAL = """\
- When an item asks questions, the harness also searches the archive for each question and shows the best-matching
  sentences right after the item (as `item N: ...`). They may not be everything that matters: use `recall` when you
  need more.
"""
MEMORY_RETRIEVAL_ALL = """\
- When an item asks questions, the harness also searches every item received so far (those still in view included)
  for each question and shows the best-matching sentences right after the item (as `item N: ...`, in item order).
  They may not be everything that matters: use `recall` when you need more.
"""
# notes_mode=rules (arm N32r): NOTES holds the rules only; values are worked out from the archive when asked.
MEMORY_RULES_ONLY = """\
- NOTES holds no current values. When a question needs a value, work it out from what is still in view and from the
  archived sentences (the retrieved ones, and `recall` for more), applying the changes in item order.
"""
# notes_mode=none without `recall` (arm R32): retrieval only, the plain "RAG" setup.
MEMORY_RAG = """
## Memory (read carefully)

- This task is long. Older turns are moved out of view automatically; you do not manage that.
- Everything moved out of view is kept in a store. Whenever an item asks questions, the harness searches the store
  for each question and shows the best-matching sentences right after the item (as `item N: ...`). They are all you
  will see of the turns that were moved out: combine them with what is still in view, in item order, to work out
  each answer.
- Fetch each item with `next` as a command of its own (nothing chained to it), so it can be stored word for word.
"""
MEMORY_RAG_ALL = """
## Memory (read carefully)

- This task is long. Older turns are moved out of view automatically; you do not manage that.
- Every item is kept in a store from the moment it arrives. Whenever an item asks questions, the harness searches
  the whole store for each question, the items still in view included, and shows the best-matching sentences right
  after the item (as `item N: ...`, in item order). Work out each answer from that list, applying the changes in
  item order.
- Fetch each item with `next` as a command of its own (nothing chained to it), so it can be stored word for word.
"""

# The instruction comes AFTER the turns. The first live run (2026-10-11, campaign 6) had it before them: the model
# read 8K tokens of its own turns last and simply wrote one more (a running state, no RULES section), so the rule
# of item 1 was lost at the first cut.
NOTES_REQUEST = """\
The oldest part of this conversation is about to be moved out of view. It stays in a searchable archive, but you \
will no longer see it. Below are your current NOTES and the turns being moved out; after them you are asked to \
write the new NOTES.

=== CURRENT NOTES ===
{notes}

=== TURNS BEING MOVED OUT ===
{turns}

=== END OF THE TURNS ===

Do not continue the task and do not call any tool. Write the new NOTES now, so that the work can continue without \
those turns. Use exactly this layout; the first line of your reply is the word RULES:

RULES
one line per standing rule, method or definition that the turns being moved out state and that applies from then \
on, complete and in its original words, after every RULES line of the current NOTES, copied unchanged. Never drop \
or shorten a rule. Do not repeat the task statement at the top of the conversation: it stays in view. If there is \
no rule, write (none).
STATE
what later work depends on, one fact per line, current values only: replace a superseded value, and keep a line \
`name removed` for something that was removed.
OPEN
anything unfinished or to watch for (may be empty).

Keep the whole NOTES under about {cap} tokens. Output only the NOTES.
"""
LAYOUT_RETRY = ("Your reply did not use the layout. Reply with the NOTES only: first line RULES, then the rules, "
                "then a line STATE, then the state, then a line OPEN.")


# Changes-only notes (notes_mode=delta, arm N32d; campaign 10). Measured on the 1M run of N32j: 110 notes calls wrote
# 231K tokens (2,100 a call: about 1,400 of thinking and a rewrite of about 700) and took 53 % of the 83 minutes. Here
# the model writes only the lines that changed, showing its working on the line so that it needs no thinking, and the
# harness applies them. Working of the form `a + b - c = d` is checked: a wrong sum is corrected, and working that
# starts from a value the NOTES do not hold sends that cut back to the full rewrite with thinking.
NOTES_REQUEST_DELTA = """\
The oldest part of this conversation is about to be moved out of view. It stays in a searchable archive, but you \
will no longer see it. Below are your current NOTES and the turns being moved out; after them you are asked for \
the changes those turns make to the NOTES.

=== CURRENT NOTES ===
{notes}

=== TURNS BEING MOVED OUT ===
{turns}

=== END OF THE TURNS ===

Do not continue the task and do not call any tool. Do not write the NOTES out again. Write only what the turns \
being moved out change; the harness applies it to the NOTES and keeps every line you do not mention. Use exactly \
this layout; the first line of your reply is the words NEW RULES:

NEW RULES
one line per standing rule, method or definition that the turns being moved out state and that applies from then \
on, complete and in its original words. The rules already in the NOTES stay; do not repeat them, and do not repeat \
the task statement at the top of the conversation. If the turns state no new rule, write (none).
CHANGES
one line `name: value` per fact of STATE that the turns being moved out set or change, in the order in which the \
turns give the changes (so a thing changed twice has two lines). The harness replaces the STATE line of that name, \
or adds one. When the new value follows from the old one, write the working and put the result last, like \
`stock: 120 + 49 = 169`, starting from the value in the NOTES or in your earlier line. A thing that is new, or \
opened again after it was removed, first gets a line with its opening value. Write `name: removed` when \
something is removed. Go through the turns from the first to the last and leave no change out. If the turns \
change nothing, write (none).
OPEN
at most three short lines: what is unfinished right now and what to watch for (this replaces the old OPEN \
section; may be empty). Do not list what has been received or answers already given.

Output only these three sections.
"""
NOTES_REQUEST_RULES = """\
The oldest part of this conversation is about to be moved out of view. It stays in a searchable archive, but you \
will no longer see it. Below are your current NOTES and the turns being moved out.

=== CURRENT NOTES ===
{notes}

=== TURNS BEING MOVED OUT ===
{turns}

=== END OF THE TURNS ===

Do not continue the task and do not call any tool. Use exactly this layout; the first line of your reply is the \
words NEW RULES:

NEW RULES
one line per standing rule, method or definition that the turns being moved out state and that applies from then \
on, complete and in its original words. The rules already in the NOTES stay; do not repeat them, and do not repeat \
the task statement at the top of the conversation. If the turns state no new rule, write (none).
OPEN
anything unfinished or to watch for, complete (this replaces the old OPEN section; may be empty).

Output only these two sections. Values and other facts are not noted: they stay in the archive.
"""
# In-place notes (notes_inplace, arm N32x; campaign 10). Server counters of campaign 10 after 1,170 requests: 54 % of
# the server's time is reading (6.3M new prompt tokens at 2,640 tokens/s), 46 % writing. In arm N32e every stream
# token is read about four times: on arrival, again when the turns kept by a cut are read back at their new place
# (391K tokens over 23 cuts), and again when the cut turns are shown to the notes call as text (312K). Here the
# notes call is the live conversation itself with one more message at its end, so the server has already read all
# of it; and the cut then takes every turn in view, so nothing is read back. The cut is made every few items (not
# when the window is full), because a notes call that does not think reads about six items reliably.
INPLACE_REQUEST = """\
[[Message from the harness, not part of the task]] Every turn above, from the {start} on, is about to be moved \
out of view. It all stays in a searchable archive, but you will no longer see it. Do not continue the task and do \
not call any tool. Write only what those turns change in the NOTES; the harness applies it and keeps every line \
you do not mention. Use exactly this layout; the first line of your reply is the words NEW RULES:

NEW RULES
one line per standing rule, method or definition that those turns state and that applies from then on, complete \
and in its original words. The rules already in the NOTES stay; do not repeat them, and do not repeat the task \
statement at the top of the conversation. If the turns state no new rule, write (none).
CHANGES
one line `name: value` per fact of STATE that those turns set or change, in the order in which the turns give the \
changes (so a thing changed twice has two lines). The harness replaces the STATE line of that name, or adds one. \
When the new value follows from the old one, write the working and put the result last, like \
`stock: 120 + 49 = 169`, starting from the value in the NOTES or in your earlier line. A thing that is new, or \
opened again after it was removed, first gets a line with its opening value. Write `name: removed` when \
something is removed. Go through the turns from the first to the last and leave no change out. If the turns \
change nothing, write (none).
OPEN
at most three short lines: what is unfinished right now and what to watch for (this replaces the old OPEN \
section; may be empty). Do not list what has been received or answers already given.

Output only these three sections.
"""
PIN_TAIL = ("[[Everything received so far is in the NOTES above or in the archive. The last output moved out began: "
            "{last!r}. It is already counted in the NOTES. Continue the task from there.]]")
DELTA_RETRY = ("Your reply did not use the layout. Reply with the sections only: first line NEW RULES, then the new "
               "rules or (none), then a line CHANGES, then one `name: value` line per change or (none), then a line OPEN.")
RULES_RETRY = ("Your reply did not use the layout. Reply with the sections only: first line NEW RULES, then the new "
               "rules or (none), then a line OPEN.")
DELTA_HEADS = ("NEW RULES", "CHANGES", "OPEN")
RESULT = re.compile(r"\s*(-?\d+)\.?(?:\s*\(.*\))?\s*$")        # the last part of working: `= 169`, `= 169 (item 4)`


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                     "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}


def numbers_in(text: str) -> set[int]:
    """Every whole number the text states, in digits or in English words ("four hundred and two", "forty-nine"),
    each with both signs (a "minus" or "lost" before it is not parsed)."""
    out: set[int] = set()
    total = part = 0
    open_ = False
    def close() -> None:
        nonlocal total, part, open_
        if open_:
            out.update((total + part, -(total + part)))
        total, part, open_ = 0, 0, False
    for tok in re.findall(r"[a-z]+|\d[\d,]*", text.lower()):
        if tok[0].isdigit():
            close()
            n = int(tok.replace(",", "") or 0)
            out.update((n, -n))
        elif tok in _UNITS:
            part, open_ = part + _UNITS[tok], True
        elif tok in _TENS:
            part, open_ = part + _TENS[tok], True
        elif tok == "hundred" and open_:
            part *= 100
        elif tok == "thousand" and open_:
            total, part = total + part * 1000, 0
        elif tok == "and" and open_:
            continue
        else:
            close()
    close()
    return out


def _plain(line: str) -> str:
    return line.strip().lstrip("-*\u2022 ").strip()


def _is_none(line: str) -> bool:
    return _plain(line).lower().strip("().") in ("", "none", "nothing", "empty")


def delta_section_of(line: str) -> str:
    """NEW RULES, CHANGES or OPEN if the line is that heading, else ''."""
    head = " ".join(line.strip().strip("#*_ ").rstrip(":").strip("*_ ").upper().split())
    return head if head in DELTA_HEADS else ""


def fact_of(line: str) -> tuple[str, str]:
    """(name, value) of a STATE or CHANGES line: `name: value`, `name = value`, or `name rest` when it has neither.
    The name is lower-cased; bullets and backticks are dropped."""
    s = _plain(line)
    m = re.match(r"`?([^:=`]+?)`?\s*[:=]\s*(.*)$", s)
    if m and m.group(1).strip() and len(m.group(1).split()) <= 6:
        key, val = m.group(1), m.group(2)
    else:
        key, _, val = s.partition(" ")
    return key.strip().strip("`*_ ").lower(), val.strip().strip("`")


def number_of(value: str) -> int | None:
    """The whole number a STATE value holds now: the one it starts with (`75 (60, gained 15 in item 606)` -> 75), the
    one after an arrow (`-107 -> -31` -> -31), or the only one in it (`opened at 402` -> 402); None for `removed`
    and for anything else."""
    v = re.split(r"\u2192|->|=>", value.strip())[-1].strip()
    m = re.match(r"(-?\d[\d,]*)(?![\d.])", v)
    if m:
        return int(m.group(1).replace(",", ""))
    nums = re.findall(r"-?\d[\d,]*", re.sub(r"\(.*?\)", "", v))
    if len(nums) == 1 and not re.match(r"(removed|closed|struck|deleted|gone)\b", v.lower()):
        return int(nums[0].replace(",", ""))
    return None


def _calc(expr: str) -> float | None:
    """The value of plain arithmetic (numbers, + - * /, brackets); None for anything else."""
    import ast
    def ev(n: Any) -> float:
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            x, y = ev(n.left), ev(n.right)
            return {ast.Add: x + y, ast.Sub: x - y, ast.Mult: x * y}.get(type(n.op)) if not isinstance(n.op, ast.Div) else x / y
        raise ValueError(n)
    try:
        return ev(ast.parse(expr.strip(), mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError, RecursionError):
        return None


def work_out(value: str) -> tuple[int | None, int | None, int] | None:
    """(start, result, stated result) of a value written as working that ends in `= number`, such as
    `120 + 49 - 3 = 166`, `40 x 2 = 80` or `90 - 90/3 = 60`; None when the value is not working. `start` is the
    number the working begins with (None if it begins with something else). `result` is computed when the working
    is plain arithmetic; it is None when plain arithmetic has no whole-number value (`7 / 2`, `7 / 0`): such a line
    cannot be right. Working in words (`119 + what efgh34 holds (402) = 521`) cannot be checked: `result` is then
    the stated result."""
    v = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", value.strip())
    v = v.replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
    arrow = re.fullmatch(r"(-?\d+)\s*(?:\u2192|->|=>)\s*(-?\d+)\.?", v)      # `-107 -> -31`: old value, then the new one
    if arrow:
        return int(arrow.group(1)), int(arrow.group(2)), int(arrow.group(2))
    v = re.sub(r"(?<=[\d)])\s*x\s*(?=[\d(-])", " * ", v)
    parts = v.split("=")
    m = RESULT.fullmatch(parts[-1]) if len(parts) > 1 else None
    expr = parts[-2].strip() if m else ""
    if not m or not re.match(r"\(?\s*-?\d", expr) or not re.search(r"[\d)]\s*[-+*/]\s*\S", expr):
        return None
    stated = int(m.group(1))
    first = re.match(r"\(?\s*(-?\d+)(?![\d.])", parts[0].strip())
    total: int | None = stated
    if re.fullmatch(r"[\d\s+\-*/().]+", expr):
        val = _calc(expr)
        total = int(val) if val is not None and float(val).is_integer() else None
    return (int(first.group(1)) if first else None), total, stated


def parse_delta(reply: str, need_changes: bool = True) -> dict | None:
    """{'rules': [...], 'changes': [(name, value), ...], 'open': [...]} from a reply in the NEW RULES / CHANGES / OPEN
    layout (text before NEW RULES is dropped); None if the layout is missing. 'open' is None when the reply has no
    OPEN heading: the old OPEN section then stays."""
    lines = reply.splitlines()
    at = next((i for i, ln in enumerate(lines) if delta_section_of(ln) == "NEW RULES"), None)
    if at is None:
        return None
    sec, seen = "NEW RULES", {"NEW RULES"}
    out: dict[str, list[str]] = {h: [] for h in DELTA_HEADS}
    for ln in lines[at + 1:]:
        head = delta_section_of(ln)
        if head:
            sec = head
            seen.add(head)
        elif ln.strip():
            out[sec].append(ln.strip())
    if need_changes and "CHANGES" not in seen:
        return None
    return {"rules": [_plain(ln) for ln in out["NEW RULES"] if not _is_none(ln)],
            "changes": [fact_of(ln) for ln in out["CHANGES"] if not _is_none(ln) and fact_of(ln)[0]],
            "open": [ln for ln in out["OPEN"] if not _is_none(ln)] if "OPEN" in seen else None}


def apply_delta(notes: str, delta: dict, seen: set[int] | None = None) -> tuple[str, dict]:
    """The NOTES after the changes, and what happened: lines changed and added, sums corrected, and `mismatch`:
    working that cannot be trusted (it starts from a value the NOTES do not hold, it starts from a number although
    the NOTES say the thing was removed, or it is arithmetic without a whole-number value); the caller then falls
    back to a full rewrite. `seen` is every number the turns being moved out state (numbers_in): working may start
    from one of those instead of the NOTES value, because the turns can set a thing and then change it and the
    model writes both on one line (`abcd12: 294 + 12 = 306`). The first run of arm N32d (rules stream, seed 0) sent
    8 of 23 cuts to the full rewrite for exactly that; all eight were such lines. RULES lines are never removed; a new rule that rewords an existing one is not added.
    A STATE line keeps its place; a value given as working is stored as its result. The OPEN section is replaced
    when the reply has one and kept otherwise."""
    rules, state, opened, sec = [], [], [], ""
    for ln in notes.splitlines():
        head = section_of(ln)
        if head:
            sec = head
        elif ln.strip() and sec == "RULES" and not _is_none(ln):
            rules.append(ln.rstrip())
        elif ln.strip() and sec == "STATE":
            state.append(ln.rstrip())
        elif ln.strip() and sec == "OPEN":
            opened.append(ln.rstrip())
    info: dict[str, Any] = {"changed": 0, "added": 0, "sums_corrected": [], "mismatch": [], "new_rules": 0}
    have = [_plain(r) for r in rules]
    for r in delta.get("rules", []):
        if not any(same_rule(r, h) for h in have):
            rules.append("- " + r)
            have.append(r)
            info["new_rules"] += 1
    where = {fact_of(ln)[0]: i for i, ln in enumerate(state)}
    for name, value in delta.get("changes", []):
        w = work_out(value)
        if w:
            start, total, stated = w
            old = fact_of(state[where[name]])[1] if name in where else None
            held = number_of(old) if old is not None else None
            if total is None:
                info["mismatch"].append(f"{name}: `{value}` has no whole-number value")
                total = stated
            elif start is not None and seen is not None and start in seen:
                info["set_in_turns"] = info.get("set_in_turns", 0) + (held != start)
            elif start is not None and held is not None and held != start:
                info["mismatch"].append(f"{name}: working starts from {start}, NOTES hold {held}")
            elif start is not None and old is not None and re.match(r"(removed|closed|struck|deleted|gone)\b", old.lower()):
                info["mismatch"].append(f"{name}: working starts from {start}, NOTES say {old.split()[0]}")
            if total != stated:
                info["sums_corrected"].append(f"{name}: {value} -> {total}")
            value = str(total)
        line = f"{name}: {value}" if value else name
        if name in where:
            state[where[name]] = line
            info["changed"] += 1
        else:
            where[name] = len(state)
            state.append(line)
            info["added"] += 1
    if delta.get("open") is not None:
        opened = list(delta["open"])
    return "\n".join(["RULES"] + (rules or ["(none)"]) + ["STATE"] + state + ["OPEN"] + opened), info


def section_of(line: str) -> str:
    """RULES, STATE or OPEN if the line is that heading (plain, with a colon, or as a markdown heading), else ''."""
    head = line.strip().strip("#*_ ").rstrip(":").strip("*_ ").upper()
    return head if head in ("RULES", "STATE", "OPEN") else ""


def from_rules(text: str) -> str:
    """The reply from its RULES heading on (a reply may open with a THOUGHT line the agent's system prompt asks for)."""
    lines = text.splitlines()
    at = next((i for i, ln in enumerate(lines) if section_of(ln) == "RULES"), None)
    return text if at is None else "\n".join(lines[at:]).strip()


def has_layout(notes: str) -> bool:
    heads = [section_of(ln) for ln in notes.splitlines()]
    return "RULES" in heads and "STATE" in heads and heads.index("RULES") < heads.index("STATE")


def split_items(tool_text: str) -> dict[int, str]:
    """Delivered items in one tool output (`next`, or `next && next`): {item number: verbatim text}."""
    body = tool_text.split("\n\n(exit_code=")[0]
    heads = list(ITEMS.finditer(body))
    out = {}
    for j, hm in enumerate(heads):
        if hm.group(3) in FINAL_KINDS:
            continue
        end = heads[j + 1].start() if j + 1 < len(heads) else len(body)
        out[int(hm.group(1))] = body[hm.end():end].strip()
    return out


def command_of(call: Any) -> str:
    fn = call.get("function") if isinstance(call, dict) else getattr(call, "function", None)
    args = (fn.get("arguments") if isinstance(fn, dict) else getattr(fn, "arguments", "")) or ""
    try:
        return str(json.loads(args).get("command", args))
    except Exception:
        return str(args)


def render_turns(turns: list[dict[str, Any]]) -> str:
    """The cut turns as plain text for the notes call (thinking included: a plain agent keeps its running state there)."""
    out = []
    for m in turns:
        role, text = m.get("role"), str(m.get("content") or "").strip()
        if role == "assistant":
            think = str(m.get("reasoning_content") or "").strip()
            if think:
                out.append("ASSISTANT THINKING: " + think)
            if text:
                out.append("ASSISTANT: " + text)
            out += ["COMMAND: " + command_of(c) for c in (m.get("tool_calls") or [])]
        elif role == "tool":
            out.append("OUTPUT: " + text)
        elif text:
            out.append("NOTE: " + text)
    return "\n".join(out)


def split_turns(turns: list[dict[str, Any]], count: Any, max_tokens: int) -> list[list[dict[str, Any]]]:
    """The messages of the cut turns in as few pieces as fit `max_tokens` each (as `count(messages)` measures them),
    whole turns only and of about equal size; one piece when max_tokens is 0. A changes-only notes call that does not
    think reads about six items reliably (39/39 twice) and eleven not (36/39), so a deeper cut is noted in pieces."""
    if not max_tokens or not turns:
        return [turns]
    groups: list[list[dict[str, Any]]] = []
    for m in turns:
        if m.get("role") == "assistant" or not groups:
            groups.append([])
        groups[-1].append(m)
    sizes = [count(g) for g in groups]
    pieces_wanted = max(1, -(-sum(sizes) // max_tokens))
    target = sum(sizes) / pieces_wanted
    pieces, piece, size = [], [], 0
    for g, n in zip(groups, sizes):
        if piece and (size + n > max_tokens or (size + n / 2 > target and len(pieces) < pieces_wanted - 1)):
            pieces.append(piece)
            piece, size = [], 0
        piece = piece + g
        size += n
    if piece:
        pieces.append(piece)
    return pieces


def rule_lines(notes: str) -> list[str]:
    """Lines of the RULES section (between the line RULES and the line STATE), bullets stripped."""
    lines, on = [], False
    for ln in notes.splitlines():
        s, head = ln.strip(), section_of(ln)
        if head:
            on = head == "RULES"
        elif on and s:
            lines.append(s.lstrip("-* ").strip())
    return [ln for ln in lines if ln and ln.lower().strip("().") != "none"]


def same_rule(a: str, b: str) -> bool:
    """Two wordings of one rule: most of the words of the shorter are in the longer, and both name the same things
    (every word with a digit in it: names such as abcd12, and numbers). "abcd12 is secret" and "efgh34 is secret"
    share all but one word and are two rules."""
    wa, wb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    named = lambda w: {t for t in w if any(c.isdigit() for c in t)}
    return bool(wa and wb) and named(wa) == named(wb) and len(wa & wb) >= 0.8 * min(len(wa), len(wb))


def keep_rules(old: str, new: str) -> tuple[str, list[str]]:
    """`new` with every RULES line of `old` that it lost put back at the top of its RULES section. A rule the model
    reworded comes back in its original wording and the rewording is removed, so the section cannot fill up with
    variants of one rule (the proxy saw 95 put-backs over a 1M stream; this arm saw none, and now cannot)."""
    norm = lambda s: " ".join(s.split())            # exact words and case; only spacing may differ
    have = {norm(r) for r in rule_lines(new)}
    lost = [r for r in rule_lines(old) if norm(r) not in have]
    if not lost:
        return new, []
    lines = new.splitlines()
    at = next((i for i, ln in enumerate(lines) if section_of(ln) == "RULES"), None)
    if at is None:
        lines, at = ["RULES"] + lines, 0
    kept, in_rules = lines[:at + 1], True
    for ln in lines[at + 1:]:
        if section_of(ln):
            in_rules = section_of(ln) == "RULES"
        elif in_rules and ln.strip() and any(same_rule(ln.strip().lstrip("-* ").strip(), r) for r in lost):
            continue                                 # a rewording of a rule that is being put back
        kept.append(ln)
    kept[at + 1:at + 1] = lost
    return "\n".join(kept), lost


ASKS = re.compile(r"(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)")
RECITE_HEAD = "[[RULES in force (from NOTES); apply every one that covers a question before you answer it]]"


def recital(notes: str, messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The reminder to append when the newest message is a tool output that asks questions and NOTES holds rules
    (None otherwise). On the 1M stream a pinned rule was applied 22 times in 29; it slipped more often late, with the
    rule far above the question. This puts the rules next to the question at the moment they are needed."""
    rules = rule_lines(notes)
    if not rules or not messages or messages[-1].get("role") != "tool":
        return None
    if not ASKS.search(str(messages[-1].get("content") or "")):
        return None
    return {"role": "user", "content": RECITE_HEAD + "\n" + "\n".join("- " + r for r in rules)}


QUESTION = re.compile(r"(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)|^PROBE:|STREAM END|NOT RUN|Traceback|No tool call in your last turn"
                      r"|CONTEXT LIMIT|FINAL turn")


def wants_thinking(messages: list[dict[str, Any]]) -> bool:
    """Judgement policy: think when the newest tool output (or a harness message after it) holds a question, the end
    of the stream, a refusal or an error, when the last command failed, before any tool output exists, and for as
    long as a question is open: the newest DELIVERED item asks questions and no later item has arrived. A routine
    fetch of the next item is answered without thinking.
    (Until 2026-10-11 thinking went off again right after the question item itself; on the 1M stream the model then
    worked on a probe with thinking off and repeated one recall command 790 times.)"""
    last_tool = next((i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "tool"), -1)
    if last_tool < 0:            # nothing delivered yet: think, unless a NOTES message shows the task is under way
        return not any(m.get("role") == "user" and PIN_RE.match(str(m.get("content") or "")) for m in messages)
    tail = [str(m.get("content") or "") for m in messages[last_tool:]]
    if any(QUESTION.search(t) for t in tail):
        return True
    codes = re.findall(r"\(exit_code=(-?\d+)\)", tail[0])
    if codes and codes[-1] != "0":
        return True
    for m in reversed(messages):                     # the newest delivery: is it a question item?
        text = str(m.get("content") or "") if m.get("role") == "tool" else ""
        if ITEMS.search(text):
            return bool(ASKS.search(text) or QUESTION.search(text))
    return False


ANSWERS = "/app/answers.json"
REPEAT_NOTE = ("NOT RUN: this is exactly the command you just ran, and nothing has changed since, so its result would be "
               "the same. Use the result you already have and decide the next step.")


def is_repeat(cmd: str, last: str, fetches: bool) -> bool:
    """A command identical to the previous one, unless it fetches the next item (each fetch delivers something new)."""
    return bool(cmd) and cmd == last and not fetches



def lost_answers(before: dict, now: Any) -> dict:
    """Keys of `before` that a later write dropped from the answers file ({} if `now` is not a JSON object: an
    unreadable file is left to the agent). On the 1M stream an agent rewrote the file at the final item with the
    final counters only, and 196 probe answers were gone."""
    if not isinstance(now, dict):
        return {}
    return {k: v for k, v in before.items() if k not in now}


class _KeeperEnv(_cb._NoMirrorEnv):
    """Keeps the verbatim text of every delivered item as `next` printed it (for the archive) and the size of the
    largest delivery (so the cut can leave room for the next one)."""

    agent: "KeeperAgent"

    async def step(self, command, messages, *, environment, pending=None):
        a = self.agent
        # Repeat guard. On the 1M stream (campaign 7) the agent, with thinking off, issued `recall "p13_3"` several
        # hundred times in a row, each with the same result, until the run had to be stopped. A command identical to
        # the one just run is not run again unless it is a fetch; the refusal says so, and "NOT RUN" turns thinking on.
        cmd = (command or "").strip()
        if a.repeat_guard and is_repeat(cmd, a._last_cmd, bool(a._guard_cmd.search(cmd))):
            a.n_repeats_refused += 1
            res = types.SimpleNamespace(stdout=REPEAT_NOTE, stderr="", return_code=75)
            return StepResult(result=res, ctx_changed=False, stdout_block=REPEAT_NOTE + "\n\n(exit_code=75)",
                              readout="", notes="", exec_time=0.0, touched_ctx=False)
        a._last_cmd = cmd
        res = await super().step(command, messages, environment=environment, pending=pending)
        got = split_items(getattr(res.result, "stdout", "") or "")
        if got:
            if ONLY_NEXT.fullmatch(command or ""):
                a._delivered.update(got)
            else:   # `next && something`: the last item's text would run on into the other command's output
                a._mixed.update(got)
            a._largest_delivery = max(a._largest_delivery, self.budget.count([{"role": "tool", "content": res.stdout_block}]))
            if a.auto_retrieve and a.retrieve_scope == "all":       # the store holds every item from the moment it arrives
                for num, text in got.items():
                    if not ASKS.search(text):
                        a._index.add(num, text)
        if "answers.json" in (command or ""):
            try:
                await self._keep_answers(environment, res)
            except Exception as exc:              # the guard must never be the reason a step fails
                logger.warning("keeper: answers guard skipped: %s", exc)
        return res

    async def _keep_answers(self, environment: Any, res: Any) -> None:
        """Answers already given are never lost: keys a write dropped are put back (values the agent wrote stay)."""
        a = self.agent
        r = await environment.exec(command=f"cat {ANSWERS} 2>/dev/null", timeout_sec=30)
        try:
            now = json.loads(getattr(r, "stdout", "") or "")
        except ValueError:
            return
        lost = lost_answers(a._answers, now)
        if lost:
            merged = {**lost, **now}
            blob = base64.b64encode(json.dumps(merged, indent=1).encode()).decode()
            await environment.exec(command=f"echo {blob} | base64 -d > {ANSWERS}", timeout_sec=30)
            a.n_answers_put_back += len(lost)
            res.stdout_block += (f"\n[harness: that write dropped {len(lost)} answers given earlier "
                                 f"({' '.join(list(lost)[:5])}{' ...' if len(lost) > 5 else ''}); they were put back. "
                                 f"Add or change keys, never rewrite the file from scratch.]")
            now = merged
        if isinstance(now, dict):
            a._answers = dict(now)


class _KeeperGuard:
    """Wraps the checkpointer: after its maybe(), the agent archives, takes notes and cuts if it is over the limit
    (the same place as the sliding-window baseline's cut: right before the budget gate and the model call)."""

    def __init__(self, inner: Any, agent: "KeeperAgent") -> None:
        self._inner, self._agent = inner, agent

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def maybe(self, environment: Any, messages: list[dict[str, Any]]) -> bool:
        r = await self._inner.maybe(environment, messages)
        a = self._agent
        # Room for the retrieved sentences is reserved before the cut, and the search runs after it: the items that
        # this cut moves out are then in the store, and the message cannot push the context over the limit.
        room = a._retrieval_room(messages) if a.auto_retrieve else 0
        await a._keep(environment, messages, reserve=room // 3 if room else 0)
        note = recital(a.notes, messages) if a.recite_rules else None
        found = a._retrieval(messages, room, [note] if note else []) if room else None
        if found:                                     # retrieved sentences first, the rules last (next to the answer)
            messages.append(found)
            a.n_retrievals += 1
        if note:
            messages.append(note)
            a.n_recitals += 1
        return r


class KeeperAgent(TruncateAgent):
    """Sliding window + archive of the cut items + NOTES rewritten at each cut + `recall` (see the module docstring)."""

    calls_file = "keeper_calls.json"

    @staticmethod
    def name() -> str:
        return "keeper"

    def __init__(self, *args: Any, notes_max_tokens: int | str = 2048, notes_call_max_tokens: int | str = 4096,
                 notes_thinking: Any = False, thinking_policy: str = "always", recite_rules: Any = True,
                 keep_headroom: int | str = 1024, repeat_guard: Any = True, notes_mode: str = "full",
                 auto_retrieve: int | str = 0, retrieve_floor: float | str = 0.0, recall_tool: Any = True,
                 retrieve_max_chars: int | str = 30000, retrieve_window: int | str = 1, retrieve_scope: str = "archive",
                 notes_chunk_tokens: int | str = 0, notes_inplace: Any = False, inplace_turn_tokens: int | str = 9500,
                 **kwargs: Any) -> None:
        kwargs.setdefault("truncate_target_ratio", 0.6)   # cut deeper than W32 (0.75): fewer cuts, fewer notes calls
        super().__init__(*args, **kwargs)
        # A delivered item is never cut on arrival (the budget's newest-output cap head/tail-truncates whatever does
        # not fit, which is how W32 loses text near its limit); instead the cut is made early enough to leave room
        # for the largest delivery seen plus keep_headroom, and the archive is written from what `next` printed.
        self.keep_headroom, self._largest_delivery, self._delivered = int(keep_headroom), 0, {}
        self._mixed: dict[int, str] = {}              # items delivered by a command that printed something else too
        self.repeat_guard, self._last_cmd, self.n_repeats_refused = _cb._as_bool(repeat_guard), "", 0
        self._answers: dict = {}                      # the answers file as last seen; earlier keys are never lost
        self.n_answers_put_back = 0
        self.n_archive_failed = self.n_not_archived_mixed = 0
        self._ctx.__class__ = _KeeperEnv
        self._ctx.agent = self
        orig_cap, is_delivery = self._budget.cap_newest_output, self._guard_out

        def cap_newest_output(messages, tool_content, *, floor=128):
            return tool_content if is_delivery.search(tool_content) else orig_cap(messages, tool_content, floor=floor)

        self._budget.cap_newest_output = cap_newest_output
        self.notes_max_tokens, self.notes_call_max_tokens = int(notes_max_tokens), int(notes_call_max_tokens)
        self.notes_thinking = _cb._as_bool(notes_thinking)
        self.recite_rules, self.n_recitals = _cb._as_bool(recite_rules), 0
        # thinking_policy (arm N32j): always = the agent's enable_thinking on every call (as W32); judgement = thinking
        # only on calls that hold a question, a refusal or an error (see _wants_thinking). The running state then no
        # longer sits in the agent's thinking, so the notes call does the bookkeeping: pair it with notes_thinking=true.
        self.thinking_policy = str(thinking_policy or "always").strip().lower()
        if self.thinking_policy not in ("always", "judgement"):
            raise ValueError(f"thinking_policy must be always|judgement, not {thinking_policy!r}")
        self._base_thinking = self.enable_thinking
        self.n_thinking_on = self.n_thinking_off = 0
        if self.thinking_policy == "judgement":
            # the Qwen3.8 template adds a sentence to the system message when thinking is on; reasoning_effort=medium
            # removes it, so switching per call does not change the first line of the prompt (clm_improved, stable_system)
            import clm_improved as _ci
            _ci._install_extra_body_hook()
            _ci._CTK_EXTRA["reasoning_effort"] = "medium"
        self.notes = ""
        self.n_notes_calls = self.n_items_archived = self.n_rules_put_back = self.n_notes_failed = 0
        # notes_mode: full = NOTES rewritten at each cut (N32, N32j); delta = the model writes only the changed lines
        # and the harness applies them (N32d); rules = only new rules are noted, values stay in the archive (N32r);
        # none = no notes call at all (R32, the retrieval-only arm).
        self.notes_mode = str(notes_mode or "full").strip().lower()
        if self.notes_mode not in ("full", "delta", "rules", "none"):
            raise ValueError(f"notes_mode must be full|delta|rules|none, not {notes_mode!r}")
        self.n_delta_fallbacks = self.n_sums_corrected = 0
        # notes_chunk_tokens (delta and rules modes): the turns of one cut go to the notes call in pieces of at most
        # this many tokens, one call each, in order (0 = one call per cut). See split_turns.
        self.notes_chunk_tokens = int(notes_chunk_tokens)
        # notes_inplace (delta mode): once the turns in view hold more than inplace_turn_tokens, and the newest one
        # is an ordinary delivery (no question open), the notes call is the live conversation plus one message, and
        # every turn is then moved out (see INPLACE_REQUEST). The ordinary cut stays as the safety net.
        self.notes_inplace, self.inplace_turn_tokens = _cb._as_bool(notes_inplace), int(inplace_turn_tokens)
        if self.notes_inplace and self.notes_mode != "delta":
            raise ValueError("notes_inplace needs notes_mode=delta")
        self.n_inplace = self.n_inplace_failed = self.inplace_cached = self.inplace_prompt = 0
        self._pin_tail = ""
        self.inplace_failures: list[dict[str, Any]] = []
        self.n_inplace_redone = 0
        self.inplace_turn_hold = 0                    # after a failed in-place call: no new attempt on the same turns
        # auto_retrieve=K: when a delivered item asks questions, the K best-matching archived sentences per question
        # (BM25, rag_retrieve.py) are shown right after it, each with the retrieve_window sentences that follow it
        # (a rule's subject and what to do about it, or "X. It went up by ...", sit in neighbouring sentences).
        # recall_tool=false leaves the search tool out (R32).
        self.auto_retrieve, self.retrieve_floor = int(auto_retrieve), float(retrieve_floor)
        self.retrieve_max_chars, self.retrieve_window = int(retrieve_max_chars), int(retrieve_window)
        # retrieve_scope: archive = only the items already moved out of view are searched (what is in view is not
        # repeated); all = every delivered item is searched, so the retrieved list for a question is complete on its
        # own (R32 seed 0 answered 7 of 14 final queries although every needed sentence was in its context: the
        # older changes were in the retrieved list and the newer ones in the window, and it took stale values).
        self.retrieve_scope = str(retrieve_scope or "archive").strip().lower()
        if self.retrieve_scope not in ("archive", "all"):
            raise ValueError(f"retrieve_scope must be archive|all, not {retrieve_scope!r}")
        self.recall_tool = _cb._as_bool(recall_tool)
        self._index, self.n_retrievals, self.retrieved_chars, self.n_retrievals_skipped = _rag.Index(), 0, 0, 0
        self._ckpt = _KeeperGuard(self._ckpt, self)   # TruncateAgent's own guard stays inside; its _manage is a no-op here

    def _manage(self, messages: list[dict[str, Any]]) -> None:
        return                                        # the cut happens in _keep (it needs the sandbox and a model call)

    def _wants_thinking(self, messages: list[dict[str, Any]]) -> bool:
        return wants_thinking(messages) and bool(self._base_thinking)

    async def _query_with_retry(self, model: str, messages: list[dict[str, Any]]) -> Any:
        if self.thinking_policy == "judgement":
            self.enable_thinking = self._wants_thinking(messages)
        if self.enable_thinking:
            self.n_thinking_on += 1
        else:
            self.n_thinking_off += 1
        return await super()._query_with_retry(model, messages)

    async def setup(self, environment: Any) -> None:
        await super().setup(environment)
        tool = ("cat > /usr/local/bin/recall <<'RECALL_EOF'\n" + RECALL_SRC.read_text() + "\nRECALL_EOF\n"
                "chmod +x /usr/local/bin/recall") if self.recall_tool else "true"
        await environment.exec(command=f"mkdir -p {ARCH} && touch {ARCH}/.on && " + tool, timeout_sec=60)

    def _pin(self, n: int) -> dict[str, Any]:
        if self.notes_mode == "none":
            return {"role": "user", "content": PIN_PLAIN.format(n=n)}
        tail = ("\n" + self._pin_tail) if self._pin_tail else ""
        return {"role": "user", "content": PIN_HEAD.format(n=n) + "\n" + (self.notes or "(no notes yet)") + tail}

    def _asked(self, messages: list[dict[str, Any]]) -> str:
        """The newest message, if it is a delivered item that asks questions (else '')."""
        if not messages or messages[-1].get("role") != "tool":
            return ""
        text = str(messages[-1].get("content") or "")
        return text.split("\n\n(exit_code=")[0] if ITEMS.search(text) and ASKS.search(text) else ""

    def _retrieval_room(self, messages: list[dict[str, Any]]) -> int:
        """Characters to reserve for the retrieved sentences of the newest item (0 if it asks nothing): a quarter more
        than a search of the store as it is now returns, at least 4,000, at most retrieve_max_chars."""
        text = self._asked(messages)
        if not text:
            return 0
        now = len(_rag.retrieval_note(self._index, text, self.auto_retrieve, self.retrieve_floor, window=self.retrieve_window))
        return min(self.retrieve_max_chars, max(int(now * 1.25) + 600, 4000))

    def _retrieval(self, messages: list[dict[str, Any]], room: int, after: list[dict[str, Any]]) -> dict[str, Any] | None:
        """The retrieved sentences to show after the newest item: within `room` characters, and within the tokens
        that are really left once the cut is made and the messages in `after` (the rules reminder) are counted. The
        weakest matches go first; with no room left nothing is shown and the skip is counted."""
        text = self._asked(messages)
        if not text:
            return None
        limit = self._budget.strict_target
        left = (limit - self._budget.count(messages + after) - 256) if limit else 10 ** 9
        budget = min(room, 3 * left)
        while budget >= 600:
            note = _rag.retrieval_note(self._index, text, self.auto_retrieve, self.retrieve_floor, budget_chars=budget,
                                       window=self.retrieve_window)
            if not note:
                return None
            msg = {"role": "user", "content": note}
            if self._budget.count([msg]) <= left:
                self.retrieved_chars += len(note)
                return msg
            budget = int(budget * 0.8)
        self.n_retrievals_skipped += 1
        return None

    def _head(self, messages: list[dict[str, Any]]) -> tuple[int, int]:
        i = self._protect
        if i < len(messages) and messages[i].get("role") == "user":
            m = PIN_RE.match(str(messages[i].get("content") or ""))
            if m:
                return i + 1, int(m.group(1))
        return i, 0

    async def _archive(self, environment: Any, turns: list[dict[str, Any]]) -> int:
        """Write the items of the cut turns to the archive from what `next` printed. An item the harness did not see
        arrive as the whole output of a `next` command is not archived (its text could not be verbatim, and a file
        that is not a verbatim item voids a memory-only run); a failed write is counted, and the text is kept for
        the next cut."""
        n = 0
        for m in turns:
            if m.get("role") != "tool":
                continue
            for num in split_items(str(m.get("content") or "")):
                text = self._delivered.get(num)
                if text is None:
                    self.n_not_archived_mixed += num in self._mixed
                    self._mixed.pop(num, None)
                    continue
                blob = base64.b64encode((text + "\n").encode()).decode()
                f = f"{ARCH}/item-{num:03d}.txt"
                try:
                    r = await environment.exec(
                        command=f"[ -e {f} ] || {{ echo {blob} | base64 -d > {f} && chmod 444 {f}; }}", timeout_sec=60)
                    ok = getattr(r, "return_code", 0) in (0, None)
                except Exception as exc:
                    logger.warning("keeper: archiving item %d failed: %s", num, exc)
                    ok = False
                if ok:
                    self._delivered.pop(num, None)
                    if self.auto_retrieve and not ASKS.search(text):
                        # an item that only asks questions is not stored: earlier questions share their words with
                        # the next question and crowd the evidence out (rag_coverage.py on the 1M stream: 111 of 228
                        # questions covered at 20 sentences each with them in the store, 187 without)
                        self._index.add(num, text)
                    n += 1
                else:
                    self.n_archive_failed += 1
        return n

    def _notes_call(self, req: list[dict[str, Any]], thinking: bool | None = None, live: bool = False):
        model = self.model_name or ""
        kw: dict[str, Any] = {"model": model, "messages": req, token_cap_key(model): self.notes_call_max_tokens,
                              "api_base": self.api_base, "timeout": _h._LLM_TIMEOUT_SECONDS, "num_retries": 2,
                              "drop_params": True}
        if live:      # the same tool list as the main loop, so the prompt is the one the server has already read
            kw.update(tools=[_h.BASH_TOOL], tool_choice="none")
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        if self.top_p is not None:
            kw["top_p"] = self.top_p
        if self.send_chat_template_kwargs:
            kw["extra_body"] = {"chat_template_kwargs": {
                "enable_thinking": self.notes_thinking if thinking is None else thinking}}
        self.n_lm_calls += 1
        self.n_notes_calls += 1
        try:
            return litellm.completion(**kw)
        except Exception as exc:
            logger.warning("keeper: notes call failed: %s: %s", type(exc).__name__, exc)
            return exc

    async def _keep(self, environment: Any, messages: list[dict[str, Any]], reserve: int = 0) -> None:
        """Archive, take notes and cut when the context is over the limit, or would be once `reserve` tokens (the
        retrieved sentences about to be appended) are added."""
        limit = self._budget.strict_target
        if not limit:
            return
        before = self._budget.count(messages)
        if self.notes_inplace and await self._keep_inplace(environment, messages, before):
            return
        if before + reserve <= min(self.trigger_ratio * limit, limit - self._largest_delivery - self.keep_headroom):
            return
        start, prev = self._head(messages)
        head, body = messages[:self._protect], messages[start:]
        starts = [k for k, m in enumerate(body) if m.get("role") == "assistant"]
        if starts and starts[0] > 0:
            starts.insert(0, 0)                       # leading non-assistant messages count as one turn
        target = max(min(int(self.target_ratio * limit), limit - self.keep_headroom - reserve), int(0.2 * limit))
        n, keep = 0, body
        for cut in starts[1:]:                        # never the newest turn
            if self._budget.count(head + [self._pin(prev + n)] + keep) < target:
                break
            n += 1
            keep = body[cut:]
        if not n:
            return
        gone = body[:len(body) - len(keep)]
        self._pin_tail, self.inplace_turn_hold = "", 0     # the turns that an in-place call could not note are going now
        rec: dict[str, Any] = {"reason": "keep", "turns_dropped": n, "before": before,
                               "items_archived": await self._archive(environment, gone)}
        self.n_items_archived += rec["items_archived"]
        if self.notes_mode != "none":
            chunk = self.notes_chunk_tokens if self.notes_mode in ("delta", "rules") else 0
            pieces = split_turns(gone, self._budget.count, chunk)
            rec.update(notes_prompt_tokens=0, notes_completion_tokens=0, notes_attempts=0, notes_mode=self.notes_mode,
                       notes_pieces=len(pieces))
            for piece in pieces:
                await self._take_notes(head, render_turns(piece), rec)
        messages[:] = head + [self._pin(prev + n)] + keep
        rec["after"] = self._budget.count(messages)
        self._record(rec)

    async def _keep_inplace(self, environment: Any, messages: list[dict[str, Any]], before: int) -> bool:
        """The in-place cut (see INPLACE_REQUEST). True when it was made; False leaves everything as it was."""
        start, prev = self._head(messages)
        head, body = messages[:self._protect], messages[start:]
        last = str(body[-1].get("content") or "") if body and body[-1].get("role") == "tool" else ""
        if not last or not ITEMS.search(last) or ASKS.search(last) or QUESTION.search(last):
            return False                              # not an ordinary delivery: a question may be open
        size = self._budget.count(body)
        if size <= self.inplace_turn_tokens or (self.inplace_turn_hold and size >= self.inplace_turn_hold):
            return False                              # too little to note, or these turns already failed once
        self.inplace_turn_hold = 0
        n = sum(1 for m in body if m.get("role") == "assistant") or 1
        rec: dict[str, Any] = {"reason": "keep-inplace", "turns_dropped": n, "before": before, "notes_mode": "delta",
                               "notes_prompt_tokens": 0, "notes_completion_tokens": 0, "notes_attempts": 0, "cached": 0}
        req = messages + [{"role": "user", "content": INPLACE_REQUEST.format(
            start="message that holds the NOTES" if start > self._protect else "first turn after the task statement")}]
        self._snap(req, "keeper")
        base, seen, why = req, numbers_in(render_turns(body)), "no reply"
        thinking = self.notes_thinking
        for _attempt in (1, 2, 3):
            # a reply without the layout is asked for once more; working that cannot be trusted is asked for again
            # from the start with thinking on (first run of N32x: one such reply ended the in-place cuts for good)
            rec["notes_attempts"] += 1
            resp = await asyncio.to_thread(self._notes_call, req, thinking, True)
            if isinstance(resp, Exception):
                why = f"{type(resp).__name__}: {resp}"
                continue
            text = self._tally(rec, resp)
            details = getattr(getattr(resp, "usage", None), "prompt_tokens_details", None)
            rec["cached"] += getattr(details, "cached_tokens", 0) or 0
            delta = parse_delta(text) if rec["notes_finish"] != "length" else None
            if delta is None:
                why = "reply without the NEW RULES layout" if rec["notes_finish"] != "length" else "reply cut at the token cap"
                rec["notes_bad_layout"] = text[:200]
                req = req + [{"role": "assistant", "content": text}, {"role": "user", "content": DELTA_RETRY}]
                continue
            new, info = apply_delta(self.notes, delta, seen)
            size = self._budget.count([{"role": "user", "content": new}])
            if info["mismatch"]:
                why = "working starts from a value the NOTES do not hold: " + "; ".join(info["mismatch"][:3])
                rec.setdefault("inplace_redo", why)
                if not thinking:
                    req, thinking = base, True
                    continue
            elif size > 2 * self.notes_max_tokens:
                why = f"NOTES of {size} tokens after the changes, over twice the cap"
            else:
                why = ""
                rec["items_archived"] = await self._archive(environment, body)
                self.n_items_archived += rec["items_archived"]
                self.n_sums_corrected += len(info["sums_corrected"])
                self.notes, self._pin_tail = new, PIN_TAIL.format(last=last.split("\n", 1)[0][:80])
                rec.update(notes_tokens=size, rules=len(rule_lines(new)), rules_put_back=[], delta=info)
                messages[:] = head + [self._pin(prev + n)]
                rec["after"] = self._budget.count(messages)
                self.n_inplace += 1
                self.n_inplace_redone += "inplace_redo" in rec
                self.inplace_cached += rec["cached"]
                self.inplace_prompt += rec["notes_prompt_tokens"]
                self._record(rec)
                return True
            break
        self.n_inplace_failed += 1                    # nothing was changed; the ordinary cut will handle these turns
        logger.warning("keeper: in-place notes not applied: %s", why)
        self.inplace_failures.append({"step": self.n_lm_calls, "why": why, "prompt": rec["notes_prompt_tokens"],
                                      "written": rec["notes_completion_tokens"]})
        self.inplace_turn_hold = self._budget.count(body)
        return False

    async def _take_notes(self, head: list[dict[str, Any]], turns: str, rec: dict[str, Any]) -> None:
        thinking = None
        if self.notes_mode in ("delta", "rules"):
            why = await self._notes_delta(head, turns, rec)
            if not why:
                return
            rec.setdefault("delta_fallback", why)     # the first reason of this cut; the count is in delta_fallbacks_n
            rec["delta_fallbacks_n"] = rec.get("delta_fallbacks_n", 0) + 1
            self.n_delta_fallbacks += 1
            if self.notes_mode == "rules":            # nothing to fall back to: the rules of this cut are one cut behind
                self.n_notes_failed += 1
                rec["notes_error"] = why + "; previous notes kept"
                return
            thinking = True                           # the full rewrite keeps the books by thinking, as N32j does
        await self._notes_full(head, turns, rec, thinking)

    def _tally(self, rec: dict[str, Any], resp: Any) -> str:
        usage = getattr(resp, "usage", None)
        rec["notes_prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
        rec["notes_completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
        rec["notes_finish"] = resp.choices[0].finish_reason
        return (resp.choices[0].message.content or "").strip()

    async def _notes_delta(self, head: list[dict[str, Any]], turns: str, rec: dict[str, Any]) -> str:
        """Changes-only notes for one cut. Returns '' when the NOTES were updated, else why not."""
        delta_mode = self.notes_mode == "delta"
        req = head + [{"role": "user", "content": (NOTES_REQUEST_DELTA if delta_mode else NOTES_REQUEST_RULES).format(
            notes=self.notes or "(none yet)", turns=turns)}]
        self._snap(req, "keeper")
        why = "no reply"
        for _attempt in (1, 2):                       # a reply without the layout is asked for once more
            rec["notes_attempts"] += 1
            resp = await asyncio.to_thread(self._notes_call, req)
            if isinstance(resp, Exception):
                why = f"{type(resp).__name__}: {resp}"
                continue
            text = self._tally(rec, resp)
            if rec["notes_finish"] == "length":
                return "reply cut at the token cap"
            delta = parse_delta(text, need_changes=delta_mode)
            if delta is None:
                why = "reply without the NEW RULES layout"
                rec["notes_bad_layout"] = text[:200]
                req = req + [{"role": "assistant", "content": text},
                             {"role": "user", "content": DELTA_RETRY if delta_mode else RULES_RETRY}]
                continue
            if not delta_mode:
                delta["changes"] = []
            new, info = apply_delta(self.notes, delta, numbers_in(turns))
            if info["mismatch"]:
                return "working starts from a value the NOTES do not hold: " + "; ".join(info["mismatch"][:3])
            size = self._budget.count([{"role": "user", "content": new}])
            if size > 2 * self.notes_max_tokens:
                return f"NOTES of {size} tokens after the changes, over twice the cap"
            self.n_sums_corrected += len(info["sums_corrected"])
            was = rec.get("delta") or {}
            info = {k: (was.get(k, [] if isinstance(v, list) else 0) + v) for k, v in info.items()}   # summed over pieces
            rec.update(notes_tokens=size, rules=len(rule_lines(new)), rules_put_back=[], delta=info)
            self.notes = new
            return ""
        return why

    async def _notes_full(self, head: list[dict[str, Any]], turns: str, rec: dict[str, Any],
                          thinking: bool | None = None) -> None:
        req = head + [{"role": "user", "content": NOTES_REQUEST.format(
            cap=self.notes_max_tokens, notes=self.notes or "(none yet)", turns=turns)}]
        self._snap(req, "keeper")
        for _attempt in (1, 2):                       # an empty, failed or oversized reply is asked for once more
            rec["notes_attempts"] += 1
            resp = await asyncio.to_thread(self._notes_call, req, thinking)
            if isinstance(resp, Exception):
                rec["notes_error"] = f"{type(resp).__name__}: {resp}"
                continue
            text = from_rules(self._tally(rec, resp))
            size = self._budget.count([{"role": "user", "content": text}]) if text else 0
            if not text:
                rec["notes_error"] = "empty reply"
            elif size > 2 * self.notes_max_tokens:
                rec["notes_error"] = f"reply of {size} tokens is over twice the cap"
            elif not has_layout(text):
                rec["notes_error"] = "reply without the RULES / STATE layout"
                rec["notes_bad_layout"] = text[:200]
                req = req + [{"role": "assistant", "content": text}, {"role": "user", "content": LAYOUT_RETRY}]
            else:
                text, lost = keep_rules(self.notes, text)
                self.n_rules_put_back += len(lost)
                rec.pop("notes_error", None)
                rec.update(notes_tokens=size, rules=len(rule_lines(text)), rules_put_back=lost)
                self.notes = text
                break
        if "notes_error" in rec:                      # the cut still happens (the items are in the archive); the record
            self.n_notes_failed += 1                  # says the NOTES are one cut behind
            rec["notes_error"] += "; previous notes kept"

    def _memory_note(self) -> str:
        if self.notes_mode == "none" and not self.recall_tool:
            return MEMORY_RAG_ALL if self.retrieve_scope == "all" else MEMORY_RAG
        note = MEMORY_NOTE
        if self.auto_retrieve:
            note += MEMORY_RETRIEVAL_ALL if self.retrieve_scope == "all" else MEMORY_RETRIEVAL
        if self.notes_mode == "rules":
            note += MEMORY_RULES_ONLY
        return note

    async def run(self, instruction, environment, context) -> None:
        saved = _cb.BASELINE_SYSTEM
        if "{{finish_instructions}}" not in saved:
            raise RuntimeError("clm_keeper: BASELINE_SYSTEM changed; update the Memory section's anchor")
        _cb.BASELINE_SYSTEM = saved.replace("{{finish_instructions}}", self._memory_note() + "\n{{finish_instructions}}")
        try:
            await super().run(instruction, environment, context)
        finally:
            _cb.BASELINE_SYSTEM = saved
            try:
                (self.logs_dir / "notes_final.txt").write_text(self.notes + "\n")
                (self.logs_dir / "keeper_stats.json").write_text(json.dumps({
                    "thinking_policy": self.thinking_policy, "thinking_on_calls": self.n_thinking_on,
                    "thinking_off_calls": self.n_thinking_off, "notes_calls": self.n_notes_calls,
                    "notes_thinking": self.notes_thinking, "items_archived": self.n_items_archived,
                    "rules_put_back": self.n_rules_put_back, "rules": rule_lines(self.notes),
                    "recite_rules": self.recite_rules, "recitals": self.n_recitals,
                    "notes_failed": self.n_notes_failed, "archive_writes_failed": self.n_archive_failed,
                    "answers_put_back": self.n_answers_put_back, "repeats_refused": self.n_repeats_refused,
                    "items_not_archived_mixed_output": self.n_not_archived_mixed,
                    "notes_mode": self.notes_mode, "delta_fallbacks": self.n_delta_fallbacks,
                    "notes_chunk_tokens": self.notes_chunk_tokens, "notes_inplace": self.notes_inplace,
                    "inplace_cuts": self.n_inplace, "inplace_failed": self.n_inplace_failed,
                    "inplace_redone_with_thinking": self.n_inplace_redone,
                    "inplace_failures": self.inplace_failures[:20], "inplace_prompt_tokens": self.inplace_prompt,
                    "inplace_cached_tokens": self.inplace_cached, "inplace_turn_tokens": self.inplace_turn_tokens,
                    "sums_corrected": self.n_sums_corrected, "auto_retrieve": self.auto_retrieve,
                    "retrievals": self.n_retrievals, "retrieved_chars": self.retrieved_chars,
                    "retrievals_skipped": self.n_retrievals_skipped, "retrieve_window": self.retrieve_window,
                    "retrieve_scope": self.retrieve_scope,
                    "passages_indexed": len(self._index.docs), "recall_tool": self.recall_tool,
                    "notes_max_tokens": self.notes_max_tokens, "target_ratio": self.target_ratio,
                    "largest_delivery_tokens": self._largest_delivery, "keep_headroom": self.keep_headroom}, indent=1) + "\n")
            except Exception:
                pass
