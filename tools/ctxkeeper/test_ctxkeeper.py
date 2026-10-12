"""Tests of ctxkeeper.py against a scripted model (no model server, no GPU, standard library only)."""
import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import ctxkeeper as ck


def reply(content=None, tool_calls=None, prompt_tokens=0):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"id": "x", "model": "m", "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 1}}


class Model:
    """A scripted model: writes NOTES when asked to, otherwise answers 'ok'; records every request."""

    def __init__(self):
        self.requests, self.notes_rules, self.recall_once = [], ["Always answer in French."], None

    def __call__(self, body):
        self.requests.append(body)
        last = body["messages"][-1]
        if "=== TURNS BEING MOVED OUT ===" in str(last.get("content")):
            return reply("Here are the notes.\nRULES\n" + "\n".join("- " + r for r in self.notes_rules)
                         + f"\nSTATE\n- notes call number {sum(1 for r in self.requests if 'TURNS BEING MOVED OUT' in str(r['messages'][-1].get('content')))}\nOPEN\n")
        if self.recall_once and last.get("role") != "tool":
            args, self.recall_once = self.recall_once, None
            return reply(None, [{"id": "c1", "type": "function", "function": {"name": "recall", "arguments": json.dumps(args)}}])
        return reply(f"ok {len(body['messages'])}")


def conversation(turns, words=60):
    msgs = [{"role": "system", "content": "You are a careful assistant."}, {"role": "user", "content": "The task: keep the ledger."}]
    for i in range(turns):
        msgs.append({"role": "assistant", "content": f"step {i}", "tool_calls": [
            {"id": f"t{i}", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": f"next {i}"})}}]})
        msgs.append({"role": "tool", "tool_call_id": f"t{i}", "content": f"ITEM {i}: the clerk moved counter abcd{i:02d} to {i * 7}. " + "filler " * words})
    return msgs


class LedgerModel:
    """A scripted model for in-place notes: asked for the changes, it writes one line per `counter abcdNN to V` it can
    see in the turns after the NOTES message (the scripted replies in `script` come first); otherwise 'ok'."""

    def __init__(self, script=None, rules=("Always answer in French.",)):
        self.requests, self.script, self.rules, self.notes_requests = [], list(script or []), list(rules), []

    def __call__(self, body):
        self.requests.append(body)
        last = str(body["messages"][-1].get("content") or "")
        asked = last.startswith("[[Message from the context keeper") or last.startswith("The turns mention these names") \
            or last.startswith("Check these lines") or last.startswith("Your reply did not use the layout")
        if not asked:
            return reply(f"ok {len(body['messages'])}", prompt_tokens=0)
        self.notes_requests.append(body)
        if self.script:
            text = self.script.pop(0)
        else:
            import re
            seen = []
            for m in body["messages"]:
                if m.get("role") == "tool":
                    seen += re.findall(r"counter (abcd\d\d) to (\d+)", str(m.get("content")))
            first = not any(str(m.get("content") or "").startswith("[[NOTES kept") for m in body["messages"])
            text = ("NEW RULES\n" + ("\n".join("- " + r for r in self.rules) if first else "(none)")
                    + "\nCHANGES\n" + ("\n".join(f"{k}: {v}" for k, v in seen) or "(none)") + "\nOPEN\n- keep going")
        resp = reply(text)
        resp["usage"] = {"prompt_tokens": 1000, "completion_tokens": 50, "prompt_tokens_details": {"cached_tokens": 900}}
        return resp


class InPlace(unittest.TestCase):
    """--notes-mode inplace: the notes call rides on the request the server has just read; the reply is the changes."""

    def keeper(self, model, **kw):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        args = dict(budget=6000, reply_reserve=400, headroom=100, target_ratio=0.5, notes_cap=600, memory_note=False,
                    notes_mode="inplace", inplace_tokens=300)
        args.update(kw)
        return ck.Keeper(model, Path(self.dir.name), **args)

    def run_conversation(self, keeper, turns, start=1, tools=None):
        for n in range(start, turns + 1):
            body = {"model": "m", "messages": conversation(n)}
            if tools:
                body["tools"] = tools
            keeper.complete(body)
        return next(iter(keeper.sessions.values()))

    def test_turns_are_noted_in_place_and_all_moved_out(self):
        model = LedgerModel()
        tools = [{"type": "function", "function": {"name": "bash"}}]
        keeper = self.keeper(model)
        s = self.run_conversation(keeper, 12, tools=tools)
        self.assertGreaterEqual(s.state["inplace_cuts"], 2)
        self.assertEqual(s.state["cuts"], s.state["inplace_cuts"])                 # the ordinary cut never had to run
        self.assertEqual(s.state["inplace_failed"], 0)
        self.assertEqual(len(s.archive.rows()), s.state["cut"])                    # everything moved out is in the archive
        self.assertEqual(s.archive.rows()[1]["message"], conversation(12)[3])      # verbatim
        self.assertEqual(ck.rule_lines(s.state["notes"]), ["Always answer in French."])
        self.assertIn("abcd00: 0", s.state["notes"])
        # the view right after an in-place cut: opening messages, NOTES, and the newest exchange only
        first = model.notes_requests[0]
        i = model.requests.index(first)
        after = model.requests[i + 1]["messages"]
        self.assertEqual([m["role"] for m in after], ["system", "user", "user", "assistant", "tool"])
        self.assertTrue(after[2]["content"].startswith("[[NOTES kept by the context keeper"))
        # the notes request is the request before it with one message added (so the server has read all but the end)
        before = model.requests[i - 1]["messages"]
        self.assertEqual(first["messages"][:-1], before)
        self.assertTrue(first["messages"][-1]["content"].startswith("[[Message from the context keeper"))
        self.assertEqual(first["tool_choice"], "none")
        self.assertEqual([t["function"]["name"] for t in first["tools"]], ["bash"])    # the tool list of the calls before it
        self.assertEqual([t["function"]["name"] for t in model.notes_requests[1]["tools"]], ["bash", "recall"])
        self.assertEqual(s.state["notes_cached_tokens"], 900 * len(model.notes_requests))
        self.assertGreater(len((Path(self.dir.name) / next(iter(keeper.sessions)) / "notes-history.jsonl").read_text().splitlines()), 1)

    def test_the_prefix_is_stable_between_in_place_cuts(self):
        model = LedgerModel()
        keeper = self.keeper(model)
        self.run_conversation(keeper, 12)
        main = [r["messages"] for r in model.requests if r not in model.notes_requests]
        grown = sum(1 for a, b in zip(main, main[1:]) if b[:len(a)] == a)
        self.assertEqual(grown + len(model.notes_requests), len(main) - 1)         # every other call only adds to the last one

    def test_changes_are_applied_and_sums_recomputed(self):
        model = LedgerModel(script=["NEW RULES\n(none)\nCHANGES\nstock: 7\nabcd00: 0\nOPEN\n",
                                    "NEW RULES\n- Second rule.\nCHANGES\nstock: 7 + 5 = 13\nOPEN\n- check stock"])
        keeper = self.keeper(model)
        s = self.run_conversation(keeper, 6)
        self.assertEqual(s.state["inplace_cuts"], 2)
        self.assertIn("stock: 12", s.state["notes"])                               # the proxy did the sum
        self.assertIn("abcd00: 0", s.state["notes"])                               # a line not mentioned again is kept
        self.assertEqual(ck.rule_lines(s.state["notes"]), ["Second rule."])
        self.assertTrue(s.state["notes"].rstrip().endswith("- check stock"))

    def test_working_from_a_wrong_value_is_asked_about_once(self):
        bad, good = "NEW RULES\n- R one.\nCHANGES\nstock: 99 + 1 = 100\nOPEN\n", "NEW RULES\n(none)\nCHANGES\nstock: 7 + 1 = 8\nOPEN\n"
        model = LedgerModel(script=["NEW RULES\n(none)\nCHANGES\nstock: 7\nOPEN\n", bad, good])
        keeper = self.keeper(model)
        s = self.run_conversation(keeper, 9)
        self.assertIn("stock: 8", s.state["notes"])
        self.assertEqual(ck.rule_lines(s.state["notes"]), ["R one."])              # named only in the reply that was asked for again
        self.assertEqual(s.state["inplace_reasks"], 1)
        again = model.notes_requests[2]["messages"]
        self.assertTrue(again[-1]["content"].startswith("Check these lines"))
        self.assertEqual(again[-2], {"role": "assistant", "content": bad.strip()})
        events = (Path(self.dir.name) / next(iter(keeper.sessions)) / "events.jsonl").read_text()
        self.assertIn("asked again", events)

    def test_a_reply_without_the_layout_twice_leaves_the_turns_to_the_ordinary_cut(self):
        model = LedgerModel(script=["I will continue the task.", "next"])
        keeper = self.keeper(model, budget=2400, inplace_tokens=300)
        notes = Model()                                                        # the full rewrite answers the ordinary cut
        def both(body):
            last = str(body["messages"][-1].get("content") or "")
            return notes(body) if "=== TURNS BEING MOVED OUT ===" in last else model(body)
        keeper.ask = both
        s = self.run_conversation(keeper, 4)
        self.assertEqual((s.state["inplace_failed"], s.state["cut"], s.state["notes"]), (1, 0, ""))
        self.assertGreater(s.state["hold"], 0)
        tried = len(model.notes_requests)
        s = self.run_conversation(keeper, 6, start=5)
        self.assertEqual(len(model.notes_requests), tried)                         # not tried again on the same turns
        s = self.run_conversation(keeper, 30, start=7)
        self.assertGreater(s.state["cuts"], 0)                                     # the ordinary cut took over, then in-place again
        self.assertGreater(s.state["inplace_cuts"], 0)
        self.assertEqual(len(s.archive.rows()), s.state["cut"])
        self.assertEqual([r["n"] for r in s.archive.rows()], list(range(3, 3 + s.state["cut"])))   # nothing twice, nothing missing

    def test_a_question_in_a_tool_result_blocks_the_in_place_cut(self):
        model = LedgerModel()
        keeper = self.keeper(model, think_when=r"QUESTION:", think_until=r"ITEM \d+: the clerk")
        msgs = conversation(8)
        msgs[-1] = dict(msgs[-1], content="QUESTION: what is abcd03 now? " + "filler " * 60)
        keeper.complete({"model": "m", "messages": msgs})
        s = next(iter(keeper.sessions.values()))
        self.assertEqual((s.state["inplace_cuts"], len(model.notes_requests)), (0, 0))
        more = msgs + conversation(10)[len(msgs):]                               # two ordinary items follow: the question is closed
        keeper.complete({"model": "m", "messages": more})
        self.assertEqual(s.state["inplace_cuts"], 1)

    def test_the_latest_user_message_stays_in_view_until_the_next_one(self):
        model = LedgerModel()
        keeper = self.keeper(model)
        msgs = conversation(3) + [{"role": "user", "content": "Now tidy the ledger, counter by counter."}]
        for i in range(3, 12):
            msgs += conversation(i + 1)[2 + 2 * i:]
            keeper.complete({"model": "m", "messages": list(msgs)})
        s = next(iter(keeper.sessions.values()))
        self.assertGreater(s.state["inplace_cuts"], 0)
        self.assertEqual(msgs[s.state["kept_user"]]["content"], "Now tidy the ledger, counter by counter.")
        view = model.requests[-1]["messages"]
        self.assertEqual([m["role"] for m in view[:4]], ["system", "user", "user", "user"])
        self.assertEqual(view[3]["content"], "Now tidy the ledger, counter by counter.")
        self.assertEqual(len(s.archive.rows()), s.state["cut"])                    # it is in the archive as well
        msgs.append({"role": "assistant", "content": "Tidied."})
        msgs.append({"role": "user", "content": "Thanks. Next: close counter abcd02."})
        keeper.complete({"model": "m", "messages": list(msgs)})
        self.assertIsNone(s.state["kept_user"])                                    # a newer user message is in view now
        self.assertNotIn("Now tidy the ledger", json.dumps(model.requests[-1]["messages"][3:4]))

    def test_count_check_asks_about_a_name_left_out(self):
        short = "NEW RULES\n(none)\nCHANGES\nabcd00: 0\nOPEN\n"
        model = LedgerModel(script=[short])
        keeper = self.keeper(model, notes_checks="near")
        s = self.run_conversation(keeper, 6)
        self.assertEqual(s.state["inplace_reasks"], 1)                             # abcd01.. were mentioned and not accounted for
        self.assertIn("more often than your CHANGES account for", model.notes_requests[1]["messages"][-1]["content"])
        self.assertIn("abcd01: 7", s.state["notes"])                               # the second reply (the scripted ledger) is applied

    def test_state_survives_a_restart_in_place(self):
        model = LedgerModel()
        keeper = self.keeper(model)
        s = self.run_conversation(keeper, 9)
        cut, notes = s.state["cut"], s.state["notes"]
        again = ck.Keeper(model, Path(self.dir.name), budget=6000, reply_reserve=400, headroom=100, target_ratio=0.5,
                          notes_cap=600, memory_note=False, notes_mode="inplace", inplace_tokens=300)
        again.complete({"model": "m", "messages": conversation(9)})
        s2 = next(iter(again.sessions.values()))
        self.assertEqual((s2.state["cut"], s2.state["notes"], s2.state.get("restarts", 0)), (cut, notes, 0))

    def test_a_tool_call_is_never_parted_from_its_results(self):
        """Review, 2026-10-12: assistant(tool calls) -> results -> a user message. The whole exchange stays in view."""
        model = LedgerModel()
        keeper = self.keeper(model)
        msgs = conversation(6) + [{"role": "user", "content": "And now close counter abcd02."}]
        keeper.complete({"model": "m", "messages": msgs})
        s = next(iter(keeper.sessions.values()))
        self.assertEqual(s.state["inplace_cuts"], 1)
        view = model.requests[-1]["messages"]
        self.assertEqual([m["role"] for m in view[:6]], ["system", "user", "user", "assistant", "tool", "user"])
        self.assertEqual(view[3]["tool_calls"][0]["id"], view[4]["tool_call_id"])
        self.assertEqual(view[5]["content"], "And now close counter abcd02.")
        self.assertTrue(view[6]["content"].startswith("[[RULES in force"))             # the reminder after a user message, as always
        notes_req = model.notes_requests[0]["messages"]
        self.assertEqual(notes_req[-2]["role"], "tool")                            # the noted part ends on a completed exchange
        for i, m in enumerate(notes_req):
            if m.get("role") == "tool":
                self.assertEqual(notes_req[i - 1]["role"], "assistant")

    def test_the_archive_takes_no_number_twice_and_a_failed_commit_changes_nothing(self):
        model = LedgerModel()
        keeper = self.keeper(model)
        s0 = keeper.session({"model": "m", "messages": conversation(1)}, None)
        calls = {"n": 0}
        real = s0.log_notes
        def failing(upto):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("disk full")
            return real(upto)
        s0.log_notes = failing
        with self.assertRaises(OSError):
            self.run_conversation(keeper, 3)
        self.assertEqual((s0.state["cut"], s0.state["notes"], s0.state["inplace_cuts"]), (0, "", 0))
        rows_after_failure = len(s0.archive.rows())
        self.run_conversation(keeper, 4, start=3)                                  # the same cut is made again
        self.assertEqual(s0.state["inplace_cuts"], 1)
        numbers = [r["n"] for r in s0.archive.rows()]
        self.assertEqual(numbers, sorted(set(numbers)))                            # nothing archived twice
        self.assertEqual(len(numbers), s0.state["cut"])
        self.assertGreater(rows_after_failure, 0)
        self.assertEqual(s0.state["notes"].count("abcd00: 0"), 1)                  # and its changes applied once

    def test_a_kept_user_message_is_not_counted_again_and_keeps_thinking_on(self):
        model = LedgerModel()
        keeper = self.keeper(model, think_when=r"QUESTION:", think_until=r"NEVER MATCHES")
        msgs = conversation(3) + [{"role": "user", "content": "Add 5 to stock, then keep auditing."}]
        for i in range(3, 9):
            msgs += conversation(i + 1)[2 + 2 * i:]
            keeper.complete({"model": "m", "messages": list(msgs)})
        s = next(iter(keeper.sessions.values()))
        self.assertIsNotNone(s.state["kept_user"])
        later = [r for r in model.notes_requests if any(m.get("content") == "Add 5 to stock, then keep auditing." for m in r["messages"][2:4])]
        self.assertTrue(later)
        self.assertIn("do not count it again", later[-1]["messages"][-1]["content"])
        self.assertTrue(model.requests[-1]["chat_template_kwargs"]["enable_thinking"])   # the request is still open
        # a question arriving in a tool result does not release the user's message
        msgs += [{"role": "assistant", "content": "", "tool_calls": [{"id": "q", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]},
                 {"role": "tool", "tool_call_id": "q", "content": "QUESTION: is abcd03 still open?"}]
        keeper.complete({"model": "m", "messages": list(msgs)})
        self.assertIsNotNone(s.state["kept_user"])

    def test_a_failed_attempt_waits_for_the_ordinary_cut_whatever_the_token_estimate(self):
        model = LedgerModel(script=["no layout", "still none"])
        keeper = self.keeper(model)
        s = self.run_conversation(keeper, 4)
        self.assertEqual((s.state["inplace_failed"], s.state["hold"]), (1, 1))
        tried = len(model.notes_requests)
        s.state["ratio"] = 6.0                                                     # the same turns now look smaller
        self.run_conversation(keeper, 5, start=5)
        s.state["ratio"] = 2.5                                                     # or larger
        self.run_conversation(keeper, 6, start=6)
        self.assertEqual(len(model.notes_requests), tried)

    THINK = r"(?m)^(?:ASK \S+?:|QUERY \S+)|^PROBE:|Traceback|\(exit_code=[1-9-]"     # as the campaigns set them
    RECITE = r"(?m)^(?:ASK \S+?:|QUERY \S+)"
    UNTIL = r"(?m)^ITEM \d+:"

    def asking(self, extra=0):
        """Three items, a question item, then the model reads a lot before it answers (one read fails)."""
        msgs = conversation(3)
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": "q", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]})
        msgs.append({"role": "tool", "tool_call_id": "q", "content": "PROBE: answer now.\nASK p1_1: What value does abcd01 hold?" + "\nASK more: x" * extra})
        steps = []
        for i in range(12):
            call = {"role": "assistant", "content": "", "tool_calls": [{"id": f"r{i}", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": f"cat part{i}"})}}]}
            out = "cat: part: No such file\n\n(exit_code=1)" if i == 5 else "archived text " + "filler " * 150
            steps.append([call, {"role": "tool", "tool_call_id": f"r{i}", "content": out}])
        return msgs, steps

    def test_an_open_question_from_a_tool_result_survives_every_cut(self):
        """The in-place cut waits while such a question is open; the ordinary cut does not, and it must not take the
        question out of view (the harness arm lost seven answers at 1M that way). A failed command, a client's
        nudge, or enough turns for an in-place cut do not unpin it; the next ordinary item does."""
        model = LedgerModel()
        keeper = self.keeper(model, budget=2600, think_when=self.THINK, recite_when=self.RECITE, think_until=self.UNTIL, inplace_tokens=300)
        msgs, steps = self.asking()
        for i, step in enumerate(steps):
            msgs += step
            if i == 8:
                msgs.append({"role": "user", "content": "(No tool call in your last turn.)"})
            keeper.complete({"model": "m", "messages": list(msgs)})
        s = next(iter(keeper.sessions.values()))
        self.assertGreater(s.state["cuts"], 1)
        self.assertEqual(s.state["inplace_cuts"], 0)                               # enough turns for one, but the question is open
        view = model.requests[-1]["messages"]
        shown = [m for m in view if str(m.get("content")).startswith(ck.OPEN_HEAD)]
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]["role"], "user")
        self.assertIn("ASK p1_1: What value does abcd01 hold?", shown[0]["content"])
        self.assertTrue(view[2]["content"].startswith("[[NOTES kept"))             # after the opening two and NOTES
        self.assertIn(shown[0], view[3:5])                                         # beside the kept user message, if any
        self.assertNotIn("No such file", shown[0]["content"])                      # the failed command did not take its place
        # the next ordinary item closes it
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": "n", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": "next"})}}]})
        msgs.append({"role": "tool", "tool_call_id": "n", "content": "ITEM 4: the clerk moved counter abcd04 to 28. " + "filler " * 60})
        keeper.complete({"model": "m", "messages": list(msgs)})
        self.assertIsNone(s.state["kept_open"])
        self.assertFalse([m for m in model.requests[-1]["messages"] if str(m.get("content")).startswith(ck.OPEN_HEAD)])

    def test_a_question_that_also_matches_the_closing_pattern_keeps_its_pin(self):
        """The question's own message matches --think-until too (`ITEM 9: ...` with ASK lines): it is a question,
        and only a later message closes it (as `opener` already reads it)."""
        model = LedgerModel()
        keeper = self.keeper(model, budget=2600, think_when=r"(?m)^ASK ", recite_when=r"(?m)^ASK ", think_until=r"(?m)^ITEM ", inplace_tokens=100000)
        msgs = conversation(3)
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": "q", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]})
        msgs.append({"role": "tool", "tool_call_id": "q", "content": "ITEM 9: question\nASK q1: What is abcd12?"})
        for i in range(12):
            msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": f"r{i}", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": f"cat part{i}"})}}]})
            msgs.append({"role": "tool", "tool_call_id": f"r{i}", "content": "some recalled facts " + "filler " * 150})
            keeper.complete({"model": "m", "messages": list(msgs)})
        s = next(iter(keeper.sessions.values()))
        self.assertGreater(s.state["cuts"], 0)
        self.assertIsNotNone(s.state["kept_open"])
        self.assertTrue([m for m in model.requests[-1]["messages"] if str(m.get("content")).startswith(ck.OPEN_HEAD) and "ASK q1" in m["content"]])

    def test_nothing_is_pinned_without_a_pattern_that_closes_it_and_a_long_question_says_where_it_is_cut(self):
        model = LedgerModel()
        keeper = self.keeper(model, budget=2600, think_when=self.THINK, recite_when=self.RECITE, inplace_tokens=100000)
        msgs, steps = self.asking()
        for step in steps:
            msgs += step
            keeper.complete({"model": "m", "messages": list(msgs)})
        s = next(iter(keeper.sessions.values()))
        self.assertGreater(s.state["cuts"], 0)
        self.assertIsNone(s.state["kept_open"])                                    # nothing could ever close it: not kept
        old = ck.OPEN_CHARS
        ck.OPEN_CHARS = 60
        self.addCleanup(setattr, ck, "OPEN_CHARS", old)
        model2 = LedgerModel()
        k2 = self.keeper(model2, budget=2600, think_when=self.THINK, recite_when=self.RECITE, think_until=self.UNTIL, inplace_tokens=100000)
        msgs, steps = self.asking(extra=20)
        for step in steps:
            msgs += step
            k2.complete({"model": "m", "messages": list(msgs)})
        shown = [m["content"] for m in model2.requests[-1]["messages"] if str(m.get("content")).startswith(ck.OPEN_HEAD)]
        self.assertEqual(len(shown), 1)
        self.assertRegex(shown[0].splitlines()[-1], r"^\[cut here: \d+ more characters; `recall` has the whole message\]$")

    def test_full_mode_ignores_a_kept_user_message_left_in_saved_state(self):
        model = Model()
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        keeper = ck.Keeper(model, Path(d.name), budget=2400, reply_reserve=400, headroom=100, target_ratio=0.5, notes_cap=400, memory_note=False)
        for n in range(1, 21):
            keeper.complete({"model": "m", "messages": conversation(n)})
        s = next(iter(keeper.sessions.values()))
        self.assertGreater(s.state["cut"], 4)
        s.state["kept_user"] = 3                                                   # as if left by an earlier in-place run
        view = keeper.view(s, conversation(20))
        self.assertTrue(view[2]["content"].startswith("[[NOTES kept"))
        self.assertEqual(view[3], conversation(20)[2 + s.state["cut"]])            # straight on to the recent turns

    def test_an_asked_for_reply_with_only_the_corrected_line_loses_nothing(self):
        """Campaign 11, X32i seed 1: the model answered a re-ask with one line and the changes of nine items were gone."""
        first = "NEW RULES\n- R one.\nCHANGES\nstock: 99 + 1 = 100\nabcd00: 0\nabcd01: 7\nOPEN\n- watch stock"
        only = "NEW RULES\n(none)\nCHANGES\nstock: 7 + 1 = 8\nOPEN\n"
        nothing = "NEW RULES\n(none)\nCHANGES\n(none)\nOPEN\n"
        for second, stock in ((only, "stock: 8"), (nothing, "stock: 100")):
            model = LedgerModel(script=["NEW RULES\n(none)\nCHANGES\nstock: 7\nOPEN\n", first, second])
            keeper = self.keeper(model)
            s = self.run_conversation(keeper, 6)
            self.assertEqual(s.state["inplace_cuts"], 2)
            for line in (stock, "abcd00: 0", "abcd01: 7"):
                self.assertIn(line, s.state["notes"])
            self.assertEqual(ck.rule_lines(s.state["notes"]), ["R one."])
            events = (Path(self.dir.name) / next(iter(keeper.sessions)) / "events.jsonl").read_text()
            self.assertIn('"event": "in-place notes reply"', events)               # every reply is kept for later reading

    def test_only_matching_messages_are_read_for_the_checks(self):
        """1M proxy run: the agent printed its answers file and the keys (p21_7 ...) were taken for things of STATE."""
        reply_text = "NEW RULES\n(none)\nCHANGES\n" + "\n".join(f"abcd{i:02d}: {i * 7}" for i in range(5)) + "\nOPEN\n"
        for scan, reasks in ((None, 1), (r"^ITEM \d+: the clerk", 0)):
            model = LedgerModel(script=[reply_text, reply_text])
            keeper = self.keeper(model, notes_checks="near", notes_scan=scan, inplace_tokens=700)
            msgs = conversation(6)
            msgs[6:6] = [{"role": "assistant", "content": "", "tool_calls": [{"id": "cat", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]},
                         {"role": "tool", "tool_call_id": "cat", "content": '{"p21_7": 571, "p22_1": 3} ' + "filler " * 60}]   # a printed answers file
            s = keeper.session({"model": "m", "messages": msgs}, None)
            s.state["notes"] = "RULES\n(none)\nSTATE\np21_7: 571\nOPEN"       # the model had noted an answer key as a thing of STATE
            keeper.complete({"model": "m", "messages": msgs})
            self.assertEqual((s.state["inplace_cuts"], s.state["inplace_reasks"]), (1, reasks))

    class Tampering(LedgerModel):
        """The scripted ledger, with lines added to the CHANGES of chosen notes replies ({reply number: [lines]}, the
        first notes reply is 1), and fixed answers to a "Check these lines" question."""

        def __init__(self, add, on_check=None):
            super().__init__()
            self.add, self.on_check, self.replies = add, list(on_check or []), 0

        def __call__(self, body):
            last = str(body["messages"][-1].get("content") or "")
            if last.startswith("Check these lines") and self.on_check:
                self.requests.append(body)
                self.notes_requests.append(body)
                return reply(self.on_check.pop(0))
            resp = super().__call__(body)
            text = resp["choices"][0]["message"]["content"]
            if text.startswith("NEW RULES"):
                self.replies += 1
                extra = self.add.get(self.replies)
                if extra:
                    resp["choices"][0]["message"]["content"] = text.replace("\nOPEN", "\n" + "\n".join(extra) + "\nOPEN", 1)
            return resp

    def events(self, keeper):
        return (Path(self.dir.name) / next(iter(keeper.sessions)) / "events.jsonl").read_text()

    def test_what_the_kept_message_says_about_a_noted_result_is_not_noted_twice(self):
        """After a cut the newest exchange stays in view; its assistant message was written about the result before
        it, which the NOTES already cover. The model is told, and a line for a name that none of the turns being
        noted mentions is left out without a question (X32n seed 1: `sahidi23: 423 - 84 = 339`, a stale answer)."""
        model = self.Tampering({2: ["abcd00: 0 - 84 = -84", "abcd01: opened at 214"]})
        keeper = self.keeper(model, notes_checks="near")
        s = self.run_conversation(keeper, 12)
        self.assertGreaterEqual(s.state["inplace_cuts"], 2)
        first, second = (r["messages"] for r in model.notes_requests[:2])
        self.assertNotIn(ck.OVERLAP_NOTE.strip(), first[-1]["content"])           # nothing was noted before the first cut
        self.assertIn(ck.OVERLAP_NOTE.strip(), second[-1]["content"])
        self.assertEqual(second[3]["role"], "assistant")                         # the opening two, NOTES, then the kept message
        self.assertIn("abcd00: 0", s.state["notes"].splitlines())
        self.assertIn("abcd01: 7", s.state["notes"].splitlines())
        self.assertEqual((s.state["inplace_reasks"], s.state["inplace_failed"]), (0, 0))
        self.assertIn("names the turns do not mention left out", self.events(keeper))

    def test_a_misspelled_name_in_the_notes_is_put_right(self):
        """X32n2 at 1M wrote `vozi36` for `vozimi36`: the line was left out as unsupported and the change was lost."""
        class Misspelling(LedgerModel):
            def __call__(self, body):
                resp = super().__call__(body)
                msg = resp["choices"][0]["message"]
                if str(msg.get("content")).startswith("NEW RULES") and len(self.notes_requests) == 1:
                    msg["content"] = msg["content"].replace("abcd01:", "abd01:")
                return resp

        keeper = self.keeper(Misspelling(), notes_checks="near")
        s = self.run_conversation(keeper, 4)
        notes = s.state["notes"].splitlines()
        self.assertIn("abcd01: 7", notes)
        self.assertFalse([ln for ln in notes if ln.startswith("abd01")])
        self.assertEqual((s.state["inplace_reasks"], s.state["inplace_failed"]), (0, 0))
        self.assertIn("a misspelled name put right", self.events(keeper))

    def test_a_correction_under_the_same_misspelling_replaces_the_line_it_corrects(self):
        first = "NEW RULES\n(none)\nCHANGES\nabcd00: 0\nabd01: 999\nOPEN\n"
        second = "NEW RULES\n(none)\nCHANGES\nabd01: 7\nOPEN\n"
        model = LedgerModel(script=[first, second])
        keeper = self.keeper(model, notes_checks="near")
        s = self.run_conversation(keeper, 4)
        notes = s.state["notes"].splitlines()
        self.assertIn("abcd01: 7", notes)                                          # asked about the working; the answer came under the same misspelling
        self.assertFalse([ln for ln in notes if ln.startswith("abd01")])
        self.assertEqual(s.state["inplace_reasks"], 1)

    def test_a_second_reply_without_the_layout_is_asked_for_the_layout_once_and_its_rules_count(self):
        first = "NEW RULES\n(none)\nCHANGES\nabcd00: 0\nabcd01: 999\nabcd02: 14\nOPEN\n"
        loose = "You are right, the line should read abcd01: 7."
        cut_off = "NEW RULES\n- A late rule.\nCHANGES\nabcd01: 7"
        model = LedgerModel(script=[first, loose, cut_off])
        keeper = self.keeper(model, notes_checks="near")
        s = self.run_conversation(keeper, 4)
        asked = [r["messages"][-1]["content"][:40] for r in model.notes_requests]
        self.assertTrue(asked[1].startswith("Check these lines") and asked[2].startswith("Your reply did not use the layout"), asked)
        self.assertIn("abcd01: 7", s.state["notes"].splitlines())                 # the third reply was in the layout and is used
        self.assertEqual(ck.rule_lines(s.state["notes"]), ["A late rule."])
        self.assertEqual(s.state["inplace_failed"], 0)

    def test_no_usable_second_reply_means_the_first_stands_without_the_questioned_line(self):
        model = self.Tampering({1: ["abcd01: 999"]}, on_check=[""])
        keeper = self.keeper(model, notes_checks="near")
        s = self.run_conversation(keeper, 6)
        self.assertEqual((s.state["inplace_failed"], s.state["inplace_reasks"]), (0, 1))
        self.assertGreaterEqual(s.state["inplace_cuts"], 1)                       # the cut was made in place, no full rewrite
        self.assertIn("abcd01: 7", s.state["notes"].splitlines())
        self.assertNotIn("999", s.state["notes"])
        self.assertIn("abcd00: 0", s.state["notes"].splitlines())
        ev = self.events(keeper)
        self.assertIn("no usable second reply, the first stands", ev)
        self.assertIn("abcd01: 999", ev)

    def test_a_number_the_turns_do_not_state_is_left_out_after_the_second_reply(self):
        again = "NEW RULES\n(none)\nCHANGES\nabcd00: 0\nabcd01: 7\nabcd01: 999\nabcd02: 14\nOPEN\n"
        model = self.Tampering({1: ["abcd01: 999"]}, on_check=[again])
        keeper = self.keeper(model, notes_checks="near")
        s = self.run_conversation(keeper, 4)
        notes = s.state["notes"].splitlines()
        self.assertTrue({"abcd00: 0", "abcd01: 7"} <= set(notes), notes)
        self.assertNotIn("999", s.state["notes"])
        self.assertEqual(s.state["inplace_failed"], 0)
        self.assertIn("lines left out (the turns do not bear them out)", self.events(keeper))

    def test_options_are_checked(self):
        with self.assertRaises(ValueError):
            ck.Keeper(lambda b: None, Path(tempfile.gettempdir()), notes_mode="fast")


class Policy(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.model = Model()
        self.keeper = ck.Keeper(self.model, Path(self.dir.name), budget=2400, reply_reserve=400, headroom=100,
                                target_ratio=0.5, notes_cap=400, memory_note=False)

    def tearDown(self):
        self.dir.cleanup()

    def run_conversation(self, turns, start=1):
        for n in range(start, turns + 1):
            self.keeper.complete({"model": "m", "messages": conversation(n)})
        return next(iter(self.keeper.sessions.values()))

    def test_short_conversation_is_untouched(self):
        body = {"model": "m", "messages": conversation(2), "tools": [{"type": "function", "function": {"name": "bash"}}]}
        resp = self.keeper.complete(body)
        sent = self.model.requests[-1]
        self.assertEqual(sent["messages"], body["messages"])
        self.assertEqual([t["function"]["name"] for t in sent["tools"]], ["bash"])       # no recall tool before any cut
        self.assertEqual(resp["choices"][0]["message"]["content"], "ok 6")

    def test_long_conversation_is_cut_archived_and_noted(self):
        s = self.run_conversation(30)
        self.assertGreater(s.state["cut"], 0)
        self.assertGreater(s.state["cuts"], 1)
        rows = s.archive.rows()
        self.assertEqual(len(rows), s.state["cut"])                               # every cut message is in the archive
        self.assertEqual(rows[0]["n"], 3)                                         # numbered as in the conversation
        self.assertIn("counter abcd00 to 0", rows[1]["text"])                     # verbatim
        self.assertEqual(rows[1]["message"], conversation(30)[3])                 # and the message itself, as sent
        self.assertEqual(ck.rule_lines(s.state["notes"]), ["Always answer in French."])
        sent = [r for r in self.model.requests if "TURNS BEING MOVED OUT" not in str(r["messages"][-1].get("content"))][-1]
        view = sent["messages"]
        self.assertEqual([m["role"] for m in view[:3]], ["system", "user", "user"])
        self.assertTrue(view[2]["content"].startswith("[[NOTES kept by the context keeper"))
        self.assertNotEqual(view[3]["role"], "tool")                              # never starts at an orphan tool result
        self.assertLess(self.keeper.tokens(s, view), 2400 - 400)
        self.assertEqual(sent["tools"][-1]["function"]["name"], "recall")
        self.assertEqual(view[-1], conversation(30)[-1])                          # the newest turn is always there

    def test_prefix_is_stable_between_cuts(self):
        self.run_conversation(30)
        chat = [r["messages"] for r in self.model.requests if "TURNS BEING MOVED OUT" not in str(r["messages"][-1].get("content"))]
        stable = sum(1 for a, b in zip(chat, chat[1:]) if b[:len(a)] == a)
        self.assertGreater(stable, len(chat) // 2)                                # most requests only append

    def test_a_dropped_rule_is_put_back(self):
        self.run_conversation(16)
        s = next(iter(self.keeper.sessions.values()))
        cuts = s.state["cuts"]
        self.model.notes_rules = ["Dates are written day first."]                 # the model now forgets the first rule
        self.run_conversation(30, start=17)                                       # the same conversation goes on
        self.assertGreater(s.state["cuts"], cuts)
        self.assertEqual(ck.rule_lines(s.state["notes"]), ["Always answer in French.", "Dates are written day first."])
        self.assertGreater(s.state["rules_put_back"], 0)

    def test_recall_is_answered_by_the_proxy(self):
        s = self.run_conversation(30)
        self.model.recall_once = {"pattern": "abcd03"}
        before = len(self.model.requests)
        resp = self.keeper.complete({"model": "m", "messages": conversation(30) + [{"role": "user", "content": "What was counter abcd03 set to?"}]})
        self.assertIsNone(resp["choices"][0]["message"].get("tool_calls"))        # the client never sees the recall
        self.assertEqual(s.state["recalls"], 1)
        second = self.model.requests[-1]["messages"]
        self.assertEqual(second[-1]["role"], "tool")
        self.assertIn("counter abcd03 to 21", second[-1]["content"])
        self.assertGreaterEqual(len(self.model.requests) - before, 2)

    def test_recall_and_notes_at_use_the_contents_own_numbers_when_told_to(self):
        k = ck.Keeper(self.model, Path(self.dir.name) / "lab", budget=2400, reply_reserve=400, headroom=100, target_ratio=0.5,
                      notes_cap=400, memory_note=False, recall_label=r"ITEM (\d+):", recall_unit="item")
        for n in range(1, 31):
            k.complete({"model": "m", "messages": conversation(n)})
        s = next(iter(k.sessions.values()))
        self.assertGreater(s.state["cuts"], 1)
        asked = conversation(30) + [{"role": "user", "content": "What was counter abcd03 set to?"}]
        self.model.recall_once = {"pattern": "abcd03", "before": 5}
        k.complete({"model": "m", "messages": asked})
        sent = self.model.requests[-1]
        self.assertEqual(sent["messages"][-1]["content"], "item 3 (tool): ITEM 3: the clerk moved counter abcd03 to 21.")
        self.assertIn("All numbers here are item numbers", sent["tools"][-1]["function"]["description"])
        saves = [json.loads(l)["upto"] for l in (s.dir / "notes-history.jsonl").read_text().splitlines()]
        item = {r["n"]: r["k"] for r in s.archive.labelled(k.recall_label)}
        first_item, first_msg = item[saves[0]], saves[0]
        self.assertLess(first_item, first_msg - 2)                                 # the two numberings differ here, so the test can tell
        self.model.recall_once = {"notes_at": first_item - 1}
        k.complete({"model": "m", "messages": asked})
        self.assertEqual(self.model.requests[-1]["messages"][-1]["content"],
                         f"recall: no NOTES were saved at or before item {first_item - 1} (the first save covers items up to {first_item})")
        self.model.recall_once = {"notes_at": first_item + 1}                      # as a message number this is before the first save
        k.complete({"model": "m", "messages": asked})
        text = self.model.requests[-1]["messages"][-1]["content"]
        self.assertTrue(text.startswith(f"NOTES as saved after item {first_item}. Anything said in items {first_item + 1}-{first_item + 1} is not in them"), text[:160])

    def test_notes_history_answers_what_was_true_then(self):
        s = self.run_conversation(30)
        rows = [json.loads(l) for l in (s.dir / "notes-history.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), s.state["cuts"])
        self.assertEqual(rows[-1]["upto"], 2 + s.state["cut"])                    # head of 2, then the archived messages
        first, second = rows[0]["upto"], rows[1]["upto"]
        out = s.notes_at(second - 1)
        self.assertTrue(out.startswith(f"NOTES as saved after message {first}."))
        self.assertIn(f"`after` {first + 1} and `before` {second - 1}", out)
        self.assertIn("notes call number 1", out)
        self.assertNotIn("is not in them", s.notes_at(second))
        self.assertIn("no NOTES were saved at or before message 1", s.notes_at(1))
        self.model.recall_once = {"notes_at": second}
        self.keeper.complete({"model": "m", "messages": conversation(30) + [{"role": "user", "content": "What did we know back then?"}]})
        self.assertIn("notes call number 2", self.model.requests[-1]["messages"][-1]["content"])

    def test_a_rejected_notes_call_is_logged_and_retried_without_thinking(self):
        calls = []

        def model(body):
            if "=== TURNS BEING MOVED OUT ===" in str(body["messages"][1].get("content")) or any(
                    "=== TURNS BEING MOVED OUT ===" in str(m.get("content")) for m in body["messages"]):
                calls.append(body)
                thinking = (body.get("chat_template_kwargs") or {}).get("enable_thinking")
                return reply("" if thinking else "RULES\n- Keep it short.\nSTATE\n- fine\nOPEN")
            return reply("ok")

        k = ck.Keeper(model, Path(self.dir.name) / "r", budget=2400, reply_reserve=400, headroom=100, target_ratio=0.5,
                      notes_cap=400, memory_note=False)
        for n in range(1, 16):
            k.complete({"model": "m", "messages": conversation(n)})
        s = next(iter(k.sessions.values()))
        self.assertGreater(s.state["cuts"], 0)
        self.assertEqual(s.state["notes_failed"], 0)                              # every cut got its notes on the retry
        self.assertEqual(ck.rule_lines(s.state["notes"]), ["Keep it short."])
        self.assertEqual([c["chat_template_kwargs"]["enable_thinking"] for c in calls[:2]], [True, False])
        events = [json.loads(l) for l in (s.dir / "events.jsonl").read_text().splitlines()]
        self.assertEqual((events[0]["event"], events[0]["why"], events[0]["attempt"]), ("notes call rejected", "empty reply", 1))

    def test_the_client_never_receives_a_recall_call(self):
        seen = []

        def greedy(body):                           # a model that always wants one more search, while it has the tool
            seen.append(body)
            names = [t["function"]["name"] for t in body.get("tools") or []]
            if "recall" in names:
                return reply("still checking", [{"id": f"c{len(seen)}", "type": "function", "function": {"name": "recall", "arguments": json.dumps({"pattern": "abcd"})}}])
            return reply("Here is my answer with what I have.")

        k = ck.Keeper(greedy, Path(self.dir.name) / "g", budget=100000, max_recalls=3, memory_note=True)
        resp = k.complete({"model": "m", "messages": conversation(3), "tools": [{"type": "function", "function": {"name": "bash"}}]})
        msg = resp["choices"][0]["message"]
        self.assertFalse(msg.get("tool_calls"))
        self.assertEqual(msg["content"], "Here is my answer with what I have.")
        stubborn = lambda body: reply(None, [{"id": "c", "type": "function", "function": {"name": "recall", "arguments": "{}"}}])
        k2 = ck.Keeper(stubborn, Path(self.dir.name) / "g2", budget=100000, max_recalls=2)
        r2 = k2.complete({"model": "m", "messages": conversation(3)})["choices"][0]
        self.assertEqual((r2["finish_reason"], "tool_calls" in r2["message"], bool(r2["message"]["content"])), ("stop", False, True))
        self.assertEqual(len(seen), 4)                                            # three searches, then one call without the tool
        self.assertEqual([t["function"]["name"] for t in seen[-1]["tools"]], ["bash"])
        self.assertIn("last archive search for this turn", seen[-1]["messages"][-1]["content"])
        s = next(iter(k.sessions.values()))
        self.assertEqual((s.state["recalls"], s.state["recall_limit_hit"]), (3, 1))

    def test_searches_of_a_turn_that_ended_empty_are_shown_again_once(self):
        """The proxy answers `recall` itself, so the client's history never holds what was found. A turn that ends
        with nothing for the client (X32m at 1M: six blank answers) must not lose it."""
        s = self.run_conversation(30)
        seen = []
        call = lambda: reply(None, [{"id": f"c{len(seen)}", "type": "function", "function": {"name": "recall", "arguments": json.dumps({"pattern": "abcd03"})}}])

        def thinks_it_away(body):
            seen.append(body)
            return call() if len(seen) == 1 else reply(None)

        self.keeper.ask = thinks_it_away
        asked = conversation(30) + [{"role": "user", "content": "What was counter abcd03 set to?"}]
        resp = self.keeper.complete({"model": "m", "messages": asked, "chat_template_kwargs": {"enable_thinking": True}})
        self.assertFalse(resp["choices"][0]["message"].get("content"))
        self.assertEqual(len(seen), 3)                                            # the search, the empty reply, one more try
        self.assertIs(seen[2]["chat_template_kwargs"]["enable_thinking"], False)  # ... without thinking
        self.assertEqual(seen[2]["messages"], seen[1]["messages"])
        self.assertEqual((s.state["empty_replies_retried"], s.state["carried"]), (1, 1))
        self.assertIn("counter abcd03 to 21", s.state["carry"]["text"])
        # the client nudges; the next request shows the searches again, and an answer ends the carrying
        self.keeper.ask = lambda body: seen.append(body) or reply("It was set to 21.")
        nudged = asked + [{"role": "assistant", "content": ""}, {"role": "user", "content": "(No tool call in your last turn.)"}]
        self.keeper.complete({"model": "m", "messages": nudged})
        shown = [m for m in seen[-1]["messages"] if str(m.get("content")).startswith(ck.CARRY_HEAD)]
        self.assertEqual(len(shown), 1)
        self.assertIn("recall(pattern='abcd03') returned:", shown[0]["content"])
        self.assertIn("counter abcd03 to 21", shown[0]["content"])
        self.assertIsNone(s.state["carry"])
        self.keeper.complete({"model": "m", "messages": nudged + [{"role": "assistant", "content": "It was set to 21."}, {"role": "user", "content": "Thanks."}]})
        self.assertFalse([m for m in seen[-1]["messages"] if str(m.get("content")).startswith(ck.CARRY_HEAD)])

    def test_carried_searches_stay_with_their_conversation_and_inside_the_window(self):
        calls = []

        def model(body):
            calls.append(body)
            if len(calls) == 1:
                return reply(None, [{"id": "c1", "type": "function", "function": {"name": "recall", "arguments": json.dumps({"pattern": "secret"})}}])
            return reply(None)

        k = ck.Keeper(model, Path(self.dir.name) / "c", budget=3000, reply_reserve=400, memory_note=True)
        s = k.session({"messages": conversation(1)}, "one-client")
        s.archive.add(3, [{"role": "tool", "content": "The secret of task A is 4711. " + "filler " * 40}] * 30)
        k.complete({"model": "m", "messages": conversation(1)}, "one-client")
        self.assertIn("4711", s.state["carry"]["text"])
        # the same session header, another conversation, and still before any cut: nothing of task A is shown
        k.ask = lambda body: calls.append(body) or reply("ok")
        k.complete({"model": "m", "messages": [{"role": "user", "content": "Unrelated task B"}]}, "one-client")
        self.assertNotIn("4711", json.dumps(calls[-1]["messages"]))
        self.assertIsNone(s.state["carry"])
        # a history that goes on, with a large new message: the carried text is cut to the room that is left
        s.state["carry"] = {"text": "found: 4711. " * 600, "n": 4, "of": ck.fingerprint(ck.with_memory_note(conversation(1)))}
        long = conversation(1) + [{"role": "assistant", "content": ""}, {"role": "user", "content": "go on " * 900}]
        k.complete({"model": "m", "messages": long}, "one-client")
        sent = calls[-1]["messages"]
        self.assertTrue(any(str(m.get("content")).startswith(ck.CARRY_HEAD) for m in sent))
        self.assertLessEqual(k.tokens(s, sent), k.budget - k.reply_reserve)

    def test_a_batch_of_searches_shares_the_room(self):
        calls = []

        def model(body):
            calls.append(body)
            if len(calls) == 1:
                return reply(None, [{"id": f"c{i}", "type": "function", "function": {"name": "recall", "arguments": json.dumps({"pattern": "filler"})}} for i in range(32)])
            return reply("done")

        k = ck.Keeper(model, Path(self.dir.name) / "b", budget=4000, reply_reserve=1000, memory_note=True)
        s = k.session({"messages": conversation(1)}, "batch")
        s.archive.add(3, [{"role": "tool", "content": "filler " * 300}] * 40)
        k.complete({"model": "m", "messages": conversation(1)}, "batch")
        sent = calls[-1]["messages"]
        results = [m["content"] for m in sent if m.get("role") == "tool" and m.get("tool_call_id", "").startswith("c")]
        self.assertEqual(len(results), 32)                                        # every call has its result
        self.assertGreaterEqual(results.count(ck.RECALL_NONE_NOTE), 25)
        self.assertLessEqual(k.tokens(s, sent), k.budget - k.reply_reserve + 600)   # the short lines of 32 calls, no more

    def test_an_empty_reply_is_asked_once_more_without_thinking(self):
        seen = []

        def model(body):
            seen.append(body)
            return reply(None) if (body.get("chat_template_kwargs") or {}).get("enable_thinking") is not False else reply("done")

        k = ck.Keeper(model, Path(self.dir.name) / "e", budget=100000)
        resp = k.complete({"model": "m", "messages": conversation(2), "chat_template_kwargs": {"enable_thinking": True, "x": 1}})
        self.assertEqual(resp["choices"][0]["message"]["content"], "done")
        self.assertEqual([b["chat_template_kwargs"] for b in seen], [{"enable_thinking": True, "x": 1}, {"enable_thinking": False, "x": 1}])
        self.assertIsNone(next(iter(k.sessions.values())).state["carry"])        # nothing was searched: nothing to carry
        seen.clear()
        k.complete({"model": "m", "messages": conversation(2), "chat_template_kwargs": {"enable_thinking": False}})
        self.assertEqual(len(seen), 1)                                            # thinking was off already: the reply stands

    def test_searches_stop_when_the_window_has_no_room_left(self):
        """A search result is cut to the room left beside the reply, and then no further search is made this turn."""
        s = self.run_conversation(30)
        seen = []

        def greedy(body):
            seen.append(body)
            if any(t["function"]["name"] == "recall" for t in body.get("tools") or []):
                return reply(None, [{"id": f"c{len(seen)}", "type": "function", "function": {"name": "recall", "arguments": json.dumps({"pattern": "counter"})}}])
            return reply("Answer with what I have.")

        self.keeper.ask = greedy
        resp = self.keeper.complete({"model": "m", "messages": conversation(30) + [{"role": "user", "content": "List every counter."}]})
        self.assertEqual(resp["choices"][0]["message"]["content"], "Answer with what I have.")
        final = seen[-1]["messages"]
        self.assertEqual(final[-1]["content"], ck.RECALL_ROOM_NOTE)
        results = [m["content"] for m in final if m.get("role") == "tool" and str(m.get("tool_call_id", "")).startswith("c")]
        self.assertTrue(results and results[0].startswith("["), results[:1])      # fitted: the count line, then the nearest matches
        self.assertRegex(results[0].splitlines()[0], r"^\[\d+ matches; showing the newest \d+; \d+ earlier ones are not shown")
        self.assertTrue(results[0].splitlines()[-1].startswith("message "))
        self.assertLess(len(seen), self.keeper.max_recalls + 1)                   # stopped by room, not by the count
        self.assertLessEqual(self.keeper.tokens(s, final), self.keeper.budget - self.keeper.reply_reserve + 150)
        self.assertEqual(s.state["recall_limit_hit"], 1)

    def test_rules_are_recited_after_a_new_user_message(self):
        self.run_conversation(30)
        self.keeper.complete({"model": "m", "messages": conversation(30) + [{"role": "user", "content": "And in item 3?"}]})
        view = self.model.requests[-1]["messages"]
        self.assertTrue(view[-1]["content"].startswith(ck.RECITE_HEAD))
        self.assertIn("Always answer in French.", view[-1]["content"])
        self.assertEqual(view[-2]["content"], "And in item 3?")

    def test_questions_in_a_tool_result_can_trigger_recital_and_thinking(self):
        k = ck.Keeper(self.model, Path(self.dir.name) / "q", budget=2400, reply_reserve=400, headroom=100, target_ratio=0.5,
                      notes_cap=400, recite_when=r"(?m)^ASK ", think_when=r"(?m)^ASK |Traceback", effort="medium")
        for n in range(1, 31):
            k.complete({"model": "m", "messages": conversation(n), "chat_template_kwargs": {"enable_thinking": True}})
        routine = self.model.requests[-1]
        self.assertEqual(routine["chat_template_kwargs"], {"enable_thinking": False, "reasoning_effort": "medium"})
        self.assertFalse(routine["messages"][-1]["content"].startswith(ck.RECITE_HEAD))
        asked = conversation(30)
        asked[-1] = dict(asked[-1], content="PROBE: answer now.\nASK p1_1: What value does abcd03 hold?")
        k.complete({"model": "m", "messages": asked})
        probe = self.model.requests[-1]
        self.assertTrue(probe["chat_template_kwargs"]["enable_thinking"])
        self.assertTrue(probe["messages"][-1]["content"].startswith(ck.RECITE_HEAD))
        self.assertEqual(probe["messages"][-2]["role"], "tool")

    def test_memory_note_is_added_once_and_recall_is_there_from_the_start(self):
        k = ck.Keeper(self.model, Path(self.dir.name) / "n", budget=2400, reply_reserve=400, headroom=100, target_ratio=0.5, notes_cap=400)
        for n in (1, 2, 30):
            k.complete({"model": "m", "messages": conversation(n)})
        first = [r for r in self.model.requests if len(r["messages"]) == 4][0]
        self.assertTrue(first["messages"][0]["content"].endswith(ck.MEMORY_NOTE))
        self.assertEqual(first["messages"][0]["content"].count("## Memory"), 1)
        self.assertEqual(first["tools"][-1]["function"]["name"], "recall")
        last = self.model.requests[-1]["messages"]
        self.assertEqual(last[0], first["messages"][0])                           # the start of the prompt never changes
        bare = ck.with_memory_note([{"role": "user", "content": "hi"}])
        self.assertEqual([m["role"] for m in bare], ["system", "user"])
        self.assertEqual(ck.with_memory_note(bare), bare)

    def test_a_rewritten_history_is_a_new_conversation(self):
        s = self.run_conversation(30)
        changed = conversation(30)
        changed[10] = dict(changed[10], content="something else entirely")
        self.keeper.complete({"model": "m", "messages": changed[:12]})
        self.assertEqual((s.state["cut"], s.state["notes"], s.state["restarts"]), (0, "", 1))
        self.assertEqual(s.archive.rows(), [])                                    # the new conversation searches nothing old
        self.assertEqual(len(list(s.dir.glob("archive-until-*.jsonl"))), 1)       # ... and nothing was deleted
        self.assertEqual(self.model.requests[-1]["messages"], changed[:12])

    def test_dropped_thinking_and_text_parts_do_not_look_like_a_new_conversation(self):
        base = conversation(30)
        with_thinking = [dict(m, reasoning_content="hmm, let me see") if m["role"] == "assistant" else m for m in base]
        for n in range(1, 31):
            self.keeper.complete({"model": "m", "messages": with_thinking[:2 + 2 * n]})
        s = next(iter(self.keeper.sessions.values()))
        cut, notes = s.state["cut"], s.state["notes"]
        self.assertGreater(cut, 0)
        as_parts = [dict(m, content=[{"type": "text", "text": m["content"]}]) if m["role"] == "tool" else m for m in base]
        self.keeper.complete({"model": "m", "messages": as_parts + [{"role": "user", "content": "go on"}]})   # thinking gone, parts
        self.assertEqual((s.state.get("restarts", 0), s.state["cut"] >= cut, bool(s.state["notes"])), (0, True, True))
        changed = list(base)
        changed[3] = dict(changed[3], content="an early archived message, rewritten")           # not the boundary message
        self.keeper.complete({"model": "m", "messages": changed})
        self.assertEqual(s.state["restarts"], 1)

    def test_a_cut_off_notes_reply_is_not_accepted(self):
        def model(body):
            if any("=== TURNS BEING MOVED OUT ===" in str(m.get("content")) for m in body["messages"]):
                r = reply("RULES\n- Keep it short.\nSTATE\n- half a sta")
                r["choices"][0]["finish_reason"] = "length"
                return r
            return reply("ok")
        k = ck.Keeper(model, Path(self.dir.name) / "c", budget=2400, reply_reserve=400, headroom=100, target_ratio=0.5, notes_cap=400, memory_note=False)
        for n in range(1, 16):
            k.complete({"model": "m", "messages": conversation(n)})
        s = next(iter(k.sessions.values()))
        self.assertEqual(s.state["notes"], "")                                    # nothing half-written was kept
        self.assertGreater(s.state["notes_failed"], 0)
        why = [json.loads(l)["why"] for l in (s.dir / "events.jsonl").read_text().splitlines()]
        self.assertIn("cut off by the token cap", why)

    def test_request_fields_are_cleaned_and_one_choice_only(self):
        self.keeper.complete({"model": "m", "messages": conversation(2), "stream": True, "stream_options": {"include_usage": True}, "seed": 7})
        sent = self.model.requests[-1]
        self.assertNotIn("stream_options", sent)
        self.assertEqual((sent["stream"], sent["seed"]), (False, 7))
        with self.assertRaises(ValueError):
            self.keeper.complete({"model": "m", "messages": conversation(2), "n": 2})

    def test_state_survives_a_restart(self):
        s = self.run_conversation(30)
        again = ck.Keeper(self.model, Path(self.dir.name), budget=2400, reply_reserve=400, headroom=100, target_ratio=0.5,
                          notes_cap=400, memory_note=False)
        t = again.session({"model": "m", "messages": conversation(30)}, None)
        self.assertEqual((t.state["cut"], t.state["notes"]), (s.state["cut"], s.state["notes"]))


class Loops(unittest.TestCase):
    def step(self, cmd, out):
        return [{"role": "assistant", "content": None, "tool_calls": [{"id": "x", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": cmd})}}]},
                {"role": "tool", "tool_call_id": "x", "content": out}]

    def test_repeats(self):
        base = [{"role": "system", "content": "s"}, {"role": "user", "content": "task"}]
        self.assertEqual(ck.repeats(base), 0)
        self.assertEqual(ck.repeats(base + self.step("next", "ITEM 1")), 1)
        same = self.step('recall "p13_3"', "item 273: ASK p13_3: who?")
        self.assertEqual(ck.repeats(base + self.step("next", "ITEM 1") + same * 4), 4)
        self.assertEqual(ck.repeats(base + same * 2 + self.step('recall "p13_3"', "something else")), 1)

    def test_a_stuck_model_is_told_and_made_to_think(self):
        with tempfile.TemporaryDirectory() as d:
            model = Model()
            k = ck.Keeper(model, Path(d), budget=100000, think_when=r"(?m)^ASK ", think_until=r"(?m)^ITEM \d+ ", effort="medium", memory_note=False)
            base = [{"role": "system", "content": "s"}, {"role": "user", "content": "task"}] + self.step("next", "ITEM 1 (UPDATE) a quiet day")
            k.complete({"model": "m", "messages": base + self.step("next", "ITEM 2 (UPDATE) more of it")})
            self.assertFalse(model.requests[-1]["chat_template_kwargs"]["enable_thinking"])          # routine
            probe = base + self.step("next", "PROBE\nASK p1_1: who did it?")
            same = self.step('recall "p13_3"', "message 9 (tool): ASK p13_3: who?")
            k.complete({"model": "m", "messages": probe + same})
            self.assertTrue(model.requests[-1]["chat_template_kwargs"]["enable_thinking"])           # the question is still open
            self.assertEqual(model.requests[-1]["messages"][-1]["role"], "tool")
            k.complete({"model": "m", "messages": probe + same * 3})
            last = model.requests[-1]
            self.assertIn("same tool call 3 times", last["messages"][-1]["content"])
            self.assertTrue(last["chat_template_kwargs"]["enable_thinking"])
            k.complete({"model": "m", "messages": probe + same + self.step("next", "ITEM 3 (UPDATE) on it goes")})
            self.assertFalse(model.requests[-1]["chat_template_kwargs"]["enable_thinking"])          # closed by the next item


class Pure(unittest.TestCase):
    def test_cut_points_never_start_at_a_tool_result(self):
        body = conversation(4)[2:]
        pts = ck.cut_points(body)
        self.assertTrue(all(body[i]["role"] == "assistant" for i in pts))
        self.assertEqual(pts[-1], len(body) - 2)                                  # the newest turn (call + result) stays
        self.assertEqual(ck.choose_cut(body, lambda kept: len(kept), 3), len(body) - 2)
        self.assertEqual(ck.choose_cut(body, lambda kept: len(kept), 100), 0)

    def test_head(self):
        self.assertEqual(ck.head_length(conversation(3)), 2)
        self.assertEqual(ck.head_length([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "x"}]), 1)

    def test_a_reworded_rule_comes_back_in_its_own_words_once(self):
        old = "RULES\n- Storage rule: stream contents only in my context; never redirect or tee next. Mirror file is context.\n- A is secret: answer protected.\nSTATE\nx"
        new = "RULES\n- Storage rule: stream contents only in my context; never redirect or tee next.\n- A is secret: answer protected.\n- Dates day first.\nSTATE\ny"
        kept, lost = ck.keep_rules(old, new)
        self.assertEqual(len(lost), 1)
        self.assertEqual(ck.rule_lines(kept), ["Storage rule: stream contents only in my context; never redirect or tee next. Mirror file is context.",
                                               "A is secret: answer protected.", "Dates day first."])
        again, lost2 = ck.keep_rules(kept, kept)
        self.assertEqual((again, lost2), (kept, []))
        self.assertFalse(ck.same_rule("A is secret: answer protected.", "Dates are written day first."))
        self.assertFalse(ck.same_rule("abcd12 is secret: answer protected", "efgh34 is secret: answer protected"))
        self.assertFalse(ck.same_rule("the tally is value times 5 plus 13", "the tally is value times 3 plus 15"))
        self.assertTrue(ck.same_rule("abcd12 is secret: answer protected", "abcd12 is secret, so answer protected."))

    def test_recall_places_a_sentence_by_the_first_line_of_its_message(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        a = ck.Archive(Path(d.name) / "a.jsonl")
        a.add(5, [{"role": "tool", "content": "ITEM 50/617 (UPDATE)\nThe cook slept. ziru63 was set to 485. It rained."},
                  {"role": "assistant", "content": "ziru63 is 485 now."}])
        out = a.recall("ziru63").splitlines()
        self.assertEqual(out[0], 'message 5 (tool, "ITEM 50/617 (UPDATE)"): ziru63 was set to 485.')
        self.assertEqual(out[1], "message 6 (assistant): ziru63 is 485 now.")            # a one-line message needs no heading

    def test_archive_recall(self):
        with tempfile.TemporaryDirectory() as d:
            a = ck.Archive(Path(d) / "a.jsonl")
            a.add(5, [{"role": "tool", "content": f"The porter moved box {i}. Nothing else happened."} for i in range(50)])
            out = a.recall(pattern="porter").splitlines()
            # more than fit: the count comes first and the newest are shown (the first 40 of 63, with the note last,
            # were read as "that is all" at 1M and hid every later change)
            self.assertEqual(out[0], "[50 matches; showing the newest 40; 10 earlier ones are not shown (narrow with `after`, or search for less)]")
            self.assertEqual((out[1], out[-1], len(out)), ("message 15 (tool): The porter moved box 10.", "message 54 (tool): The porter moved box 49.", 41))
            near = a.recall(pattern="porter", before=48).splitlines()
            self.assertEqual(near[0], "[44 matches; showing the 40 nearest before message 48; 4 earlier ones are not shown (narrow with `after`, or search for less)]")
            self.assertEqual((near[1], near[-1]), ("message 9 (tool): The porter moved box 4.", "message 48 (tool): The porter moved box 43."))
            onward = a.recall(pattern="porter", after=10).splitlines()
            self.assertEqual(onward[0], "[45 matches; showing the first 40 from message 10 on; 5 later ones are not shown (narrow with `before`, or search for less)]")
            self.assertEqual(onward[1], "message 10 (tool): The porter moved box 5.")
            self.assertEqual(a.recall(pattern="porter", before=20, last=2).splitlines(),
                             ["[16 matches; showing the newest 2; 14 earlier ones are not shown (narrow with `after`, or search for less)]",
                              "message 19 (tool): The porter moved box 14.", "message 20 (tool): The porter moved box 15."])
            self.assertTrue(a.recall(message=7).startswith("message 7 (tool):\nThe porter moved box 2."))
            self.assertIn("is not in the archive", a.recall(message=99))
            self.assertIn("nothing in the archive matches", a.recall(pattern="zebra"))

    def test_recall_in_the_contents_own_numbering(self):
        """With --recall-label every number the tool shows or takes is the content's own (items here), never a
        message number: X32n2 at 1M passed `before` 332 meaning item 332 and was cut off at message 332, item 150."""
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        a = ck.Archive(Path(d.name) / "a.jsonl")
        msgs = []
        for i in range(1, 61):
            msgs.append({"role": "tool", "content": f"ITEM {i}/617 (UPDATE)\nThe fog lifted. moja47 was set to {i * 3}. It rained."})
            msgs.append({"role": "assistant", "content": f"moja47 is {i * 3} now."})
        a.add(3, msgs)
        label = ck.re.compile(r"(?m)^ITEM (\d+)/")
        out = a.recall("moja47 was set", before=58, label=label, unit="item").splitlines()
        self.assertEqual(out[0], "[58 matches; showing the 40 nearest before item 58; 18 earlier ones are not shown (narrow with `after`, or search for less)]")
        self.assertEqual((out[1], out[-1]), ("item 19 (tool): moja47 was set to 57.", "item 58 (tool): moja47 was set to 174."))
        self.assertEqual(a.recall("moja47", after=59, label=label, unit="item").splitlines(),
                         ["item 59 (tool): moja47 was set to 177.", "item 59 (assistant): moja47 is 177 now.",
                          "item 60 (tool): moja47 was set to 180.", "item 60 (assistant): moja47 is 180 now."])
        self.assertEqual(a.recall(message=7, label=label, unit="item"), "item 7 (tool):\nITEM 7/617 (UPDATE)\nThe fog lifted. moja47 was set to 21. It rained.")
        self.assertIn("item 99 is not in the archive", a.recall(message=99, label=label, unit="item"))
        self.assertEqual(a.recall("zebra", before=5, label=label, unit="item"), "recall: nothing in the archive matches 'zebra' at or before item 5")
        tool = ck.recall_tool("item")["function"]["description"]
        self.assertIn("All numbers here are item numbers", tool)
        self.assertNotIn("message number", tool)
        self.assertIn("All numbers here are message numbers", ck.RECALL_TOOL["function"]["description"])

    def test_labels_come_only_from_what_the_task_delivered_and_the_pattern_is_checked(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        a = ck.Archive(Path(d.name) / "a.jsonl")
        a.add(3, [{"role": "tool", "content": "ITEM 7/9 (UPDATE)\nabcd12 was set to 5."},
                  {"role": "assistant", "content": "ITEM 2/9 was the one with the rule.\nabcd12 is 5 now."},
                  {"role": "tool", "content": "ITEM x/9 (UPDATE)\nabcd12 gained 1."}])
        label = ck.re.compile(r"(?m)^ITEM (\w+)/")
        self.assertEqual([(r["k"], r["own"]) for r in a.labelled(label)], [(7, True), (7, False), (7, False)])
        with self.assertRaises(ValueError):
            ck.Keeper(lambda b: reply("ok"), Path(d.name) / "k", recall_label=r"^ITEM \d+/")

    def test_a_search_result_is_fitted_by_leaving_out_the_farthest_matches(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        a = ck.Archive(Path(d.name) / "a.jsonl")
        a.add(5, [{"role": "tool", "content": f"The porter moved box {i}. Nothing else happened."} for i in range(50)])
        out = a.recall(pattern="porter", before=40, max_chars=600).splitlines()
        self.assertRegex(out[0], r"^\[36 matches; showing the \d+ nearest before message 40; \d+ earlier ones are not shown")
        self.assertEqual(out[-1], "message 40 (tool): The porter moved box 35.")     # the nearest one is there
        self.assertLessEqual(sum(len(x) + 1 for x in out), 600)
        self.assertLess(len(out), 20)
        onward = a.recall(pattern="porter", after=10, max_chars=600).splitlines()
        self.assertEqual(onward[1], "message 10 (tool): The porter moved box 5.")
        self.assertLessEqual(sum(len(x) + 1 for x in onward), 600)

    def test_text_of_counts_calls_and_parts(self):
        m = {"role": "assistant", "content": [{"type": "text", "text": "hello"}], "reasoning_content": "hmm",
             "tool_calls": [{"function": {"name": "bash", "arguments": "{}"}}]}
        self.assertEqual(ck.text_of(m), "(thinking) hmm\nhello\n(tool call) bash {}")


class Http(unittest.TestCase):
    def test_through_the_wire(self):
        model = Model()

        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                data = b'{"data": [{"id": "m"}]}'
                self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                data = json.dumps(model(body)).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        up = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        threading.Thread(target=up.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{up.server_address[1]}"
        with tempfile.TemporaryDirectory() as d:
            keeper = ck.Keeper(lambda b: ck.post_json(base + "/v1/chat/completions", b, 30), Path(d), budget=2400,
                               reply_reserve=400, headroom=100, target_ratio=0.5, notes_cap=400)
            px = ThreadingHTTPServer(("127.0.0.1", 0), ck.make_handler(keeper, base, 30))
            threading.Thread(target=px.serve_forever, daemon=True).start()
            me = f"http://127.0.0.1:{px.server_address[1]}"
            self.assertEqual(json.load(urllib.request.urlopen(me + "/v1/models", timeout=10)), {"data": [{"id": "m"}]})
            for n in (5, 30):
                out = ck.post_json(me + "/v1/chat/completions", {"model": "m", "messages": conversation(n)}, 30)
            self.assertTrue(out["choices"][0]["message"]["content"].startswith("ok "))
            req = urllib.request.Request(me + "/v1/chat/completions", data=json.dumps(
                {"model": "m", "messages": conversation(30), "stream": True}).encode(), headers={"Content-Type": "application/json"})
            sse = urllib.request.urlopen(req, timeout=30).read().decode()
            self.assertTrue(sse.startswith("data: {"))
            self.assertTrue(sse.rstrip().endswith("data: [DONE]"))
            self.assertEqual(json.loads(sse.split("\n\n")[0][6:])["choices"][0]["delta"]["role"], "assistant")
            status = json.load(urllib.request.urlopen(me + "/ctxkeeper/status", timeout=10))
            self.assertGreater(next(iter(status.values()))["cut"], 0)
            px.shutdown(); up.shutdown(); px.server_close(); up.server_close()


if __name__ == "__main__":
    unittest.main()
