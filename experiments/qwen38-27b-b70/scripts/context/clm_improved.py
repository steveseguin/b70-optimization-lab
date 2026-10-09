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

v3 (2026-10-05, after the third run):
  8. Stable prompt layout: preserve_thinking=true with earlier thinking stripped (every earlier
     turn renders the same on every call: no "empty-think flip"), mirror edits keep every turn the
     model did not change as the exact original message (_stable_parse), rollback notices are
     appended at the end instead of rewritten in place after the task prefix. improved_stats.json
     records prefix stability per call (prefix_stable / prefix_unstable_no_edit / ..._after_edit,
     mean longest-common-prefix share) and the first unstable call without an edit.
  9. Per-call thinking, thinking_policy = always (default) | judgement (arm B32in; see
     _wants_thinking for the exact rule) | never (arm B32io). With judgement, reasoning_effort=
     medium keeps the system message identical whether thinking is on or off (stable_system).
  Not stable by design: the pinned message moves to the end when STATE.txt/FOLD.py change; any
  turn the model edits; switching thinking on/off when stable_system is off (system line changes);
  the server's last-block re-read (832-token blocks, drafting).

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
from clm_harness.context_env import env as _envmod
from clm_harness.context_utils.context_string import rendered_text, _HEADER_RE, _VALID_ROLES

import litellm

from clm_baselines import _as_bool, _setup_drop_thinking

THINK_BRIDGE = "(Thinking budget reached; acting now.)"
_NEXT_EXTRA: dict[str, Any] = {}
# chat_template_kwargs added to every call (e.g. reasoning_effort, see stable_system)
_CTK_EXTRA: dict[str, Any] = {}
_EXTRA_PATCHED = False


def _install_extra_body_hook() -> None:
    """litellm.completion wrapper: merge one-shot top-level body fields (continue_final_message,
    add_generation_prompt) for the next call only."""
    global _EXTRA_PATCHED
    if _EXTRA_PATCHED:
        return
    orig = litellm.completion

    def completion(*a: Any, **kw: Any) -> Any:
        if _NEXT_EXTRA or _CTK_EXTRA:
            eb = dict(kw.get("extra_body") or {})
            eb.update(_NEXT_EXTRA)
            _NEXT_EXTRA.clear()
            if _CTK_EXTRA:
                ctk = dict(eb.get("chat_template_kwargs") or {})
                ctk.update(_CTK_EXTRA)
                eb["chat_template_kwargs"] = ctk
            kw["extra_body"] = eb
        return orig(*a, **kw)

    litellm.completion = completion
    _EXTRA_PATCHED = True

STATE_PATH = "/tmp/.live_ctx/STATE.txt"
FOLD_PATH = "/tmp/.live_ctx/FOLD.py"
CTXFOLD_SRC = __import__("pathlib").Path(__file__).with_name("ctxfold.py")
RECALL_SRC = __import__("pathlib").Path(__file__).with_name("recall.py")
PIN_TAG = "[[PINNED STATE: this is /tmp/.live_ctx/STATE.txt; edit that file, not this turn]]"

PROTOCOL = """

## Working protocol for streamed data (read carefully)

- Keep everything you will need later in `/tmp/.live_ctx/STATE.txt`. It is part of your context:
  the harness shows its current content (and your FOLD.py) in a pinned message every turn. It is
  NOT a notes file; it counts against your budget like everything else. Keep it compact and exact.
- After each item arrives, fold it into STATE.txt (by a script if the item is machine-readable,
  by reading it yourself if it is not), then delete the raw item from your context.
- For machine-readable items, write `/tmp/.live_ctx/FOLD.py` ONCE, defining
    fold(state: str, lines: list[str]) -> (new_state: str, tally: dict)   # tally = {first word: lines applied}
    selftest() -> list[str]   # asserts on a tiny MADE-UP example covering every kind of line; returns the first words covered
  and fold every item with the command `ctxfold`: it runs your selftest, applies fold() to each
  delivered item still in your context, checks the tally against the item, writes STATE.txt and
  removes the folded item turns from your context. If it says REFUSED, nothing changed: fix FOLD.py
  (edit it, do not re-type the data) and run `ctxfold` again. Do not re-type the fold logic each batch.
- For items you have to read yourself, write the updated STATE.txt with a short inline command and
  delete the item's turn from the mirror file in the same command.
- Before running a command that delivers a large item, make sure there is room for it: the
  harness refuses to run such a command when the item would not fit ("NOT RUN").
- Your earlier thinking is not kept between turns: write anything you must remember into
  STATE.txt. Keep each turn's thinking short; act every turn.
- Write /app/answers.json only after the final item with the questions has arrived, and put in it only
  the counters it asks for (never the whole table). The harness refuses an earlier write or submit. The one
  exception: a PROBE item asks a few questions mid-stream; answer those at once under the keys it gives
  (add to the file, keep every key already in it), then fold the probe item like any other and carry on.
- If STATE.txt plus the next item cannot fit in your budget, you must decide what to drop from
  STATE.txt yourself; anything dropped is lost (answer "" for it), so drop the least useful.
"""


def _stable_parse(text: str, protected: list[dict[str, Any]], originals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map an edited mirror back to messages, keeping every turn the model did NOT change as the
    exact original message dict (same role, content, tool_calls, ids), so it renders byte-for-byte
    as it was sent. The upstream parse_back rebuilds ALL turns as plain role+text, merges
    consecutive same-role turns and turns tool calls into `bash {...}` text, which changed
    already-sent text after every edit (prefix-cache census, 2026-10-05). Turns whose text was
    changed become plain turns exactly as parse_back would make them; tool-call/tool-result pairs
    that lost their partner are flattened to text so the history stays legal."""
    editable = originals[len(protected):]
    matches = list(_HEADER_RE.finditer(text))
    out: list[dict[str, Any]] = [dict(m) for m in protected]
    lead = text[: matches[0].start()].strip() if matches else text.strip()
    if lead:
        out.append({"role": "user", "content": lead})
    for k, mt in enumerate(matches):
        n, role = int(mt.group(1)), mt.group(2).lower()
        role = role if role in _VALID_ROLES else "user"
        end = matches[k + 1].start() if k + 1 < len(matches) else len(text)
        body = text[mt.end():end].strip()
        if not body:
            continue
        orig = editable[n - 1] if 1 <= n <= len(editable) else None
        if orig is not None and orig.get("role") == role and rendered_text(orig).strip() == body:
            out.append(orig)
        else:
            out.append({"role": "assistant" if role == "assistant" else "user", "content": body})
    # keep tool-call pairs legal: an assistant tool call must be followed by its tool result
    fixed: list[dict[str, Any]] = []
    for i, m in enumerate(out):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            ids = {tc.get("id") for tc in m["tool_calls"]}
            nxt = out[i + 1] if i + 1 < len(out) else None
            if not (nxt and nxt.get("role") == "tool" and nxt.get("tool_call_id") in ids):
                m = {"role": "assistant", "content": rendered_text(m)}
        elif m.get("role") == "tool":
            prv = fixed[-1] if fixed else None
            if not (prv and prv.get("role") == "assistant" and prv.get("tool_calls")
                    and m.get("tool_call_id") in {tc.get("id") for tc in prv["tool_calls"]}):
                m = {"role": "user", "content": rendered_text(m)}
        fixed.append(m)
    return fixed


PROTOCOL_READ = """

## Working protocol for streamed data (read carefully)

- Keep every counter in `/tmp/.live_ctx/STATE.txt`, one line per counter: `name value`, or
  `name removed` for a counter removed from the ledger (nothing else in the file). It is part of your
  context: the harness shows it in a pinned message every turn. It is NOT a notes file.
- The reports are prose. Do not write a program to parse them: read each report yourself and work out
  exactly what it changes.
- After each item, in ONE command: apply only the changed counters to STATE.txt with a short inline
  script (for example `python3 - <<'EOF'` holding a dict of new values and the removed names, reading
  and rewriting STATE.txt), then `ctxfold --drop`, which removes the item from your context. It
  refuses (and changes nothing) if a counter the item mentions has no line in STATE.txt.
- Do not edit the mirror file by hand: `ctxfold --drop` removes the items, and the harness keeps the
  rest compact. STATE.txt changes only in the same command as a new item's update; a counter line never
  disappears (`name removed` stays until the counter is opened again, then it becomes `name value`).
- Before running a command that delivers a large item, make sure there is room for it: the harness
  refuses to run such a command when the item would not fit ("NOT RUN").
- Your earlier thinking is not kept between turns. Keep your thinking to what the current item needs;
  act every turn.
- Write /app/answers.json only after the final item with the questions has arrived, and put in it only
  the counters it asks for (never the whole table). The harness refuses an earlier write or submit. The one
  exception: a PROBE item asks a few questions mid-stream; answer those at once under the keys it gives
  (add to the file, keep every key already in it), then fold the probe item like any other and carry on.
"""

PROTOCOL_QUOTED = """

## Working protocol for streamed data (read carefully)

- The harness keeps the counters in `/tmp/.live_ctx/STATE.txt` (`name value`, or `name removed`) and
  shows them in a pinned message every turn. You never write STATE.txt (any other change to it is undone):
  the harness does the arithmetic. You may read it.
- The reports are prose. Do not write a program to parse them: read each report yourself.
- After each item, in ONE command that holds nothing else, send the item's changes as an event list, one
  line per change, in the order they happen in the report:
      ctxfold --events <<'EOF'
      name | op | amount | "exact quote from the report"
      EOF          (the EOF line starts at the beginning of the line, not indented)
  op is one of:
    set     the counter now holds amount (a value given outright, or the corrected value of a correction)
    add     the counter went up by amount
    sub     the counter went down by amount (amount positive)
    remove  the counter was removed from the ledger (leave amount empty: `name | remove | | "..."`)
    reopen  a counter opened (new, or opened again after a removal) with value amount
  amount is written in digits (`-7`, `42`), even when the report spells the number out
  ("minus seven", "forty-two"). The quote is copied exactly from the report (whitespace aside) and is
  the words that state this change. A plan counts only if the report says it went ahead: then quote
  the sentence that says so and give the planned amount. If the item changes nothing, send one line
  `none`. Example (a report saying "abcd12 went down by eighty-three." and "A new page was started for
  efgh34, at minus five."):
      abcd12 | sub | 83 | "abcd12 went down by eighty-three."
      efgh34 | reopen | -5 | "A new page was started for efgh34, at minus five."
- The harness checks every line: the counter name occurs in the report, the quote is verbatim in it, the
  amount is written in the quoted sentence (or in a sentence of the same paragraph that names the
  counter), add/sub/remove need a live counter and reopen a new or removed one (set on a new counter
  counts as reopen), and every counter the report names has a STATE line afterwards. If any line fails, it
  refuses the WHOLE list ("ctxfold: REFUSED (reason): ...") and applies nothing: fix it and send the
  whole list again. On success it applies the events, removes the item from your context and prints
  "ctxfold: applied N events".
- A refusal names the failing line and shows the delivered sentence it should quote: copy that sentence,
  fix only that line, and send the whole list again (do not change a correct amount to get past a check).
- Do not edit the mirror file by hand, and never copy a report or an event list into a note or a file
  (stream text in files voids the run). If a counter name keeps being refused, send the list again with
  the sentence quoted exactly: the harness corrects a misspelled name when the quote shows the right one.
- After the final item arrives, the harness keeps it in the pinned message, so compacting cannot lose the
  questions.
- Before running a command that delivers a large item, make sure there is room for it: the harness
  refuses to run such a command when the item would not fit ("NOT RUN").
- Your earlier thinking is not kept between turns. Keep your thinking to what the current item needs;
  act every turn.
- Write /app/answers.json only after the final item with the questions has arrived, and put in it only
  the counters it asks for (never the whole table). The harness refuses an earlier write or submit. The one
  exception: a PROBE item asks a few questions mid-stream; answer those at once under the keys it gives
  (add to the file, keep every key already in it), then fold the probe item like any other and carry on.
- A question about a counter's value at the end of an earlier item: `recall NAME` lists every archived
  sentence about it with its item number (one short command per counter); apply them in order up to that
  item. Do not answer such a question with the current value.
"""

READ_REASONS = """- In your visible reply (not in your thinking), before the command, write one short line per changed
  counter: `name: old -> new (the words that decide it)`.
"""


class _ImprovedEnv(ContextEnv):
    agent: "ClmImprovedAgent"

    def _apply_edit(self, messages, rendered, read_back, before, limit, edit_rec):
        if not self.agent.stable_mirror:
            return super()._apply_edit(messages, rendered, read_back, before, limit, edit_rec)
        originals = list(messages)
        orig_parse = _envmod.parse_back
        _envmod.parse_back = lambda text, prot: _stable_parse(text, prot, originals)
        try:
            return super()._apply_edit(messages, rendered, read_back, before, limit, edit_rec)
        finally:
            _envmod.parse_back = orig_parse

    async def step(self, command, messages, *, environment, pending=None):
        a = self.agent
        # Repeat guard (2026-10-05, B32in 480K: with thinking off, greedy decoding re-issued `ctxfold`
        # about 150 times on an unchanged context until the step cap; B32ir re-ran an update command):
        # the exact command just run, when no new item has been delivered since, is not run again.
        cmd = (command or "").strip()
        if a.archive and "live_ctx/archive" in cmd and not re.match(r"(recall|ctxfold)\b", cmd):
            a.n_archive_refused += 1
            text = ("NOT RUN: the archive is read-only and kept by the harness; search it with `recall PATTERN` "
                    "or `recall --item N`.")
            res = types.SimpleNamespace(stdout=text, stderr="", return_code=75)
            return StepResult(result=res, ctx_changed=False, stdout_block=text + "\n\n(exit_code=75)",
                              readout="", notes="", exec_time=0.0, touched_ctx=False)
        # Quoted events (arm B32iq): STATE.txt is written only by `ctxfold --events` (any other change is
        # restored by _PinnedState); the other fold commands are not run, and an events command runs alone
        # (just the here-document), so nothing else in that command can touch STATE.txt.
        if a.quoted and (re.search(r"(?:^|[;&|]\s*|\n\s*)ctxfold\b(?!\s+--events)", cmd)
                         or (re.search(r"(?:^|[;&|]\s*|\n\s*)ctxfold\s+--events", cmd)
                             and not _events_cmd_alone(cmd))
                         # d12 rerun: event lists written by python into /tmp/ev22.sh and run with `bash`
                         # (two files holding stream data: VOID)
                         or ("ctxfold --events" in cmd and not _events_cmd_alone(cmd) and _WRITES.search(cmd))
                         or re.search(r"(?:^|[;&|]\s*)(?:bash|sh|source|\.)\s+/(?:tmp|app)/\S+", cmd)):
            a.n_quoted_refused_cmds += 1
            text = ("NOT RUN: in this run the harness keeps STATE.txt; send the item's changes as an event list, "
                    "as a command of its own: `ctxfold --events <<'EOF'`, one `name | op | amount | \"quote\"` line "
                    "per change, then `EOF`, and nothing else in that command. Never write event lists or "
                    "stream text to files (that voids the run); a misspelled counter name is corrected by the "
                    "harness when the quote shows the right one.")
            res = types.SimpleNamespace(stdout=text, stderr="", return_code=75)
            return StepResult(result=res, ctx_changed=False, stdout_block=text + "\n\n(exit_code=75)",
                              readout="", notes="", exec_time=0.0, touched_ctx=False)
        # Answers guard (2026-10-05: B32ir sparse seed 1 and B32in 478K both wrote the WHOLE table to
        # /app/answers.json before the final item with the questions had arrived -> VOID): writing the
        # answers file or submitting is not run until the final item has been delivered.
        if a.answers_guard and not a._final_seen and (
                (ANSWERS in cmd and _WRITES.search(cmd) and not a._asked)
                or cmd == "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"):
            a.n_answers_refused += 1
            text = ("NOT RUN: the final item with the questions has not arrived yet. Fetch it with `next` "
                    "(keep folding items until it comes). /app/answers.json may be written only after it "
                    "(or after a PROBE item, with the keys that item asks for), and only with the counters it asks for.")
            res = types.SimpleNamespace(stdout=text, stderr="", return_code=75)
            return StepResult(result=res, ctx_changed=False, stdout_block=text + "\n\n(exit_code=75)",
                              readout="", notes="", exec_time=0.0, touched_ctx=False)
        if (a.repeat_guard and cmd and cmd == a._last_cmd and a._deliveries == a._deliveries_at_last
                and not a._guard_cmd.search(cmd)):
            a.n_repeats_refused += 1
            text = ("NOT RUN: this is exactly the command you just ran, and no new item has arrived since; "
                    "running it again would change nothing or apply the same changes twice. Decide the next "
                    "step (usually `next` to fetch the next item).")
            res = types.SimpleNamespace(stdout=text, stderr="", return_code=75)
            return StepResult(result=res, ctx_changed=False, stdout_block=text + "\n\n(exit_code=75)",
                              readout="", notes="", exec_time=0.0, touched_ctx=False)
        a._last_cmd, a._deliveries_at_last = cmd, a._deliveries
        # read mode: was an undropped item in the context when this command ran? (STATE.txt may change
        # only then; see _PinnedState)
        a._item_pending = any(m.get("role") == "tool" and re.match(r"ITEM \d+/\d+ \((?!QUERY|GET)", str(m.get("content") or ""))
                              for m in messages if isinstance(m, dict))
        if a._guard_cmd.search(command or ""):
            shown = messages + ([pending] if pending else [])
            now = self.budget.count(shown)
            n_fetch = max(1, len(re.findall(r"(?:^|[;&|]\s*)next\b", command or "")))
            need = a._largest_delivery * n_fetch + a.guard_headroom
            limit = self.budget.strict_target or 0
            if limit and a._largest_delivery and now + need > limit:
                a.n_gate_refusals += 1
                text = (f"NOT RUN: `{command.strip()[:60]}` delivers {n_fetch} item(s) of up to "
                        f"~{a._largest_delivery} tokens each, and only ~{max(limit - now, 0)} of the "
                        f"{limit}-token limit are free (need ~{need} incl. headroom). Fold the "
                        f"newest item into {STATE_PATH} and delete its turn first.")
                res = types.SimpleNamespace(stdout=text, stderr="", return_code=75)
                return StepResult(result=res, ctx_changed=False, stdout_block=text + "\n\n(exit_code=75)",
                                  readout=f"\n[context: ~{now}/{limit} tokens]", notes="",
                                  exec_time=0.0, touched_ctx=False)
        items_before = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "tool"
                           and _ITEM_UPDATE.match(str(m.get("content") or "")))
        res = await super().step(command, messages, environment=environment, pending=pending)
        # any context edit that removed a delivered item counts as a successful fold for the
        # thinking-policy rule (B32in 478K folded with its own script, never via ctxfold, so the rule
        # never saw "ctxfold: folded" and kept thinking on for all 177 calls)
        if res.ctx_changed and sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "tool"
                                   and _ITEM_UPDATE.match(str(m.get("content") or ""))) < items_before:
            a._fold_ok = True
        out0 = getattr(res.result, "stdout", "") or ""
        if _ITEM_PROBE.search(out0):
            a.n_probes_seen += 1
            a._asked = a._asked + re.findall(r"(?m)^ASK (\S+?):", out0)
        if _ITEM_FINAL.search(out0):
            a._final_seen = True
            a._asked = a._asked + re.findall(r"(?m)^(?:QUERY|GET) (\S+)\s*$", out0) + re.findall(r"(?m)^ASK (\S+?):", out0)
            if a.quoted:
                # keep the final item (the questions) in the pinned message: B32iq ret s0 rerun compacted the
                # mirror after two recalls, cut the final item away with it, and left all 12 retention
                # questions blank (final items are never archived, so recall could not bring them back)
                fm = _ITEM_FINAL.search(out0)
                a._final_text = out0[fm.start():].split("\n\n(exit_code=")[0].strip()
        if a.answers_guard and a._asked and ANSWERS in cmd and _WRITES.search(cmd):
            try:
                r = await environment.exec(command="python3 -c 'import json; print(json.dumps(sorted("
                                                   "json.load(open(\"/app/answers.json\")))))'", timeout_sec=30)
                keys = set(json.loads((getattr(r, "stdout", "") or "[]").strip() or "[]"))
                extra, missing = sorted(keys - set(a._asked)), (sorted(set(a._asked) - keys) if a._final_seen else [])
                if extra or missing:
                    a.n_answer_key_notes += 1
                    res.notes += (f"\n[harness: /app/answers.json has {len(extra)} keys that were not asked"
                                  + (f" ({' '.join(extra[:6])}...)" if extra else "")
                                  + (f" and lacks {len(missing)} asked keys ({' '.join(missing[:6])})" if missing else "")
                                  + "; it may contain exactly the asked counters. Rewrite it.]")
            except Exception:
                pass
        out = getattr(res.result, "stdout", "") or ""
        if a._guard_out.search(out):
            a._deliveries += max(1, len(re.findall(r"(?m)^ITEM \d+/\d+ \(", out)))
        if re.match(r"recall\b", cmd):
            a.n_recalls += 1
            a.recall_tokens += self.budget.count([{"role": "tool", "content": res.stdout_block}])
        if res.ctx_changed:
            a._edit_since_call = True
        if out.lstrip().startswith(("ctxfold: folded", "ctxfold: removed items")):
            a._fold_ok = True
        if a.quoted and re.match(r"ctxfold\s+--events\b", cmd):
            m = re.match(r"\s*ctxfold: applied (\d+) events", out)
            if m:
                a._fold_ok = a._harness_wrote = True
                a.n_events_applied += int(m.group(1))
                a.n_event_lists_applied += 1
                if a._event_refused_last:
                    a.n_event_retries += 1
                a._event_refused_last = False
                a._refused_streak = 0
            else:
                r = re.search(r"ctxfold: REFUSED \(([a-z ]+)\)", out)
                if r:
                    a.lists_refused[r.group(1)] = a.lists_refused.get(r.group(1), 0) + 1
                    a._event_refused_last = True
                    a._refused_streak += 1
        if a._guard_out.search(out):
            a._largest_delivery = max(a._largest_delivery,
                                      int(tk.count_tokens([{"role": "tool", "content": out}])[0]
                                          * self.budget.tok_ratio))
        return res


_TEXT_CALL = re.compile(r"(?s)\bbash\s*(\{\s*\"command\"\s*:.*\})\s*$")


def _install_text_call_recovery(agent: Any) -> None:
    """With thinking off the model sometimes writes its action as text (`... bash {"command": "next"}`)
    instead of a tool call, imitating earlier turns that the mirror flattened into text; the harness then
    answered "No tool call" and the call was wasted (77 of 343 calls in B32in 480K). If a reply has no
    tool call but its text ends with such a block that parses as JSON with a "command", it is used as the
    tool call (counted in improved_stats.json: text_calls_recovered)."""
    orig = _h._extract_tool_call
    if getattr(orig, "_recovering", False):
        return

    def extract(msg: dict) -> dict:
        if not msg.get("tool_calls"):
            m = _TEXT_CALL.search(str(msg.get("content") or ""))
            if m:
                try:
                    args = json.loads(m.group(1))
                except Exception:
                    args = None
                if isinstance(args, dict) and isinstance(args.get("command"), str):
                    agent.n_text_calls_recovered += 1
                    msg["content"] = str(msg.get("content") or "")[:m.start()].rstrip()
                    msg["tool_calls"] = [{"id": f"recovered-{agent.n_text_calls_recovered}", "type": "function",
                                          "function": {"name": "bash", "arguments": json.dumps(args)}}]
        return orig(msg)

    extract._recovering = True
    _h._extract_tool_call = extract


ANSWERS = "/app/answers.json"
_WRITES = re.compile(r">|open\(|json\.dump|write|tee\b|cp\b|mv\b")
_ITEM_UPDATE = re.compile(r"ITEM \d+/\d+ \((?!QUERY|GET)")
_ITEM_FINAL = re.compile(r"ITEM \d+/\d+ \((?:QUERY|GET)\)")
_ITEM_PROBE = re.compile(r"ITEM \d+/\d+ \(PROBE\)")   # mid-stream questions (make_sparse_prose_tasks --probes-every)
# Quoting the delimiter is required: an unquoted heredoc executes shell expansions
# before ctxfold runs, allowing side effects even when the command otherwise stands alone.
_EVENTS_CMD = re.compile(r"(?s)\s*ctxfold\s+--events(?:\s+[A-Z]+)*\s*<<-?\s*(['\"])(\w+)\1[ \t]*\n.*?\n?\2\s*$")


def _events_cmd_alone(cmd: str) -> bool:
    """The command is `ctxfold --events <<TERM`, the lines, TERM, and nothing else (TERM once)."""
    m = _EVENTS_CMD.match(cmd)
    return bool(m) and sum(1 for ln in cmd.splitlines() if ln.strip() == m.group(2)) == 1


ARCHIVE_NOTE = """- Every item you drop is kept verbatim in a read-only archive (nothing is lost, only moved out of view).
  `recall PATTERN` prints the archived sentences that match (as `item N: ...`), `recall --item N` prints
  item N. Their output enters your context like any tool output, so search narrowly. Questions about
  earlier items (old values, who did what) are answered from the archive, not from STATE.txt.
"""

FOLD_N_NOTE = """- To save calls, fetch up to {k} items in one command (`{cmd}`) when the room check allows it, then
  fold them all in ONE update (apply the items in order) and drop them together with `ctxfold --drop`.
"""


class _PinnedState:
    """Pre-call hook: re-read STATE.txt, validate it, and show it as the last message."""

    def __init__(self, inner: Any, agent: "ClmImprovedAgent") -> None:
        self._inner, self._agent = inner, agent

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def maybe(self, environment: Any, messages: list[dict[str, Any]]) -> bool:
        a = self._agent
        try:
            r = await environment.exec(command=f"cat {STATE_PATH} 2>/dev/null", timeout_sec=30)
            text = (getattr(r, "stdout", "") or "").strip()
        except Exception:
            text = a._last_state
        try:
            r = await environment.exec(command=f"cat {FOLD_PATH} 2>/dev/null", timeout_sec=30)
            fold = (getattr(r, "stdout", "") or "").strip()
        except Exception:
            fold = a._last_fold
        a._last_fold = fold
        note = ""
        if text != a._last_state:
            bad = a._validate(text)
            if not bad and a.quoted and not a._harness_wrote:
                bad = "STATE.txt is written only by `ctxfold --events`"
            elif not bad and a.quoted:
                pass  # written by the harness from a checked event list
            elif not bad and a.fold_mode == "read":
                # (b) a counter line never just disappears: a removed counter keeps a `name removed` line
                was = set(re.findall(r"(?m)^\s*([a-z]+\d\d)\b", a._last_state))
                now_ = set(re.findall(r"(?m)^\s*([a-z]+\d\d)\b", text))
                gone = sorted(was - now_)
                if gone:
                    bad = f"lines vanished without a `removed` marker: {' '.join(gone[:8])}"
                # (d) STATE.txt changes only together with a delivered item (B32ir 119K: after a drop, with
                # thinking off, it re-applied invented/old changes with no item in context)
                elif not getattr(a, "_item_pending", True):
                    bad = ("STATE.txt changed while no new item was in your context; fetch the next item "
                           "first (corrections of earlier mistakes go into the next item's update)")
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
        a._harness_wrote = False
        content = f"{PIN_TAG}\n{text}{note}"
        if a.quoted and a._final_text:
            content += ("\n--- the final item, kept here by the harness (answer exactly these keys) ---\n"
                        + a._final_text)
        if fold:
            content += f"\n--- {FOLD_PATH} ---\n{fold}"
        # A context edit can merge the pinned message into a neighbouring turn (upstream
        # parse_back merges consecutive same-role turns), which then no longer STARTS with the
        # tag; cut any embedded copy so a stale state never survives in the history.
        for m in messages:
            c = m.get("content") if isinstance(m, dict) else None
            if isinstance(c, str) and PIN_TAG in c and not c.startswith(PIN_TAG):
                m["content"] = c[:c.index(PIN_TAG)].rstrip()
        messages[:] = [m for m in messages
                       if not (isinstance(m, dict) and m.get("content") == "" and m.get("role") == "user")]
        pins = [i for i, m in enumerate(messages)
                if isinstance(m, dict) and str(m.get("content") or "").startswith(PIN_TAG)]
        if len(pins) == 1 and messages[pins[0]].get("content") == content:
            pass  # unchanged: leave it where it is, so the prefix cache stays valid
        else:
            messages[:] = [m for i, m in enumerate(messages) if i not in set(pins)]
            if text or note or fold:
                messages.append({"role": "user", "content": content})
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
                 think_cap: int | str = 0, empty_streak_limit: int | str = 1,
                 fallback_think_cap: int | str = 2048,
                 stable_render: Any = True, stable_mirror: Any = True,
                 thinking_policy: str = "always", stable_system: Any = None,
                 fold_mode: str = "script", read_reasons: Any = False, repeat_guard: Any = True,
                 recover_text_calls: Any = True, answers_guard: Any = True, archive: Any = False,
                 fold_batches: int | str = 1, quoted: Any = False,
                 retry_think_cap: int | str = 2048, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # v3 (2026-10-05): stable prompt layout and per-call thinking
        self.stable_mirror = _as_bool(stable_mirror)
        # fold_mode: script = FOLD.py + ctxfold (machine-readable items); read = the model reads each
        # report itself, writes STATE.txt ("name value" lines, validated) and drops the item with
        # `ctxfold --drop` (prose ledger; ctxfold's first-word coverage check cannot apply to prose and
        # pushed counter names into FOLD.py in the first prose trial)
        self.fold_mode = str(fold_mode or "script").strip().lower()
        self.read_reasons = _as_bool(read_reasons)
        self.repeat_guard = _as_bool(repeat_guard)
        self.answers_guard = _as_bool(answers_guard)
        # quoted events (arm B32iq): the model sends `name | op | amount | "quote"` lines to
        # `ctxfold --events`, which checks the quotes against the delivered text and does the arithmetic;
        # read mode, archive on unless archive is given explicitly as false
        self.quoted = _as_bool(quoted)
        self.retry_think_cap = int(retry_think_cap or 0)
        self.n_retry_capped = 0
        self._refused_streak = 0
        self._final_text = ""
        if self.quoted:
            self.fold_mode = "read"
            if archive is False or archive is None:
                archive = True
        self.n_events_applied = self.n_event_lists_applied = self.n_event_retries = 0
        self.n_quoted_refused_cmds = 0
        self.lists_refused: dict[str, int] = {}
        self._event_refused_last = self._harness_wrote = False
        # archive-on-drop + recall (arm B32ira) and multi-item folding (FOLD_BATCHES)
        self.archive = _as_bool(archive)
        self.fold_batches = max(1, int(fold_batches or 1))
        self.n_archive_refused = self.n_recalls = self.recall_tokens = 0
        self._final_seen, self._asked = False, []
        self.n_probes_seen = 0
        self.n_answers_refused = self.n_answer_key_notes = 0
        self._last_cmd, self._deliveries, self._deliveries_at_last = "", 0, -1
        self._item_pending = True
        self.n_repeats_refused = 0
        self.n_text_calls_recovered = 0
        if _as_bool(recover_text_calls):
            _install_text_call_recovery(self)
        if self.fold_mode == "read" and not state_line_regex:
            state_line_regex = r"^[a-z]+\d\d\s+(-?\d+|removed)$"
        self.thinking_policy = str(thinking_policy or "always").strip().lower()
        if self.thinking_policy not in ("always", "judgement", "never"):
            raise ValueError(f"thinking_policy must be always|judgement|never, not {thinking_policy!r}")
        self._base_thinking = self.enable_thinking
        # The Qwen3.8 template puts a reasoning-effort sentence into the system message only when
        # thinking is on (effort xhigh by default, or low). Switching thinking per call would then
        # change the very first line of the prompt and force a full re-read at every switch.
        # stable_system (default: on for thinking_policy=judgement) sends reasoning_effort=medium,
        # for which the template adds no sentence, so the system message is identical with thinking
        # on or off. Cost: thinking calls lose the "think carefully" xhigh sentence.
        self.stable_system = (self.thinking_policy == "judgement") if stable_system is None \
            else _as_bool(stable_system)
        if self.stable_system:
            _CTK_EXTRA["reasoning_effort"] = "medium"
        self._fold_ok = False
        self._edit_since_call = False
        self._prev_canon: list[str] | None = None
        self._prev_thinking: bool | None = None
        self.pstats = {"calls": 0, "stable": 0, "unstable_no_edit": 0, "unstable_after_edit": 0,
                       "lcp_share_sum": 0.0, "thinking_on": 0, "thinking_off": 0, "thinking_toggles": 0,
                       "first_unstable_no_edit": None}
        self._guard_cmd = re.compile(guard_command_regex)
        self._guard_out = re.compile(guard_output_regex)
        self.guard_headroom = int(guard_headroom)
        self._state_line = re.compile(state_line_regex) if state_line_regex else None
        self.state_max_tokens = int(state_max_tokens)
        self._largest_delivery = 0
        self._last_state = ""
        self._last_fold = ""
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
        self._continuation_broken = ""
        _install_extra_body_hook()
        self._ctx.__class__ = _ImprovedEnv
        self._ctx.agent = self
        self._ckpt = _PinnedState(self._ckpt, self)
        _setup_drop_thinking(self, drop_old_thinking, stable_render)  # strip first, then pin the state
        self._protect_deliveries()
        orig_cap = self._budget.cap_newest_output
        guard = self._guard_out

        def cap_newest_output(messages, tool_content, *, floor=128):
            if guard.search(tool_content or ""):
                return tool_content  # never cut a delivered item; the room check budgets it
            return orig_cap(messages, tool_content, floor=floor)

        self._budget.cap_newest_output = cap_newest_output

    # ---------------- per-call thinking (arms B32in / B32io)
    _JUDGEMENT = ("ctxfold: REFUSED", "NOT RUN", "REJECTED", "Traceback", "This was the last item",
                  "STREAM END", "No tool call in your last turn", "CONTEXT LIMIT", "FINAL turn",
                  "ROLLED BACK", "no unfolded item", "no delivered item", "harness recovered",
                  "keys that were not asked", "asked keys", "has not arrived yet")

    def _wants_thinking(self, messages: list[dict[str, Any]]) -> bool:
        """thinking_policy: always = the agent's enable_thinking; never = off on every call;
        judgement = off on routine calls, on when (in this order):
          1. no `ctxfold` has folded an item yet (FOLD.py not proven), or
          2. the newest tool output, or any harness/user message after it (nudges, rollback and
             final-turn notices, the pinned state with a REJECTED note), contains a judgement
             marker (_JUDGEMENT: a ctxfold refusal, a room-check "NOT RUN", a state rejection,
             a Python traceback, the final item, the stream end, a missing-tool-call notice, a
             budget/rollback notice), or
          3. the newest tool output ended with a non-zero exit code.
        Everything else ("fetch the next item", "fold it") is routine: thinking off."""
        if self.thinking_policy == "never":
            return False
        if self.thinking_policy == "always":
            return bool(self._base_thinking)
        if not self._fold_ok:
            return True
        last_tool = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "tool":
                last_tool = i
                break
        tail = [str(m.get("content") or "") for m in messages[max(last_tool, 0):]] if last_tool >= 0 else \
            [str(m.get("content") or "") for m in messages[-3:]]
        if any(mark in t for t in tail for mark in self._JUDGEMENT):
            return True
        if last_tool >= 0:
            mm = re.findall(r"\(exit_code=(-?\d+)\)", str(messages[last_tool].get("content") or ""))
            if mm and mm[-1] != "0":
                return True
        return False

    def _canon(self, messages: list[dict[str, Any]]) -> list[str]:
        out = []
        for m in messages:
            if str(m.get("content") or "").startswith(PIN_TAG):
                continue
            out.append(json.dumps({k: m.get(k) for k in ("role", "content", "tool_calls", "tool_call_id",
                                                           "reasoning_content")}, sort_keys=True, default=str))
        return out

    def _prefix_stats(self, messages: list[dict[str, Any]], thinking: bool) -> None:
        cur = self._canon(messages)
        p = self.pstats
        p["calls"] += 1
        if self._prev_canon is not None:
            prev = self._prev_canon
            stable = cur[:len(prev)] == prev and (self._prev_thinking == thinking or self.thinking_policy != "judgement")
            a, b = "".join(prev), "".join(cur)
            n = 0
            lim = min(len(a), len(b))
            while n < lim and a[n] == b[n]:
                n += 1
            p["lcp_share_sum"] += n / max(len(a), 1)
            if cur[:len(prev)] == prev:
                p["stable"] += 1
            elif self._edit_since_call:
                p["unstable_after_edit"] += 1
            else:
                p["unstable_no_edit"] += 1
                if p["first_unstable_no_edit"] is None:
                    k = next((i for i in range(min(len(prev), len(cur))) if prev[i] != cur[i]), min(len(prev), len(cur)))
                    p["first_unstable_no_edit"] = {"call": p["calls"], "message": k,
                                                   "prev": prev[k][:160] if k < len(prev) else None,
                                                   "cur": cur[k][:160] if k < len(cur) else None}
            if self._prev_thinking is not None and self._prev_thinking != thinking:
                p["thinking_toggles"] += 1  # the template's system line changes: full re-read
        self._prev_canon, self._prev_thinking = cur, thinking
        self._edit_since_call = False

    async def _query_with_retry(self, model: str, messages: list[dict[str, Any]]) -> Any:
        thinking = self._wants_thinking(messages)
        self.enable_thinking = thinking
        self.pstats["thinking_on" if thinking else "thinking_off"] += 1
        self._prefix_stats(messages, thinking)
        cap = self.think_cap if thinking else 0
        last_tool = next((str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "tool"), "")
        if (self.quoted and thinking and self.retry_think_cap and self._refused_streak in (1, 2)
                and "ctxfold: REFUSED" in last_tool):
            # adaptive retry cap: the call right after a refused event list gets retry_think_cap (2K), after a
            # second refusal in a row 2x that, from the third on the normal cap. Only that call: the d12
            # rerun capped 90 calls at 2K because the flag stayed set through 230 steps of diagnosis.
            rc = self.retry_think_cap * self._refused_streak
            cap = min(cap or rc, rc)
            self.n_retry_capped += 1
        if (not cap and thinking and self.empty_streak_limit
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
        if self._continuation_broken:
            return r1
        _NEXT_EXTRA.update(continue_final_message=True, add_generation_prompt=False)
        self.max_tokens = rest
        try:
            r2 = await super()._query_with_retry(model, list(messages) + [prefill])
        except Exception as exc:  # server rejects the continuation: keep running without it
            self._continuation_broken = f"{type(exc).__name__}: {exc}"[:300]
            return r1
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

    def _note_rollback(self, messages, dropped, after) -> None:
        """Append-only variant: the upstream ledger sits right after the task prefix and is
        rewritten in place on every retry ("retry 13/50" -> "14/50"), which re-read the whole
        context each time in B32. Here the notice is appended at the end like any message."""
        for m in dropped:
            for tc in m.get("tool_calls") or []:
                try:
                    cmd = json.loads(tc["function"]["arguments"]).get("command", "")
                except Exception:
                    cmd = ""
                cmd = " ".join(cmd.split())[:70]
                if cmd and cmd not in self._rolled_back_cmds:
                    self._rolled_back_cmds.append(cmd)
        del self._rolled_back_cmds[:-5]
        messages.append({"role": "user",
                         "content": self._budget.rollback_message(len(dropped), after, self._rolled_back_cmds)})

    async def setup(self, environment: Any) -> None:
        await super().setup(environment)
        src = CTXFOLD_SRC.read_text()
        await environment.exec(
            command="cat > /usr/local/bin/ctxfold <<'CTXFOLD_EOF'\n" + src + "\nCTXFOLD_EOF\n"
                    "chmod +x /usr/local/bin/ctxfold", timeout_sec=60)
        if self.archive:
            rsrc = RECALL_SRC.read_text()
            await environment.exec(
                command="mkdir -p /tmp/.live_ctx/archive && touch /tmp/.live_ctx/archive/.on && "
                        "cat > /usr/local/bin/recall <<'RECALL_EOF'\n" + rsrc + "\nRECALL_EOF\n"
                        "chmod +x /usr/local/bin/recall", timeout_sec=60)

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
        proto = (PROTOCOL_READ + (READ_REASONS if self.read_reasons else "")) if self.fold_mode == "read" \
            else PROTOCOL
        if self.quoted:
            proto = PROTOCOL_QUOTED
        if self.archive:
            proto += ARCHIVE_NOTE
        if self.fold_batches > 1:
            proto += FOLD_N_NOTE.format(k=self.fold_batches, cmd=" && ".join(["next"] * self.fold_batches))
            if self.quoted:
                proto = proto.replace("fold them all in ONE update (apply the items in order) and drop them together "
                                      "with `ctxfold --drop`", "send all their events, in order, in ONE `ctxfold --events` list")
        _h._SYSTEM_TEMPLATE = saved.replace("{{finish_instructions}}", proto + "\n{{finish_instructions}}") \
            if "{{finish_instructions}}" in saved else saved + proto
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
                    "continuation_error": self._continuation_broken,
                    "repeats_refused": self.n_repeats_refused,
                    "answers_refused": self.n_answers_refused,
                    "archive": self.archive, "fold_batches": self.fold_batches,
                    "quoted": self.quoted, "events_applied": self.n_events_applied,
                    "event_lists_applied": self.n_event_lists_applied,
                    "event_lists_refused": dict(self.lists_refused),
                    "event_lists_refused_total": sum(self.lists_refused.values()),
                    "event_retries": self.n_event_retries, "quoted_cmds_refused": self.n_quoted_refused_cmds,
                    "retry_think_cap": self.retry_think_cap if self.quoted else None,
                    "retry_capped_calls": self.n_retry_capped, "final_item_pinned": bool(self._final_text),
                    "recall_calls": self.n_recalls, "recall_output_tokens": self.recall_tokens,
                    "archive_write_refused": self.n_archive_refused,
                    "answer_key_notes": self.n_answer_key_notes,
                    "text_calls_recovered": self.n_text_calls_recovered,
                    "thinking_policy": self.thinking_policy,
                    "fold_mode": self.fold_mode,
                    "read_reasons": self.read_reasons,
                    "stable_system": self.stable_system,
                    "stable_render": _as_bool(getattr(self, "stable_render", False)),
                    "stable_mirror": self.stable_mirror,
                    "thinking_on_calls": self.pstats["thinking_on"],
                    "thinking_off_calls": self.pstats["thinking_off"],
                    "thinking_toggles": self.pstats["thinking_toggles"],
                    "prefix_calls": self.pstats["calls"],
                    "prefix_stable": self.pstats["stable"],
                    "prefix_unstable_after_edit": self.pstats["unstable_after_edit"],
                    "prefix_unstable_no_edit": self.pstats["unstable_no_edit"],
                    "prefix_lcp_share_mean": round(self.pstats["lcp_share_sum"] / max(self.pstats["calls"] - 1, 1), 4),
                    "first_unstable_no_edit": self.pstats["first_unstable_no_edit"],
                    "extra_prompt_tokens": self.extra_prompt_tokens,
                    "dropped_thinking_chars": getattr(self, "dropped_thinking_chars", 0),
                    "drop_old_thinking": _as_bool(getattr(self, "drop_old_thinking", False)),
                }, indent=1) + "\n")
            except Exception:
                pass
