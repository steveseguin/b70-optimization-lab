#!/usr/bin/env python3
"""Tiny fake OpenAI-compatible server for wiring tests (no model, no GPU).

  fake_openai_server.py [PORT]   (default 18199; prints "listening <port> pid <pid>")

/v1/models lists one model. /v1/chat/completions answers with a scripted bash tool call
when the request carries tools: `next` until the stream ends, then write an empty
/app/answers.json, then the submit command. Without tools (e.g. a summary request) it
returns fixed text. /v1/completions returns fixed text. Usage numbers are rough
(chars/4) so the harness's tokenizer calibration has something to read.
"""
import json, os, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = os.environ.get("FAKE_MODEL", "qwen38-27b-fp8")


def plan(msgs):
    tools = "\n".join(str(m.get("content") or "") for m in msgs if m.get("role") in ("tool", "user")
                      and m is not msgs[1])  # skip the task prompt (it names the submit command)
    if "answers.json written" in tools:
        return "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
    if "STREAM END" in tools or "This was the last item" in tools:
        return "echo '{}' > /app/answers.json && echo answers.json written"
    return "next"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        sys.stderr.write("fake: " + (a[0] % a[1:]) + "\n")

    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._send({"object": "list", "data": [{"id": MODEL, "object": "model", "max_model_len": 33024}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        msgs = req.get("messages") or []
        sys.stderr.write("fake-req: " + json.dumps({k: v for k, v in req.items()
                         if k not in ("messages", "tools")} | {"n_messages": len(msgs),
                         "has_tools": bool(req.get("tools"))}) + "\n")
        pt = sum(len(json.dumps(m)) for m in msgs) // 4 or 1
        usage = {"prompt_tokens": pt, "completion_tokens": 12, "total_tokens": pt + 12}
        base = {"id": "fake-%d" % time.time_ns(), "created": int(time.time()), "model": MODEL, "usage": usage}
        if self.path.endswith("/completions") and "chat" not in self.path:
            return self._send({**base, "object": "text_completion",
                               "choices": [{"index": 0, "text": "OK", "finish_reason": "stop"}]})
        if req.get("tools"):
            cmd = plan(msgs)
            msg = {"role": "assistant", "content": "THOUGHT: scripted stub step.",
                   "tool_calls": [{"id": "call_%d" % time.time_ns(), "type": "function",
                                   "function": {"name": "bash", "arguments": json.dumps({"command": cmd})}}]}
            fr = "tool_calls"
        else:
            msg = {"role": "assistant", "content": "Stub summary: nothing to report."}
            fr = "stop"
        self._send({**base, "object": "chat.completion",
                    "choices": [{"index": 0, "message": msg, "finish_reason": fr}]})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18199
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"listening {port} pid {os.getpid()}", flush=True)
    srv.serve_forever()
