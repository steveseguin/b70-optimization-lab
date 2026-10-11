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

Everything else (`/v1/models`, `/health`, `/v1/completions`, ...) is passed through untouched.

  ctxkeeper.py --upstream http://127.0.0.1:18196 --port 18200 --budget 32768

Standard library only. State (archive, notes) is kept per conversation under --state-dir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PIN_HEAD = "[[NOTES kept by the context keeper: {n} earlier messages are in the archive (search it with the `recall` tool)]]"
RECITE_HEAD = "[[RULES in force (from NOTES); apply every one that covers this before you answer]]"
MEMORY_NOTE = """

## Memory

- This conversation may be long. Older turns are moved out of view automatically; you do not manage that.
- When that has happened, a NOTES message near the top holds the standing RULES stated so far and the current STATE.
  Read the RULES before you answer or act, and apply every one that covers what you are doing.
- Everything moved out of view is kept verbatim in an archive. The `recall` tool searches it; you may call it in
  addition to any other tool whenever something you need is no longer in view."""
RECALL_TOOL = {
    "type": "function",
    "function": {
        "name": "recall",
        "description": ("Search the archive of earlier conversation that was moved out of view (it is kept verbatim). "
                        "Give `pattern` (text or a regular expression, case-insensitive) to list matching sentences "
                        "with their message numbers; narrow with `before` / `after` (message numbers) and take the "
                        "newest with `last`. Give `message` alone to print one archived message in full. Give "
                        "`notes_at` alone (a message number) to see the NOTES as they stood at the last save at or "
                        "before that message: what was true then, not now."),
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}, "before": {"type": "integer"}, "after": {"type": "integer"},
            "last": {"type": "integer"}, "message": {"type": "integer"}, "notes_at": {"type": "integer"}}},
    },
}
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
RECALL_LIMIT_NOTE = ("[[That was the last archive search for this turn ({n} made). Do not call `recall` again now: "
                     "act or answer with what you have. You can search again on a later turn.]]")
REPEAT_NOTE = ("[[You have made the same tool call {n} times in a row with the same result. Calling it again will not "
               "change anything: use the result you have and decide the next step.]]")
LAYOUT_RETRY = ("Your reply did not use the layout. Reply with the NOTES only: first line RULES, then the rules, "
                "then a line STATE, then the state, then a line OPEN.")


# ------------------------------------------------------------------ notes (pure)
def section_of(line: str) -> str:
    """RULES, STATE or OPEN if the line is that heading (plain, with a colon, or as a markdown heading), else ''."""
    head = line.strip().strip("#*_ ").rstrip(":").strip("*_ ").upper()
    return head if head in ("RULES", "STATE", "OPEN") else ""


def from_rules(text: str) -> str:
    """The reply from its RULES heading on (models often open with a sentence of their own)."""
    lines = text.splitlines()
    at = next((i for i, ln in enumerate(lines) if section_of(ln) == "RULES"), None)
    return text if at is None else "\n".join(lines[at:]).strip()


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


def keep_rules(old: str, new: str) -> tuple[str, list[str]]:
    """`new` with every RULES line of `old` that it lost put back at the top of its RULES section."""
    norm = lambda s: " ".join(s.split())            # exact words and case; only spacing may differ
    have = {norm(r) for r in rule_lines(new)}
    lost = [r for r in rule_lines(old) if norm(r) not in have]
    if not lost:
        return new, []
    lines = new.splitlines()
    at = next((i for i, ln in enumerate(lines) if section_of(ln) == "RULES"), None)
    if at is None:
        lines, at = ["RULES"] + lines, 0
    lines[at + 1:at + 1] = lost
    return "\n".join(lines), lost


# ------------------------------------------------------------------ messages (pure)
def with_memory_note(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The conversation with the Memory paragraph at the end of its system message (added once, always the same
    text, so the start of the prompt never changes). A conversation without a system message gets one."""
    if messages and messages[0].get("role") in ("system", "developer") and isinstance(messages[0].get("content"), str):
        if MEMORY_NOTE.strip() in messages[0]["content"]:
            return messages
        return [dict(messages[0], content=messages[0]["content"] + MEMORY_NOTE)] + messages[1:]
    return [{"role": "system", "content": MEMORY_NOTE.strip()}] + messages


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


def render_turns(turns: list[dict[str, Any]]) -> str:
    return "\n".join(f"{str(m.get('role', '?')).upper()}: {text_of(m)}" for m in turns)


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
    """Append-only, verbatim. One JSON line per archived message: {"n": number in the conversation, "role", "text"}."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()

    def add(self, first_number: int, messages: list[dict[str, Any]]) -> None:
        with self.lock, self.path.open("a") as f:
            for k, m in enumerate(messages):
                f.write(json.dumps({"n": first_number + k, "role": m.get("role"), "text": text_of(m)}) + "\n")

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.lock:
            return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def recall(self, pattern: str | None = None, before: int | None = None, after: int | None = None,
               last: int | None = None, message: int | None = None, limit: int = 40) -> str:
        rows = self.rows()
        if message is not None:
            hit = [r for r in rows if r["n"] == message]
            return (f"message {message} ({hit[0]['role']}):\n{hit[0]['text']}" if hit else
                    f"recall: message {message} is not in the archive (it holds {len(rows)} messages"
                    + (f", numbers {rows[0]['n']}-{rows[-1]['n']})" if rows else ")"))
        if not pattern:
            return "recall: give `pattern`, or `message` for one archived message in full"
        try:
            rx = re.compile(pattern, re.I)
        except re.error:
            rx = re.compile(re.escape(pattern), re.I)
        hits = []
        for r in rows:
            if (before is not None and r["n"] > before) or (after is not None and r["n"] < after):
                continue
            for s in re.split(r"(?<=[.!?])\s+|\n+", r["text"]):
                if s.strip() and rx.search(s):
                    hits.append(f"message {r['n']} ({r['role']}): {s.strip()[:300]}")
        if not hits:
            return f"recall: nothing in the archive matches {pattern!r}"
        shown = hits[-last:] if last else hits[:limit]
        note = ("" if len(shown) == len(hits) else
                f"\n[{len(hits)} matches; showing the {'last' if last else 'first'} {len(shown)}. Narrow with "
                f"`before` / `after`, or take the newest with `last`]")
        return "\n".join(shown) + note


# ------------------------------------------------------------------ one conversation
class Session:
    def __init__(self, root: Path, key: str) -> None:
        self.dir = root / key
        self.dir.mkdir(parents=True, exist_ok=True)
        self.archive = Archive(self.dir / "archive.jsonl")
        self.lock = threading.Lock()
        self.state = {"cut": 0, "notes": "", "boundary": "", "ratio": 3.6, "cuts": 0, "rules_put_back": 0,
                      "notes_failed": 0, "recalls": 0, "largest_turn": 0}
        f = self.dir / "state.json"
        if f.exists():
            self.state.update(json.loads(f.read_text()))

    def log_event(self, record: dict[str, Any]) -> None:
        """Things worth finding later (a rejected notes call, a restart) go to events.jsonl in the session folder."""
        with (self.dir / "events.jsonl").open("a") as f:
            f.write(json.dumps(dict(record, at=round(time.time(), 1))) + "\n")

    def log_notes(self, upto: int) -> None:
        """Every accepted NOTES version is kept with the number of the last message it covers."""
        with (self.dir / "notes-history.jsonl").open("a") as f:
            f.write(json.dumps({"upto": upto, "at": round(time.time(), 1), "notes": self.state["notes"]}) + "\n")

    def notes_at(self, n: int) -> str:
        f = self.dir / "notes-history.jsonl"
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
        older = [r for r in rows if r["upto"] <= n]
        if not older:
            return (f"recall: no NOTES were saved at or before message {n}"
                    + (f" (the first save covers messages up to {rows[0]['upto']})" if rows else " (none saved yet)"))
        r = older[-1]
        later = "" if r["upto"] == n else (f" Anything said in messages {r['upto'] + 1}-{n} is not in them: "
                                           f"search those with `pattern`, `after` {r['upto'] + 1} and `before` {n}.")
        return f"NOTES as saved after message {r['upto']}.{later}\n{r['notes']}"

    def restart(self) -> None:
        stamp = f"{time.strftime('%Y%m%dT%H%M%S')}-{self.state['cuts']}"
        if (self.dir / "notes-history.jsonl").exists():
            (self.dir / "notes-history.jsonl").rename(self.dir / f"notes-history-until-{stamp}.jsonl")
        if self.archive.path.exists():
            self.archive.path.rename(self.dir / f"archive-until-{stamp}.jsonl")
        self.log_event({"event": "new conversation: the history no longer contains what was archived", "set_aside": stamp})
        self.state.update(cut=0, notes="", boundary="", cuts=0, largest_turn=0, restarts=self.state.get("restarts", 0) + 1)
        self.save()

    def save(self) -> None:
        tmp = self.dir / "state.json.tmp"
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.dir / "state.json")


def fingerprint(messages: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps([[m.get("role"), text_of(m)] for m in messages]).encode()).hexdigest()[:16]


class Keeper:
    """The policy. `ask(body) -> response dict` talks to the model server."""

    def __init__(self, ask, state_dir: Path, budget: int = 32768, target_ratio: float = 0.6, headroom: int = 2048,
                 notes_cap: int = 2048, notes_max_tokens: int = 8192, notes_thinking: bool | None = True,
                 recite: bool = True, max_recalls: int = 8, reply_reserve: int = 4096,
                 recite_when: str | None = None, think_when: str | None = None, effort: str | None = None,
                 memory_note: bool = True, think_until: str | None = None, repeat_limit: int = 3) -> None:
        self.ask, self.root = ask, Path(state_dir)
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
        self.sessions: dict[str, Session] = {}
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

    def learn(self, s: Session, sent: list[dict[str, Any]], response: dict[str, Any]) -> None:
        """Characters per token, from the server's own count. Only sizeable prompts teach (on a short one the tool
        schemas and the chat template dominate), a step moves the ratio by a fifth, and it stays between 2.5 and 6."""
        pt = ((response.get("usage") or {}).get("prompt_tokens")) or 0
        if pt > 2000:
            r = min(max(chars_of(sent) / pt, 2.5), 6.0)
            s.state["ratio"] = round(0.8 * s.state["ratio"] + 0.2 * r, 4)

    def pin(self, s: Session) -> dict[str, Any]:
        return {"role": "user", "content": PIN_HEAD.format(n=s.state["cut"]) + "\n" + (s.state["notes"] or "(no notes yet)")}

    def view(self, s: Session, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        h = head_length(messages)
        if not s.state["cut"]:
            return list(messages)
        return messages[:h] + [self.pin(s)] + messages[h + s.state["cut"]:]

    def notes_call(self, s: Session, model: Any, head: list[dict[str, Any]], gone: list[dict[str, Any]], upto: int = 0) -> None:
        req = head + [{"role": "user", "content": NOTES_REQUEST.format(
            cap=self.notes_cap, notes=s.state["notes"] or "(none yet)", turns=render_turns(gone))}]
        thinking = self.notes_thinking
        for attempt in (1, 2):
            body: dict[str, Any] = {"model": model, "messages": req, "max_tokens": self.notes_max_tokens, "temperature": 0}
            if thinking is not None:
                body["chat_template_kwargs"] = {"enable_thinking": bool(thinking)}
            if self.effort:                           # the same effort as every other call: without it a Qwen notes
                body.setdefault("chat_template_kwargs", {})["reasoning_effort"] = self.effort   # call thinks at full effort
            why, text, finish = "", "", None
            try:
                resp = self.ask(body)
                choice = (resp.get("choices") or [{}])[0]
                finish = choice.get("finish_reason")
                text = from_rules(str((choice.get("message") or {}).get("content") or "").strip())
            except Exception as exc:
                why = f"{type(exc).__name__}: {exc}"
            size = self.tokens(s, [{"role": "user", "content": text}]) if text else 0
            if not why:
                why = ("empty reply" if not text else "no RULES / STATE layout" if not has_layout(text)
                       else f"{size} tokens, over twice the cap" if size > 2 * self.notes_cap else "")
            if not why:
                text, lost = keep_rules(s.state["notes"], text)
                s.state["rules_put_back"] += len(lost)
                s.state["notes"] = text
                s.log_notes(upto)
                return
            s.log_event({"event": "notes call rejected", "attempt": attempt, "why": why, "finish_reason": finish,
                         "thinking": thinking, "upto": upto, "reply_start": text[:160]})
            # ask once more: with the model's own reply and a correction if it wrote something, and without thinking
            # (a reply cut off or emptied by a long think is the usual reason for nothing usable coming back)
            if text:
                req = req + [{"role": "assistant", "content": text}, {"role": "user", "content": LAYOUT_RETRY}]
            if thinking:
                thinking = False
        s.state["notes_failed"] += 1                 # the cut still happens: the turns are in the archive

    def keep(self, s: Session, model: Any, messages: list[dict[str, Any]]) -> None:
        """Cut, archive and take notes if the view no longer leaves room for a reply and one more large turn."""
        h = head_length(messages)
        # A history that no longer contains what was archived (the client rewrote it, or started the same task again)
        # is a new conversation: notes and cut start over, and the old archive is set aside, not searched.
        if s.state["cut"] and (len(messages) < h + s.state["cut"]
                               or fingerprint(messages[h + s.state["cut"] - 1:h + s.state["cut"]]) != s.state["boundary"]):
            s.restart()
        view = self.view(s, messages)
        limit = self.budget - self.reply_reserve
        if self.tokens(s, view) <= limit - max(s.state["largest_turn"], 0) - self.headroom:
            return
        body = messages[h + s.state["cut"]:]
        fixed = messages[:h] + [self.pin(s)]
        n = choose_cut(body, lambda kept: self.tokens(s, fixed + kept), int(self.target_ratio * limit))
        if not n:
            return
        gone = body[:n]
        s.archive.add(h + s.state["cut"] + 1, gone)
        self.notes_call(s, model, messages[:h], gone, upto=h + s.state["cut"] + n)
        s.state["cut"] += n
        s.state["boundary"] = fingerprint(gone[-1:])
        s.state["cuts"] += 1
        s.save()

    def complete(self, body: dict[str, Any], header: str | None = None) -> dict[str, Any]:
        """One chat completion through the keeper. Returns the server's response for the client."""
        s = self.session(body, header)
        with s.lock:
            messages = list(body.get("messages") or [])
            if self.memory_note:
                messages = with_memory_note(messages)
            if messages:
                s.state["largest_turn"] = max(s.state["largest_turn"], self.tokens(s, messages[-1:]))
            self.keep(s, body.get("model"), messages)
            view = self.view(s, messages)
            newest = text_of(messages[-1]) if messages else ""
            from_user = bool(messages) and messages[-1].get("role") == "user"
            asked = from_user or bool(self.recite_when and self.recite_when.search(newest))
            if self.recite and asked and rule_lines(s.state["notes"]):
                view.append({"role": "user", "content": RECITE_HEAD + "\n" + "\n".join("- " + r for r in rule_lines(s.state["notes"]))})
            stuck = self.repeat_limit and repeats(messages) >= self.repeat_limit
            if stuck:
                view.append({"role": "user", "content": REPEAT_NOTE.format(n=repeats(messages))})
                s.state["repeats_broken"] = s.state.get("repeats_broken", 0) + 1
            out = dict(body, messages=view, stream=False)
            if self.think_when is not None or self.effort or stuck:
                ctk = dict(body.get("chat_template_kwargs") or {})
                if self.think_when is not None:
                    h = head_length(messages)
                    ctk["enable_thinking"] = (from_user or bool(self.think_when.search(newest)) or bool(stuck) or (
                        self.think_until is not None and question_open(messages[h + s.state["cut"]:], self.think_when, self.think_until)))
                elif stuck:
                    ctk["enable_thinking"] = True
                if self.effort:
                    ctk["reasoning_effort"] = self.effort
                out["chat_template_kwargs"] = ctk
            if s.state["cut"] or self.memory_note:   # with the note the tool is there from the start (a stable prompt)
                out["tools"] = list(body.get("tools") or []) + [RECALL_TOOL]
            resp: dict[str, Any] = {}
            for round_ in range(self.max_recalls + 1):
                if round_ == self.max_recalls:
                    # The budget of searches for one turn is used up. The client must never be handed a `recall` call
                    # (it does not know the tool): ask once more without it, and say why.
                    out = dict(out, messages=out["messages"] + [{"role": "user", "content": RECALL_LIMIT_NOTE.format(n=self.max_recalls)}],
                               tools=[t for t in out.get("tools") or [] if t is not RECALL_TOOL])
                    if not out["tools"]:
                        out.pop("tools")
                    s.state["recall_limit_hit"] = s.state.get("recall_limit_hit", 0) + 1
                resp = self.ask(out)
                self.learn(s, out["messages"], resp)
                msg = ((resp.get("choices") or [{}])[0].get("message") or {})
                calls = msg.get("tool_calls") or []
                mine = [c for c in calls if ((c.get("function") or {}).get("name")) == "recall"]
                if not mine:
                    break
                if round_ == self.max_recalls:      # it asked anyway: the client gets the words without the call
                    msg["tool_calls"] = [c for c in calls if c not in mine] or None
                    break
                if len(mine) < len(calls):          # mixed with the client's own tools: hand those over, drop ours
                    msg["tool_calls"] = [c for c in calls if c not in mine]
                    break
                results = []
                for c in mine:
                    try:
                        args = json.loads((c.get("function") or {}).get("arguments") or "{}")
                        if args.get("notes_at") is not None:
                            text = s.notes_at(int(args["notes_at"]))
                        else:
                            text = s.archive.recall(**{k: args[k] for k in ("pattern", "before", "after", "last", "message") if args.get(k) is not None})
                    except Exception as exc:
                        text = f"recall: bad arguments ({exc})"
                    s.state["recalls"] += 1
                    results.append({"role": "tool", "tool_call_id": c.get("id"), "content": text})
                out = dict(out, messages=out["messages"] + [msg] + results)
            s.save()
            return resp


# ------------------------------------------------------------------ HTTP
def post_json(url: str, body: dict[str, Any], timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def as_stream(resp: dict[str, Any]) -> bytes:
    """A finished completion as the server-sent events a streaming client expects (one chunk, then [DONE])."""
    choices = []
    for c in resp.get("choices") or []:
        m = c.get("message") or {}
        delta = {k: m[k] for k in ("role", "content", "reasoning_content") if m.get(k) is not None}
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
            data = self.rfile.read(int(self.headers.get("Content-Length") or 0))
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
    ap.add_argument("--notes-thinking", choices=("on", "off", "unset"), default="on",
                    help="chat_template_kwargs.enable_thinking for the notes call (unset: do not send the field)")
    ap.add_argument("--no-recite", action="store_true", help="do not repeat the RULES after a new user message")
    ap.add_argument("--recite-when", help="also repeat the RULES when the newest message matches this regular expression")
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
    ap.add_argument("--state-dir", type=Path, default=Path.home() / ".cache" / "ctxkeeper")
    ap.add_argument("--timeout", type=float, default=1800)
    a = ap.parse_args()
    upstream = a.upstream.rstrip("/")
    keeper = Keeper(lambda body: post_json(upstream + "/v1/chat/completions", body, a.timeout), a.state_dir,
                    budget=a.budget, target_ratio=a.target_ratio, headroom=a.headroom, notes_cap=a.notes_cap,
                    notes_thinking={"on": True, "off": False, "unset": None}[a.notes_thinking],
                    recite=not a.no_recite, reply_reserve=a.reply_reserve, recite_when=a.recite_when,
                    think_when=a.think_when, effort=a.effort, memory_note=not a.no_memory_note,
                    think_until=a.think_until, repeat_limit=a.repeat_limit)
    server = ThreadingHTTPServer((a.host, a.port), make_handler(keeper, upstream, a.timeout))
    print(f"ctxkeeper: http://{a.host}:{a.port}/v1 -> {upstream}/v1, live window {a.budget} tokens, state in {a.state_dir}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
