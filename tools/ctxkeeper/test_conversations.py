"""Durable conversation tests: real SQLite and subprocess CLI, scripted models, no GPU."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import ctxkeeper as ck
from test_ctxkeeper import Model, conversation, reply


class SavedConversations(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.body = {"model": "m", "messages": [{"role": "user", "content": "Remember café."}],
                     "temperature": 0, "stream": True, "stream_options": {"include_usage": True}}

    def keeper(self, model=None, **kwargs):
        return ck.Keeper(model or (lambda body: reply("Saved.")), self.root, save_conversations=True,
                         memory_note=False, **kwargs)

    def read(self, session="work", turn=None):
        return ck.Conversations(self.root).export(session, turn)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(Path(ck.__file__)), "--state-dir", str(self.root), *args],
                              capture_output=True, text=True, timeout=15)

    def test_original_request_final_response_and_managed_view_survive_process_restart(self):
        keeper = self.keeper()
        response = keeper.complete(self.body, "work")
        result = self.cli("--sessions", "export", "--session", "work")
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(result.stdout)
        self.assertEqual(saved["request"], self.body)
        self.assertEqual(saved["response"], response)
        self.assertEqual(saved["status"], "complete")
        self.assertEqual(saved["keeper_state"]["requests"], 1)
        self.assertFalse(saved["main_calls"][0]["request"]["stream"])
        self.assertNotIn("stream_options", saved["main_calls"][0]["request"])
        self.assertEqual(saved["continuation"]["headers"], {"X-Ctx-Session": "work"})
        self.assertEqual(saved["continuation"]["body"]["messages"],
                         self.body["messages"] + [response["choices"][0]["message"]])
        self.assertEqual(self.body["messages"], [{"role": "user", "content": "Remember café."}])

    def test_resume_with_new_keeper_retains_archive_and_rules(self):
        body = {"model": "m", "messages": conversation(30)}
        keeper = self.keeper(Model(), budget=2800, headroom=100, reply_reserve=300)
        keeper.complete(body, "work")
        saved = self.read()
        self.assertGreater(saved["keeper_state"]["cut"], 0)
        continued = saved["continuation"]["body"]
        continued["messages"].append({"role": "user", "content": "Continue."})
        restarted = self.keeper(Model(), budget=2800, headroom=100, reply_reserve=300)
        restarted.complete(continued, saved["continuation"]["headers"]["X-Ctx-Session"])
        self.assertNotIn("restarts", restarted.sessions["work"].state)
        self.assertIn("Always answer in French", restarted.sessions["work"].state["notes"])
        self.assertTrue((self.root / "work" / "archive.jsonl").is_file())
        self.assertEqual(len(ck.Conversations(self.root).listing("work")), 2)

    def test_branch_does_not_overwrite_old_turn_or_duplicate_messages(self):
        keeper = self.keeper()
        keeper.complete(self.body, "work")
        first = self.read()
        keeper.complete(dict(self.body, messages=[{"role": "user", "content": "New branch"}]), "work")
        keeper.complete(self.body, "work")
        self.assertEqual(self.read(turn=first["turn"]), first)
        self.assertEqual(self.read()["request"], self.body)
        with sqlite3.connect(self.root / "conversations.sqlite3") as db:
            count = db.execute("SELECT COUNT(*) FROM objects WHERE data = ?",
                               (json.dumps(self.body["messages"][0], ensure_ascii=False,
                                           separators=(",", ":")),)).fetchone()[0]
        self.assertEqual(count, 1)

    def test_multimodal_reasoning_and_parallel_tool_ids_round_trip_without_execution(self):
        calls = [{"id": key, "type": "function", "function": {"name": "bash", "arguments": "{}"}}
                 for key in ("one", "two")]
        response = reply(None, calls)
        response["choices"][0]["message"]["reasoning_content"] = "Some reasoning"
        body = dict(self.body, messages=[{"role": "user", "content": [
            {"type": "text", "text": "image"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]}])
        self.keeper(lambda body: response).complete(body, "work")
        saved = self.read()
        self.assertEqual(saved["request"], body)
        self.assertEqual(saved["response"], response)
        self.assertEqual(saved["continuation"]["pending_tool_calls"], calls)
        self.assertEqual(saved["continuation"]["body"]["messages"][-1]["reasoning_content"], "Some reasoning")

    def test_all_main_calls_are_saved_before_recall_filtering_and_retry(self):
        calls = []
        def model(body):
            calls.append(body)
            if len(calls) == 1:
                return reply(None, [{"id": "search", "type": "function", "function": {
                    "name": "recall", "arguments": '{"pattern":"café"}'}}])
            if len(calls) == 2:
                return reply("")
            return reply("Finished")
        keeper = self.keeper(model)
        response = keeper.complete(self.body, "work")
        saved = self.read()
        self.assertEqual(len(saved["main_calls"]), 3)
        self.assertEqual([c["request"] for c in saved["main_calls"]], calls)
        self.assertEqual(saved["response"], response)
        self.assertEqual(saved["main_calls"][0]["response"]["choices"][0]["message"]["tool_calls"][0]["id"], "search")
        self.assertEqual(saved["continuation"]["pending_tool_calls"], [])

    def test_input_is_durable_before_model_call_and_failure_is_not_a_completed_turn(self):
        def fail(body):
            pending = self.read()
            self.assertEqual(pending["status"], "pending")
            self.assertEqual(pending["request"], self.body)
            self.assertIsNone(pending["main_calls"][0]["response"])
            raise ConnectionError("unavailable")
        with self.assertRaises(ConnectionError):
            self.keeper(fail).complete(self.body, "work")
        saved = self.read()
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["error"], "ConnectionError")
        self.assertIsNone(saved["response"])
        self.assertIsNone(saved["continuation"])

    def test_interruption_leaves_a_pending_record_and_clears_thread_context(self):
        def interrupt(body):
            raise KeyboardInterrupt()
        keeper = self.keeper(interrupt)
        with self.assertRaises(KeyboardInterrupt):
            keeper.complete(self.body, "work")
        self.assertIsNone(keeper.clock.turn)
        saved = self.read()
        self.assertEqual(saved["status"], "pending")
        self.assertIsNone(saved["continuation"])

    def test_simultaneous_sessions_have_separate_turns(self):
        barrier = threading.Barrier(2)
        def model(body):
            barrier.wait(timeout=5)
            return reply(body["messages"][0]["content"])
        keeper = self.keeper(model)
        def run(name):
            keeper.complete({"model": "m", "messages": [{"role": "user", "content": name}]}, name)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(run, ("alpha", "beta")))
        for name in ("alpha", "beta"):
            saved = self.read(name)
            self.assertEqual(saved["response"]["choices"][0]["message"]["content"], name)
            self.assertEqual(len(saved["main_calls"]), 1)

    def test_background_calls_do_not_borrow_foreground_turn(self):
        keeper = self.keeper()
        original = keeper.ask
        def model(body):
            session = keeper.sessions["work"]
            errors = []
            def background():
                try:
                    keeper.upstream({"model": "m", "messages": [{"role": "user", "content": "prewarm"}]},
                                    session, "prewarm")
                except Exception as error:
                    errors.append(error)
            thread = threading.Thread(target=background)
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            return reply("foreground")
        def ask(body):
            return original(body) if body["messages"][0]["content"] == "prewarm" else model(body)
        keeper.ask = ask
        keeper.complete(self.body, "work")
        self.assertEqual(len(self.read()["main_calls"]), 1)

    def test_off_by_default_and_missing_journal_cli_does_not_create_files(self):
        keeper = ck.Keeper(lambda body: reply("ok"), self.root, memory_note=False)
        keeper.complete(self.body, "work")
        self.assertFalse((self.root / "conversations.sqlite3").exists())
        result = self.cli("--sessions", "list")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no saved conversations", result.stderr)
        self.assertFalse((self.root / "conversations.sqlite3").exists())

    def test_cli_lists_sessions_and_turns_and_rejects_missing_selection(self):
        keeper = self.keeper()
        keeper.complete(self.body, "work")
        result = self.cli("--sessions", "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]["session"], "work")
        result = self.cli("--sessions", "list", "--session", "work")
        self.assertEqual(json.loads(result.stdout)[0]["status"], "complete")
        result = self.cli("--sessions", "export")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("needs --session", result.stderr)
        result = self.cli("--sessions", "export", "--session", "missing")
        self.assertNotEqual(result.returncode, 0)

    def test_journal_write_failure_prevents_model_call(self):
        called = []
        keeper = self.keeper(lambda body: called.append(body))
        with patch.object(keeper.conversations, "begin", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                keeper.complete(self.body, "work")
        self.assertEqual(called, [])

    def test_corrupted_object_and_unknown_schema_are_rejected(self):
        self.keeper().complete(self.body, "work")
        with sqlite3.connect(self.root / "conversations.sqlite3") as db:
            db.execute("UPDATE objects SET data = '{}' WHERE hash IN (SELECT request FROM turns)")
        with self.assertRaisesRegex(ValueError, "missing or damaged"):
            self.read()
        with sqlite3.connect(self.root / "conversations.sqlite3") as db:
            db.execute("PRAGMA user_version = 99")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            ck.Conversations(self.root)

    def test_saved_names_do_not_collide_via_sanitization_or_escape_root(self):
        keeper = self.keeper()
        for name in (".", "..", "../outside", "work/name", "x" * 65, ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                keeper.complete(self.body, name)
        self.assertEqual(ck.Conversations(self.root).listing(), [])

    def test_schema_initialization_rolls_back_on_error_and_can_be_retried(self):
        real_connect = sqlite3.connect
        class Interrupted(sqlite3.Connection):
            def executescript(self, script):
                self.set_authorizer(lambda action, *args:
                                    sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_INDEX else sqlite3.SQLITE_OK)
                return super().executescript(script)
        with patch.object(ck.sqlite3, "connect", side_effect=lambda *a, **kw:
                          real_connect(*a, **kw, factory=Interrupted)):
            with self.assertRaises(sqlite3.DatabaseError):
                ck.Conversations(self.root, create=True)
        with real_connect(self.root / "conversations.sqlite3") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0], 0)
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(ck.Conversations(self.root, create=True).listing(), [])

    def test_abrupt_process_exit_preserves_input_and_pending_call(self):
        script = """
import os, sys
from pathlib import Path
import ctxkeeper as ck
def model(body):
    os._exit(17)
keeper = ck.Keeper(model, Path(sys.argv[1]), save_conversations=True, memory_note=False)
keeper.complete({'model': 'm', 'messages': [{'role': 'user', 'content': 'Before exit'}]}, 'crash')
"""
        result = subprocess.run([sys.executable, "-c", script, str(self.root)],
                                cwd=Path(ck.__file__).parent, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 17, result.stderr)
        saved = self.read("crash")
        self.assertEqual(saved["status"], "pending")
        self.assertEqual(saved["request"]["messages"][0]["content"], "Before exit")
        self.assertEqual(len(saved["main_calls"]), 1)
        self.assertIsNone(saved["main_calls"][0]["response"])

    def test_order_of_tool_schema_properties_and_repeated_messages_is_preserved(self):
        message = {"role": "user", "content": "Repeat"}
        tool = {"type": "function", "function": {"name": "command", "parameters": {
            "type": "object", "properties": {"zulu": {"type": "string"}, "alpha": {"type": "integer"}}}}}
        body = dict(self.body, messages=[message, message], tools=[tool])
        self.keeper().complete(body, "work")
        saved = self.read()
        self.assertEqual(saved["request"]["messages"], [message, message])
        self.assertEqual(list(saved["request"]["tools"][0]["function"]["parameters"]["properties"]), ["zulu", "alpha"])

    def test_streamed_http_reply_has_a_durable_final_response(self):
        import urllib.request
        from http.server import ThreadingHTTPServer
        keeper = self.keeper()
        server = ThreadingHTTPServer(("127.0.0.1", 0), ck.make_handler(keeper, "http://127.0.0.1:1", 5))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                                             data=json.dumps(self.body).encode(),
                                             headers={"Content-Type": "application/json", "X-Ctx-Session": "work"})
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.headers.get("Content-Type"), "text/event-stream")
                self.assertIn("data: [DONE]", response.read().decode())
            saved = self.read()
            self.assertEqual(saved["status"], "complete")
            self.assertEqual(saved["response"]["choices"][0]["message"]["content"], "Saved.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
