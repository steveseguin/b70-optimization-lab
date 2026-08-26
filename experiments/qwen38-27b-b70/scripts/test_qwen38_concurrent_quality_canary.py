#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT = Path(__file__).with_name("qwen38-concurrent-quality-canary.py")
SPEC = importlib.util.spec_from_file_location("concurrent_quality", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        prompt = payload["messages"][-1]["content"]
        answers = [
            ("Reply with exactly", "OK"),
            ("Copy this exact phrase", "satin cobalt orbit"),
            ("There are 9 crates", "60"),
            ("Return only compact JSON", '{"answer":42,"unit":"widgets"}'),
            ("chemical symbol for gold", "Au"),
            ("Widget Z metal", "yes"),
            ("sum(i * i", "14"),
        ]
        answer = next(value for marker, value in answers if marker in prompt)
        body = json.dumps(
            {
                "choices": [{"message": {"content": answer}}],
                "usage": {
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ConcurrentQualityCanaryTest(unittest.TestCase):
    def test_seven_cases_pass_at_concurrency(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                output = Path(temp_dir) / "result.json"
                old_argv = sys.argv
                sys.argv = [
                    str(SCRIPT),
                    "--base-url",
                    f"http://127.0.0.1:{server.server_port}",
                    "--model",
                    "fixture",
                    "--concurrency",
                    "7",
                    "--rounds",
                    "1",
                    "--output-json",
                    str(output),
                ]
                try:
                    self.assertEqual(MODULE.main(), 0)
                finally:
                    sys.argv = old_argv
                result = json.loads(output.read_text())
                self.assertTrue(result["pass_all"])
                self.assertEqual(result["total_requests"], 7)
                self.assertEqual(result["results"][0]["passed"], 7)
                self.assertEqual(result["results"][0]["failed"], 0)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
