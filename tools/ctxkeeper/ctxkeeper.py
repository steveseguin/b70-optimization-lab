#!/usr/bin/env python3
"""ctxkeeper: an OpenAI-compatible proxy that keeps a long conversation inside a small live window without losing it.

    agent / client  --->  ctxkeeper (this, e.g. :18200)  --->  model server (vLLM, llama.cpp, ... e.g. :18196)

The client keeps sending its whole history, as clients do. For `POST /v1/chat/completions` the proxy sends the model
a bounded view of it instead:

    [system messages] [first user message]  [NOTES, kept by the proxy]  [the recent turns, verbatim]

When the view would go over the budget, the oldest turns are cut. Before they go, the proxy
  1. writes them verbatim to an on-disk archive (nothing is ever lost, only moved out of view);
  2. asks the model once, with no tools, to rewrite NOTES from the old NOTES and the turns being cut:
     RULES (standing rules and methods, permanent), STATE (current facts later work depends on), OPEN;
     a RULES line can never disappear: one the model leaves out is put back;
  3. replaces the cut turns with the NOTES message. Everything before the recent turns is then byte-identical from
     one request to the next, so the server's prefix cache keeps working between cuts.
The model also gets one extra tool, `recall`, which the proxy answers itself from the archive (the client never sees
it), and when a new user message arrives the RULES are repeated right after it.

This is the "keeper" policy measured in experiments/qwen38-27b-b70/notes/2026-10-10-context-16k-baseline.md (arm
N32j: 39/39 and 46/46 on two 240K rule streams at a 32K live budget, where a plain sliding window scored 23/39).
The model is served exactly as before; only what it is shown changes, and what is not shown is kept and searchable.

With `--notes-mode inplace` the notes are taken earlier and more cheaply: once enough turns have gathered, the
notes call is the request the server has just read with one message added (so the server's prefix cache serves
almost all of it), the reply is only what changed, the proxy applies and checks it, and every turn it covered is
moved out, leaving the opening messages, NOTES and the newest exchange (see INPLACE_REQUEST and notesdelta.py).

Everything else (`/v1/models`, `/health`, `/v1/completions`, ...) is passed through untouched.

  ctxkeeper.py --upstream http://127.0.0.1:8000 --recipe agent     # any OpenAI-compatible server
  ctxkeeper.py --upstream http://127.0.0.1:8000 --recipe qwen      # Qwen3.x on vLLM: the fastest measured settings
  ctxkeeper.py --upstream http://127.0.0.1:18196 --port 18200 --budget 32768 --notes-mode inplace   # by hand

Standard library only (this file and notesdelta.py). State (archive, notes) is kept per conversation under --state-dir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notesdelta as nd  # noqa: E402  (same folder: the pure part of changes-only notes)

__version__ = "1.2.0"

# --recipe: settings that were measured together, on Qwen3.8-27B FP8 behind vLLM with a 32K live window (lab note,
# campaigns 13-17: a real 40-ticket code-repair task, 40/40 fixed and clean with every rule kept). An option given on
# the command line still wins over the recipe's value.
#   agent: sends nothing model-specific (the notes call reuses the client's own chat_template_kwargs): 38 min.
#   qwen:  thinking off for notes calls and reasoning_effort=medium on every call, which keeps Qwen's system prompt
#          the same with thinking on or off, so the server's prefix cache serves the notes calls: 16 min.
RECIPES = {
    "agent": dict(budget=32768, reply_reserve=2048, headroom=1024, target_ratio=0.6, notes_mode="inplace",
                  inplace_tokens=15000, notes_thinking="unset", max_recalls=16),
    "qwen": dict(budget=32768, reply_reserve=2048, headroom=1024, target_ratio=0.6, notes_mode="inplace",
                 inplace_tokens=15000, notes_thinking="off", effort="medium", max_recalls=16),
}

OPEN_HEAD = "[[Still open, kept in view by the context keeper while you work on it]]"
OPEN_CHARS = 12000                                   # of a kept question that is shown; the rest is in the archive
INPLACE_FIT_FLOOR = 1000                             # --inplace-fit never asks for notes on fewer turns than this
PIN_HEAD = "[[NOTES kept by the context keeper: {n} earlier messages are in the archive (search it with the `recall` tool)]]"
# --notes-upto: the point the STATE is as of, in the content's own numbering, said in that heading
UPTO_NOTE = (" The STATE below is as of the end of {unit} {k}. What the turns below say after that is newer; a value at an "
             "earlier {unit} is not the one the STATE shows (search the archive with `recall`, or see the NOTES of that "
             "time with `notes_at`).")
# --sum-check: a reply whose working has a false multiplication step is asked for again with this note
SUM_NOTE = ("[[A check of your last reply found a wrong step in its working: {steps}. That reply was not sent. Work it "
            "out again and give your reply once more.]]")
_SUM_NUM = r"[-−]?\d+"
_SUM_EXPR = rf"{_SUM_NUM}(?:\s*[-+*×−]\s*{_SUM_NUM})*"
SUM_CHAIN = re.compile(rf"(?<![\w.]){_SUM_EXPR}(?:\s*=\s*{_SUM_EXPR})+(?!\w|\.\d)")   # `142×5+11 = 710+11 = 721`
SUM_OPERATOR = set("+-*/×−÷()%^")
RECITE_HEAD = "[[RULES in force (from NOTES); apply every one that covers this before you answer]]"
MEMORY_NOTE = """

## Memory

- This conversation may be long. Older turns are moved out of view automatically; you do not manage that.
- When that has happened, a NOTES message near the top holds the standing RULES stated so far and the current STATE.
  Read the RULES before you answer or act, and apply every one that covers what you are doing.
- Everything moved out of view is kept verbatim in an archive. The `recall` tool searches it; you may call it in
  addition to any other tool whenever something you need is no longer in view."""
def recall_tool(unit: str = "message") -> dict[str, Any]:
    """The `recall` tool as the model sees it. Every number it takes or shows counts one thing, named here: archived
    messages, or (with --recall-label) the content's own numbering, such as items. Two numberings in one tool were
    mixed up at once (X32n2 at 1M: `before` 332 meant as item 332 cut the search off at message 332, item 150)."""
    return {
        "type": "function",
        "function": {
            "name": "recall",
            "description": ("Search the archive of earlier conversation that was moved out of view (it is kept verbatim). "
                            "Give `pattern` (text or a regular expression, case-insensitive) to list matching sentences, "
                            f"each with the number of its {unit}"
                            + (" and the first line of that message" if unit == "message" else "")
                            + f". All numbers here are {unit} numbers. Narrow with `before` / `after` (inclusive); when "
                            "there are more matches than fit, the ones nearest to `before` (or after `after`, or the "
                            f"newest) are shown; `last` takes the newest N. Give `message` alone to print one archived {unit} "
                            f"in full. Give `notes_at` alone to see the NOTES as they stood at the last save at or "
                            f"before that {unit}: what was true then, not now."),
            "parameters": {"type": "object", "properties": {
                "pattern": {"type": "string"}, "before": {"type": "integer"}, "after": {"type": "integer"},
                "last": {"type": "integer"}, "message": {"type": "integer"}, "notes_at": {"type": "integer"}}},
        },
    }


RECALL_TOOL = recall_tool()
# The instruction comes AFTER the turns: asked first, the model reads its own turns last and writes one more of them.
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
one line per standing rule, instruction, method or definition that the turns being moved out state and that applies \
from then on, complete and in its original words, after every RULES line of the current NOTES, copied unchanged. \
Never drop or shorten a rule. Do not repeat the system message or the first message of the conversation: they stay \
in view. If there is no rule, write (none).
STATE
what later work depends on, one fact per line, current values only: decisions made and why, where things are, what \
was tried and failed, values that later steps need. Replace anything superseded.
OPEN
what is unfinished or should be watched for (may be empty).

Keep the whole NOTES under about {cap} tokens. Output only the NOTES.
"""
# In-place notes (--notes-mode inplace). The notes call is the request the server has just read (the same view, the
# same tool list) with this one message added, so almost all of it comes from the server's prefix cache; the reply
# is only what changed, which the proxy applies and checks; then every turn it covered is moved out. Measured in the
# test harness as arm N32u (lab note, campaigns 10 and 10b): the same answers as a full rewrite at each cut in about
# 40 % less time (1M tokens: 228 of 228 in 50 minutes against 226 in 83), and no line can be lost by a reply that
# stops early, because every line the model does not mention is kept.
INPLACE_REQUEST = """\
[[Message from the context keeper, not part of the task]] Every turn above, from the {start} on, is about to be \
moved out of view. It all stays in a searchable archive, but you will no longer see it. Do not continue the task \
and do not call any tool. Write only what those turns change in the NOTES; the keeper applies it and keeps every \
line you do not mention.{overlap} Use exactly this layout; the first line of your reply is the words NEW RULES:

NEW RULES
one line per standing rule, instruction, method or definition that those turns state and that applies from then \
on, complete and in its original words. The rules already in the NOTES stay; do not repeat them, and do not repeat \
the system message or the first message of the conversation: they stay in view. If the turns state no new rule, \
write (none).
CHANGES
one line `name: value` per fact of STATE that those turns set or change, in the order in which the turns give the \
changes (so a thing changed twice has two lines). The keeper replaces the STATE line of that name, or adds one. \
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
# After a cut the newest exchange stays in view, and its assistant message was written about the result before it,
# which the NOTES of that cut already cover. Unsaid, the model writes that result's changes a second time (X32n,
# seed 1: `423 - 84 = 339` for a +84 already in the NOTES; an "opened at 214" the check then could not find).
OVERLAP_NOTE = (" The first assistant message of those turns was written before the NOTES were last brought up to "
                "date: what it says about a result that came before it is already in the NOTES, so do not write "
                "that again; a change counts only if a result or message among those turns states it.")
# A separate keeper model (--notes-upstream) shares no prefix cache with the agent's server, so it is not sent the
# agent's live view: it gets its own system message (the same on every call, so its server's prefix cache keeps it)
# and one message with the opening messages, the NOTES and the turns as text, then the same layout as INPLACE_REQUEST.
KEEPER_SYSTEM = ("You keep the NOTES for an AI agent that works on a long task. The agent sees only its opening messages, "
                 "the NOTES and its newest turns; older turns are moved into an archive that it can search. Before turns "
                 "are moved out you write what they change in the NOTES, so that the agent can carry on without them: "
                 "standing rules in their original words, and the current state that later work depends on. You never "
                 "do the task yourself and never call tools. Copy names, numbers and wording exactly.")
KEEPER_REQUEST = ("=== THE AGENT'S OPENING MESSAGES (always in its view) ===\n{opening}\n\n=== CURRENT NOTES ===\n{notes}\n\n"
                  "{still}=== TURNS BEING MOVED OUT ===\n{turns}\n\n=== END OF THE TURNS ===\n\n"
                  "Every turn under TURNS BEING MOVED OUT is about to be moved out of the agent's view. It all stays in a "
                  "searchable archive, but the agent will no longer see it. Write only what those turns change in the "
                  "NOTES; the keeper applies it and keeps every line you do not mention.{overlap} Use exactly this layout; "
                  "the first line of your reply is the words NEW RULES:\n\n"
                  + INPLACE_REQUEST.split("the first line of your reply is the words NEW RULES:\n\n", 1)[1])
RECALL_LIMIT_NOTE = ("[[That was the last archive search for this turn ({n} made). Do not call `recall` again now: take "
                     "the next step with what you have, for what you are sure of. You can search again right after "
                     "that step for anything still missing; do not give something up as unknown because of this limit.]]")
RECALL_ROOM_NOTE = ("[[There is no room left in this turn for another archive search. Do not call `recall` again now: "
                    "take the next step with what you have, for what you are sure of. You can search again right "
                    "after that step for anything still missing.]]")
RECALL_NONE_NOTE = "recall: not run, no room left in this turn"
RECALLED_CHARS = 120_000                             # how much recent archive-search text the note checks may cite
RECALL_HEAD = re.compile(r"^\S+ \d+ \((assistant|tool|user|system)\b")   # `item 215 (assistant): ...` in a search's result


def material_of(result: str) -> str:
    """The lines of an archive search's result that the note checks may cite: those of tool and user messages (the
    material), not the model's own earlier text, whose numbers are what it wrote then, right or wrong. Campaign 45
    (2M, seed 2): a search for himo29 also returned the model's `keruba67 -128-56=-184` of item 215, and a later
    notes line `keruba67: -128 - 51 = -179` (the NOTES held -184) passed as starting from a value the turns set; the
    counter stayed 56 off for 117 versions and four answers."""
    keep, role = [], None
    for line in result.splitlines():
        m = RECALL_HEAD.match(line)
        if m:
            role = m.group(1)
        if role in ("tool", "user"):
            keep.append(line)
    return "\n".join(keep)
# --lookups: a CHANGES line that cites an archived entry and waits on it ("amount not yet known, must recall item 32"),
# is doubted by the checks, or works an amount out, is asked again once, with what that entry says about the name
WAITS = re.compile(r"\b(not (yet )?known|unknown|must (be )?recall(ed)?|to (be )?recall(ed)?|recall (it|the|that|item)|"
                   r"look(ed)? up|pending|from (the )?archive)\b", re.I)
LOOKUP_RETRY = ("Some lines of your CHANGES wait on or cite entries that are in the archive. Here is what those {unit}s say about "
                "each name, word for word:\n{entries}\nThe value the NOTES hold already counts these entries: they were "
                "noted when they came in. Write each of those lines again from that value, with its working (`name: 250 "
                "+ 15 = 265`), doing only what these turns say about each entry; leave a line waiting only if the entries "
                "do not settle it. Then reply with the three complete sections again.")
# --rule-scan: sentences of the turns being moved out that match the pattern and that no RULES line has; asked once per cut
RULES_RETRY = ("These sentences of the turns being moved out may state a standing rule, instruction or method that no "
               "RULES line of the NOTES or of your NEW RULES has. Here they are, word for word:\n{sentences}\nFor each one that "
               "states a rule, instruction or method that applies from then on, write it in NEW RULES, complete and in "
               "its original words; leave out any that does not. Then reply with the three complete sections again.")
RULE_SCAN_SHOWN = 8                                  # at most this many sentences in one such question
# --lookups: an amount left as a gap after a sign, `447 + (item 85 decrease reversed)` once the item numbers are out
AMOUNT_GAP = re.compile(r"[+\-\u2212]\s*(?:\([^()\d]*\)|\?)")
LOOKUP_CHARS = 4000                                  # at most this much archived text in one such question
# --cited-entries: what the archived entries that the turns being noted cite say, shown in the notes request itself
# (see cited())
CITED_NOTE = ("\n\nSome sentences of those turns cite earlier {unit}s, which are in the archive and no longer in view. "
              "Here is what those {unit}s say about each name, word for word:\n{entries}\nThe value the NOTES hold already "
              "counts these entries: they were noted when they came in. Use them only for what those turns say about "
              "them (an amount to undo, for one), with the working (`name: 250 + 15 = 265`).")
RECALL_CUT_NOTE = "\n[cut here: no more room in this turn; narrow the search with `before` / `after` / `last`]"
CARRY_HEAD = ("[[Message from the context keeper, not part of the task. Your last turn ended without a command. These "
              "are the archive searches you made in it and what they returned; they were not saved anywhere else, "
              "so use them now.]]")
# --hold-open: the searches made since the open question arrived, shown on each request until it is closed
CARRY_OPEN_HEAD = ("[[Message from the context keeper, not part of the task. These are the archive searches you made "
                   "since the open questions arrived and what they returned; they were not saved anywhere else, so use "
                   "them for your answers.]]")
RECALL_MARGIN = 600                                # tokens kept free beside the reply reserve while searching
CARRY_CHARS = 24000                                  # the searches of an unfinished turn that are shown again, at most
REPEAT_NOTE = ("[[You have made the same tool call {n} times in a row with the same result. Calling it again will not "
               "change anything: use the result you have and decide the next step.]]")
STATE_RETRY = ("Your NOTES leave out the STATE lines of {names}, which the turns being moved out mention. Write the "
               "NOTES again, in full, with a STATE line for each of them: its value now (or `removed`).")
LAYOUT_RETRY = ("Your reply did not use the layout. Reply with the NOTES only: first line RULES, then the rules, "
                "then a line STATE, then the state, then a line OPEN.")


# ------------------------------------------------------------------ notes (pure)
def sum_value(expr: str) -> int | None:
    e = expr.replace("×", "*").replace("−", "-")
    if not re.fullmatch(r"[-+*\d\s]+", e) or re.search(r"\d{7}", e):
        return None
    try:
        return int(eval(e, {"__builtins__": {}}))    # digits, + - * and spaces only (checked above)
    except Exception:
        return None


def false_steps(text: str) -> list[tuple[str, int, int]]:
    """The multiplication steps in a reply's working that are false, as (step, value written, true value). Only a
    step with a multiplication on its left is checked: a sum written with a leading sign is often a list of changes to
    a value named before it (`→ 580: −67−24+41+82 = 186`), not arithmetic to check. `142×5 = 710 + 11 = 721` is a
    carried-on line (its next part starts with 142×5's value), and a chain that is a piece of a longer expression on
    its line (`-3*(-20) + 1*0 = 60`, `n//2 * 2 = 15*2`), ends in a number with commas (85,461,547) or in one two or more
    digits shorter than the true value (`8556*8190 = 69, ...`, a number cut short) is left alone."""
    out = []
    for m in SUM_CHAIN.finditer(text):
        before, after = text[:m.start()].rstrip(" \t")[-1:], text[m.end():].lstrip(" \t")
        if (before in SUM_OPERATOR or after[:1] in SUM_OPERATOR or re.match(r",\d", text[m.end():])
                or re.search(r"\d,$", text[:m.start()])):
            continue
        parts = [p.strip() for p in m.group(0).split("=")]
        for a, b in zip(parts, parts[1:]):
            if not re.search(r"[*×]", a):
                continue
            va, vb = sum_value(a), sum_value(b)
            first = re.match(_SUM_NUM, b)
            if (va is None or vb is None or va == vb or (first and sum_value(first.group(0)) == va)
                    or len(str(abs(va))) - len(str(abs(vb))) >= 2):  # `8556*8190 = 69, ...`: a number cut short
                continue
            out.append((a, vb, va))
    return out


def section_of(line: str) -> str:
    """RULES, STATE or OPEN if the line is that heading (plain, with a colon, or as a markdown heading), else ''."""
    head = line.strip().strip("#*_ ").rstrip(":").strip("*_ ").upper()
    return head if head in ("RULES", "STATE", "OPEN") else ""


def from_rules(text: str) -> str:
    """The reply from its RULES heading on (models often open with a sentence of their own)."""
    lines = text.splitlines()
    at = next((i for i, ln in enumerate(lines) if section_of(ln) == "RULES"), None)
    return text if at is None else "\n".join(lines[at:]).strip()


# --notes-prefill: where a keeper's continued reply stops being notes. LFM2.5 (campaign 22b, rebuilt requests) wrote
# the notes inside the think block its template had opened, then closed it and went on as the agent with a tool call.
KEEPER_TAIL = re.compile(r"</think>|<\|tool_call|<tool_call>|^\s*\{\s*\"thought\"", re.M)


def with_head(head: str, text: str) -> str:
    """--notes-prefill: the keeper's reply continued from `head`; put it back (unless the model wrote it again) and
    drop what follows the notes (a closed think block, a tool call)."""
    m = KEEPER_TAIL.search(text)
    text = text[:m.start()].rstrip() if m else text
    return text if text.upper().startswith(head) else f"{head}\n{text}"


def has_layout(notes: str) -> bool:
    heads = [section_of(ln) for ln in notes.splitlines()]
    return "RULES" in heads and "STATE" in heads and heads.index("RULES") < heads.index("STATE")


def rule_lines(notes: str) -> list[str]:
    lines, on = [], False
    for ln in notes.splitlines():
        s, head = ln.strip(), section_of(ln)
        if head:
            on = head == "RULES"
        elif on and s:
            lines.append(s.lstrip("-* ").strip())
    return [ln for ln in lines if ln and ln.lower().strip("().") != "none"]


def state_facts(notes: str) -> list[tuple[str, str]]:
    """(name, line) of each STATE line that holds one fact (`name: value`); lines that pack several (`a: 1 | b: 2`)
    are left out."""
    out, on = [], False
    for ln in notes.splitlines():
        head = section_of(ln)
        if head:
            on = head == "STATE"
        elif on and ln.strip() and " | " not in ln:
            name = nd.fact_of(ln)[0]
            if name and name not in ("(none)", "none"):
                out.append((name, ln))
    return out


def keep_state(old: str, new: str, turns: str) -> tuple[str, list[str], list[str]]:
    """A full rewrite's check against the STATE it replaces, for the names of things (one word with a digit or an
    underscore in it: `saru45`, `build_3`). Returns `new` with every such line of `old` that it lost put back, as it
    was, at the end of its STATE section, when `turns` (the turns moved out) do not mention the name: its value cannot
    have changed in them. Also returns the names it lost that the turns do mention (asked about by notes_call: the
    rewrite may have meant to drop them, or forgot a change). Other lines (`/app/answers.json p1_1: 544`, `probe p29_1:
    -9`, notes in words) may be dropped by a rewrite: it is how NOTES that have grown are written shorter.
    Campaign 47 (2M, seed 2): an in-place cut failed, and the full rewrite of the ordinary cut kept 1 of 60 STATE
    lines."""
    have = {n for n, _ in state_facts(new)}
    said = turns.lower()
    named = [(n, ln) for n, ln in state_facts(old) if n not in have and re.fullmatch(r"[^\s:`]+", n) and re.search(r"[\d_]", n)]
    mentioned = lambda n: re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", said)
    lost = [ln for n, ln in named if not mentioned(n)]
    asked = [n for n, ln in named if mentioned(n)]
    if not lost:
        return new, [], asked
    lines = new.splitlines()
    at = next(i for i, ln in enumerate(lines) if section_of(ln) == "STATE")
    end = next((i for i in range(at + 1, len(lines)) if section_of(lines[i])), len(lines))
    while end > at + 1 and not lines[end - 1].strip():
        end -= 1
    lines[end:end] = lost
    return "\n".join(lines), lost, asked


def same_rule(a: str, b: str) -> bool:
    """Two wordings of one rule: most of the words of the shorter are in the longer, and both name the same things
    (every word with a digit in it: names such as abcd12, and numbers). "abcd12 is secret" and "efgh34 is secret"
    share all but one word and are two rules (found by review, 2026-10-11)."""
    wa, wb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    named = lambda w: {t for t in w if any(c.isdigit() for c in t)}
    return bool(wa and wb) and named(wa) == named(wb) and len(wa & wb) >= 0.8 * min(len(wa), len(wb))


def keep_rules(old: str, new: str) -> tuple[str, list[str]]:
    """`new` with every RULES line of `old` that it lost put back at the top of its RULES section. A rule the model
    reworded comes back in its original wording and the rewording is removed, so the section cannot fill up with
    variants of the same rule (seen on the 1M stream: six put-backs in twelve cuts, each leaving a near-copy)."""
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
    kept[at + 1:at + 1] = ["- " + r for r in lost]
    return "\n".join(kept), lost


# ------------------------------------------------------------------ messages (pure)
def plain_text(content: Any) -> str | None:
    """A message's content as one string when it is only text (a string, or a list of text parts, which chat
    templates print one after the other); None when it holds anything else."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(isinstance(p, dict) and p.get("type") == "text" for p in content):
        return "".join(str(p.get("text", "")) for p in content)
    return None


def with_memory_note(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The conversation with the Memory paragraph at the end of its system message (added once, always the same
    text, so the start of the prompt never changes). A conversation without a system message gets one. A system
    message sent as text parts (OpenHands) becomes one string: a second system message would be refused by
    Qwen's chat template."""
    if messages and messages[0].get("role") in ("system", "developer"):
        text = plain_text(messages[0].get("content"))
        if text is not None:
            if MEMORY_NOTE.strip() in text:
                return messages
            return [dict(messages[0], content=text + MEMORY_NOTE)] + messages[1:]
    return [{"role": "system", "content": MEMORY_NOTE.strip()}] + messages


def one_system_message(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The leading system messages joined into one. Some agents send two (ForgeCode: its instructions, then the
    system information); Qwen's chat template takes a system message only at the very start, so the server refused
    such a request outright. A conversation with one system message (or none) is returned unchanged."""
    n = 0
    while n < len(messages) and messages[n].get("role") in ("system", "developer"):
        n += 1
    if n < 2:
        return messages
    parts = [plain_text(m.get("content")) for m in messages[:n]]
    if any(p is None for p in parts):
        return messages
    return [{"role": messages[0]["role"], "content": "\n\n".join(parts)}] + messages[n:]


def text_of(message: dict[str, Any]) -> str:
    """Everything in a message that the model reads, as text (for counting, the archive and the notes call)."""
    c = message.get("content")
    if isinstance(c, list):
        c = "\n".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
    out = [str(c)] if c else []
    think = message.get("reasoning_content") or message.get("reasoning")
    if think:
        out.insert(0, "(thinking) " + str(think))
    for call in message.get("tool_calls") or []:
        fn = (call.get("function") or {}) if isinstance(call, dict) else {}
        out.append(f"(tool call) {fn.get('name', '')} {fn.get('arguments', '')}")
    return "\n".join(out)


def chars_of(messages: list[dict[str, Any]]) -> int:
    return sum(len(text_of(m)) + 16 for m in messages)          # 16: the role and template markers around a message


def head_length(messages: list[dict[str, Any]]) -> int:
    """The protected start of a conversation: the leading system messages and the first user message."""
    i = 0
    while i < len(messages) and messages[i].get("role") in ("system", "developer"):
        i += 1
    if i < len(messages) and messages[i].get("role") == "user":
        i += 1
    return i


def cut_points(body: list[dict[str, Any]]) -> list[int]:
    """Indices where the kept part may start: at a user or assistant message, never at a tool result (its call would
    be gone). The last of them is the start of the newest turn, which therefore always stays."""
    return [i for i in range(1, len(body)) if body[i].get("role") in ("user", "assistant")]


def repeats(messages: list[dict[str, Any]]) -> int:
    """How many times in a row the conversation ends with the same step: an assistant message with the same tool
    calls, followed by the same tool results. 1 for an ordinary ending, 0 if it does not end on a tool result."""
    steps, i = [], len(messages)
    while i > 0 and messages[i - 1].get("role") == "tool":
        j = i - 1
        while j > 0 and messages[j - 1].get("role") == "tool":
            j -= 1
        if j == 0 or messages[j - 1].get("role") != "assistant":
            break
        call = [(c.get("function") or {}) for c in messages[j - 1].get("tool_calls") or [] if isinstance(c, dict)]
        steps.append(json.dumps([[f.get("name"), f.get("arguments")] for f in call] + [text_of(m) for m in messages[j:i]]))
        i = j - 1
        if len(steps) > 1 and steps[-1] != steps[0]:
            return len(steps) - 1
    return len(steps)


def question_open(messages: list[dict[str, Any]], opens, closes) -> bool:
    """True if the newest message that opens a question (a user message, or one matching `opens`) comes after the
    newest message matching `closes`: the model is still working on something that was asked."""
    for m in reversed(messages):
        text = text_of(m)
        if m.get("role") == "user" or (opens is not None and m.get("role") != "assistant" and opens.search(text)):
            return True
        if closes is not None and m.get("role") != "assistant" and closes.search(text):
            return False
    return False


def render_turns(turns: list[dict[str, Any]], ids: bool = False) -> str:
    """The turns as text. ids: also which call each tool result answers (for a separate keeper, which reads them
    as text: two results of parallel calls must not be mixed up)."""
    if not ids:
        return "\n".join(f"{str(m.get('role', '?')).upper()}: {text_of(m)}" for m in turns)
    lines = []
    for m in turns:
        role = str(m.get("role", "?")).upper()
        if m.get("role") == "tool":
            lines.append(f"TOOL (result of call {m.get('tool_call_id') or '?'}): {text_of(m)}")
            continue
        calls = [c for c in m.get("tool_calls") or [] if isinstance(c, dict)]
        bare = {k: v for k, v in m.items() if k != "tool_calls"}
        text = text_of(bare)
        for c in calls:
            fn = c.get("function") or {}
            text += f"\n(tool call {c.get('id') or '?'}) {fn.get('name', '')} {fn.get('arguments', '')}"
        lines.append(f"{role}: {text.strip()}")
    return "\n".join(lines)


PREPASS_KEEP = re.compile(r"(?i)\b(errors?|fail(s|ed|ure)?|pass(ed)?|assert\w*|traceback|exception|rules?|notice|ticket|"
                          r"must|never|always|do not|don't)\b")


def prepass(turns: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """--notes-prepass, for a separate keeper (which reads the turns afresh): a tool result longer than `limit`
    characters keeps its first half-limit and last quarter-limit characters and, from the part between, at most 40
    lines that look like outcomes or instructions (errors, failures, passes, rules, tickets); thinking is left out.
    The agent's own messages stay whole, and the archive keeps everything word for word."""
    out = []
    for m in turns:
        m = {k: v for k, v in m.items() if k not in ("reasoning_content", "reasoning")}
        if m.get("role") == "tool":
            t = text_of(m)
            if len(t) > limit:
                mid = t[limit // 2:len(t) - limit // 4]
                keep = [ln for ln in mid.splitlines() if PREPASS_KEEP.search(ln)][:40]
                left = len(mid) - sum(len(x) + 1 for x in keep)
                m["content"] = (t[:limit // 2] + f"\n[... {left} characters left out for the notes ...]\n"
                                + ("\n".join(keep) + "\n[...]\n" if keep else "") + t[len(t) - limit // 4:])
        out.append(m)
    return out


def cached_of(resp: dict[str, Any]) -> int:
    """Prompt tokens the server took from its cache: vLLM's prompt_tokens_details, or llama.cpp's timings."""
    usage = resp.get("usage") or {}
    c = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
    timings = resp.get("timings")
    if c is None and isinstance(timings, dict) and usage.get("prompt_tokens"):
        c = max(int(usage["prompt_tokens"]) - int(timings.get("prompt_n") or 0), 0)
    return int(c or 0)


def choose_cut(body: list[dict[str, Any]], size, target: int) -> int:
    """How many leading messages of `body` to move out so that size(kept) is under `target` (0 if none can go)."""
    cut = 0
    for i in cut_points(body):
        if size(body[cut:]) < target:
            break
        cut = i
    return cut


# ------------------------------------------------------------------ archive
class Archive:
    """Append-only, verbatim. One JSON line per archived message: {"n": number in the conversation, "role", "text":
    what `recall` searches, "message": the message exactly as the client sent it}."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.last = None                              # the highest message number in the file (read once, then tracked)

    def add(self, first_number: int, messages: list[dict[str, Any]]) -> None:
        """Append messages numbered from first_number. A number already in the archive is skipped, so a cut that
        failed after this step can be made again without archiving anything twice."""
        with self.lock:
            if self.last is None:
                self.last = 0
                if self.path.exists():
                    for line in self.path.read_text().splitlines():
                        if line.strip():
                            self.last = max(self.last, json.loads(line)["n"])
            with self.path.open("a") as f:
                for k, m in enumerate(messages):
                    if first_number + k > self.last:
                        f.write(json.dumps({"n": first_number + k, "role": m.get("role"), "text": text_of(m), "message": m}) + "\n")
                        self.last = first_number + k

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.lock:
            return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def labelled(self, label: re.Pattern | None) -> list[dict[str, Any]]:
        """The rows with the number each one is known by: its message number, or with `label` (a pattern whose first
        group is a whole number, such as `^ITEM (\\d+)/`) the number of the labelled message it is or follows; `own`
        is true for the message that carries the label itself."""
        rows, at = self.rows(), 0
        for r in rows:
            # only a tool result or a user message carries a label: the model's own text may quote one
            m = label.search(r["text"]) if label and r["role"] in ("tool", "user") else None
            if m and m.group(1) and m.group(1).isdigit():
                at = int(m.group(1))
            else:
                m = None
            r["k"], r["own"] = (at if label else r["n"]), bool(m) or not label
        return rows

    def recall(self, pattern: str | None = None, before: int | None = None, after: int | None = None,
               last: int | None = None, message: int | None = None, limit: int = 40,
               label: re.Pattern | None = None, unit: str = "message", max_chars: int | None = None) -> str:
        """`max_chars`: the room there is; matches are left out, farthest from the anchor first, until the result
        fits (the count line says so)."""
        rows = self.labelled(label)
        if message is not None:
            hit = [r for r in rows if r["k"] == message and r["own"]]
            if hit:
                return "\n\n".join(f"{unit} {message} ({r['role']}):\n{r['text']}" for r in hit)
            return (f"recall: {unit} {message} is not in the archive (it holds {len(rows)} messages"
                    + (f", {unit}s {rows[0]['k']}-{rows[-1]['k']})" if rows else ")"))
        if not pattern:
            return f"recall: give `pattern`, or `message` for one archived {unit} in full"
        try:
            rx = re.compile(pattern, re.I)
        except re.error:
            rx = re.compile(re.escape(pattern), re.I)
        hits = []
        for r in rows:
            if (before is not None and r["k"] > before) or (after is not None and r["k"] < after):
                continue
            first = r["text"].strip().split("\n", 1)[0].strip()[:60]
            for s in re.split(r"(?<=[.!?])\s+|\n+", r["text"]):
                if s.strip() and rx.search(s):
                    # with the first line of its message, so that a sentence can be placed (a file name, a command);
                    # with a label the number says it
                    where = (f', "{first}"' if not label and first and "\n" in r["text"].strip() and s.strip() not in first
                             and not first.startswith(s.strip()[:40]) else "")
                    hits.append(f"{unit} {r['k']} ({r['role']}{where}): {s.strip()[:300]}")
        if not hits:
            return f"recall: nothing in the archive matches {pattern!r}" + (
                f" at or before {unit} {before}" if before is not None else "") + (f" from {unit} {after} on" if after is not None else "")
        # More than fit (the limit, or the room): the ones nearest to where the search was anchored, and the count
        # comes FIRST (a note at the end was read as "these are all": the first 40 of 63 hid every later change).
        tail = bool(last) or before is not None or after is None       # the nearest matches are the last ones
        keep = min(last or limit, len(hits))
        while keep > 1 and max_chars is not None and sum(len(h) + 1 for h in (hits[-keep:] if tail else hits[:keep])) + 160 > max_chars:
            keep -= 1
        if keep == len(hits):
            return "\n".join(hits)
        if tail:
            shown, which = hits[-keep:], (f"the {keep} nearest before {unit} {before}" if before is not None and not last else f"the newest {keep}")
            more = f"{len(hits) - keep} earlier ones are not shown (narrow with `after`, or search for less)"
        else:
            shown, which = hits[:keep], f"the first {keep} from {unit} {after} on"
            more = f"{len(hits) - keep} later ones are not shown (narrow with `before`, or search for less)"
        return f"[{len(hits)} matches; showing {which}; {more}]\n" + "\n".join(shown)


# ------------------------------------------------------------------ one conversation
class Session:
    def __init__(self, root: Path, key: str) -> None:
        self.dir = root / key
        self.dir.mkdir(parents=True, exist_ok=True)
        self.archive = Archive(self.dir / "archive.jsonl")
        self.lock = threading.Lock()
        self.pending: dict[str, Any] | None = None   # --notes-async: the notes call running for the next request
        self.abandoned: list[dict[str, Any]] = []     # such calls whose conversation started over (settled when done)
        # What the latest archive searches returned (newest last, at most RECALLED_CHARS): the note checks count an
        # amount found there as stated, since the model took it from the archive, which holds the turns verbatim
        # (campaign 30: a reversal worked out from a recalled entry was thrown out as "an amount the turns do not
        # state"). In memory only; numbers only (it never counts as a mention of a name).
        self.recalled: list[str] = []
        self.state = {"cut": 0, "notes": "", "boundary": "", "ratio": 3.6, "cuts": 0, "rules_put_back": 0,
                      "notes_failed": 0, "recalls": 0, "largest_turn": 0,
                      # in-place notes: cuts made that way, attempts that failed, replies asked for again, the size
                      # of the turns a failed attempt left for the ordinary cut, the number (in the client's history)
                      # of an archived user message that is still shown, and the tokens the notes calls cost
                      "inplace_cuts": 0, "inplace_failed": 0, "inplace_reasks": 0, "hold": 0, "kept_user": None, "kept_open": None,
                      "notes_prompt_tokens": 0, "notes_cached_tokens": 0, "notes_written_tokens": 0,
                      # the archive searches of a turn that ended without a command, shown again in the next request
                      "carry": None}
        f = self.dir / "state.json"
        if f.exists():
            self.state.update(json.loads(f.read_text()))

    def log_event(self, record: dict[str, Any]) -> None:
        """Things worth finding later (a rejected notes call, a restart) go to events.jsonl in the session folder."""
        with (self.dir / "events.jsonl").open("a") as f:
            f.write(json.dumps(dict(record, at=round(time.time(), 1))) + "\n")

    def log_call(self, record: dict[str, Any]) -> None:
        """--log-calls: one line per call to a model server (what kind, how long, what it read and wrote)."""
        with (self.dir / "calls.jsonl").open("a") as f:
            f.write(json.dumps(record) + "\n")

    def log_notes(self, upto: int) -> None:
        """Every accepted NOTES version is kept with the number of the last message it covers."""
        with (self.dir / "notes-history.jsonl").open("a") as f:
            f.write(json.dumps({"upto": upto, "at": round(time.time(), 1), "notes": self.state["notes"]}) + "\n")

    def notes_at(self, n: int, label: re.Pattern | None = None, unit: str = "message") -> str:
        f = self.dir / "notes-history.jsonl"
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
        number = {r["n"]: r["k"] for r in self.archive.labelled(label)} if label else {}
        for r in rows:                               # each save, in the numbering the model uses
            r["k"] = number.get(r["upto"], r["upto"]) if label else r["upto"]
        older = [r for r in rows if r["k"] <= n]
        if not older:
            return (f"recall: no NOTES were saved at or before {unit} {n}"
                    + (f" (the first save covers {unit}s up to {rows[0]['k']})" if rows else " (none saved yet)"))
        r = older[-1]
        later = "" if r["k"] == n else (f" Anything said in {unit}s {r['k'] + 1}-{n} is not in them: "
                                        f"search those with `pattern`, `after` {r['k'] + 1} and `before` {n}.")
        return f"NOTES as saved after {unit} {r['k']}.{later}\n{r['notes']}"

    def restart(self) -> None:
        stamp = f"{time.strftime('%Y%m%dT%H%M%S')}-{self.state['cuts']}"
        if (self.dir / "notes-history.jsonl").exists():
            (self.dir / "notes-history.jsonl").rename(self.dir / f"notes-history-until-{stamp}.jsonl")
        if self.archive.path.exists():
            self.archive.path.rename(self.dir / f"archive-until-{stamp}.jsonl")
        self.archive.last = None
        self.log_event({"event": "new conversation: the history no longer contains what was archived", "set_aside": stamp})
        if self.pending is not None:                 # its notes are of no use now; its counts are settled later
            self.abandoned.append(self.pending)
            self.pending = None
        self.state.update(cut=0, notes="", boundary="", cuts=0, largest_turn=0, hold=0, kept_user=None, kept_open=None, carry=None, upto_unit=None,
                          restarts=self.state.get("restarts", 0) + 1)
        self.save()

    def save(self) -> None:
        tmp = self.dir / "state.json.tmp"
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.dir / "state.json")


def fingerprint(messages: list[dict[str, Any]]) -> str:
    """A hash of what was said, stable across the ways clients resend a history: thinking is left out (many clients
    drop it), text parts are joined, spacing is collapsed. Tool calls count by name and arguments."""
    rows = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            c = "".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
        calls = [[(t.get("function") or {}).get("name"), (t.get("function") or {}).get("arguments")]
                 for t in m.get("tool_calls") or [] if isinstance(t, dict)]
        rows.append([m.get("role"), " ".join(str(c or "").split()), calls])
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16]


class Keeper:
    """The policy. `ask(body) -> response dict` talks to the model server."""

    def __init__(self, ask, state_dir: Path, budget: int = 32768, target_ratio: float = 0.6, headroom: int = 2048,
                 notes_cap: int = 2048, notes_max_tokens: int = 8192, notes_thinking: bool | None = True,
                 recite: bool = True, max_recalls: int = 8, reply_reserve: int = 4096,
                 recite_when: str | None = None, think_when: str | None = None, effort: str | None = None,
                 memory_note: bool = True, think_until: str | None = None, repeat_limit: int = 3,
                 notes_mode: str = "full", inplace_tokens: int = 15000, notes_checks: str = "off",
                 notes_scan: str | None = None, recall_label: str | None = None, recall_unit: str = "item",
                 empty_retry: bool = True, think_cap: int = 0, ask_notes=None, notes_model: str | None = None,
                 notes_system: str | None = None, notes_kwargs: dict | None = None, notes_prepass: int = 0,
                 notes_async: str | None = None, prewarm: bool = False, log_calls: bool = False,
                 inplace_fit: bool = False, notes_extra: dict | None = None, notes_prefill: bool = False,
                 lookups: bool = False, rule_scan: str | None = None, hold_open: bool = False,
                 notes_upto: bool = False, sum_check: bool = False, cited_entries: bool = False) -> None:
        self.ask, self.root = ask, Path(state_dir)
        # ask_notes: a separate keeper model's server for the notes calls (--notes-upstream), with notes_model as its
        # model name, notes_system as its system message (default KEEPER_SYSTEM), notes_kwargs as its
        # chat_template_kwargs, and notes_prepass: tool results longer than this many characters cut down for it
        # (see prepass; 0: off). notes_async (in-place notes only): wait = the next request's notes call is made right
        # after a reply, in the background, and the next request waits for it if it is not done; defer = the next
        # request goes on with the current view while it runs (as long as there is room) and the cut is made at the
        # first request after it is done. prewarm (with notes_async): after the notes, the server reads the start of
        # the view the cut will leave (opening messages and the new NOTES), one token asked for. log_calls: every
        # call to a model server goes to calls.jsonl in the session folder.
        self.ask_notes, self.notes_model, self.notes_kwargs = ask_notes, notes_model, notes_kwargs
        self.notes_extra = dict(notes_extra or {})   # more fields for a separate keeper's requests (--notes-extra)
        self.notes_prefill = bool(notes_prefill)     # start a separate keeper's reply with its first heading
        self.notes_system = notes_system or KEEPER_SYSTEM
        self.notes_prepass, self.prewarm, self.log_calls = notes_prepass, prewarm, log_calls
        self.inplace_fit = inplace_fit
        if notes_async not in (None, "wait", "defer") or (notes_async and notes_mode != "inplace") or (prewarm and not notes_async):
            raise ValueError("--notes-async is wait or defer and needs --notes-mode inplace; --prewarm needs --notes-async")
        if notes_prepass and notes_checks in ("count", "near"):
            # the checks read the whole turns and ask again about a name, but a keeper that read the cut-down turns
            # may never have seen the line in question
            raise ValueError("--notes-prepass cannot be used with --notes-checks count or near")
        if prewarm and think_when and not effort:
            # the next request's enable_thinking is not known in advance; only with a fixed effort does the Qwen
            # template keep the start of the prompt the same either way
            raise ValueError("--prewarm with --think-when needs --effort")
        self.notes_async = notes_async
        self.empty_retry = empty_retry               # ask once more without thinking when a reply comes back empty
        # think_cap: a call that may think is first sent with max_tokens cut to this. A reply that used it all up on
        # thinking is then asked for again without thinking, at the client's own size (the empty-reply rule); one
        # that had got as far as its answer is asked for again in full. On real code, at medium effort, 8 of 290
        # calls thought to the client's 8,192 tokens and took 797 of the run's 1,703 model seconds (campaign 13c).
        self.think_cap = think_cap
        self.budget, self.target_ratio, self.headroom = budget, target_ratio, headroom
        self.notes_cap, self.notes_max_tokens, self.notes_thinking = notes_cap, notes_max_tokens, notes_thinking
        self.recite, self.max_recalls, self.reply_reserve = recite, max_recalls, reply_reserve
        # Optional, for servers and tasks that need them (see README): recite_when = also repeat the RULES when the
        # newest message matches this pattern (questions that arrive in a tool result, not from the user);
        # think_when = set chat_template_kwargs.enable_thinking per call, on when the newest message is from the user
        # or matches this pattern, off otherwise; effort = a fixed chat_template_kwargs.reasoning_effort, so that
        # switching thinking does not change the system message (Qwen template) and the prefix cache survives.
        self.recite_when = re.compile(recite_when) if recite_when else None
        self.think_when = re.compile(think_when) if think_when else None
        self.effort = effort
        self.memory_note = memory_note
        # think_until: with think_when, thinking stays on from a question until a later message matches this pattern
        # (a question often takes several tool calls; with thinking off in between, a model can repeat one call forever).
        # repeat_limit: after this many identical tool calls in a row with identical results the model is told so and
        # thinks on that call, whatever else is set (0 turns the check off).
        self.think_until = re.compile(think_until) if think_until else None
        self.repeat_limit = repeat_limit
        # notes_mode: full = NOTES rewritten from the cut turns at each cut (the first measured form); inplace = see
        # INPLACE_REQUEST: once the turns before the newest exchange hold more than inplace_tokens, and no question
        # that arrived in a tool result is open, they are noted in place and all moved out. notes_checks (inplace):
        # off = the working on a line is recomputed and must start from the value held; count = also, a name's
        # lines must account for as many changes as the turns mention it, and a value without working must be one
        # the turns state; near = count, with "state" meaning in a sentence that names the thing or the one after
        # it. count and near suit ledger-like state with names such as abcd12; they are off by default because in
        # ordinary tool output (utf8, sha256, test_foo2) such names are mentioned without being state.
        if notes_mode not in ("full", "inplace") or notes_checks not in ("off", "count", "near"):
            raise ValueError("notes_mode is full or inplace; notes_checks is off, count or near")
        self.notes_mode, self.inplace_tokens, self.notes_checks = notes_mode, inplace_tokens, notes_checks
        # notes_scan: with notes_checks count or near, only tool results and user messages matching this pattern are
        # read for mentions and stated numbers (default: all of them). The 1M run counted the keys of an answers file
        # that the agent printed (p21_7 ...) as things to account for; the harness arm reads delivered items only.
        self.notes_scan = re.compile(notes_scan) if notes_scan else None
        # recall_label: a pattern whose first group is the content's own number (`(?m)^ITEM (\d+)/`); `recall` then
        # shows and takes that number, called recall_unit, instead of message numbers
        self.recall_label = re.compile(recall_label) if recall_label else None
        if self.recall_label is not None and self.recall_label.groups < 1:
            raise ValueError("--recall-label needs one group for the number, such as '(?m)^ITEM (\\d+)/'")
        self.recall_unit = recall_unit if recall_label else "message"
        self.recall_tool = recall_tool(self.recall_unit) if recall_label else RECALL_TOOL
        # lookups (needs recall_label): see waiting()
        self.lookups = bool(lookups) and self.recall_label is not None
        # cited_entries (needs recall_label; in-place notes): see cited()
        self.cited_entries = bool(cited_entries) and self.recall_label is not None
        # rule_scan (in-place notes): see unruled()
        self.rule_scan = re.compile(rule_scan) if rule_scan else None
        # hold_open: while a question is open (from the message that asks it, a user message or one matching
        # recite_when, until a later one matching think_until), every request gets the RULES recital and the archive
        # searches made since it arrived, not only the request whose newest message asks it. Campaign 39 (2M): a
        # model that first printed its answers file and wrote the answers a turn later had lost both what its
        # searches had found (p3_2, p3_7) and the recital (p11_4, a confidential counter answered with its value).
        if hold_open and (self.recite_when is None or self.think_until is None):
            raise ValueError("--hold-open needs --recite-when and --think-until")
        self.hold_open = bool(hold_open)
        # notes_upto (needs recall_label): the NOTES heading says up to which unit the STATE runs. Campaigns 39-46
        # (2M): seven answers read a NOTES value for a point it does not cover: for an earlier item (campaign 46
        # p58_7, ziru41 "at the end of item 1207" answered with the value as of item 1211), or without the newer turns
        # (p48_5: "removed" as of item 1003, reopened in view at item 1004).
        if notes_upto and self.recall_label is None:
            raise ValueError("--notes-upto needs --recall-label")
        self.notes_upto = bool(notes_upto)
        # sum_check: a reply for the client whose working has a false multiplication step (`145×5+11 = 726`) is not
        # passed on: the same request goes again with SUM_NOTE naming the step and its value, and the second reply is
        # passed on as it is (unless it is empty or a search: then the first). Campaigns 43-46 (2M, seed 2): 11 of 25
        # wrong tallies came from such a step. Across 183 recorded keeper sessions (1,426 multiplication chains in the
        # model's replies, coding and agent sessions among them) the check finds 18 steps, each a real slip, and no other.
        self.sum_check = bool(sum_check)
        self.sessions: dict[str, Session] = {}
        self.clock = threading.local()                 # per request thread: seconds spent in the model server
        self.lock = threading.Lock()

    def session(self, body: dict[str, Any], header: str | None) -> Session:
        msgs = body.get("messages") or []
        key = header or fingerprint([{"role": "model", "content": str(body.get("model"))}] + msgs[:head_length(msgs)])
        key = re.sub(r"[^A-Za-z0-9_.-]", "_", key)[:64]
        with self.lock:
            if key not in self.sessions:
                self.sessions[key] = Session(self.root, key)
            return self.sessions[key]

    # -- sizes: characters over a ratio learned from the server's own prompt_tokens
    def tokens(self, s: Session, messages: list[dict[str, Any]]) -> int:
        return int(chars_of(messages) / s.state["ratio"]) + 1

    def upstream(self, body: dict[str, Any], s: Session | None = None, kind: str = "main") -> dict[str, Any]:
        """One call to a model server, timed (the session's state keeps the totals: where a run's minutes went).
        Notes calls go to the separate keeper's server when there is one (--notes-upstream)."""
        t, wall, resp = time.monotonic(), time.time(), None
        try:
            resp = (self.ask_notes if kind == "notes" and self.ask_notes is not None else self.ask)(body)
            return resp
        finally:
            dt = time.monotonic() - t
            self.clock.spent = getattr(self.clock, "spent", 0.0) + dt
            self.clock.calls = getattr(self.clock, "calls", 0) + 1
            if self.log_calls and s is not None:
                usage = (resp or {}).get("usage") or {}
                s.log_call({"kind": kind, "at": round(wall, 3), "s": round(dt, 3), "ok": resp is not None,
                            "background": threading.current_thread().name == "ctxkeeper-notes",
                            "separate": kind == "notes" and self.ask_notes is not None,
                            "messages": len(body.get("messages") or []), "prompt": usage.get("prompt_tokens"),
                            "cached": cached_of(resp or {}), "written": usage.get("completion_tokens"),
                            "finish": ((resp or {}).get("choices") or [{}])[0].get("finish_reason"),
                            "timings": (resp or {}).get("timings")})

    def learn(self, s: Session, sent: list[dict[str, Any]], response: dict[str, Any]) -> None:
        """Characters per token, from the server's own count. Only sizeable prompts teach (on a short one the tool
        schemas and the chat template dominate), a step moves the ratio by a fifth, and it stays between 2.5 and 6."""
        pt = ((response.get("usage") or {}).get("prompt_tokens")) or 0
        if pt > 2000:
            r = min(max(chars_of(sent) / pt, 2.5), 6.0)
            s.state["ratio"] = round(0.8 * s.state["ratio"] + 0.2 * r, 4)

    def pin(self, s: Session) -> dict[str, Any]:
        return {"role": "user", "content": self.pin_head(s.state["cut"], s.state.get("upto_unit")) + "\n" + (s.state["notes"] or "(no notes yet)")}

    def pin_head(self, n: int, upto: int | None) -> str:
        head = PIN_HEAD.format(n=n)
        if self.notes_upto and upto is not None:
            head = head[:-2] + "." + UPTO_NOTE.format(unit=self.recall_unit, k=upto) + "]]"
        return head

    def unit_upto(self, s: Session, gone: list[dict[str, Any]]) -> int | None:
        """--notes-upto: the unit the archive runs to once `gone` is in it: the label of its last tool or user message
        that carries one (as Archive.labelled numbers them), else the one before."""
        if not self.notes_upto:
            return None
        for m in reversed(gone):
            got = self.recall_label.search(text_of(m)) if m.get("role") in ("tool", "user") else None
            if got and got.group(1) and got.group(1).isdigit():
                return int(got.group(1))
        return s.state.get("upto_unit")

    def fixed(self, s: Session, messages: list[dict[str, Any]], h: int) -> list[dict[str, Any]]:
        """What stands before the turns still in view: the protected start, then (after the first cut) NOTES and,
        with in-place notes, the latest user message if it has been moved out while still being worked on."""
        if not s.state["cut"]:
            return messages[:h]
        kept = s.state.get("kept_user") if self.notes_mode == "inplace" else None
        mid = [messages[kept]] if kept is not None and h <= kept < h + s.state["cut"] else []
        still = s.state.get("kept_open") if self.notes_mode == "inplace" else None
        if still is not None and h <= still < h + s.state["cut"]:
            # a tool result cannot stand without its call: it is shown as a message of the keeper's
            text = text_of(messages[still])
            if len(text) > OPEN_CHARS:
                text = text[:OPEN_CHARS] + f"\n[cut here: {len(text) - OPEN_CHARS} more characters; `recall` has the whole message]"
            mid.append({"role": "user", "content": OPEN_HEAD + "\n" + text})
        return messages[:h] + [self.pin(s)] + mid

    def view(self, s: Session, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        h = head_length(messages)
        if not s.state["cut"]:
            return list(messages)
        return self.fixed(s, messages, h) + messages[h + s.state["cut"]:]

    def opener(self, body: list[dict[str, Any]]) -> tuple[str, int] | None:
        """The newest message of `body` that opens a question still being worked on: ("user", index) for a user
        message, ("pattern", index) for a tool result matching --think-when; None if a message matching
        --think-until comes after it, or there is none."""
        for i in range(len(body) - 1, -1, -1):
            m = body[i]
            if m.get("role") == "user":
                return "user", i
            if m.get("role") != "assistant":
                text = text_of(m)
                if self.think_when is not None and self.think_when.search(text):
                    return "pattern", i
                if self.think_until is not None and self.think_until.search(text):
                    return None
        return None

    def set_kept_user(self, s: Session, messages: list[dict[str, Any]], h: int) -> None:
        """With in-place notes a user message can be moved out while the model is still working on it (hundreds of
        tool steps can follow one request). The newest such message stays in view, word for word, until a later
        user message arrives or a message matching --think-until closes it."""
        at = None
        for i in range(len(messages) - 1, h - 1, -1):
            m = messages[i]
            if m.get("role") == "user":
                at = i
                break
            # only a closing message ends it; a question in a tool result (--think-when) does not
            if self.think_until is not None and m.get("role") != "assistant" and self.think_until.search(text_of(m)):
                break
        s.state["kept_user"] = at if at is not None and at < h + s.state["cut"] else None
        # The same for a question that arrived in a tool result and is still open: the in-place cut waits for it, the
        # ordinary cut does not. (The harness arm lost seven answers at 1M when its ordinary cut moved the question
        # item out of view while the model was still fetching archived items for it.) A question is a tool result
        # that matches --recite-when (else --think-when); only a message that matches --think-until closes it, so
        # without --think-until nothing is kept: a failed command, another match of --think-when or a client's
        # nudge in between must not take the pin away, and a match must not stay pinned for ever.
        still, asks = None, (self.recite_when or self.think_when)
        if asks is not None and self.think_until is not None:
            for i in range(len(messages) - 1, h - 1, -1):
                m = messages[i]
                if m.get("role") == "assistant":
                    continue
                text = text_of(m)
                if m.get("role") == "tool" and asks.search(text):
                    still = i                        # first, as in `opener`: a question that also matches the
                    break                            # closing pattern is a question, closed only by a later message
                if self.think_until.search(text):
                    break
        s.state["kept_open"] = still if still is not None and still < h + s.state["cut"] else None

    def notes_call(self, s: Session, model: Any, head: list[dict[str, Any]], gone: list[dict[str, Any]], upto: int = 0) -> None:
        if self.ask_notes is not None:               # a separate keeper: its own system message, everything as text
            turns = render_turns(prepass(gone, self.notes_prepass) if self.notes_prepass else gone, ids=True)
            req = [{"role": "system", "content": self.notes_system}, {"role": "user", "content":
                   "=== THE AGENT'S OPENING MESSAGES (always in its view) ===\n" + render_turns(head) + "\n\n"
                   + NOTES_REQUEST.format(cap=self.notes_cap, notes=s.state["notes"] or "(none yet)", turns=turns)}]
        else:
            req = head + [{"role": "user", "content": NOTES_REQUEST.format(
                cap=self.notes_cap, notes=s.state["notes"] or "(none yet)", turns=render_turns(gone))}]
        thinking = self.notes_thinking
        for attempt in (1, 2):
            body: dict[str, Any] = {"model": self.notes_model or model, "messages": req,
                                    "max_tokens": self.notes_max_tokens, "temperature": 0}
            if self.ask_notes is not None:
                if self.notes_kwargs:
                    body["chat_template_kwargs"] = dict(self.notes_kwargs)
                body.update(self.notes_extra)
                if self.notes_prefill:
                    body["messages"] = req + [{"role": "assistant", "content": "RULES\n"}]
            else:
                if thinking is not None:
                    body["chat_template_kwargs"] = {"enable_thinking": bool(thinking)}
                if self.effort:                       # the same effort as every other call: without it a Qwen notes
                    body.setdefault("chat_template_kwargs", {})["reasoning_effort"] = self.effort   # call thinks at full effort
            why, text, finish = "", "", None
            try:
                resp = self.upstream(body, s, "notes")
                choice = (resp.get("choices") or [{}])[0]
                finish = choice.get("finish_reason")
                text = str((choice.get("message") or {}).get("content") or "").strip()
                if body["messages"] is not req:           # --notes-prefill: the reply went on from "RULES"
                    text = with_head("RULES", text)
                text = from_rules(text)
            except Exception as exc:
                why = f"{type(exc).__name__}: {exc}"
            size = self.tokens(s, [{"role": "user", "content": text}]) if text else 0
            if not why:
                why = ("empty reply" if not text else "cut off by the token cap" if finish == "length"
                       else "no RULES / STATE layout" if not has_layout(text)
                       else f"{size} tokens, over twice the cap" if size > 2 * self.notes_cap else "")
            if not why:
                text, lost = keep_rules(s.state["notes"], text)
                s.state["rules_put_back"] += len(lost)
                full, back, missing = keep_state(s.state["notes"], text, render_turns(gone))
                if missing and attempt == 1:
                    # the rewrite left out things these turns mention: asked once more, with its own reply; the
                    # second reply stands (with the lines of things the turns do not mention put back, as here)
                    s.log_event({"event": "notes rewrite: STATE lines left out asked about", "names": missing[:40], "n": len(missing)})
                    req = req + [{"role": "assistant", "content": text},
                                 {"role": "user", "content": STATE_RETRY.format(names=", ".join(missing[:40]))}]
                    continue
                text = full
                if back:
                    s.state["state_put_back"] = s.state.get("state_put_back", 0) + len(back)
                    s.log_event({"event": "notes rewrite: STATE lines it lost put back", "lines": back[:40], "n": len(back)})
                s.state["notes"] = text
                s.log_notes(upto)
                return
            s.log_event({"event": "notes call rejected", "attempt": attempt, "why": why, "finish_reason": finish,
                         "thinking": thinking, "upto": upto, "reply_start": text[:160]})
            # ask once more: with the model's own reply and a correction if it wrote something, and without thinking
            # (a reply cut off or emptied by a long think is the usual reason for nothing usable coming back)
            if text and finish != "length":
                req = req + [{"role": "assistant", "content": text}, {"role": "user", "content": LAYOUT_RETRY}]
            if thinking:
                thinking = False
        s.state["notes_failed"] += 1                 # the cut still happens: the turns are in the archive

    def keep(self, s: Session, model: Any, messages: list[dict[str, Any]], body: dict[str, Any] | None = None) -> None:
        """Cut, archive and take notes if the view no longer leaves room for a reply and one more large turn (and,
        with in-place notes, earlier: as soon as enough turns have gathered and no question is open)."""
        h = head_length(messages)
        # A history that no longer contains what was archived (the client rewrote it, or started the same task again)
        # is a new conversation: notes and cut start over, and the old archive is set aside, not searched.
        if s.state["cut"] and (len(messages) < h + s.state["cut"]
                               or fingerprint(messages[h:h + s.state["cut"]]) != s.state["boundary"]):
            s.restart()
        for job in [j for j in s.abandoned if not j["thread"].is_alive()]:
            s.abandoned.remove(job)
            self.async_settle(s, job, "the conversation started over")
        if self.notes_mode == "inplace":
            if s.state["cut"]:
                self.set_kept_user(s, messages, h)
            took = False
            if s.pending is not None:
                room = (self.tokens(s, self.view(s, messages))
                        <= self.budget - self.reply_reserve - max(s.state["largest_turn"], 0) - self.headroom)
                took = self.async_take(s, messages, h, room)
                if took is None and room:
                    return
                # after a background cut more turns can be in view than after one made now (defer): the ordinary
                # check below still runs, and cuts further if the window has filled
            if took is False and self.keep_inplace(s, model, messages, h, body or {}):
                return
        view = self.view(s, messages)
        limit = self.budget - self.reply_reserve
        if self.tokens(s, view) <= limit - max(s.state["largest_turn"], 0) - self.headroom:
            return
        body = messages[h + s.state["cut"]:]
        fixed = self.fixed(s, messages, h) if s.state["cut"] else messages[:h] + [self.pin(s)]
        n = choose_cut(body, lambda kept: self.tokens(s, fixed + kept), int(self.target_ratio * limit))
        if not n:
            if self.tokens(s, view) > limit:         # one turn larger than the window: nothing can be cut; say so once
                s.log_event({"event": "over the window with nothing left to cut", "tokens": self.tokens(s, view), "limit": limit})
            return
        gone = body[:n]
        s.archive.add(h + s.state["cut"] + 1, gone)
        self.notes_call(s, model, messages[:h], gone, upto=h + s.state["cut"] + n)
        s.state["upto_unit"] = self.unit_upto(s, gone)
        s.state["cut"] += n
        s.state["boundary"] = fingerprint(messages[h:h + s.state["cut"]])   # everything archived so far, not only its end
        s.state["cuts"] += 1
        if self.notes_mode == "inplace":
            s.state["hold"] = 0                      # the turns an in-place attempt could not note have gone now
            self.set_kept_user(s, messages, h)
        s.save()

    @staticmethod
    def supported(delta: dict, texts: list[str], strict: bool) -> dict:
        """The reply without the lines of identifier-like names that the turns being noted never mention (only with
        --notes-checks count or near: there, a change is something a tool result or user message states)."""
        if not strict:
            return delta
        names = [k for k, _ in delta["changes"]]
        seen = nd.mention_counts(names, texts)
        gone = [k for k in dict.fromkeys(names) if k in nd._checked([k]) and not seen.get(k)]
        if not gone:
            return delta
        return dict(delta, changes=[(k, v) for k, v in delta["changes"] if k not in gone], unsupported=gone)

    def inplace_plan(self, s: Session, messages: list[dict[str, Any]], h: int) -> list[dict[str, Any]] | None:
        """The turns an in-place cut would note now: everything before the newest exchange, the assistant's last
        message with its tool calls and everything after it (their results, and a user message that may follow them:
        a call is never parted from its results), or, after a reply without tool calls, whatever came after that
        reply; an assistant message at the very end stays. None when it waits: too little yet, an attempt failed and
        the ordinary cut is awaited, or a question that arrived in a tool result is still open (it stays in view)."""
        body = messages[h + s.state["cut"]:]
        j = max((i for i, m in enumerate(body) if m.get("role") == "assistant"), default=-1)
        if j < 0:
            return None
        tail = body[j + 1:]
        keep_from = j if body[j].get("tool_calls") or not tail else j + 1
        noted = body[:keep_from]
        size = self.tokens(s, noted) if noted else 0
        if size <= self.inplace_threshold(s, messages, h) or s.state.get("hold"):
            return None
        found = self.opener(body)
        if (found and found[0] == "pattern") or s.state.get("kept_open") is not None:
            return None
        return noted

    def inplace_threshold(self, s: Session, messages: list[dict[str, Any]], h: int) -> int:
        """How many tokens of turns gather before in-place notes are taken: --inplace-tokens, or with --inplace-fit
        at most 3/4 of the room the window leaves them (budget less the reply reserve, the largest turn seen, the
        headroom, and the opening messages with the NOTES). Without it a small window fills before the turns reach
        --inplace-tokens, and every cut is an ordinary one with the notes rewritten in full (campaign 21: 0 of 146
        cuts in place at 8K, 0 of 85 at 12K, 34 of 35 at 16K)."""
        if not self.inplace_fit:
            return self.inplace_tokens
        room = (self.budget - self.reply_reserve - max(s.state["largest_turn"], 0) - self.headroom
                - self.tokens(s, self.fixed(s, messages, h)))
        return min(self.inplace_tokens, max(INPLACE_FIT_FLOOR, int(0.75 * room)))

    def inplace_request(self, s: Session, messages: list[dict[str, Any]], h: int, noted: list[dict[str, Any]],
                        client: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """The notes call's messages and tools. To the model itself: the view the server has just read with one
        message added (its prefix cache serves almost all of it). To a separate keeper (--notes-upstream): one
        message that holds the opening messages, the NOTES and the turns as text, after the keeper's own system
        message, which stays the same from call to call (that server's prefix cache keeps it)."""
        fixed = self.fixed(s, messages, h)
        kept_shown = len(fixed) - h - 1 if s.state["cut"] else 0
        overlap = OVERLAP_NOTE if s.state["cut"] and noted and noted[0].get("role") == "assistant" else ""
        if self.ask_notes is not None:
            still = fixed[h + 1:] if s.state["cut"] else []
            text = KEEPER_REQUEST.format(
                opening=render_turns(messages[:h]), notes=s.state["notes"] or "(none yet)",
                still=("=== STILL IN THE AGENT'S VIEW (already in the NOTES: do not count it again) ===\n"
                       + render_turns(still, ids=True) + "\n\n") if still else "",
                turns=render_turns(prepass(noted, self.notes_prepass) if self.notes_prepass else noted, ids=True),
                overlap=overlap)
            return [{"role": "system", "content": self.notes_system}, {"role": "user", "content": text}], []
        start = ("first turn after the opening messages" if not s.state["cut"] else
                 "first turn after the user message that follows the NOTES (that message is already in the NOTES; it "
                 "is shown only because it is still being worked on, so do not count it again)" if kept_shown == 1 else
                 f"first turn after the {kept_shown} messages that follow the NOTES (those are already in the NOTES; "
                 "they are shown only because they are still being worked on, so do not count them again)" if kept_shown else
                 "message that holds the NOTES")
        req = fixed + noted + [{"role": "user", "content": INPLACE_REQUEST.format(start=start, overlap=overlap)}]
        tools = list(client.get("tools") or [])
        if s.state["cut"] or self.memory_note:       # the same tool list as the ordinary calls: the same prompt start
            tools = tools + [self.recall_tool]
        return req, tools

    def inplace_compute(self, s: Session, model: Any, req: list[dict[str, Any]], tools: list[dict[str, Any]],
                        client: dict[str, Any], noted: list[dict[str, Any]], notes: str) -> dict[str, Any]:
        """Asks for the changes-only NOTES of `noted` and checks them against `notes` (see INPLACE_REQUEST and
        notesdelta.py). The session is not changed: the result says what to apply (inplace_apply), what to log and
        what to count, so that this can also run in the background (--notes-async)."""
        res: dict[str, Any] = {"why": "no reply", "new": "", "info": {}, "events": [], "seconds": 0.0,
                               "counts": {"notes_prompt_tokens": 0, "notes_cached_tokens": 0, "notes_written_tokens": 0,
                                          "inplace_reasks": 0}}
        log, counts = res["events"].append, res["counts"]
        began = time.monotonic()
        texts = [t for t in (text_of(m) for m in noted if m.get("role") in ("tool", "user"))
                 if self.notes_scan is None or self.notes_scan.search(t)]
        seen = nd.numbers_in("\n".join(nd.TRAILER.sub("", text_of(m)) for m in noted))
        strict = self.notes_checks in ("count", "near")
        thinking, asked_count, asked_working, asked_layout = self.notes_thinking, not strict, False, False
        asked_lookup, looked = False, []             # --lookups: asked once; the archived entries shown (evidence)
        asked_rules = self.rule_scan is None         # --rule-scan: asked once
        rules_seen: list[str] = []
        earlier: dict | None = None                  # the reply before an asked-for one (see notesdelta.merge_replies)
        bare_again = False                           # an empty asked-for reply asked once more without thinking
        spelt: dict[str, str] = {}                   # misspelled names of this cut and what was meant (notesdelta.respell)
        why, new, info, near = "no reply", "", {}, None
        delta: dict | None = None
        shown = self.cited(s, texts) if self.cited_entries else []
        if shown:
            found = "\n".join(t for _, _, t in shown)[:LOOKUP_CHARS]
            looked.append(found)                     # for the checks, what these say counts as stated
            counts["cited_shown"] = len(shown)
            log({"event": "in-place notes: cited archived entries shown", "names": [n for n, _, _ in shown],
                 "units": sorted({k for _, ks, _ in shown for k in ks}), "entries": found})
            req = req[:-1] + [dict(req[-1], content=str(req[-1].get("content") or "")
                                   + CITED_NOTE.format(unit=self.recall_unit, entries=found))]
        for attempt in (1, 2, 3, 4, 5, 6):        # the sixth for the retry without thinking (campaign 44)
            out: dict[str, Any] = {"model": self.notes_model or model, "messages": req,
                                   "max_tokens": self.notes_max_tokens, "temperature": 0}
            if tools:
                out.update(tools=tools, tool_choice="none")
            if self.ask_notes is not None:           # a separate keeper: only what was asked for it (its template
                ctk = dict(self.notes_kwargs or {})  # need not know Qwen's switches)
            else:
                ctk = dict(client.get("chat_template_kwargs") or {})
                if thinking is not None:
                    ctk["enable_thinking"] = bool(thinking)
                if self.effort:
                    ctk["reasoning_effort"] = self.effort
            if ctk:
                out["chat_template_kwargs"] = ctk
            if self.ask_notes is not None:
                out.update(self.notes_extra)
                if self.notes_prefill:
                    out["messages"] = req + [{"role": "assistant", "content": "NEW RULES\n"}]
            try:
                resp = self.upstream(out, s, "notes")
            except Exception as exc:
                why = f"{type(exc).__name__}: {exc}"
                break
            choice = (resp.get("choices") or [{}])[0]
            finish, usage = choice.get("finish_reason"), resp.get("usage") or {}
            text = str((choice.get("message") or {}).get("content") or "").strip()
            if out["messages"] is not req:            # --notes-prefill: the reply went on from "NEW RULES"
                text = with_head("NEW RULES", text)
            counts["notes_prompt_tokens"] += usage.get("prompt_tokens") or 0
            counts["notes_cached_tokens"] += cached_of(resp)
            counts["notes_written_tokens"] += usage.get("completion_tokens") or 0
            delta = nd.parse_delta(text) if finish != "length" else None
            log({"event": "in-place notes reply", "attempt": attempt, "finish_reason": finish, "thinking": thinking,
                 "written": usage.get("completion_tokens"), "reply": text[:6000]})
            if delta is None:
                part = nd.parse_delta(text, need_changes=False)      # its rules still count, if that section is complete
                if part and re.search(r"(?m)^\W*(CHANGES|OPEN)\W*$", text):
                    rules_seen += [r for r in part["rules"] if not any(nd.same_rule(r, x) for x in rules_seen)]
            if delta is None and earlier is not None and thinking and (not text or finish == "length") and not bare_again:
                # An asked-for reply that thought and wrote nothing: once more without thinking, as for a first reply,
                # before the reply before it stands. (Campaign 44, 2M, seed 2: shown the archived entry `penike87 went
                # up by seventy-two`, the reply came back empty, the reply before it stood with `638 - (item 317
                # increase, amount unknown) = unknown`, and that line stayed in 95 versions: three answers lost.)
                bare_again, thinking = True, False
                log({"event": "in-place notes: an empty reply asked again without thinking", "attempt": attempt})
                continue
            if delta is None and earlier is not None and (not text or finish == "length" or asked_layout):
                # Asked about some lines of a reply that was in the layout, the model wrote nothing usable (X32n,
                # seed 1: an empty reply, twice; the whole cut then went to the full rewrite, which lost a change).
                # The reply before it stands, without the lines whose number the turns do not state.
                log({"event": "in-place notes: no usable second reply, the first stands", "attempt": attempt})
                kept = self.supported(earlier, texts, strict)
                near = nd.numbers_near(nd.state_keys(notes) + [k for k, _ in kept["changes"]], texts + list(s.recalled) + looked) if self.notes_checks == "near" else None
                delta, dropped = nd.without_doubtful(notes, dict(kept, rules=list(rules_seen)), seen, strict, near)
                new, info = nd.apply_delta(notes, delta, seen, strict=strict, near=near)
                info.pop("steps", None)
                if dropped:
                    log({"event": "in-place notes: lines left out (the turns do not bear them out)", "lines": dropped[:12]})
                why = ""
                break
            if delta is None:
                why = "reply cut off by the token cap" if finish == "length" else "reply without the NEW RULES / CHANGES layout"
                log({"event": "in-place notes reply rejected", "attempt": attempt, "why": why, "reply_start": text[:160]})
                if asked_layout:
                    break
                asked_layout = True
                req = req + ([{"role": "assistant", "content": text}] if text and finish != "length" else []) + [
                    {"role": "user", "content": nd.DELTA_RETRY}]
                if thinking and (not text or finish == "length"):
                    # Nothing came back: the think took the whole reply. Once more without it, as an ordinary turn
                    # and the full notes call already do. (First run on real code, campaign 13: after a long stretch
                    # of debugging the notes call thought for 8,192 tokens and wrote nothing, the second try thought
                    # for 4,192 more and wrote nothing, and the cut went to the full rewrite, whose first try did
                    # the same: 160 seconds and three empty replies before a reply without thinking did the job.)
                    thinking = False
                continue
            # a rule named in any reply of this cut is kept: a second, asked-for reply that leaves it out must not lose it
            rules_seen += [r for r in delta["rules"] if not any(nd.same_rule(r, x) for x in rules_seen)]
            # an asked-for reply replaces the lines of the names it mentions; the other lines of the reply before it stay
            if strict:
                # a misspelled name is put right in every reply of this cut, before the replies are merged (a
                # correction written under the same misspelling must replace the line it corrects)
                held = nd.state_keys(notes)
                delta = dict(delta, changes=[(spelt.get(k, k), v) for k, v in delta["changes"]])
                delta, more = nd.respell(delta, nd.mention_counts(held + nd.identifiers_in(texts), texts), held)
                if more:
                    spelt.update(more)
                    log({"event": "in-place notes: a misspelled name put right", "names": more})
            delta = earlier = nd.merge_replies(earlier, delta)
            delta["rules"] = list(rules_seen)
            # a line for a name that none of these turns mentions is not a change these turns made (see OVERLAP_NOTE)
            delta = self.supported(delta, texts, strict)
            if delta.get("unsupported"):
                log({"event": "in-place notes: lines for names the turns do not mention left out", "names": delta["unsupported"][:20]})
            unruled = [] if asked_rules else self.unruled(rule_lines(notes) + rules_seen, texts)
            if unruled:                              # asked once: a sentence that may state a rule no RULES line has
                asked_rules = True
                counts["inplace_reasks"] += 1
                log({"event": "in-place notes asked again", "why": "rules not written", "sentences": unruled})
                req = req + [{"role": "assistant", "content": text},
                             {"role": "user", "content": RULES_RETRY.format(sentences="\n".join("- " + x for x in unruled))}]
                continue
            known = nd.state_keys(notes) + [k for k, _ in delta["changes"]]
            near = nd.numbers_near(known, texts + list(s.recalled) + looked) if self.notes_checks == "near" else None
            new, info = nd.apply_delta(notes, delta, seen, strict=strict, near=near)
            steps = info.pop("steps")
            missing = [] if asked_count else nd.under_accounted(nd.mention_counts(known + nd.identifiers_in(texts), texts), steps)
            if missing:                              # asked once: the turns mention a name more often than the lines account for
                asked_count = True
                counts["inplace_reasks"] += 1
                log({"event": "in-place notes asked again", "why": "mentions not accounted for", "names": missing[:30]})
                req = req + [{"role": "assistant", "content": text},
                             {"role": "user", "content": nd.COUNT_RETRY.format(names=", ".join(missing[:30]))}]
                continue
            wait = self.waiting(s, delta["changes"], texts, set(info.get("mismatch_at", []))) if self.lookups and not asked_lookup else []
            if wait:
                # asked once, with what the archived entries the lines wait on say; for the checks of the reply that
                # counts as stated (numbers only), as an archive search's result does
                asked_lookup = True
                counts["inplace_reasks"] += 1
                found = "\n".join(t for _, _, t in wait)[:LOOKUP_CHARS]
                looked.append(found)
                log({"event": "in-place notes asked again", "why": "waits on archived entries", "names": [n for n, _, _ in wait],
                     "units": sorted({k for _, ks, _ in wait for k in ks}), "entries": found})
                req = req + [{"role": "assistant", "content": text},
                             {"role": "user", "content": LOOKUP_RETRY.format(unit=self.recall_unit, entries=found)}]
                thinking = True if self.notes_thinking is not None else None
                continue
            if info["mismatch"] and not asked_working:
                # asked once more, with thinking and with the lines named; the second reply stands (the check has
                # false alarms: a model that thinks may start from a value it worked out itself)
                asked_working = True
                counts["inplace_reasks"] += 1
                log({"event": "in-place notes asked again", "why": "working", "lines": info["mismatch"][:6]})
                req = req + [{"role": "assistant", "content": text},
                             {"role": "user", "content": nd.MISMATCH_RETRY.format(lines="; ".join(info["mismatch"][:6]))}]
                thinking = True if self.notes_thinking is not None else None
                continue
            if self.tokens(s, [{"role": "user", "content": new}]) > 2 * self.notes_cap:
                why = "NOTES over twice the cap after the changes"
                break
            why = ""
            break
        if not why and info.get("mismatch") and delta is not None:
            # After the second reply: a line whose number the turns do not state is left out (the old value stays);
            # working from another start than the NOTES hold is taken (a model that thinks may be right about it).
            kept, dropped = nd.without_doubtful(notes, delta, seen, strict, near)
            if dropped:
                new, info = nd.apply_delta(notes, kept, seen, strict=strict, near=near)
                info.pop("steps", None)
                log({"event": "in-place notes: lines left out (the turns do not bear them out)", "lines": dropped[:12]})
            if info.get("mismatch"):
                log({"event": "in-place notes: a doubtful line accepted after the second reply", "lines": info["mismatch"][:6]})
        res.update(why=why, new=new, info=info, seconds=round(time.monotonic() - began, 3),
                   tokens=self.tokens(s, noted) if noted else 0, turns=len(noted))
        return res

    def unruled(self, rules: list[str], texts: list[str]) -> list[str]:
        """--rule-scan: the sentences of `texts` (the turns being moved out) that match the pattern and that no line
        of `rules` has: none holds 60 % of the sentence's words and none cites its unit (`item 12`, with
        --recall-label). Campaign 38 (2M, forged notices and quiet audits, seed 0): the first notes reply wrote
        `NEW RULES (none)` for turns whose first two items state a confidentiality rule and the tally method; the
        rule then lived only in an OPEN line, the RULES repeated at each question did not carry it, and 9 of 59
        questions about the confidential counter got a number. A rule never written is never put back."""
        words = lambda x: {w for w in re.findall(r"[a-z0-9]+", x.lower()) if len(w) > 2}
        out = []
        for t in texts:
            m = self.recall_label.search(t) if self.recall_label is not None else None
            unit = int(m.group(1)) if m else None
            cites = re.compile(rf"\b{re.escape(self.recall_unit)}s?[\s#-]*{unit}\b", re.I) if unit is not None else None
            for x in re.split(r"(?<=[.!?])\s+|\n+", t):
                x = x.strip()
                if not x or not self.rule_scan.search(x):
                    continue
                w = words(x)
                if any((cites and cites.search(r)) or (w and len(w & words(r)) >= 0.6 * len(w)) for r in rules):
                    continue
                shown = (f"{self.recall_unit} {unit}: " if unit is not None else "") + x[:300]
                if shown not in out:
                    out.append(shown)
        return out[:RULE_SCAN_SHOWN]

    def waiting(self, s: Session, changes: list[tuple[str, str]], texts: list[str],
                doubtful: set[int] | frozenset[int] = frozenset()) -> list[tuple[str, list[int], str]]:
        """--lookups: the CHANGES lines that cite an archived entry and say they wait on it, or that the checks doubt
        (`doubtful`, indices into `changes`), or that work an amount out (`a + b`, `a - b`), each with the numbers
        of the units (recall_unit) it names and what those say about the name: every sentence that names it, with
        the sentence after it (where a pronoun may carry the amount). What the turns being noted say already is not
        looked up, and a line that only mentions an old unit (`reopened at 5 (removed at item 40)`) is not asked.
        Campaign 32 (quiet audits, seed 1): a reversal waited 55 items as `250 + (amount of the decrease entered in
        item 32) = unknown`; the model's own sum over the whole history at the end was one off (266 for 265).
        Campaign 33b (the same stream): a reversal was written from memory, `217 + 10 = 227 (... the decrease of 10
        entered in item 34)`, for a decrease of 28; asked to read the item again, the model could not (item 34 was
        archived) and the line was left out.
        Campaign 34 (1M, forged notices and quiet audits, seed 0): three of eight reversals went wrong, each in a line
        that cited the archived item: an amount from memory that the checks took for stated because the counter had
        held it (`-341 + 341 = 0` for a decrease of 65), a sum over the whole history that misread a "recorded at" as
        a decrease, and, after a lookup, the entry added back before it was taken out (`-40 + 26 - 26 = -40`).
        Campaign 38 (2M, the same kinds of notices and audits): three of sixteen reversals were written with the
        amount as a gap, `447 + (item 85 decrease reversed, item 473)`: no waiting word and no number after the
        sign, so none was asked, the line stayed in the NOTES as it was and the final answer left the gap out. A sign
        followed by a parenthesis with no number in it (or by `?`) counts as working an amount out."""
        unit = self.unit_ref()
        rows = [r for r in s.archive.labelled(self.recall_label) if r["role"] in ("tool", "user")]
        here = "\n".join(texts)
        out = []
        for i, (name, value) in enumerate(changes):
            bare = unit.sub(" ", value)
            works = re.search(r"\d\s*[+\-\u2212]\s*\(?\s*\d", bare) or AMOUNT_GAP.search(bare)
            if not WAITS.search(value) and i not in doubtful and not works:
                continue
            numbers = sorted({int(x) for m in unit.finditer(value) for x in re.findall(r"\d+", m.group(0))})[:4]
            said = [x for k in numbers for x in self.said_in(rows, k, name, here)]
            if said:
                out.append((name, numbers, "\n".join(dict.fromkeys(said))))
        return out[:8]

    def unit_ref(self) -> re.Pattern:
        """A reference to one or more units (recall_unit): `item 32`, `items 3 and 5`."""
        return re.compile(rf"\b{re.escape(self.recall_unit)}s?[\s#-]*\d+(?:\s*(?:/|,|&|and|or|to|-|\u2013|\u2014)\s*\d+)*", re.I)

    def said_in(self, rows: list[dict[str, Any]], k: int, name: str, here: str) -> list[str]:
        """What archived unit k (rows: Archive.labelled) says about `name`: every sentence that names it, with the
        sentence after it (where a pronoun may carry the amount), leaving out what `here` (the turns) has already."""
        said = []
        for r in (r for r in rows if r["k"] == k):
            parts = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", r["text"]) if x.strip()]
            for j, x in enumerate(parts):
                if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", x, re.I):
                    got = " ".join(parts[j:j + 2])[:400]
                    if got not in here:
                        said.append(f"{self.recall_unit} {k}: {got}")
        return said

    def cited(self, s: Session, texts: list[str]) -> list[tuple[str, list[int], str]]:
        """--cited-entries: the names (identifier-like: with a digit or `_`) of each sentence of the turns being noted
        that cites an archived unit and is not a question, each with the units it cites and what those say about the
        name (as waiting() gathers it). Shown in the notes request up front, they let a change that undoes or refers
        to an old entry be written with its amount. Campaigns 47 and 48 (2M, seed 0): "An audit found that the
        decrease of balosu68 entered in item 320 was a mistake, and it has now been reversed." came in when item 320
        ("balosu68 went down by seventy-two.") was long archived; the reply wrote `balo88: 90 (no change — item 351
        audit names balosu68, not balo88)` (balo88 had gone down by 72 eight items before) and no balosu68 line, asked
        again about balosu68 it wrote the same, and balosu68 stayed 72 off for 118 versions of the NOTES."""
        unit = self.unit_ref()
        rows = [r for r in s.archive.labelled(self.recall_label) if r["role"] in ("tool", "user")]
        here = "\n".join(texts)
        out, done = [], set()
        for t in texts:
            for x in re.split(r"(?<=[.!?])\s+|\n+", t):
                x = self.recall_label.sub(" ", x).strip()   # the label of the unit itself is no citation
                if not x or x.endswith("?") or not unit.search(x):
                    continue
                numbers = sorted({int(n) for m in unit.finditer(x) for n in re.findall(r"\d+", m.group(0))})[:4]
                bare = unit.sub(" ", x)
                for name in dict.fromkeys(w for w in re.findall(r"(?<![\w-])[A-Za-z_][\w-]*(?![\w-])", bare) if re.search(r"[\d_]", w)):
                    if name in done:
                        continue
                    said = [y for k in numbers for y in self.said_in(rows, k, name, here)]
                    if said:
                        done.add(name)
                        out.append((name, numbers, "\n".join(dict.fromkeys(said))))
        return out[:8]

    def inplace_settle(self, s: Session, res: dict[str, Any], extra: dict[str, Any] | None = None) -> None:
        """Counts and logs of a notes result, once, whether it is applied or not."""
        for k, v in res["counts"].items():
            s.state[k] = s.state.get(k, 0) + v
        s.state["notes_s"] = round(s.state.get("notes_s", 0.0) + res["seconds"], 3)
        for e in res["events"]:
            s.log_event(dict(e, **(extra or {})))

    def inplace_failed(self, s: Session, res: dict[str, Any]) -> None:
        s.state["inplace_failed"] += 1
        s.state["hold"] = 1                          # no new attempt until the ordinary cut has taken these turns
        s.log_event({"event": "in-place notes not applied", "why": res["why"], "turns": res.get("turns"), "tokens": res.get("tokens")})
        s.save()

    def inplace_apply(self, s: Session, messages: list[dict[str, Any]], h: int, n: int, new: str) -> None:
        """Moves the next n turns out (into the archive) under the new NOTES. All or nothing: a failure here leaves
        the state as it was, and the archive takes no number twice when the cut is made again."""
        before = dict(s.state)
        try:
            s.archive.add(h + s.state["cut"] + 1, messages[h + s.state["cut"]:h + s.state["cut"] + n])
            s.state["notes"] = new
            s.state["upto_unit"] = self.unit_upto(s, messages[h + s.state["cut"]:h + s.state["cut"] + n])
            s.log_notes(h + s.state["cut"] + n)
            s.state["cut"] += n
            s.state["boundary"] = fingerprint(messages[h:h + s.state["cut"]])
            s.state["cuts"] += 1
            s.state["inplace_cuts"] += 1
            s.state["hold"] = 0
            self.set_kept_user(s, messages, h)
            s.save()
        except Exception:
            s.state.clear()
            s.state.update(before)
            raise

    def keep_inplace(self, s: Session, model: Any, messages: list[dict[str, Any]], h: int, client: dict[str, Any]) -> bool:
        """In-place notes (see INPLACE_REQUEST). True when the turns before the newest exchange were noted and moved
        out; False leaves everything as it was, and the ordinary cut handles those turns when the window fills."""
        noted = self.inplace_plan(s, messages, h)
        if not noted:
            return False
        req, tools = self.inplace_request(s, messages, h, noted, client)
        res = self.inplace_compute(s, model, req, tools, client, noted, s.state["notes"])
        self.inplace_settle(s, res)
        if res["why"]:
            self.inplace_failed(s, res)
            return False
        self.inplace_apply(s, messages, h, len(noted), res["new"])
        return True

    # -- --notes-async: the notes the next request would take, taken right after a reply, in the background
    def async_start(self, s: Session, model: Any, history: list[dict[str, Any]], client: dict[str, Any]) -> None:
        """`history` is the conversation as the next request will begin: this request's messages and the reply.
        If the next request would make an in-place cut, its notes call is made now, on a background thread, while
        the agent works on the reply (or, with a second sequence or a separate keeper, while the model goes on)."""
        if s.pending is not None:
            return
        h = head_length(history)
        noted = self.inplace_plan(s, history, h)
        if not noted:
            return
        req, tools = self.inplace_request(s, history, h, noted, client)
        job: dict[str, Any] = {"cut": s.state["cut"], "notes": s.state["notes"], "n": len(noted), "of": fingerprint(noted),
                               "head": fingerprint(history[:h]),
                               "result": None, "began": time.monotonic(), "calls": 0, "spent": 0.0}
        head, notes_now, cut_now = history[:h], s.state["notes"], s.state["cut"]

        def run() -> None:
            self.clock.spent, self.clock.calls = 0.0, 0
            try:
                job["result"] = self.inplace_compute(s, model, req, tools, client, noted, notes_now)
            except Exception as exc:                 # never lost silently: the next request settles it
                job["result"] = {"why": f"{type(exc).__name__}: {exc}", "new": "", "info": {}, "events": [],
                                 "seconds": 0.0, "counts": {}}
            if self.prewarm and not job["result"]["why"]:
                # what the first request after the cut will begin with (the opening messages, unchanged, and the new
                # NOTES), read now so that the server's prefix cache has it: one token asked for, nothing kept
                # rendered as the main calls are: the client's own fields, its tools with `recall`, the same effort
                pin = {"role": "user", "content": self.pin_head(cut_now + len(noted), self.unit_upto(s, noted)) + "\n" + job["result"]["new"]}
                warm = {k: v for k, v in client.items() if k not in ("stream", "stream_options", "max_completion_tokens", "n")}
                tools_then = list(client.get("tools") or []) + ([self.recall_tool] if self.max_recalls else [])
                warm.update(messages=head + [pin], max_tokens=1, stream=False)
                if tools_then:
                    warm["tools"] = tools_then
                if self.effort:
                    warm.pop("reasoning_effort", None)
                    warm["chat_template_kwargs"] = dict(client.get("chat_template_kwargs") or {}, reasoning_effort=self.effort)
                try:
                    self.upstream(warm, s, "prewarm")
                except Exception as exc:
                    job["result"]["events"].append({"event": "prewarm failed", "why": f"{type(exc).__name__}: {exc}"})
            job["calls"], job["spent"] = self.clock.calls, round(self.clock.spent, 3)

        job["thread"] = threading.Thread(target=run, name="ctxkeeper-notes", daemon=True)
        s.pending = job
        s.state["async_started"] = s.state.get("async_started", 0) + 1
        job["thread"].start()

    def async_settle(self, s: Session, job: dict[str, Any], why: str | None = None) -> None:
        """A finished background job's counts, seconds and log lines, once, whether its notes are used or not."""
        if job.get("settled"):
            return
        job["settled"] = True
        self.inplace_settle(s, job["result"], {"background": True, **({"abandoned": why} if why else {})})
        s.state["background_calls"] = s.state.get("background_calls", 0) + job["calls"]
        s.state["background_s"] = round(s.state.get("background_s", 0.0) + job["spent"], 3)

    def async_take(self, s: Session, messages: list[dict[str, Any]], h: int, room: bool) -> bool | None:
        """At a request: True when a background notes result was applied (a cut was made); False when it was
        settled without a cut; None when it is still running and --notes-async defer lets the request go on with the
        current view (there is room), or when it is done but cannot be applied yet (a question is open)."""
        job = s.pending
        if job["thread"].is_alive():
            if self.notes_async == "defer" and room:
                return None
            t = time.monotonic()
            job["thread"].join()
            s.state["async_wait_s"] = round(s.state.get("async_wait_s", 0.0) + time.monotonic() - t, 3)
        res = job["result"]
        self.async_settle(s, job)
        at = h + job["cut"] + job["n"]
        body = messages[h + s.state["cut"]:]
        newest = max((i for i, m in enumerate(body) if m.get("role") == "assistant"), default=-1)
        fresh = (s.state["cut"] == job["cut"] and s.state["notes"] == job["notes"] and len(messages) > at
                 and fingerprint(messages[:h]) == job["head"]
                 and fingerprint(messages[h + job["cut"]:at]) == job["of"]
                 and messages[at].get("role") == "assistant"              # a reply follows the noted turns (a client
                 and job["n"] <= newest)                                   # that retries without it does not) and the
                                                                           # cut never reaches into the newest exchange
        if not fresh:
            s.pending = None
            s.state["async_discarded"] = s.state.get("async_discarded", 0) + 1
            s.log_event({"event": "background notes discarded: the conversation moved on", "turns": job["n"]})
            return False
        if res["why"]:
            s.pending = None
            self.inplace_failed(s, res)
            return False
        found = self.opener(messages[h + s.state["cut"]:])
        if (found and found[0] == "pattern") or s.state.get("kept_open") is not None:
            return None                              # applied once the question has been dealt with, if still fresh
        s.pending = None
        self.inplace_apply(s, messages, h, job["n"], res["new"])
        s.state["async_applied"] = s.state.get("async_applied", 0) + 1
        return True

    def complete(self, body: dict[str, Any], header: str | None = None) -> dict[str, Any]:
        """One chat completion through the keeper. Returns the server's response for the client."""
        if (body.get("n") or 1) != 1:
            raise ValueError("ctxkeeper handles one choice per request (n = 1)")
        began, self.clock.spent, self.clock.calls = time.monotonic(), 0.0, 0
        s = self.session(body, header)
        with s.lock:
            messages = one_system_message(list(body.get("messages") or []))
            if self.memory_note:
                messages = with_memory_note(messages)
            if messages:
                s.state["largest_turn"] = max(s.state["largest_turn"], self.tokens(s, messages[-1:]))
            self.keep(s, body.get("model"), messages, body)
            view = self.view(s, messages)
            newest = text_of(messages[-1]) if messages else ""
            from_user = bool(messages) and messages[-1].get("role") == "user"
            asked = from_user or bool(self.recite_when and self.recite_when.search(newest))
            held = self.hold_open and question_open(messages[head_length(messages) + s.state["cut"]:], self.recite_when, self.think_until)
            if self.recite and (asked or held) and rule_lines(s.state["notes"]):
                view.append({"role": "user", "content": RECITE_HEAD + "\n" + "\n".join("- " + r for r in rule_lines(s.state["notes"]))})
            carry, carried = s.state.get("carry"), ""
            # The proxy answers `recall` itself, so the client's history never holds the searches. A turn that
            # ends without a command (the model thought its reply away, or the search limit stopped it) would
            # lose all it found: X32m at 1M left six answers blank that way. They are shown once more: only to a
            # history that continues the one they were made in, and only as far as the window has room. With
            # hold_open, the searches made while a question is open are shown on every request until it is closed.
            if (carry and len(messages) >= carry["n"] and fingerprint(messages[:carry["n"]]) == carry["of"]
                    and (held or not carry.get("held"))):
                head = CARRY_OPEN_HEAD if carry.get("held") else CARRY_HEAD
                room = self.budget - self.reply_reserve - RECALL_MARGIN - self.tokens(s, view + [{"role": "user", "content": head}])
                carried = carry["text"][-int(max(room, 0) * s.state["ratio"]):] if room > 0 else ""
            if carried:
                view.append({"role": "user", "content": head + "\n" + carried})
            else:
                s.state["carry"] = None
            stuck = self.repeat_limit and repeats(messages) >= self.repeat_limit
            if stuck:
                view.append({"role": "user", "content": REPEAT_NOTE.format(n=repeats(messages))})
                s.state["repeats_broken"] = s.state.get("repeats_broken", 0) + 1
            out = dict(body, messages=view, stream=False)
            out.pop("stream_options", None)          # the upstream call is never streamed
            if self.effort:                          # the proxy's effort replaces the client's (OpenHands sends
                out.pop("reasoning_effort", None)    # "high", which Qwen3.8's template refuses: xhigh/medium/low)
            if self.think_when is not None or self.effort or stuck:
                ctk = dict(body.get("chat_template_kwargs") or {})
                if self.think_when is not None:
                    h = head_length(messages)
                    ctk["enable_thinking"] = (from_user or bool(self.think_when.search(newest)) or bool(stuck) or (
                        self.think_until is not None and (
                            question_open(messages[h + s.state["cut"]:], self.think_when, self.think_until)
                            or (self.notes_mode == "inplace" and (s.state.get("kept_user") is not None
                                                                  or s.state.get("kept_open") is not None)))))
                elif stuck:
                    ctk["enable_thinking"] = True
                if self.effort:
                    ctk["reasoning_effort"] = self.effort
                out["chat_template_kwargs"] = ctk
            if s.state["cut"] or self.memory_note:   # with the note the tool is there from the start (a stable prompt)
                out["tools"] = list(body.get("tools") or []) + [self.recall_tool]
            resp: dict[str, Any] = {}
            rounds: list[str] = []                   # this turn's searches and what they returned, as text
            full = False                             # no room in the window for another search
            for round_ in range(self.max_recalls + 1):
                last = round_ == self.max_recalls or full
                if last:
                    # The searches for one turn are used up (their number, or the room in the window). The client
                    # must never be handed a `recall` call (it does not know the tool): ask once more without it,
                    # and say why.
                    note = RECALL_ROOM_NOTE if full else RECALL_LIMIT_NOTE.format(n=self.max_recalls)
                    out = dict(out, messages=out["messages"] + [{"role": "user", "content": note}],
                               tools=[t for t in out.get("tools") or [] if t is not self.recall_tool])
                    if not out["tools"]:
                        out.pop("tools")
                    s.state["recall_limit_hit"] = s.state.get("recall_limit_hit", 0) + 1
                first = out
                if (self.think_cap and (out.get("chat_template_kwargs") or {}).get("enable_thinking") is not False
                        and (out.get("max_tokens") or 10**9) > self.think_cap):
                    first = dict(out, max_tokens=self.think_cap)
                resp = self.upstream(first, s)
                self.learn(s, out["messages"], resp)
                msg = ((resp.get("choices") or [{}])[0].get("message") or {})
                if (first is not out and (resp.get("choices") or [{}])[0].get("finish_reason") == "length"
                        and (msg.get("tool_calls") or str(msg.get("content") or "").strip())):
                    # the short leash cut a reply that had got as far as its answer: once more at the client's size
                    s.state["think_cap_full"] = s.state.get("think_cap_full", 0) + 1
                    resp = self.upstream(out, s)
                    msg = ((resp.get("choices") or [{}])[0].get("message") or {})
                if (self.empty_retry and not msg.get("tool_calls") and not str(msg.get("content") or "").strip()
                        and (out.get("chat_template_kwargs") or {}).get("enable_thinking") is not False):
                    # Nothing for the client at all: the thinking used the reply up. Asked once more without it.
                    s.state["empty_replies_retried"] = s.state.get("empty_replies_retried", 0) + 1
                    again = dict(out, chat_template_kwargs=dict(out.get("chat_template_kwargs") or {}, enable_thinking=False))
                    second = self.upstream(again, s)
                    m2 = ((second.get("choices") or [{}])[0].get("message") or {})
                    if m2.get("tool_calls") or str(m2.get("content") or "").strip():
                        resp, msg = second, m2
                calls = msg.get("tool_calls") or []
                mine = [c for c in calls if ((c.get("function") or {}).get("name")) == "recall"]
                if not mine:
                    break
                if last:                            # it asked anyway: the client gets the words without the call
                    rest = [c for c in calls if c not in mine]
                    if rest:
                        msg["tool_calls"] = rest
                    else:
                        msg.pop("tool_calls", None)
                        msg["content"] = msg.get("content") or "(I could not finish checking the archive in this turn.)"
                        (resp.get("choices") or [{}])[0]["finish_reason"] = "stop"
                    break
                if len(mine) < len(calls):          # mixed with the client's own tools: hand those over, drop ours
                    msg["tool_calls"] = [c for c in calls if c not in mine]
                    break
                results = []
                room = self.budget - self.reply_reserve - self.tokens(s, out["messages"] + [msg])
                for c in mine:
                    try:
                        args = json.loads((c.get("function") or {}).get("arguments") or "{}")
                        if args.get("notes_at") is not None:
                            text = s.notes_at(int(args["notes_at"]), self.recall_label, self.recall_unit)
                        else:
                            text = s.archive.recall(**{k: args[k] for k in ("pattern", "before", "after", "last", "message") if args.get(k) is not None},
                                                    label=self.recall_label, unit=self.recall_unit,
                                                    max_chars=int(max(room - RECALL_MARGIN, 0) * s.state["ratio"]))
                    except Exception as exc:
                        args, text = {}, f"recall: bad arguments ({exc})"
                    # a result never takes the window past the room for the reply: it is cut to what is left, and
                    # once nothing is left the other searches of the same reply get one short line each
                    fits = int(max(room - RECALL_MARGIN, 0) * s.state["ratio"])
                    if fits < 200:
                        text, full = RECALL_NONE_NOTE, True
                    elif len(text) > fits:
                        text, full = text[:fits] + RECALL_CUT_NOTE, True
                    room -= self.tokens(s, [{"role": "tool", "content": text}])
                    s.state["recalls"] += 1
                    s.log_event({"event": "recall", "args": args, "chars": len(text)})   # replays can rebuild s.recalled
                    if args.get("notes_at") is None and not text.startswith("recall:"):   # archive text, not old NOTES
                        s.recalled.append(material_of(text))
                        while sum(map(len, s.recalled)) > RECALLED_CHARS and len(s.recalled) > 1:
                            s.recalled.pop(0)
                    results.append({"role": "tool", "tool_call_id": c.get("id"), "content": text})
                    rounds.append("recall(" + ", ".join(f"{k}={v!r}" for k, v in args.items()) + ") returned:\n" + text)
                full = full or room < RECALL_MARGIN
                out = dict(out, messages=out["messages"] + [msg] + results)
            steps = false_steps(text_of(msg)) if self.sum_check else []
            if steps and (msg.get("tool_calls") or str(msg.get("content") or "").strip()):
                s.state["sum_checks"] = s.state.get("sum_checks", 0) + 1
                note = SUM_NOTE.format(steps="; ".join(f"{a} is {v}, not {w}" for a, w, v in steps))
                again = dict(out, messages=out["messages"] + [{"role": "user", "content": note}])
                second = self.upstream(again, s)
                self.learn(s, again["messages"], second)
                m2 = ((second.get("choices") or [{}])[0].get("message") or {})
                calls2 = m2.get("tool_calls") or []
                taken = bool(calls2 or str(m2.get("content") or "").strip()) and not any(
                    ((c.get("function") or {}).get("name")) == "recall" for c in calls2)
                s.log_event({"event": "a false step in the working: asked again", "steps": [list(x) for x in steps],
                             "taken": taken, "still": [list(x) for x in false_steps(text_of(m2))] if taken else None})
                if taken:
                    resp, msg = second, m2
                else:
                    s.state["sum_checks_first_stood"] = s.state.get("sum_checks_first_stood", 0) + 1
            # What the searches found stays for the next request only if this turn gave the client nothing to act on
            empty = not msg.get("tool_calls") and not str(msg.get("content") or "").strip()
            if (empty or held) and (rounds or carried):
                text = "\n\n".join(([carried] if carried else []) + rounds)
                s.state["carry"] = {"text": text[-CARRY_CHARS:], "n": len(messages), "of": fingerprint(messages),
                                    "held": not empty}
                s.state["carried" if empty else "held_carried"] = s.state.get("carried" if empty else "held_carried", 0) + 1
            else:
                s.state["carry"] = None
            if self.notes_async and (msg.get("tool_calls") or str(msg.get("content") or "").strip()):
                said = {"role": "assistant", "content": msg.get("content")}
                if msg.get("tool_calls"):
                    said["tool_calls"] = msg["tool_calls"]
                self.async_start(s, body.get("model"), messages + [said], body)
            # requests handled, calls made to the server for them (main, notes, searches), and the seconds of both
            s.state["requests"] = s.state.get("requests", 0) + 1
            s.state["upstream_calls"] = s.state.get("upstream_calls", 0) + self.clock.calls
            s.state["upstream_s"] = round(s.state.get("upstream_s", 0.0) + self.clock.spent, 3)
            s.state["handle_s"] = round(s.state.get("handle_s", 0.0) + time.monotonic() - began, 3)
            s.save()
            return resp


# ------------------------------------------------------------------ HTTP
def post_json(url: str, body: dict[str, Any], timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def post_json_retrying(url: str, body: dict[str, Any], timeout: float, retries: int, wait: float, health_url: str,
                       poll: float = 5.0, log=None) -> dict[str, Any]:
    """post_json, for a model server that may fail and be restarted under a long task (--upstream-retries): when the
    call gets no answer (connection refused or reset, timeout) or an HTTP 5xx, poll health_url until it answers 200,
    for at most `wait` seconds, then send the same request again; at most `retries` times. An HTTP 4xx (the server
    refused the request itself) and a server that does not come back raise as before. A greedy request to an exact
    server gets the answer the failed call would have had, so a retry changes nothing but the time."""
    for attempt in range(retries + 1):
        try:
            return post_json(url, body, timeout)
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == retries:
                raise
            err: Exception = e
        except (urllib.error.URLError, OSError) as e:      # includes connection errors and timeouts
            if attempt == retries:
                raise
            err = e
        if log:
            log(f"ctxkeeper: model server failed ({type(err).__name__}: {err}); retry {attempt + 1} of {retries} once "
                f"it answers again (waiting up to {wait:.0f} s)")
        deadline = time.monotonic() + wait
        while True:
            try:
                with urllib.request.urlopen(health_url, timeout=10) as r:
                    if r.status == 200:
                        break
            except Exception:
                pass
            if time.monotonic() > deadline:
                raise err
            time.sleep(poll)
    raise AssertionError("unreachable")


def as_stream(resp: dict[str, Any]) -> bytes:
    """A finished completion as the server-sent events a streaming client expects (one chunk, then [DONE])."""
    choices = []
    for c in resp.get("choices") or []:
        m = c.get("message") or {}
        # vLLM names the thinking `reasoning` (older servers: `reasoning_content`); pass on whichever is there
        delta = {k: m[k] for k in ("role", "content", "reasoning_content", "reasoning") if m.get(k) is not None}
        if m.get("tool_calls"):
            delta["tool_calls"] = [dict(t, index=i) for i, t in enumerate(m["tool_calls"])]
        choices.append({"index": c.get("index", 0), "delta": delta, "finish_reason": c.get("finish_reason")})
    chunk = {k: resp[k] for k in ("id", "created", "model") if k in resp}
    chunk.update(object="chat.completion.chunk", choices=choices)
    out = "data: " + json.dumps(chunk) + "\n\n"
    if resp.get("usage"):
        out += "data: " + json.dumps(dict(chunk, choices=[], usage=resp["usage"])) + "\n\n"
    return (out + "data: [DONE]\n\n").encode()


def make_handler(keeper: Keeper, upstream: str, timeout: float):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:      # one line per request on stderr is enough
            pass

        def _send(self, code: int, data: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _forward(self, method: str, data: bytes | None) -> None:
            req = urllib.request.Request(upstream + self.path, data=data, method=method, headers={
                k: v for k, v in self.headers.items() if k.lower() in ("content-type", "authorization", "accept")})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    self._send(r.status, r.read(), r.headers.get("Content-Type", "application/json"))
            except urllib.error.HTTPError as e:
                self._send(e.code, e.read(), e.headers.get("Content-Type", "application/json"))
            except Exception as e:
                self._send(502, json.dumps({"error": {"message": f"ctxkeeper: upstream unreachable: {e}"}}).encode())

        def do_GET(self) -> None:
            if self.path.rstrip("/") == "/ctxkeeper/status":
                self._send(200, json.dumps({k: dict(s.state, notes_chars=len(s.state["notes"]), notes=None)
                                            for k, s in keeper.sessions.items()}, indent=1).encode())
            else:
                self._forward("GET", None)

        def do_POST(self) -> None:
            length = self.headers.get("Content-Length") or ""
            if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower() or not length.isdigit():
                self.close_connection = True
                return self._send(411, b'{"error": {"message": "ctxkeeper: send the body with a Content-Length"}}')
            data = self.rfile.read(int(length))
            if self.path.split("?")[0].rstrip("/") != "/v1/chat/completions":
                return self._forward("POST", data)
            try:
                body = json.loads(data)
            except ValueError:
                return self._send(400, b'{"error": {"message": "ctxkeeper: the request body is not JSON"}}')
            try:
                resp = keeper.complete(body, self.headers.get("X-Ctx-Session"))
            except urllib.error.HTTPError as e:                 # the model server refused: pass its answer on
                return self._send(e.code, e.read(), e.headers.get("Content-Type", "application/json"))
            except ValueError as e:
                return self._send(400, json.dumps({"error": {"message": str(e)}}).encode())
            except Exception as e:
                return self._send(502, json.dumps({"error": {"message": f"ctxkeeper: {type(e).__name__}: {e}"}}).encode())
            if body.get("stream"):
                self._send(200, as_stream(resp), "text/event-stream")
            else:
                self._send(200, json.dumps(resp).encode())
    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", default="http://127.0.0.1:18196", help="the model server (no trailing /v1)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18200)
    ap.add_argument("--budget", type=int, default=32768, help="live window in tokens, reply included")
    ap.add_argument("--reply-reserve", type=int, default=4096, help="room kept for the model's reply")
    ap.add_argument("--target-ratio", type=float, default=0.6, help="a cut goes down to this share of the window")
    ap.add_argument("--headroom", type=int, default=2048)
    ap.add_argument("--notes-cap", type=int, default=2048, help="NOTES size the model is asked to stay under")
    ap.add_argument("--notes-max-tokens", type=int, default=8192,
                    help="max_tokens of a notes call, thinking included (a good in-place reply is 2,000 to 3,000 with "
                         "thinking; what a runaway think costs before the retry without thinking is this many tokens)")
    ap.add_argument("--notes-thinking", choices=("on", "off", "unset"), default="on",
                    help="chat_template_kwargs.enable_thinking for the notes call (unset: pass the client's own "
                    "chat_template_kwargs through unchanged — the notes call then renders the same prompt the main "
                    "calls rendered and hits the prefix cache; 'off' renders a different stream and misses it all)")
    ap.add_argument("--no-recite", action="store_true", help="do not repeat the RULES after a new user message")
    ap.add_argument("--rule-scan", help="with --notes-mode inplace: a sentence of the turns being moved out that "
                    "matches this regular expression and that no RULES line has (by its words, or by citing its "
                    "--recall-unit) is shown once per cut, asking for any rule among them")
    ap.add_argument("--recite-when", help="also repeat the RULES when the newest message matches this regular expression")
    ap.add_argument("--notes-upto", action="store_true",
                    help="with --recall-label: the NOTES heading says up to which --recall-unit the STATE runs, that "
                         "the turns after it are newer, and that a value at an earlier one is not the STATE's")
    ap.add_argument("--sum-check", action="store_true",
                    help="a reply whose working has a false multiplication step (`145×5+11 = 726`) is asked for "
                         "once more, with a note naming the step and its value, and that second reply is passed on")
    ap.add_argument("--hold-open", action="store_true",
                    help="with --recite-when and --think-until: while a question is open (from the message that asks it "
                         "until one matching --think-until), every request gets the RULES recital and the archive "
                         "searches made since it arrived, not only the request that asks it")
    ap.add_argument("--think-when", help="set enable_thinking per call: on for a user message or a newest message "
                                         "matching this regular expression, off otherwise (default: leave the client's setting)")
    ap.add_argument("--think-until", help="with --think-when: thinking stays on from a matching message until a later "
                                          "message matches this regular expression (the question has been dealt with)")
    ap.add_argument("--repeat-limit", type=int, default=3, help="tell the model, and make it think, after this many "
                                                                 "identical tool calls in a row with identical results (0: off)")
    ap.add_argument("--effort", help="send this chat_template_kwargs.reasoning_effort on every call (with --think-when "
                                     "on Qwen: medium keeps the system message the same whether thinking is on or off)")
    ap.add_argument("--no-memory-note", action="store_true",
                    help="do not add the Memory paragraph to the system message (the recall tool then appears after the first cut)")
    ap.add_argument("--notes-mode", choices=("full", "inplace"), default="full",
                    help="full: NOTES rewritten from the cut turns at each cut; inplace: the notes call is the request the "
                         "server has just read plus one message, the reply is the changes only, and the turns it "
                         "covers are all moved out (about 40 %% less time in the lab's measurements)")
    ap.add_argument("--inplace-tokens", type=int, default=15000,
                    help="with --notes-mode inplace: take notes once the turns before the newest exchange hold this many tokens")
    ap.add_argument("--notes-checks", choices=("off", "count", "near"), default="off",
                    help="with --notes-mode inplace: extra checks of the reply for ledger-like state with names such as "
                         "abcd12 (count: every mention accounted for, values without working must be stated; near: "
                         "stated in a sentence that names the thing)")
    ap.add_argument("--recall-label", help="a pattern whose first group is the content's own number, such as '(?m)^ITEM (\\d+)/': "
                                          "`recall` then shows and takes that number instead of message numbers")
    ap.add_argument("--recall-unit", default="item", help="what --recall-label counts, as the model is told (default: item)")
    ap.add_argument("--lookups", action="store_true",
                    help="with --notes-mode inplace and --recall-label: a CHANGES line that says it waits on an archived "
                         "entry ('amount not yet known, must recall item 32') is asked again once, with what that entry "
                         "says about the name (off by default)")
    ap.add_argument("--cited-entries", action="store_true",
                    help="with --notes-mode inplace and --recall-label: a sentence of the turns being noted that cites an "
                         "archived entry for a name ('the decrease of balo68 entered in item 320 ... reversed') gets what "
                         "that entry says about the name shown in the notes request itself (off by default)")
    ap.add_argument("--notes-scan", help="with --notes-checks count or near: read only the tool results and user messages "
                                         "matching this regular expression for mentions and stated numbers")
    ap.add_argument("--think-cap", type=int, default=0, metavar="TOKENS",
                    help="send a call that may think with max_tokens cut to this first; a reply that spent it all on "
                         "thinking is asked for again without thinking at the client's size, one that was cut inside "
                         "its answer is asked for again in full (0: off)")
    ap.add_argument("--no-empty-retry", action="store_true",
                    help="do not ask again without thinking when a reply comes back empty (for control runs: with a "
                         "window larger than the client ever fills and --effort, the proxy then only sets the effort)")
    ap.add_argument("--max-recalls", type=int, default=8,
                    help="archive searches the model may make within one client call before it is asked to go on "
                         "(with in-place notes little is in view, and a turn with several questions needs more: 24)")
    ap.add_argument("--notes-upstream", help="a separate keeper model's server for the notes calls (no trailing /v1); "
                                             "default: the model server itself, which then reuses its own prefix cache")
    ap.add_argument("--notes-model", help="model name to send to the keeper's server")
    ap.add_argument("--notes-system", help="with --notes-upstream: the keeper's system message (text, or @file)")
    ap.add_argument("--notes-kwargs", help="with --notes-upstream: chat_template_kwargs for the keeper, as JSON")
    ap.add_argument("--notes-extra", help="with --notes-upstream: more fields for the keeper's requests, as JSON (e.g. "
                    "'{\"thinking_budget_tokens\": 0}' turns thinking off on llama.cpp for a model whose template "
                    "always starts it, such as LFM2.5)")
    ap.add_argument("--notes-prefill", action="store_true",
                    help="with --notes-upstream: start the keeper's reply with the layout's first heading, so that "
                         "it writes notes and does not carry on the agent's work (llama.cpp continues a final "
                         "assistant message by itself; vLLM needs --notes-extra "
                         "'{\"continue_final_message\": true, \"add_generation_prompt\": false}')")
    ap.add_argument("--notes-prepass", type=int, default=0, metavar="CHARS",
                    help="with --notes-upstream: tool results longer than this are cut down for the keeper to their "
                         "start, end and the lines that look like outcomes or instructions (0: off)")
    ap.add_argument("--notes-async", choices=("wait", "defer"),
                    help="with --notes-mode inplace: make the next request's notes call right after a reply, in the "
                         "background; wait = the next request waits for it, defer = goes on with the current view "
                         "while it runs and the cut follows when it is done")
    ap.add_argument("--inplace-fit", action="store_true",
                    help="with --notes-mode inplace: lower --inplace-tokens to 3/4 of the room the window leaves, so "
                         "that a small window still takes its notes in place (cheap) instead of rewriting them in full")
    ap.add_argument("--prewarm", action="store_true",
                    help="with --notes-async: after the notes, have the server read the start of the view the cut "
                         "will leave, so that the first request after it finds it in the prefix cache")
    ap.add_argument("--log-calls", action="store_true", help="write every call to a model server to calls.jsonl")
    ap.add_argument("--state-dir", type=Path, default=Path.home() / ".cache" / "ctxkeeper")
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--upstream-retries", type=int, default=0,
                    help="when the model server fails a call (no answer, or HTTP 5xx), wait for it to answer again "
                         "and send the same call again, this many times at most (default 0: pass the failure on)")
    ap.add_argument("--upstream-wait", type=float, default=900,
                    help="with --upstream-retries: seconds to wait for a failed model server to answer its health "
                         "check again before giving up (default 900: a restart of a large model and its warm-up)")
    ap.add_argument("--recipe", choices=sorted(RECIPES),
                    help="measured settings to start from (agent: any OpenAI-compatible server; qwen: Qwen3.x on vLLM, "
                         "fastest); options given on the command line still win")
    ap.add_argument("--version", action="version", version=f"ctxkeeper {__version__}")
    first, _ = ap.parse_known_args()
    if first.recipe:
        ap.set_defaults(**RECIPES[first.recipe])
    a = ap.parse_args()
    upstream = a.upstream.rstrip("/")
    keeper_url = a.notes_upstream.rstrip("/") if a.notes_upstream else None
    system = a.notes_system
    if system and system.startswith("@"):
        system = Path(system[1:]).read_text()
    def ask_upstream(base: str):
        if a.upstream_retries <= 0:
            return lambda body: post_json(base + "/v1/chat/completions", body, a.timeout)
        return lambda body: post_json_retrying(base + "/v1/chat/completions", body, a.timeout, a.upstream_retries,
                                               a.upstream_wait, base + "/health",
                                               log=lambda m: print(m, file=sys.stderr, flush=True))

    keeper = Keeper(ask_upstream(upstream), a.state_dir,
                    budget=a.budget, target_ratio=a.target_ratio, headroom=a.headroom, notes_cap=a.notes_cap,
                    notes_max_tokens=a.notes_max_tokens,
                    notes_thinking={"on": True, "off": False, "unset": None}[a.notes_thinking],
                    recite=not a.no_recite, reply_reserve=a.reply_reserve, recite_when=a.recite_when,
                    think_when=a.think_when, effort=a.effort, memory_note=not a.no_memory_note,
                    think_until=a.think_until, repeat_limit=a.repeat_limit, notes_mode=a.notes_mode,
                    inplace_tokens=a.inplace_tokens, notes_checks=a.notes_checks, notes_scan=a.notes_scan,
                    max_recalls=a.max_recalls, recall_label=a.recall_label, recall_unit=a.recall_unit,
                    empty_retry=not a.no_empty_retry, think_cap=a.think_cap,
                    ask_notes=ask_upstream(keeper_url) if keeper_url else None,
                    notes_model=a.notes_model, notes_system=system,
                    notes_kwargs=json.loads(a.notes_kwargs) if a.notes_kwargs else None, notes_prepass=a.notes_prepass,
                    notes_extra=json.loads(a.notes_extra) if a.notes_extra else None, notes_prefill=a.notes_prefill,
                    notes_async=a.notes_async, prewarm=a.prewarm, log_calls=a.log_calls, inplace_fit=a.inplace_fit,
                    lookups=a.lookups, rule_scan=a.rule_scan, hold_open=a.hold_open,
                    notes_upto=a.notes_upto, sum_check=a.sum_check, cited_entries=a.cited_entries)
    server = ThreadingHTTPServer((a.host, a.port), make_handler(keeper, upstream, a.timeout))
    print(f"ctxkeeper {__version__}" + (f" (recipe {a.recipe})" if a.recipe else "")
          + f": http://{a.host}:{a.port}/v1 -> {upstream}/v1, live window {a.budget} tokens, notes {a.notes_mode}"
          + (f" every {a.inplace_tokens} tokens{' (or less, to fit the window)' if a.inplace_fit else ''}, checks {a.notes_checks}"
             if a.notes_mode == "inplace" else "")
          + (f", notes by {keeper_url}" if keeper_url else "") + (f", notes {a.notes_async} in the background" if a.notes_async else "")
          + f", state in {a.state_dir}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
