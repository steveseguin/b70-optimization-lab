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

    def test_state_survives_a_restart(self):
        s = self.run_conversation(30)
        again = ck.Keeper(self.model, Path(self.dir.name), budget=2400, reply_reserve=400, headroom=100, target_ratio=0.5,
                          notes_cap=400, memory_note=False)
        t = again.session({"model": "m", "messages": conversation(30)}, None)
        self.assertEqual((t.state["cut"], t.state["notes"]), (s.state["cut"], s.state["notes"]))


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

    def test_archive_recall(self):
        with tempfile.TemporaryDirectory() as d:
            a = ck.Archive(Path(d) / "a.jsonl")
            a.add(5, [{"role": "tool", "content": f"The porter moved box {i}. Nothing else happened."} for i in range(50)])
            out = a.recall(pattern="porter")
            self.assertIn("message 5 (tool): The porter moved box 0.", out)
            self.assertIn("50 matches; showing the first 40", out)
            self.assertEqual(a.recall(pattern="porter", before=20, last=2).splitlines()[:2],
                             ["message 19 (tool): The porter moved box 14.", "message 20 (tool): The porter moved box 15."])
            self.assertTrue(a.recall(message=7).startswith("message 7 (tool):\nThe porter moved box 2."))
            self.assertIn("is not in the archive", a.recall(message=99))
            self.assertIn("nothing in the archive matches", a.recall(pattern="zebra"))

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
