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
  sentences that match (as `item N: ...`; with `--before N` only those up to item N, the nearest ones when there
  are many); `recall --item N` prints item N. Use it whenever a question is about
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
- Every item is kept in a store from the moment it arrives. The store is not in your sandbox: no file holds it. Whenever an item asks questions, the harness searches
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
section; may be empty). Do not list what has been received or answers already given, and do not repeat \
values here: they are in STATE.

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
something is removed. Go through the turns from the first to the last and leave no change out: every sentence \
that names a thing of STATE is either a change (a line of its own, or one step in the working of a line) or, if \
it changes nothing, a line `name: (no change)`. If the turns change nothing, write (none).
OPEN
at most three short lines: what is unfinished right now and what to watch for (this replaces the old OPEN \
section; may be empty). Do not list what has been received or answers already given, and do not repeat \
values here: they are in STATE.

Output only these three sections.
"""
PIN_TAIL = ("[[Everything received so far is in the NOTES above or in the archive. The last output moved out began: "
            "{last!r}. It is already counted in the NOTES. Continue the task from there.]]")
DELTA_RETRY = ("Your reply did not use the layout. Reply with the sections only: first line NEW RULES, then the new "
               "rules or (none), then a line CHANGES, then one `name: value` line per change or (none), then a line OPEN.")
RULES_RETRY = ("Your reply did not use the layout. Reply with the sections only: first line NEW RULES, then the new "
               "rules or (none), then a line OPEN.")
DELTA_HEADS = ("NEW RULES", "CHANGES", "OPEN")
# the last part of working: `= 169`, `= 169 (item 4)`, `= 169. (item 4) (set)`; not `= 169 (item 4). Then set to 5 (item 6)`
RESULT = re.compile(r"\s*(-?\d{1,24})\.?(?:\s*\((?:[^()]|\([^()]*\))*\))*\s*\.?\s*$")


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                     "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}


def numbers_in(text: str, signed: bool = False) -> set[int]:
    """Every whole number the text states, in digits or in English words ("four hundred and two", "forty-nine").
    Default: each with both signs (for "lost forty-nine" the sign is in the verb). With `signed`, as stated: negative
    only after "minus" / "negative" or a leading "-" ("at -106", "minus ninety-seven"); that is what a value SET by
    the text has to match. Digits inside a name (`abcd62`) and the numbers of an `ITEM 132/147 (UPDATE)` heading
    are not numbers the text states, and number words do not run on across punctuation ("one hundred. Two birds")."""
    text = re.sub(r"ITEM \d+/\d+ \(\w+\)", " ", text).replace("\u2212", "-")
    out: set[int] = set()
    total = part = 0
    open_ = neg = False

    def emit(n: int, minus: bool) -> None:
        out.update((-n,) if signed and minus else (n,) if signed else (n, -n))

    def close() -> None:
        nonlocal total, part, open_, neg
        if open_:
            emit(total + part, neg)
        total, part, open_, neg = 0, 0, False, False

    minus_next = False
    for tok in re.findall(r"[a-z_]+\d\w*|[a-z]+|(?<![\w)])-(?=\d)|\d[\d,]*|[.!?;:,]", text.lower()):
        if tok in ("minus", "negative", "-"):
            close()
            minus_next = True
            continue
        if tok[0].isalpha() and tok[-1].isdigit() or "_" in tok:
            close()                                  # a name such as abcd62
        elif tok[0].isdigit():
            close()
            emit(int(tok.replace(",", "") or 0), minus_next)
        elif tok in _UNITS or tok in _TENS:
            if not open_:
                neg = minus_next
            part, open_ = part + (_UNITS[tok] if tok in _UNITS else _TENS[tok]), True
        elif tok == "hundred" and open_:
            part *= 100
        elif tok == "thousand" and open_:
            total, part = total + part * 1000, 0
        elif tok == "and" and open_:
            continue
        else:
            close()
        minus_next = False
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
    """The whole number a STATE value holds now: the last number in it once bracketed remarks are set aside
    (`75 (60, gained 15 in item 606)` -> 75, `-107 -> -31` -> -31, `opened at 402` -> 402,
    `-58 - 35 = -93, then set to 82 (item 48)` -> 82); None for `removed ...` and for a value without a whole number.
    (A model that thinks writes such lines; reading the first number instead sent correct replies to the fallback.)"""
    v = re.sub(r"\([^()]*\)", " ", value).replace("\u2212", "-").strip()
    v = re.split(r"\u2192|->|=>", v)[-1].strip()         # `286 -> removed`: what it is now comes last
    if re.match(r"(removed|closed|struck|deleted|gone)\b", v.lower()):
        return None
    nums = re.findall(r"(?<![\w.])-?\d[\d,]*(?![\d.]*\d)", v)
    return int(nums[-1].replace(",", "")) if nums and len(nums[-1]) <= 24 else None


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
    if len(expr) > 400 or re.search(r"\d{16,}", expr):
        return None                                  # not a sum anyone wrote: no huge numbers, no endless rows of signs
    try:
        out = ev(ast.parse(expr.strip(), mode="eval").body)
        return out if abs(out) < 10**18 else None
    except (ValueError, SyntaxError, ZeroDivisionError, RecursionError, OverflowError, MemoryError):
        return None


def _whole(val: float | None) -> int | None:
    """The whole number a computed value is, if it is one."""
    try:
        return int(val) if val is not None and abs(val) < 10**18 and float(val).is_integer() else None
    except (OverflowError, ValueError):
        return None


def work_out(value: str) -> tuple[int | None, int | None, int] | None:
    """(start, result, stated result) of a value written as working that ends in `= number`, such as
    `120 + 49 - 3 = 166`, `40 x 2 = 80` or `90 - 90/3 = 60`; None when the value is not working. `start` is the
    number the working begins with (None if it begins with something else). `result` is computed when the working
    is plain arithmetic; it is None when plain arithmetic has no whole-number value (`7 / 2`, `7 / 0`): such a line
    cannot be right. Working in words (`119 + what efgh34 holds (402) = 521`) cannot be checked: `result` is then
    the stated result."""
    if re.search(r"\d{25,}", value):
        return None                                  # not a number anyone holds
    v = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", value.strip())
    v = v.replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
    if re.fullmatch(r"(-?\d+)\s*(?:\u2192|->|=>)\s*(-?\d+)\.?", v):
        return None                                  # `-107 -> -31` is an assignment of -31, checked as one; not working
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
        total = _whole(val)
        if total != stated and _ltr(expr) == stated:
            total = stated                           # `10 + 5 * 2 = 30`: taken from left to right, as the line means it
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


PARTS = re.compile(r",(?!\d{3}\b)|;|(?i:\bthen\b)")   # what separates the changes packed onto one line (also `. Then`)
REMARK = re.compile(r"\([^()]*(?:[A-Za-z]|\u2192|->|=>)[^()]*\)")      # `(item 451)`, `(382 -> -55)`; not `(5)` in working
# a remark that only says where the change is from; anything else in brackets may be part of what happened
REFERENCE = re.compile(r"\(\s*items?\s+\d+(?:\s*(?:,|&|-|\u2013|and|to)\s*(?:items?\s+)?\d+)*\s*\)", re.I)
# the words a part may use to say "the value is now N"; anything else with a number in it is not read as a set
MARK = "\x00"                                        # stands where a remark was taken out of a line (see chain_of)


def unremarked(value: str, mark: str = " ") -> str:
    """A CHANGES value without its remarks in brackets. `mark` is put where a remark stood that says more than
    where the change is from (`(then doubled)`, `(five more)`; not `(item 451)`): such a remark may hold part of
    the change. `(5 x 2)` inside working is a sum, not a remark: the `x` between two numbers is made a times sign
    first (as a remark it vanished, and `10 + (5 x 2) + 1 = 21` was read as 10 + 1)."""
    v = re.sub(r"(?<=[\d)])\s*[x\u00d7]\s*(?=[\d(-])", " * ", value)
    return REMARK.sub(lambda m: " " if REFERENCE.fullmatch(m.group(0)) else mark, v)


def _ltr(expr: str) -> float | None:
    """A sum without brackets taken strictly from left to right (`10 + 5 * 2` is 30): how changes written one after
    another are meant ("gained 5, then was doubled"). None for anything else."""
    text = expr.replace(" ", "")
    toks = re.findall(r"\d+(?:\.\d+)?|[-+*/]", text)
    if not toks or "".join(toks) != text or re.search(r"[\d.]\s+[\d.]", expr) or len(text) > 400:
        return None
    i = 0

    def num() -> float:
        nonlocal i
        sign = 1
        while i < len(toks) and toks[i] in ("+", "-"):
            sign, i = (-sign if toks[i] == "-" else sign), i + 1
        if i >= len(toks) or toks[i] in ("*", "/"):
            raise ValueError(text)
        i += 1
        return sign * float(toks[i - 1])

    try:
        acc = num()
        while i < len(toks):
            op, i = toks[i], i + 1
            y = num()
            acc = acc + y if op == "+" else acc - y if op == "-" else acc * y if op == "*" else acc / y
        return acc
    except (ValueError, ZeroDivisionError):
        return None


def two_readings(expr: str) -> bool:
    """`10 + 5 * 2` without brackets has two values: 20 by the rules of arithmetic, 30 taken from left to right."""
    x, y = _calc(expr), _ltr(expr)
    return x is not None and y is not None and x != y


SET_WORDS = frozenset("opened reopened re set reset recorded now stands starts started start at to as is was back again new page value".split())


def steps_in(value: str) -> int:
    """How many changes one CHANGES line writes. A model packs several onto a line in its own ways:
    `578 + 62 = 640, then set to 174`, `opened at 117, set to -190, +46 = -144`, `539 - 31 = 508 - 48 = 460, then
    removed`, `468 - 19 = 449, set to 473 (item 449); +31 = 504 (item 450)`, `112 + 16 + 45 = 173`. Each part between
    commas, semicolons and "then" that holds a number or a removal is a change; a part with working counts once per
    operation. Remarks in parentheses are not read. (Counting a line as one change made the count check ask again on
    a third of the notes calls at 1M, harness and proxy alike; 14 of 25 such questions in the proxy run were this.)"""
    n = 0
    for part in PARTS.split(unremarked(value)):
        part = part.strip()
        if not (re.search(r"\d", part) or re.match(r"(removed|closed|struck|deleted|gone)\b", part.lower())):
            continue
        ops = len(re.findall(r"(?<=[\d)])\s*[-+*/x\u00d7\u2212]\s*(?=[\d(-])", part))
        # `+5 = 132`: the line goes on from the value before (one change); `-10 + 5 = -5` starts from minus ten
        lead = 1 if "=" in part and re.fullmatch(r"[-+\u2212]\s*\d+", part.split("=")[0].strip()) else 0
        n += max(ops + lead, 1)
    return max(n, 1)


LOOSE = "\x00said without a number"                  # a key of the `near` table (see numbers_near): the names that some
                                                     # sentence of the turns mentions without stating any number


def implied_ok(old: int, new: int, amounts: set[int], relative: bool) -> bool:
    """`520 -> 1040` written without working: can the turns have said that change without stating the new number?
    Only when some sentence mentions the thing without any number (`relative`), and then if the change is times or
    divided by a small whole number ("was doubled"), a whole fraction of the old value ("a third written off"),
    or by an amount in `amounts`: what the turns state for the thing or what another thing of these turns holds
    ("received exactly what sajaro19 stood at"). Then the line is as good as its working. On the stream with such
    changes (hard, seed 1, 2026-10-12) most questions were about lines like this, and after the second reply
    seven of them, right ones among them, were left out. Without the condition a value written again passed as a
    change: `10 -> 20` then `10` as "halved"; `15 + 5 = 20` then `15` as "less the stated 5"."""
    if not relative:
        return False
    d = abs(new - old)
    return d in {abs(a) for a in amounts} or any(new == old * k or old == new * k or d * k == abs(old) for k in range(2, 11))


def amounts_ok(working: str, amounts: set[int] | None, start: int | None = None) -> bool:
    """Every number in this stretch of working (what is added to or taken from the value it starts from) is one the
    turns state for the thing, whatever its sign there; the caller adds every value a thing of STATE holds or held
    while the reply was applied ("went up by as much as bamo35 held at that moment"), and times or divided by a
    small whole number passes ("was doubled"), as does a whole fraction of `start`, the value the working begins
    with (`849 - 283 = 566` for "a third written off"). Working that is right as arithmetic can still be made up:
    X32m at 1M read "recorded katu85 at five hundred and twenty-three" as 623 and wrote `650 - 27 = 623`, which
    starts from the value held and adds up; 27 is nowhere in the turns."""
    if amounts is None:
        return True
    have = {abs(a) for a in amounts}
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", working).replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
    text = re.sub(r"(?:(?<=[\d)])|^)\s*x\s*(?=[\d(-])", " * ", text)
    text = re.sub(r"(?<![\w.])[A-Za-z_]\w*", " ", text)        # a name in the working (`+ 402 (bamo35)`) is not an amount
    for op, k in re.findall(r"([-+*/]?)\s*\(?\s*-?(\d{1,24})", text):
        n = int(k)
        # "was doubled", "lost a third": times or divided by a small whole number is said in words, not in figures
        if n in have or (op in ("*", "/") and 2 <= n <= 10):
            continue
        if start and n and op in ("+", "-") and abs(start) % n == 0 and 2 <= abs(start) // n <= 10:
            continue                                 # a half, a third ... a tenth of the value it starts from
        return False
    return True




def restated(value: str) -> str | None:
    """`112 + 16 + 45 = 128 + 45 = 173` is one sum written out twice, not two changes. When every piece between
    the `=` signs of a line without separators has the same value, the line is its first piece and the result
    (`112 + 16 + 45 = 173`; `90 - 90/3 = 90 - 30 = 60` is `90 - 90/3 = 60`, and the 30 is no amount to look for in
    the turns). None for anything else, such as `539 - 31 = 508 - 48 = 460`, which is two changes."""
    flat = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", unremarked(value)).replace("\u2212", "-").replace("\u00f7", "/")
    if flat.count("=") < 2 or re.search(PARTS.pattern + r"|\u2192|->|=>|\d{25,}", flat):
        return None
    pieces = [x.strip().rstrip(".").strip() for x in flat.split("=")]
    vals = [_whole(_calc(x)) if re.fullmatch(r"[\d\s+\-*/().]+", x) else None for x in pieces]
    if not re.fullmatch(r"-?\d+", pieces[-1]) or vals[0] is None or any(v != vals[0] for v in vals):
        return None
    return f"{pieces[0]} = {pieces[-1]}"


def chain_of(value: str, held: int | None, stated: set[int], amounts: set[int] | None = None,
             fixed: list[str] | None = None, relative: bool = False) -> tuple[int | None, list[int], int] | None:
    """A CHANGES line that packs several changes, followed part by part from the value the NOTES hold:
    (the value at the end, or None after a removal; the sets it took from the turns; how many of those open a part
    of working instead of standing as a part of their own). None when any part cannot be followed exactly as it is
    written; the line is then asked about (see apply_delta), never guessed at.

    Parts are separated by commas, semicolons, "then" and arrows; remarks in brackets are set aside (brackets inside
    working are part of the sum). A part is
    - a removal;
    - one number, with nothing round it but words that say "the value is now": the value so far written again, or
      a set, which the turns must state and which this line has not taken already (`opened at 117`, `set to -190`,
      the `415` of `279 -> 415`);
    - working whose every sum is right as written, read in the first of these ways that gives the written result:
      from the value so far (`292 - 67 = 225`, also `539 - 31 = 508 - 48 = 460`, which is followed when it is the
      whole line too), going on from it (`+46 = -144`, `- 75 = 287`), or from a value the turns state (a set and a
      change in one: `585 - 79 = 506`). A sum that gives the written result only when taken from left to right
      (`10 + 5 x 2 = 30`) is not followed: it may be meant that way ("gained 5, then was doubled") or miscounted
      (`100 - 40 / 2 = 30`).
    With `amounts` (see amounts_ok) every amount added or taken must be one of them.
    One wrong sum is redone, as on a plain line (and listed in `fixed`): the last sum of the line, when it starts
    from the value so far, its amounts are stated, it is plain arithmetic with one value (no remark that says
    more than `(item N)` stood in it or after its result, and its value does not depend on the order of the
    operations), and the result it writes is not a number the turns state (then the line may have run a change and a set together: asked about). X32p at 1M wrote
    `522 - 20 = 502, 502 - 17 = 485, 485 + 58 = 498`. A wrong sum anywhere else is asked about: three reviews on
    2026-10-12 found a dozen ways in which redoing it and reading on stored a wrong value without a question
    (the next part starting from the miscounted result, or repeating it; a remark that held the amount, as in
    `10 + (five more) - 1 = 14`; `10 + 2 (then doubled) = 24`)."""
    if re.search(r"\d{25,}", value):
        return None
    v = unremarked(value, f" {MARK} ")
    v = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", v).replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
    remark_at_the_end = MARK in v[max(v.rfind("="), 0):]     # also as a part of its own: `..., 12 + 2 = 28, (then doubled)`
    parts = [re.sub(r"^x\s*(?=[\d(])", "* ", x) for x in (y.strip().rstrip(".").strip() for y in re.split(PARTS.pattern + r"|\u2192|->|=>", v))
             if x.replace(MARK, "").strip()]
    if len(parts) < 2 and (not parts or parts[0].count("=") < 2):
        return None                                  # one change: apply_delta's own business
    cur, sets, opening = held, [], 0
    for k, part in enumerate(parts):
        bare = part.replace(MARK, " ").strip().rstrip(".").strip()
        if re.match(r"(removed|closed|struck|deleted|gone)\b", bare.lower()):
            cur = None
            continue
        if "=" not in part:
            nums = re.findall(r"(?<![\w.])-?\d+(?![\d.]*\d)", bare)
            words = set(re.findall(r"[a-z]+", bare.lower()))
            # (`increased by 5` is a change written without working, not a set to 5: not followed; nor is anything
            # with a sign or bracket left over, such as `reopened at - 3`, which is not a set to 3, or a bare `+5`)
            bare = re.sub(r"\*+([^*]+)\*+", r"\1", bare)             # `set to **5**`, `**set to 174**`; a lone `*5` is not a set to 5
            left = re.sub(r"[a-z]+(?:-[a-z]+)*|(?<![\w.])-?\d+", "", bare.lower()).strip(" :`")
            if len(nums) != 1 or not words <= SET_WORDS or left:
                return None
            n = int(nums[0])
            if cur is not None and n == cur:
                continue                             # the value so far, written again
            if n not in stated or n in sets:         # (a thing really set to one value twice costs a question)
                if cur is not None and amounts is not None and implied_ok(cur, n, amounts, relative):
                    cur = n                          # `520 -> 1040` for "was doubled" (see implied_ok): no set
                    continue
                return None
            sets.append(n)
            cur = n
            continue
        pieces = [x.strip() for x in part.split("=")]
        if not re.fullmatch(r"-?\d+", pieces[-1].replace(MARK, " ").strip().rstrip(".").strip()):
            return None
        for j, (raw, after) in enumerate(zip(pieces, pieces[1:])):
            expr = raw.replace(MARK, " ").strip()
            first = re.match(r"\(?\s*(-?\d+)(?![\d.])", expr)
            head = re.match(r"\(?\s*(-?\d+)(?![\d.])", after.replace(MARK, " ").strip().rstrip(".").strip())
            if not head:
                return None
            wrote, n = int(head.group(1)), (int(first.group(1)) if first else None)

            def worth(full: str, taken: str, begins: int | None) -> int | None:
                # (an operator with nothing after it, or two in a row: something that was not a number stood there)
                if (not re.fullmatch(r"[\d\s+\-*/().]+", full) or re.search(r"[-+*/]\s*(?:[+*/)]|$)|\(\s*\)", full)
                        or not amounts_ok(taken, amounts, begins)):
                    return None
                return _whole(_calc(full))

            readings = []                            # (the sum, the amounts in it, the set it starts from)
            if first and cur is not None and n == cur:
                readings.append((expr, expr[first.end():], None))
            if cur is not None and re.match(r"[-+*/]\s*\(?\d", expr):
                readings.append((f"({cur}) {expr}", expr, None))
            if first and n in stated and n not in sets:
                readings.append((expr, expr[first.end():], n))
            for full, taken, a_set in readings:
                if worth(full, taken, cur if a_set is None else a_set) == wrote:
                    if a_set is not None:
                        sets.append(a_set)
                        opening += 1
                    cur = wrote
                    break
            else:
                last = k == len(parts) - 1 and j == len(pieces) - 2
                plain = (MARK not in raw and not remark_at_the_end and re.search(r"[\d)]\s*[-+*/]\s*[\d(-]", expr)
                         and not two_readings(expr))
                val = worth(expr, expr[first.end():], cur) if last and plain and first and cur is not None and n == cur else None
                if val is None or wrote in stated or wrote in (amounts or ()):
                    return None
                cur = val
                if fixed is not None:
                    fixed.append(f"{expr} = {wrote} -> {cur}")
    return cur, sets, opening


def apply_delta(notes: str, delta: dict, seen: set[int] | None = None, strict: bool = False,
                near: dict[str, set[int]] | None = None) -> tuple[str, dict]:
    """The NOTES after the changes, and what happened: lines changed and added, sums corrected, and `mismatch`:
    working that cannot be trusted (it starts from a value the NOTES do not hold, it starts from a number although
    the NOTES say the thing was removed, or it is arithmetic without a whole-number value); the caller then falls
    back to a full rewrite. `seen` is every number the turns being moved out state (numbers_in): working may start
    from one of those instead of the NOTES value, because the turns can set a thing and then change it and the
    model writes both on one line (`abcd12: 294 + 12 = 306`). The first run of arm N32d (rules stream, seed 0) sent
    8 of 23 cuts to the full rewrite for exactly that; all eight were such lines. With `strict`, a bare number that
    the turns do not state is `mismatch` too: a worked-out value has to show its working. With `near` (see
    numbers_near) "the turns state it" means: in a sentence that names the thing, or the one after it. RULES lines are never removed; a new rule that rewords an existing one is not added.
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
    steps: dict[str, int] = {}                       # changes each name's lines account for (a line, or a step of its working)
    used: dict[str, set[int]] = {}                   # values of a name already taken from the turns as a set
    have = [_plain(r) for r in rules]
    for r in delta.get("rules", []):
        if not any(same_rule(r, h) for h in have):
            rules.append("- " + r)
            have.append(r)
            info["new_rules"] += 1
    at: list[int] = info.setdefault("mismatch_at", [])   # for each question, the index of the CHANGES line it is about
    where = {fact_of(ln)[0]: i for i, ln in enumerate(state)}
    # values that things mentioned in these turns hold, now and as the reply is applied: an amount may be one of them
    ever = {v for k, v in ((fact_of(ln)[0], number_of(fact_of(ln)[1])) for ln in state) if v is not None and near is not None and k in near}
    for index, (name, value) in enumerate(delta.get("changes", [])):
        at.extend([index - 1] * (len(info["mismatch"]) - len(at)))
        if NO_CHANGE.fullmatch(value.strip()):           # `name: (no change)`: mentioned, not changed
            steps[name] = steps.get(name, 0) + 1
            continue
        old = fact_of(state[where[name]])[1] if name in where else None
        held = number_of(old) if old is not None else None
        value = restated(value) or value                 # one sum written out twice is that sum
        if re.search(r"\d{25,}", value):                 # a number of 25 digits or more is not a value: asked about, not kept
            info["mismatch"].append(f"{name}: `{value[:60]}...` is not a value; write the line again")
            continue
        counted, asked, written = steps_in(value), len(info["mismatch"]), value
        flat = unremarked(value)
        several = sum(bool(x.strip()) for x in re.split(PARTS.pattern + r"|\u2192|->|=>", flat)) > 1 or flat.count("=") > 1
        if strict and seen is not None:
            # several changes on one line: followed part by part; a line that can be followed is right as it stands
            redone: list[str] = []
            ch = chain_of(value, held, (seen if near is None else near.get(name, set())) - used.get(name, set()),
                          None if near is None else near.get(name, set()) | ever, redone,
                          near is not None and name in near.get(LOOSE, ()))
            if ch is not None:
                final, sets, opening = ch
                info["sums_corrected"] += [f"{name}: {x}" for x in redone]
                used.setdefault(name, set()).update(sets)
                steps[name] = steps.get(name, 0) + counted + opening
                info["chained"] = info.get("chained", 0) + 1
                line = f"{name}: {final}" if final is not None else f"{name}: removed"
                ever.update(sets if final is None else sets + [final])
                if name in where:
                    state[where[name]] = line
                    info["changed"] += 1
                else:
                    where[name] = len(state)
                    state.append(line)
                    info["added"] += 1
                continue
        w = work_out(value)
        if w:
            start, total, stated = w
            # the steps the line writes, plus the set it starts from when the line opens with working from a value
            # that is not the one the NOTES hold (`585 - 79 = 506` after "opened at 585", "went down by 79")
            if start is not None and start != held and re.match(r"\s*[-\u2212]?\d+\s*[-+*/x\u00d7\u2212]", value):
                counted += 1
        steps[name] = steps.get(name, 0) + counted
        if w:
            if total is None:
                info["mismatch"].append(f"{name}: `{value}` has no whole-number value")
                total = stated
            elif start is not None and start == held:
                pass
            elif (start is not None and seen is not None and start in (seen if near is None else near.get(name, set()))
                  and start not in used.get(name, ())):
                # the turns set this value and the line starts from it; a set is good for one start
                info["set_in_turns"] = info.get("set_in_turns", 0) + 1
                used.setdefault(name, set()).add(start)
            elif start is not None and held is not None and total == held:
                # The line ends at the value the NOTES already hold, from another start: a change that was noted
                # before and is written again (with in-place notes through the proxy the newest exchange stays in
                # view, and its thought about the item just noted is read again at the next call: 6 such lines at
                # 1M, each one a reply asked for again). Applying it or not gives the same value; it is no change.
                info["renoted"] = info.get("renoted", 0) + 1
                steps[name] -= counted
                if not steps[name]:
                    del steps[name]
                continue
            elif start is not None and held is not None and held != start:
                info["mismatch"].append(f"{name}: working starts from {start}, NOTES hold {held}")
            elif start is not None and old is not None and re.match(r"(removed|closed|struck|deleted|gone)\b", old.lower()):
                info["mismatch"].append(f"{name}: working starts from {start}, NOTES say {old.split()[0]}")
            bare_text = unremarked(value)           # a remark may hold an arrow or a comma: it is not the line
            plain = sum(bool(x.strip()) for x in PARTS.split(bare_text)) == 1 and not re.search(r"\u2192|->|=>", bare_text)
            # (a line of several parts that could not be followed is judged by its result only: its last piece of
            # working is not the whole line, and X32p at 1M was asked about `517 -> 164, then 164 + 76 + 85 = 325,
            # then 325 + 18 = 343` for an "amount" of 325)
            # (Not excused: working whose result the turns state for the thing. `436 + 78 = 514` for "recorded at
            # 514" costs a question, but "gained five" also states a 5, and `100 - 95 = 5` must not pass.)
            if near is not None and strict and start is not None and len(info["mismatch"]) == asked and plain:
                expr = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", flat).replace("\u2212", "-").split("=")[-2]
                first = re.match(r"\(?\s*-?\d+", expr.strip())
                if first and not amounts_ok(expr.strip()[first.end():], near.get(name, set()) | ever, start):
                    info["mismatch"].append(f"{name}: `{value}` adds or takes an amount the turns do not state for it; read the item again")
            sum_text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", flat).replace("\u2212", "-").replace("\u00f7", "/").split("=")[-2]
            by_rule = _calc(sum_text)
            if strict and near is not None and len(info["mismatch"]) == asked:
                if two_readings(sum_text) and by_rule != stated:
                    # what the sum comes to depends on the order of the operations and the line does not write the
                    # value arithmetic gives: meant from left to right (`10 + 5 x 2 = 30` for "gained 5, then was
                    # doubled"; stored as written) or miscounted (`100 - 40 / 2 = 30`)
                    info["mismatch"].append(f"{name}: `{value}` is {by_rule:g} by the rules of arithmetic, not {stated}; write each change on a line of its own, with its working")
                elif total != stated and (stated in near.get(name, set()) or MARK in unremarked(value, MARK)):
                    # the sum is wrong, and the result it writes is a number the turns state for the thing (the line
                    # may have run a change and a set together: `10 + 5 = 16` for "gained 5", "set to 16"), or a
                    # remark holds part of what happened (`10 + 2 = 24 (then doubled)`)
                    info["mismatch"].append(f"{name}: `{value}` comes to {total}, not {stated}; write each change on a line of its own, with its working")
            if total != stated:
                info["sums_corrected"].append(f"{name}: {value} -> {total}")
            value = str(total)
        elif seen is not None and strict and re.search(r"[\d_]", name) and " " not in name:
            # a new number without working must be one the turns state for this thing (a set), whatever is written
            # round it (`402`, `opened at 402`, `402 (item 7)`, `-107 -> 402`); anything worked out must show its
            # working, so that the sum can be checked (N32w seed 0: `rumi16: -132` for 29 - 73, without working)
            old = fact_of(state[where[name]])[1] if name in where else None
            held, now = (number_of(old) if old is not None else None), number_of(value)
            stated = seen if near is None else near.get(name, set())
            if now is not None and now != held:
                if (now not in stated and near is not None and held is not None
                        and implied_ok(held, now, stated | ever, name in near.get(LOOSE, ()))):
                    info["implied"] = info.get("implied", 0) + 1     # `520 -> 1040`: a change the turns can have said so
                elif now not in stated:
                    info["mismatch"].append(f"{name}: {now} is not a value the turns state; write the working"
                                            + (f" from the value the NOTES hold, {held}" if held is not None else ""))
                else:
                    used.setdefault(name, set()).add(now)
        if several and strict and near is not None and len(info["mismatch"]) == asked:
            # several parts, and they could not be followed one by one: nothing has checked this line (`100, then
            # 100 + 999 = 1099` would otherwise pass because its amounts are looked at only on a plain line)
            info["mismatch"].append(f"{name}: `{written}` could not be followed part by part; write each change on a line of its own, with its working")
        line = f"{name}: {value}" if value else name
        if number_of(value) is not None:
            ever.add(number_of(value))
        if name in where:
            state[where[name]] = line
            info["changed"] += 1
        else:
            where[name] = len(state)
            state.append(line)
            info["added"] += 1
    at.extend([len(delta.get("changes", [])) - 1] * (len(info["mismatch"]) - len(at)))
    if delta.get("open") is not None:
        opened = list(delta["open"])
    info["steps"] = steps
    return "\n".join(["RULES"] + (rules or ["(none)"]) + ["STATE"] + state + ["OPEN"] + opened), info


def respell(delta: dict, mentions: dict[str, int], known: list[str] | tuple = ()) -> tuple[dict, dict[str, str]]:
    """A line for an identifier-like name that the turns never mention, a letter or two from a name they do mention
    and for which the reply has no line, is that name misspelled: the line is given to it. Returns the reply and
    {written: meant}. (X32n2 at 1M wrote `vozi36` for `vozimi36`; the line was left out as unsupported, the count
    question about vozimi36 got an 8,192-token reply that could not be used, and the change was lost.)
    `mentions`: how often the turns mention each identifier-like name (mention_counts). A name the NOTES hold
    (`known`) is never taken for a misspelling: `bako35` and `bamo35` can both be real."""
    import difflib
    names = list(dict.fromkeys(k for k, _ in delta["changes"]))
    free = [m for m in mentions if m not in names]
    fixed: dict[str, str] = {}
    for n in names:
        if n in mentions or n in known or len(n) < 3 or not re.search(r"[\d_]", n) or " " in n:
            continue
        tail = re.search(r"\d*$", n).group(0)
        close = [m for m in free if re.search(r"\d*$", m).group(0) == tail
                 and difflib.SequenceMatcher(None, n, m).ratio() >= 0.75]
        if len(close) == 1:
            fixed[n] = close[0]
            free.remove(close[0])
    if not fixed:
        return delta, {}
    return dict(delta, changes=[(fixed.get(k, k), v) for k, v in delta["changes"]]), fixed


DROPPABLE = ("is not a value the turns state", "adds or takes an amount the turns do not state")


def without_doubtful(notes: str, delta: dict, seen: set[int] | None, strict: bool, near: dict | None) -> tuple[dict, list[str]]:
    """The reply without the lines that are still questioned because the turns do not state their number:
    - a bare value, or `old -> new`, whose value the turns do not state for the thing (`abcd01: 999`);
    - plain working with an amount the turns do not state, unless its result is a number they do state for the
      thing (then it may be a set written as made-up working, `436 + 78 = 514` for "recorded at 514": it is kept
      as a doubtful line, not thrown away).
    After a second reply such a line was wrong or pointless every time it was looked at (campaign 12), so it is left
    out and the old value stays. Each question is bound to the line that raised it (apply_delta's `mismatch_at`);
    a later line of the same name that starts from the result of a left-out line goes with it. A line of several
    parts is never left out: that the checker cannot follow it says nothing about the turns. Returns the reply
    and the lines left out."""
    def bare(value: str) -> bool:
        v = unremarked(value).replace("\u2212", "-").strip()
        if re.fullmatch(r"-?\d+\s*(?:\u2192|->|=>)\s*[a-z ]*?-?\d+\.?", v):
            return True                              # `100 -> 999`: one value, with the old one before it
        return "=" not in v and not re.search(r"\u2192|->|=>", v) and sum(bool(x.strip()) for x in PARTS.split(v)) == 1

    def result(value: str) -> int | None:
        w = work_out(value)
        return w[1] if w and w[1] is not None else number_of(value)

    def judged(changes: list) -> list[tuple[str, int]]:
        info = apply_delta(notes, dict(delta, changes=changes), seen, strict=strict, near=near)[1]
        return list(zip(info["mismatch"], info["mismatch_at"]))

    changes, dropped = list(delta["changes"]), []
    for _ in range(len(changes) + 1):
        pick = None
        for m, i in judged(changes):
            name, v = changes[i]
            stated = near.get(name, set()) if near is not None else set()
            if (DROPPABLE[0] in m and bare(v)) or (DROPPABLE[1] in m and result(v) not in stated):
                pick = i
                break
        if pick is None:
            break
        while pick is not None:                      # the line, then any line of that name that builds on it
            name, v = changes[pick]
            dropped.append(f"{name}: {v}")
            changes = changes[:pick] + changes[pick + 1:]
            end = result(v)
            pick = next((i for m, i in judged(changes) if i >= pick and changes[i][0] == name and end is not None
                         and f"working starts from {end}," in m), None)
    return dict(delta, changes=changes), dropped


def merge_replies(first: dict | None, second: dict) -> dict:
    """What to apply when a reply was asked for again: the second reply's lines for every name it mentions (also
    `name: (no change)`, which withdraws the first reply's lines for that name), and the first reply's lines for
    the names the second does not mention; rules from both; the newer OPEN section if it has one.
    Why: the retry asks for "the three complete sections again", but a model sometimes answers with only the lines
    that were in question, or with (none). The proxy's second 240K run (campaign 11, X32i seed 1) applied such a
    reply on its own and lost every change of nine items: 15 counters wrong in the NOTES, 6 answers."""
    if not first:
        return second
    named = {k for k, _ in second["changes"]}
    rules = list(first["rules"]) + [r for r in second["rules"] if not any(same_rule(r, x) for x in first["rules"])]
    return {"rules": rules, "changes": [(k, v) for k, v in first["changes"] if k not in named] + list(second["changes"]),
            "open": second["open"] if second.get("open") is not None else first.get("open")}


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


# `name: (no change)`, also with a remark after it: `(no change - the mention is the rule itself)`. A run with six items
# per notes call stored such a remark as the value of a counter and lost its number (2026-10-12, arm N32u6).
NO_CHANGE = re.compile(r"\(?\s*(no change|unchanged|not changed|no changes)\b.*", re.I | re.S)
MISMATCH_RETRY = ("Check these lines of your CHANGES against the NOTES and the turns: {lines}. Working must start from the "
                  "value the NOTES hold, or from a value the turns set; when the turns set a new value and then change "
                  "it, write the set as a line of its own first. Then reply with the three complete sections again.")
MENTION_RETRY = ("The turns mention these names, but your CHANGES have no line for them: {names}. Go through the turns "
                 "again for each of them. Then reply with the three complete sections again (NEW RULES, CHANGES, OPEN), "
                 "every change included; for a name that the turns mention without changing it, write `name: (no change)`.")


def state_keys(notes: str) -> list[str]:
    """The names of the STATE lines of the NOTES."""
    keys, sec = [], ""
    for ln in notes.splitlines():
        head = section_of(ln)
        if head:
            sec = head
        elif ln.strip() and sec == "STATE":
            keys.append(fact_of(ln)[0])
    return keys


def unaccounted(names: list[str], turns: list[dict[str, Any]], changes: list[tuple[str, str]]) -> list[str]:
    """Names (of STATE facts) that a delivered item among the turns mentions, outside a question, although CHANGES
    has no line for them. Only names that look like identifiers (a digit or an underscore in them) are checked: a
    plain word can turn up anywhere. A notes call that thinks still missed a removal on seed 1 of the rules stream
    (`xasa62 was removed from the ledger`, the only mention of that counter in ten items); this catches that kind."""
    told = {k for k, _ in changes}
    names = [n for n in dict.fromkeys(names) if n not in told and len(n) >= 3 and re.search(r"[\d_]", n) and " " not in n]
    if not names:
        return []
    text = []
    for m in turns:
        body = str(m.get("content") or "") if m.get("role") == "tool" else ""
        if ITEMS.search(body):
            text += [s for s in re.split(r"(?<=[.!?])\s+", " ".join(body.split("\n\n(exit_code=")[0].split())) if not s.endswith("?")]
    low = " ".join(text).lower()
    return [n for n in names if re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", low)]


COUNT_RETRY = ("The turns mention these names more often than your CHANGES account for: {names}. Go through the turns again "
               "for each of them, one mention at a time. Then reply with the three complete sections again, every change "
               "included: a change is a line of its own or one step in the working of a line. For a mention that changes "
               "nothing, write `name: (no change)`.")


def identifiers_in(turns: list[dict[str, Any]]) -> list[str]:
    """Identifier-like words (letters then digits: abcd12, build_7) in the delivered items of the turns, outside
    questions: things a reply may have left out altogether, such as a counter opened in these turns that neither
    the NOTES nor the reply's CHANGES name."""
    seen: dict[str, None] = {}
    for m in turns:
        body = str(m.get("content") or "") if m.get("role") == "tool" else ""
        if ITEMS.search(body):
            for sent in re.split(r"(?<=[.!?])\s+", " ".join(ITEMS.sub("", body.split("\n\n(exit_code=")[0]).split())):
                if not sent.endswith("?"):
                    for w in re.findall(r"(?<![\w])[a-z]{2,}_?\d+[a-z0-9_]*(?![\w])", sent.lower()):
                        seen.setdefault(w)
    return list(seen)


def mention_counts(names: list[str], turns: list[dict[str, Any]]) -> dict[str, int]:
    """How often each name (identifier-like only, as in `unaccounted`) is mentioned in the delivered items of the
    turns, outside questions."""
    names = [n for n in dict.fromkeys(names) if len(n) >= 3 and re.search(r"[\d_]", n) and " " not in n]
    text = []
    for m in turns:
        body = str(m.get("content") or "") if m.get("role") == "tool" else ""
        if ITEMS.search(body):
            text += [s for s in re.split(r"(?<=[.!?])\s+", " ".join(body.split("\n\n(exit_code=")[0].split())) if not s.endswith("?")]
    low = " ".join(text).lower()
    out = {n: len(re.findall(rf"(?<![\w]){re.escape(n)}(?![\w])", low)) for n in names}
    return {n: c for n, c in out.items() if c}


def numbers_near(names: list[str], turns: list[dict[str, Any]], signed: bool = True) -> dict[str, set[int]]:
    """For each name (identifier-like only): the numbers stated in a sentence of a delivered item that mentions it, or
    in the sentence right after one ("Next on the list was abcd12. It was opened at 591."), with the sign as stated
    (see numbers_in). A value that the model writes without working has to be one of these: N32v seed 1 wrote `zija81: -62` for 134 - 16 and the looser test
    (the number occurs somewhere in the turns) let it pass."""
    want = {n for n in names if len(n) >= 3 and re.search(r"[\d_]", n) and " " not in n}
    out: dict[str, set[int]] = {}
    for m in turns:
        body = str(m.get("content") or "") if m.get("role") == "tool" else ""
        if not ITEMS.search(body):
            continue
        sents = re.split(r"(?<=[.!?])\s+", " ".join(body.split("\n\n(exit_code=")[0].split()))
        for i, sent in enumerate(sents):
            here = want & set(re.findall(r"[a-z0-9_]+", sent.lower()))
            if here:
                own = numbers_in(sent, signed)
                nums = own | (numbers_in(sents[i + 1], signed) if i + 1 < len(sents) else set())
                for n in here:
                    out.setdefault(n, set()).update(nums)
                if not own:                          # "abcd12 was doubled.": a change can be said without a number
                    out.setdefault(LOOSE, set()).update(here)
    return out


OPEN_QUESTION = "[[The question you are answering, kept in view by the harness while you work on it]]"
ASKED = re.compile(r"(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)")


def open_question(body: list[dict[str, Any]]) -> int | None:
    """The index in `body` of the newest delivered item that asks questions and has not been followed by an
    ordinary delivery (the model has not moved on), or None. N32n at 1M, second stream: while the model was fetching
    archived items for the last question item, the ordinary cut moved that item itself out of view; the model then
    saw no question, ran `next`, and seven answers were never written."""
    for i in range(len(body) - 1, -1, -1):
        m = body[i]
        if m.get("role") == "assistant":
            continue
        text = str(m.get("content") or "")
        delivered = (m.get("role") == "tool" and bool(ITEMS.search(text))) or text.startswith(OPEN_QUESTION)
        if delivered and ASKED.search(text):
            return i                                 # not `recall --item N` printing an archived question item
        if delivered:
            return None                              # a later item was delivered: the question is behind us
    return None


def kept_question(body: list[dict[str, Any]], n_gone: int) -> list[dict[str, Any]]:
    """What a cut of the first `n_gone` messages of `body` keeps in view: the open question as one message of the
    harness's, if the cut would take it; else nothing."""
    asked = open_question(body)
    if asked is None or asked >= n_gone:
        return []
    text = str(body[asked].get("content") or "")
    return [{"role": "user", "content": text if text.startswith(OPEN_QUESTION) else OPEN_QUESTION + "\n" + text}]


def answered_copy(body: list[dict[str, Any]]) -> bool:
    """True when `body` starts with a kept copy of a question that is no longer the open one."""
    return bool(body) and str(body[0].get("content") or "").startswith(OPEN_QUESTION) and open_question(body) != 0


def under_accounted(mentions: dict[str, int], steps: dict[str, int]) -> list[str]:
    """`name (mentioned 3 times, 2 changes written)` for every name whose lines account for fewer changes than the
    items mention it. N32z seed 0: three counters went wrong in the NOTES although each had a line (the second of two
    changes in one item was left out twice); a check for names without any line cannot see that."""
    return [f"{n} (mentioned {c} times, {steps.get(n, 0)} changes written)" for n, c in mentions.items() if steps.get(n, 0) < c]


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
        text = str(m.get("content") or "")
        if m.get("role") == "user" and text.startswith(OPEN_QUESTION):
            return True                              # the question, kept in view by the ordinary cut, is still open
        text = text if m.get("role") == "tool" else ""
        if ITEMS.search(text):
            return bool(ASKS.search(text) or QUESTION.search(text))
    return False


ANSWERS = "/app/answers.json"
REPEAT_NOTE = ("NOT RUN: this is exactly the command you just ran, and nothing has changed since, so its result would be "
               "the same. Use the result you already have and decide the next step.")


REPEAT_STOP = ("NOT RUN: you have now sent this same command {n} times in a row. It will not be run again, and sending it "
               "again changes nothing. Stop looking for this. If a question is open, answer it now with what you have "
               "(write \"\" for anything you cannot work out), then continue the task.")


def repeat_note(streak: int) -> str:
    """What a refused repeat is told: the plain note for the first two in a row, then the stop note with the count.
    (Hard stream, 2026-10-12: one refused command was sent 362 times in a row; the plain note did not break it.)"""
    return REPEAT_NOTE if streak < 3 else REPEAT_STOP.format(n=streak)


def loop_temperature(streak: int) -> float | None:
    """Sampling temperature for the call after `streak` refused repeats in a row: None (the run's own setting) for
    fewer than three, then 0.5 rising to 1.0. With greedy decoding the same context plus the same refusal gives the
    same command again, for ever; one sampled call is enough to leave the loop."""
    return None if streak < 3 else min(1.0, 0.5 + 0.1 * (streak - 3))


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
        fetch = bool(a._guard_cmd.search(cmd))
        if fetch:
            a._searches = {}
        # A search sent for the third time since the last item arrived is a repeat too, even with other commands in
        # between: the archive has not changed. (Hard stream: the agent circled between three searches for ten
        # minutes; a guard that looks only at the command just before never fired twice in a row.)
        circling = a.repeat_guard and cmd.startswith("recall") and a._searches.get(cmd, 0) >= 2
        if cmd.startswith("recall") and not circling:
            a._searches[cmd] = a._searches.get(cmd, 0) + 1
        if circling:
            a._repeat_streak = max(a._repeat_streak, 2)
        if circling or (a.repeat_guard and is_repeat(cmd, a._last_cmd, fetch)):
            a.n_repeats_refused += 1
            a._repeat_streak += 1
            a.longest_repeat_streak = max(a.longest_repeat_streak, a._repeat_streak)
            note = repeat_note(a._repeat_streak)
            res = types.SimpleNamespace(stdout=note, stderr="", return_code=75)
            return StepResult(result=res, ctx_changed=False, stdout_block=note + "\n\n(exit_code=75)",
                              readout="", notes="", exec_time=0.0, touched_ctx=False)
        a._last_cmd, a._repeat_streak = cmd, 0        # a command that runs ends the streak (circling is caught by _searches)
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
                 archive_files: Any = True, mention_check: Any = False, **kwargs: Any) -> None:
        kwargs.setdefault("truncate_target_ratio", 0.6)   # cut deeper than W32 (0.75): fewer cuts, fewer notes calls
        super().__init__(*args, **kwargs)
        # A delivered item is never cut on arrival (the budget's newest-output cap head/tail-truncates whatever does
        # not fit, which is how W32 loses text near its limit); instead the cut is made early enough to leave room
        # for the largest delivery seen plus keep_headroom, and the archive is written from what `next` printed.
        self.keep_headroom, self._largest_delivery, self._delivered = int(keep_headroom), 0, {}
        self._mixed: dict[int, str] = {}              # items delivered by a command that printed something else too
        self.repeat_guard, self._last_cmd, self.n_repeats_refused = _cb._as_bool(repeat_guard), "", 0
        self._repeat_streak = self.longest_repeat_streak = self.n_sampled_calls = 0
        self._searches: dict[str, int] = {}           # each search command sent since the last item arrived
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
        self.n_questions_kept = 0                     # ordinary cuts that would have moved an open question out of view
        # mention_check (in-place notes): a STATE name that the items being moved out mention, outside a question,
        # without a line in CHANGES is asked about once (see unaccounted)
        # mention_check=count: the name's lines must account for as many changes as the items mention it
        mc = str(mention_check).strip().lower()
        # mention_check=near: the count check, and a value written without working must be stated near its name
        self.mention_check = mc if mc in ("count", "near") else ("names" if _cb._as_bool(mention_check) else "")
        self.n_mention_reasks = 0
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
        # archive_files=false (arm R32b): the cut items are kept by the harness only, not as files in the sandbox. In
        # the first retrieval-only runs the model found /tmp/.live_ctx/archive on its own (the task statement names
        # /tmp/.live_ctx) and answered the final list with scripts over those files, so they were not retrieval-only.
        self.archive_files = _cb._as_bool(archive_files)
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
        heat = loop_temperature(self._repeat_streak) if self.repeat_guard else None
        if heat is None:
            return await super()._query_with_retry(model, messages)
        saved, self.temperature = self.temperature, heat     # one sampled call to leave a loop of refused repeats
        self.n_sampled_calls += 1
        try:
            return await super()._query_with_retry(model, messages)
        finally:
            self.temperature = saved

    async def setup(self, environment: Any) -> None:
        await super().setup(environment)
        tool = ("cat > /usr/local/bin/recall <<'RECALL_EOF'\n" + RECALL_SRC.read_text() + "\nRECALL_EOF\n"
                "chmod +x /usr/local/bin/recall") if self.recall_tool else "true"
        if self.archive_files or self.recall_tool:
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
                if not self.archive_files:            # kept by the harness only
                    self._delivered.pop(num, None)
                    if self.auto_retrieve and not ASKS.search(text):
                        self._index.add(num, text)
                    n += 1
                    continue
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
        if n:
            self._searches = {}                       # the archive has grown: an earlier search may now find more
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
        start, prev = self._head(messages)
        if answered_copy(messages[start:]):            # the question it held has been answered and left behind
            del messages[start]
        before = self._budget.count(messages)
        if self.notes_inplace and await self._keep_inplace(environment, messages, before):
            return
        if before + reserve <= min(self.trigger_ratio * limit, limit - self._largest_delivery - self.keep_headroom):
            return
        start, prev = self._head(messages)
        head, body = messages[:self._protect], messages[start:]
        copy = body[:1] if body and str(body[0].get("content") or "").startswith(OPEN_QUESTION) else []
        body = body[len(copy):]                       # a kept question is carried over as it is: not a turn, not noted again
        starts = [k for k, m in enumerate(body) if m.get("role") == "assistant"]
        if starts and starts[0] > 0:
            starts.insert(0, 0)                       # leading non-assistant messages count as one turn
        target = max(min(int(self.target_ratio * limit), limit - self.keep_headroom - reserve), int(0.2 * limit))
        n, keep = 0, body
        for cut in starts[1:]:                        # never the newest turn
            carried = copy or kept_question(body, len(body) - len(keep))     # the open question stays, and counts
            if self._budget.count(head + [self._pin(prev + n)] + carried + keep) < target:
                break
            n += 1
            keep = body[cut:]
        if not n:
            return
        gone = body[:len(body) - len(keep)]
        still = copy or kept_question(body, len(gone))    # an open question never leaves the view (see open_question)
        self.n_questions_kept = getattr(self, "n_questions_kept", 0) + int(bool(still) and not copy)
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
                await self._take_notes(head, render_turns(piece), rec, piece)
        messages[:] = head + [self._pin(prev + n)] + still + keep
        rec["after"] = self._budget.count(messages)
        if still:
            rec["question_kept"] = True
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
        thinking, hinted = self.notes_thinking, not self.mention_check
        rules_seen: list[str] = []                    # a rule named in any reply of this cut is kept: a second reply
        earlier: dict | None = None                   # the reply before an asked-for one (see merge_replies)
        spelt: dict[str, str] = {}                    # misspelled names of this cut and what was meant (see respell)
        for _attempt in (1, 2, 3, 4):                 # that leaves it out must not lose it (hard stream, 2026-10-12)
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
                part = parse_delta(text, need_changes=False)     # its rules still count, if that section is complete
                if part and re.search(r"(?m)^\W*(CHANGES|OPEN)\W*$", text):
                    rules_seen += [r for r in part["rules"] if not any(same_rule(r, x) for x in rules_seen)]
            stands = (delta is None and earlier is not None
                      and (not text.strip() or rec["notes_finish"] == "length" or bool(rec.get("layout_retries"))))
            if stands:
                # asked about a reply that was in the layout, the model wrote nothing usable: the reply before it
                # stands (the proxy's rule since X32n2; a fall back to the full rewrite lost changes and cost minutes)
                rec["first_reply_stands"] = text[:120]
                delta = {"rules": [], "changes": [], "open": None}
            if delta is None:
                why = "reply without the NEW RULES layout" if rec["notes_finish"] != "length" else "reply cut at the token cap"
                rec["notes_bad_layout"] = text[:200]
                if rec.get("layout_retries"):
                    break                             # asked twice already
                rec["layout_retries"] = 1
                nothing = not text.strip() or rec["notes_finish"] == "length"
                req = req + ([] if nothing else [{"role": "assistant", "content": text}]) + [{"role": "user", "content": DELTA_RETRY}]
                if thinking and nothing:
                    thinking = False                  # the think took the whole reply: once more without it (the proxy's
                continue                              # rule too; first run on real code, campaign 13)
            rules_seen += [r for r in delta["rules"] if not any(same_rule(r, x) for x in rules_seen)]
            if self.mention_check in ("count", "near"):
                # a misspelled name is put right in every reply of this cut, before the replies are merged (a
                # correction written under the same misspelling must replace the line it corrects)
                held = state_keys(self.notes)
                delta = dict(delta, changes=[(spelt.get(k, k), v) for k, v in delta["changes"]])
                delta, more = respell(delta, mention_counts(held + identifiers_in(body), body), held)
                spelt.update(more)
                if spelt:
                    rec["respelled"] = dict(spelt)
            delta = earlier = merge_replies(earlier, delta)
            delta["rules"] = list(rules_seen)
            near = None
            known = state_keys(self.notes) + [k for k, _ in delta["changes"]]
            if self.mention_check == "near":
                near = numbers_near(known, body)
            new, info = apply_delta(self.notes, delta, seen, strict=self.mention_check in ("count", "near"), near=near)
            steps = info.pop("steps")
            if hinted:
                missing = []
            elif self.mention_check in ("count", "near"):
                # also names that only the items know: a thing opened in these turns and left out of the reply
                missing = under_accounted(mention_counts(known + identifiers_in(body), body), steps)
            else:
                missing = unaccounted(state_keys(self.notes), body, delta["changes"])
            if missing and not stands:                # asked once: a name the turns mention is not accounted for
                hinted = True
                rec["unaccounted"] = missing[:30]
                self.n_mention_reasks += 1
                retry = COUNT_RETRY if self.mention_check in ("count", "near") else MENTION_RETRY
                req = req + [{"role": "assistant", "content": text},
                             {"role": "user", "content": retry.format(names=", ".join(missing[:30]))}]
                continue
            if info["mismatch"] and (stands or "inplace_redo" in rec):
                # after the second reply (or without one): a line whose number the turns do not state is left out
                kept, left = without_doubtful(self.notes, delta, seen, self.mention_check in ("count", "near"), near)
                if left:
                    rec["lines_left_out"] = left[:12]
                    new, info = apply_delta(self.notes, kept, seen, strict=self.mention_check in ("count", "near"), near=near)
                    info.pop("steps", None)
            size = self._budget.count([{"role": "user", "content": new}])
            if info["mismatch"] and "inplace_redo" not in rec and not stands:
                # asked once more, with thinking and with the lines in question named; the second reply stands
                # (the check has false alarms: a model that thinks may start from a value it worked out itself)
                rec["inplace_redo"] = "; ".join(info["mismatch"][:6])
                req = req + [{"role": "assistant", "content": text},
                             {"role": "user", "content": MISMATCH_RETRY.format(lines="; ".join(info["mismatch"][:6]))}]
                thinking = True
                continue
            if info["mismatch"]:
                rec["mismatch_accepted"] = info["mismatch"][:6]
            if size > 2 * self.notes_max_tokens:
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
        self._record({**rec, "reason": "keep-inplace-failed", "turns_dropped": 0, "why": why, "after": before})
        self.inplace_failures.append({"step": self.n_lm_calls, "why": why, "prompt": rec["notes_prompt_tokens"],
                                      "written": rec["notes_completion_tokens"]})
        self.inplace_turn_hold = self._budget.count(body)
        return False

    async def _take_notes(self, head: list[dict[str, Any]], turns: str, rec: dict[str, Any],
                          piece: list[dict[str, Any]] | None = None) -> None:
        thinking = None
        if self.notes_mode in ("delta", "rules"):
            why = await self._notes_delta(head, turns, rec, piece)
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

    async def _notes_delta(self, head: list[dict[str, Any]], turns: str, rec: dict[str, Any],
                           piece: list[dict[str, Any]] | None = None) -> str:
        """Changes-only notes for one cut (or one piece of it). Returns '' when the NOTES were updated, else why not.
        With mention_check count or near the reply is held to the same value checks as an in-place reply; a reply
        that fails them goes to the full rewrite."""
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
            strict, near = self.mention_check in ("count", "near"), None
            if self.mention_check == "near" and piece is not None:
                near = numbers_near(state_keys(self.notes) + [k for k, _ in delta["changes"]], piece)
            new, info = apply_delta(self.notes, delta, numbers_in(turns), strict=strict, near=near)
            info.pop("steps", None)
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
                    "longest_repeat_streak": self.longest_repeat_streak, "sampled_calls_to_leave_a_loop": self.n_sampled_calls,
                    "items_not_archived_mixed_output": self.n_not_archived_mixed,
                    "notes_mode": self.notes_mode, "delta_fallbacks": self.n_delta_fallbacks,
                    "notes_chunk_tokens": self.notes_chunk_tokens, "notes_inplace": self.notes_inplace,
                    "inplace_cuts": self.n_inplace, "inplace_failed": self.n_inplace_failed,
                    "inplace_redone_with_thinking": self.n_inplace_redone, "questions_kept_in_view": getattr(self, "n_questions_kept", 0),
                    "mention_check": self.mention_check, "mention_reasks": self.n_mention_reasks,
                    "inplace_failures": self.inplace_failures[:20], "inplace_prompt_tokens": self.inplace_prompt,
                    "inplace_cached_tokens": self.inplace_cached, "inplace_turn_tokens": self.inplace_turn_tokens,
                    "sums_corrected": self.n_sums_corrected, "auto_retrieve": self.auto_retrieve,
                    "retrievals": self.n_retrievals, "retrieved_chars": self.retrieved_chars,
                    "retrievals_skipped": self.n_retrievals_skipped, "retrieve_window": self.retrieve_window,
                    "retrieve_scope": self.retrieve_scope,
                    "passages_indexed": len(self._index.docs), "recall_tool": self.recall_tool,
                    "archive_files": self.archive_files,
                    "notes_max_tokens": self.notes_max_tokens, "target_ratio": self.target_ratio,
                    "largest_delivery_tokens": self._largest_delivery, "keep_headroom": self.keep_headroom}, indent=1) + "\n")
            except Exception:
                pass
