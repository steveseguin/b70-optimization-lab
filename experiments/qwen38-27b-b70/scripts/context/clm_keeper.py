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
from typing import Any

import litellm

from clm_harness.clm_agent import harness as _h
from clm_harness.utils.lm_compat import token_cap_key

import clm_baselines as _cb
from clm_baselines import TruncateAgent

logger = logging.getLogger(__name__)

ARCH = "/tmp/.live_ctx/archive"
RECALL_SRC = Path(__file__).with_name("recall.py")
PIN_HEAD = "[[NOTES kept by the harness: {n} earlier turns are in the archive (search it with `recall`)]]"
PIN_RE = re.compile(r"\[\[NOTES kept by the harness: (\d+) earlier turns")
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
    of the stream, a refusal or an error, when the last command failed, or before any tool output exists. A routine
    fetch of the next item is answered without thinking."""
    last_tool = next((i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "tool"), -1)
    if last_tool < 0:
        return True
    tail = [str(m.get("content") or "") for m in messages[last_tool:]]
    if any(QUESTION.search(t) for t in tail):
        return True
    codes = re.findall(r"\(exit_code=(-?\d+)\)", tail[0])
    return bool(codes and codes[-1] != "0")


ANSWERS = "/app/answers.json"


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
        res = await super().step(command, messages, environment=environment, pending=pending)
        got = split_items(getattr(res.result, "stdout", "") or "")
        if got:
            a = self.agent
            if ONLY_NEXT.fullmatch(command or ""):
                a._delivered.update(got)
            else:   # `next && something`: the last item's text would run on into the other command's output
                a._mixed.update(got)
            a._largest_delivery = max(a._largest_delivery, self.budget.count([{"role": "tool", "content": res.stdout_block}]))
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
        await self._agent._keep(environment, messages)
        if self._agent.recite_rules:
            note = recital(self._agent.notes, messages)
            if note:
                messages.append(note)
                self._agent.n_recitals += 1
        return r


class KeeperAgent(TruncateAgent):
    """Sliding window + archive of the cut items + NOTES rewritten at each cut + `recall` (see the module docstring)."""

    calls_file = "keeper_calls.json"

    @staticmethod
    def name() -> str:
        return "keeper"

    def __init__(self, *args: Any, notes_max_tokens: int | str = 2048, notes_call_max_tokens: int | str = 4096,
                 notes_thinking: Any = False, thinking_policy: str = "always", recite_rules: Any = True,
                 keep_headroom: int | str = 1024, **kwargs: Any) -> None:
        kwargs.setdefault("truncate_target_ratio", 0.6)   # cut deeper than W32 (0.75): fewer cuts, fewer notes calls
        super().__init__(*args, **kwargs)
        # A delivered item is never cut on arrival (the budget's newest-output cap head/tail-truncates whatever does
        # not fit, which is how W32 loses text near its limit); instead the cut is made early enough to leave room
        # for the largest delivery seen plus keep_headroom, and the archive is written from what `next` printed.
        self.keep_headroom, self._largest_delivery, self._delivered = int(keep_headroom), 0, {}
        self._mixed: dict[int, str] = {}              # items delivered by a command that printed something else too
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
        await environment.exec(
            command=f"mkdir -p {ARCH} && touch {ARCH}/.on && "
                    "cat > /usr/local/bin/recall <<'RECALL_EOF'\n" + RECALL_SRC.read_text() + "\nRECALL_EOF\n"
                    "chmod +x /usr/local/bin/recall", timeout_sec=60)

    def _pin(self, n: int) -> dict[str, Any]:
        return {"role": "user", "content": PIN_HEAD.format(n=n) + "\n" + (self.notes or "(no notes yet)")}

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
                    n += 1
                else:
                    self.n_archive_failed += 1
        return n

    def _notes_call(self, req: list[dict[str, Any]]):
        model = self.model_name or ""
        kw: dict[str, Any] = {"model": model, "messages": req, token_cap_key(model): self.notes_call_max_tokens,
                              "api_base": self.api_base, "timeout": _h._LLM_TIMEOUT_SECONDS, "num_retries": 2,
                              "drop_params": True}
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        if self.top_p is not None:
            kw["top_p"] = self.top_p
        if self.send_chat_template_kwargs:
            kw["extra_body"] = {"chat_template_kwargs": {"enable_thinking": self.notes_thinking}}
        self.n_lm_calls += 1
        self.n_notes_calls += 1
        try:
            return litellm.completion(**kw)
        except Exception as exc:
            logger.warning("keeper: notes call failed: %s: %s", type(exc).__name__, exc)
            return exc

    async def _keep(self, environment: Any, messages: list[dict[str, Any]]) -> None:
        limit = self._budget.strict_target
        if not limit:
            return
        before = self._budget.count(messages)
        if before <= min(self.trigger_ratio * limit, limit - self._largest_delivery - self.keep_headroom):
            return
        start, prev = self._head(messages)
        head, body = messages[:self._protect], messages[start:]
        starts = [k for k, m in enumerate(body) if m.get("role") == "assistant"]
        if starts and starts[0] > 0:
            starts.insert(0, 0)                       # leading non-assistant messages count as one turn
        target, n, keep = int(self.target_ratio * limit), 0, body
        for cut in starts[1:]:                        # never the newest turn
            if self._budget.count(head + [self._pin(prev + n)] + keep) < target:
                break
            n += 1
            keep = body[cut:]
        if not n:
            return
        gone = body[:len(body) - len(keep)]
        rec: dict[str, Any] = {"reason": "keep", "turns_dropped": n, "before": before,
                               "items_archived": await self._archive(environment, gone)}
        self.n_items_archived += rec["items_archived"]
        req = head + [{"role": "user", "content": NOTES_REQUEST.format(
            cap=self.notes_max_tokens, notes=self.notes or "(none yet)", turns=render_turns(gone))}]
        self._snap(req, "keeper")
        rec.update(notes_prompt_tokens=0, notes_completion_tokens=0, notes_attempts=0)
        for attempt in (1, 2):                        # an empty, failed or oversized reply is asked for once more
            rec["notes_attempts"] = attempt
            resp = await asyncio.to_thread(self._notes_call, req)
            if isinstance(resp, Exception):
                rec["notes_error"] = f"{type(resp).__name__}: {resp}"
                continue
            usage, text = getattr(resp, "usage", None), from_rules((resp.choices[0].message.content or "").strip())
            rec["notes_prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
            rec["notes_completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
            rec["notes_finish"] = resp.choices[0].finish_reason
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
        messages[:] = head + [self._pin(prev + n)] + keep
        rec["after"] = self._budget.count(messages)
        self._record(rec)

    async def run(self, instruction, environment, context) -> None:
        saved = _cb.BASELINE_SYSTEM
        if "{{finish_instructions}}" not in saved:
            raise RuntimeError("clm_keeper: BASELINE_SYSTEM changed; update the Memory section's anchor")
        _cb.BASELINE_SYSTEM = saved.replace("{{finish_instructions}}", MEMORY_NOTE + "\n{{finish_instructions}}")
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
                    "answers_put_back": self.n_answers_put_back,
                    "items_not_archived_mixed_output": self.n_not_archived_mixed,
                    "notes_max_tokens": self.notes_max_tokens, "target_ratio": self.target_ratio,
                    "largest_delivery_tokens": self._largest_delivery, "keep_headroom": self.keep_headroom}, indent=1) + "\n")
            except Exception:
                pass
