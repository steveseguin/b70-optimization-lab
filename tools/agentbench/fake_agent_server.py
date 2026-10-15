#!/usr/bin/env python3
"""fake_agent_server.py: a scripted OpenAI-compatible model for agentbench plumbing tests (no model, no GPU).

  fake_agent_server.py PORT --log requests.jsonl     (prints "listening PORT pid PID")

Derived from experiments/qwen38-27b-b70/scripts/context/fake_openai_server.py, made agent-neutral: third-party agents
name their shell tool differently (bash, shell, run_shell_command, execute_bash, terminal, developer__shell,
execute_command, Bash, exec_command, ...) and want different arguments, so the script finds the shell tool in the
request's `tools`, fills every required argument from its JSON schema, and plays this script, one tool call per
request:

  1. `next`               (the first ticket must come back in the next request)
  2. `t SplitAtTests`     (the tests of ticket 1 run in /app)
  3. `next`               (the second ticket)
  4. finish: the agent's own finish tool if it has one (finish, attempt_completion, submit, task_complete, ...),
     else `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` if the prompt asks for that (mini-swe-agent), else a plain
     text reply with no tool call.

The step is the number of tool-carrying requests this conversation has made so far (counted by the fake: behind
ctxkeeper the request holds only the proxy's view, not the whole history). Replies look like vLLM's (content null with tool calls, a `reasoning` field, ids
`chatcmpl-tool-...`). Requests without tools (titles, summaries) get a short text. ctxkeeper's own notes requests
are answered in the layout it asks for. FAKE_SCRIPT=next,next,... changes the script (FINISH is implied at the end).
Every request body is appended to --log in full (one JSON line each), so the plumbing check can read what arrived.
/v1/responses and /v1/completions answer 404: the campaign is Chat Completions only.
"""
import argparse, json, os, re, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = os.environ.get("FAKE_MODEL", "qwen38-27b-fp8")
SCRIPT = [s.strip() for s in os.environ.get("FAKE_SCRIPT", "next,t SplitAtTests,next").split(",") if s.strip()]
# History stress (FAKE_BIG_STEPS=N, FAKE_BIG_CHARS=C): after the first step, N commands that each print C characters
# of seeded random text, so the agent's history passes ~1M tokens (4M characters) and any compaction of its own
# would show up as a request that no longer starts with the one before.
BIG_STEPS, BIG_CHARS = int(os.environ.get("FAKE_BIG_STEPS", "0")), int(os.environ.get("FAKE_BIG_CHARS", "24000"))
SCRIPT = SCRIPT[:1] + ["BIG %d" % i for i in range(BIG_STEPS)] + SCRIPT[1:]


def big_command(k):
    return ("python3 -c \"import random; r = random.Random(%d); a = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'; "
            "print('\\n'.join(' '.join(''.join(r.choice(a) for _ in range(r.randint(3, 9))) for _ in range(12)) for _ in range(%d)))\""
            % (k, max(1, BIG_CHARS // 84)))
# Slow reply (FAKE_DELAY_S=N): the reply to step FAKE_DELAY_STEP (default 1, the second request) waits N seconds,
# so an agent whose request timeout is shorter shows up as a retry or a failure.
DELAY_S, DELAY_STEP = float(os.environ.get("FAKE_DELAY_S", "0")), int(os.environ.get("FAKE_DELAY_STEP", "1"))
SHELL_NAMES = ["bash", "shell", "run_shell_command", "execute_bash", "terminal", "developer__shell", "execute_command",
               "exec_command", "shell_command", "run_command", "run_commands", "run_terminal_cmd", "command", "execute"]
FINISH_NAMES = ["finish", "attempt_completion", "submit_and_exit", "submit", "task_complete", "complete_task", "task_done",
                "done", "final_answer", "complete", "finish_task", "end_task"]
SUBMIT_WORD = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
LOCK = threading.Lock()
LOG = None


def fn_of(t):
    if not isinstance(t, dict):
        return {}
    return t.get("function") if isinstance(t.get("function"), dict) else t


def find_tool(tools, names, want_cmd):
    by = {}
    for t in tools or []:
        f = fn_of(t)
        if f.get("name"):
            by[f["name"]] = f
    for n in names:                                     # exact names first, then case-insensitive
        if n in by:
            return by[n]
    low = {k.lower(): v for k, v in by.items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    if want_cmd:                                        # any tool with a command/cmd argument
        for f in by.values():
            props = ((f.get("parameters") or {}).get("properties") or {})
            if "command" in props or "cmd" in props or "commands" in props:
                if f["name"] not in ("recall",):
                    return f
    return None


def fill(schema, name, value_for):
    """A value for one argument: the caller's value if it names one, else a harmless default by type."""
    if name in value_for:
        v = value_for[name]
        return v(schema) if callable(v) else v
    if "enum" in (schema or {}):
        en = schema["enum"]
        return "LOW" if "LOW" in en else en[0]
    t = (schema or {}).get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "string")
    if t == "boolean":
        return False
    if t in ("integer", "number"):
        return 120 if "timeout" in name else 1
    if t == "array":
        return []
    if t == "object":
        return {}
    return "scripted step"


def args_for(f, value_for):
    p = f.get("parameters") or {}
    props = p.get("properties") or {}
    req = set(p.get("required") or [])
    out = {}
    for k, s in props.items():
        if k in req or k in value_for:
            out[k] = fill(s, k, value_for)
    return out


def shell_args(f, cmd):
    def command(schema):
        t = (schema or {}).get("type")
        if t == "array" or (isinstance(t, list) and "array" in t):
            return ["bash", "-lc", cmd]
        return cmd
    return args_for(f, {"command": command, "cmd": command, "commands": [cmd], "description": "scripted step", "is_background": False,
                        "requires_approval": False, "security_risk": lambda s: "LOW" if "LOW" in (s or {}).get("enum", ["LOW"]) else s["enum"][0]})


def text_of(m):
    c = m.get("content")
    if isinstance(c, list):
        c = "\n".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
    return str(c or "")


STEPS = {}


def next_step(msgs):
    """The script position of this conversation, counted here: behind ctxkeeper the request holds only the proxy's
    cut-down view, so the history cannot be counted. A conversation is its system messages + first user message."""
    h = 0
    while h < len(msgs) and msgs[h].get("role") in ("system", "developer"):
        h += 1
    h += 1 if h < len(msgs) and msgs[h].get("role") == "user" else 0
    key = json.dumps([[m.get("role"), text_of(m)] for m in msgs[:h]])
    with LOCK:
        step = STEPS.get(key, 0)
        STEPS[key] = step + 1
    return step


def reply_message(req):
    """(message, finish_reason) for one tool-carrying request."""
    msgs = req.get("messages") or []
    tools = req.get("tools") or []
    shell = find_tool(tools, SHELL_NAMES, True)
    step = next_step(msgs)
    if DELAY_S and step == DELAY_STEP:                 # a long silent wait, as a long reply behind ctxkeeper gives
        with LOCK:
            LOG.write(json.dumps({"t": time.time(), "delay_start": True, "seconds": DELAY_S}) + "\n"); LOG.flush()
        time.sleep(DELAY_S)
        with LOCK:
            LOG.write(json.dumps({"t": time.time(), "delay_end": True}) + "\n"); LOG.flush()
    if shell and step < len(SCRIPT):
        cmd = SCRIPT[step]
        if cmd.startswith("BIG "):
            cmd = big_command(int(cmd.split()[1]))
        call = {"id": "chatcmpl-tool-%s" % uuid.uuid4().hex[:16], "type": "function",
                "function": {"name": shell["name"], "arguments": json.dumps(shell_args(shell, cmd))}}
        return ({"role": "assistant", "content": None, "tool_calls": [call],
                 "reasoning": f"Scripted step {step + 1}: run `{cmd}`."}, "tool_calls")
    fin = find_tool(tools, FINISH_NAMES, False)
    if fin:
        a = args_for(fin, {"message": "All tickets are handled; the job is done.", "result": "All tickets are handled; the job is done.",
                           "summary": "All tickets are handled; the job is done.", "outcome": "success"})
        call = {"id": "chatcmpl-tool-%s" % uuid.uuid4().hex[:16], "type": "function",
                "function": {"name": fin["name"], "arguments": json.dumps(a)}}
        return ({"role": "assistant", "content": None, "tool_calls": [call], "reasoning": "Scripted finish."}, "tool_calls")
    prompt = "\n".join(text_of(m) for m in msgs[:3])
    if shell and SUBMIT_WORD in prompt and not any(SUBMIT_WORD in json.dumps(m.get("tool_calls") or []) for m in msgs):
        call = {"id": "chatcmpl-tool-%s" % uuid.uuid4().hex[:16], "type": "function",
                "function": {"name": shell["name"], "arguments": json.dumps(shell_args(shell, "echo " + SUBMIT_WORD))}}
        return ({"role": "assistant", "content": None, "tool_calls": [call], "reasoning": "Scripted submit."}, "tool_calls")
    return ({"role": "assistant", "content": "All tickets are handled; the job is done.", "reasoning": "Scripted end."}, "stop")


def text_reply_for_untooled(req):
    """Requests without tools: a text-parsing agent (a fenced command), a title/summary call, or a keeper notes call."""
    msgs = req.get("messages") or []
    ask = text_of(msgs[-1]) if msgs else ""
    if "=== TURNS BEING MOVED OUT ===" in ask:
        if "NEW RULES" in ask:
            return "NEW RULES\n- Stub rule: answer politely.\nCHANGES\nstubitems: 1\nOPEN\n- nothing"
        return "RULES\n- Stub rule: answer politely.\nSTATE\nstubitems: 1\nOPEN\n- nothing"
    sysmsg = "\n".join(text_of(m) for m in msgs if m.get("role") == "system")
    if "```" in sysmsg and ("bash" in sysmsg.lower()):     # a text-parsed agent: answer with one fenced command
        done = sum(1 for m in msgs if m.get("role") == "assistant" and "```" in text_of(m))
        if done < len(SCRIPT):
            return f"THOUGHT: scripted step {done + 1}.\n\n```bash\n{SCRIPT[done]}\n```"
        if SUBMIT_WORD in sysmsg:
            return f"THOUGHT: scripted submit.\n\n```bash\necho {SUBMIT_WORD}\n```"
        return "All tickets are handled; the job is done."
    return "Repair queue"


def sse(resp):
    c = resp["choices"][0]
    m = c["message"]
    delta = {"role": "assistant"}
    if m.get("reasoning"):
        delta["reasoning"] = m["reasoning"]
        delta["reasoning_content"] = m["reasoning"]
    if m.get("content") is not None:
        delta["content"] = m["content"]
    if m.get("tool_calls"):
        delta["tool_calls"] = [dict(t, index=i) for i, t in enumerate(m["tool_calls"])]
    base = {k: resp[k] for k in ("id", "created", "model")}
    out = "data: " + json.dumps(dict(base, object="chat.completion.chunk",
                                     choices=[{"index": 0, "delta": delta, "finish_reason": c["finish_reason"]}])) + "\n\n"
    out += "data: " + json.dumps(dict(base, object="chat.completion.chunk", choices=[], usage=resp["usage"])) + "\n\n"
    return (out + "data: [DONE]\n\n").encode()


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json"):
        b = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _log(self, rec):
        with LOCK:
            LOG.write(json.dumps(rec) + "\n")
            LOG.flush()

    def do_GET(self):
        self._log({"t": time.time(), "method": "GET", "path": self.path})
        if self.path.rstrip("/").endswith("/models"):
            return self._send({"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "vllm",
                                                           "max_model_len": int(os.environ.get("FAKE_MAX_MODEL_LEN", "262144"))}]})
        self._send({"error": {"message": "fake: no such path"}}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            req = json.loads(raw or b"{}")
        except ValueError:
            req = {"_unparsed": raw[:200].decode("utf-8", "replace")}
        path = self.path.split("?")[0].rstrip("/")
        self._log({"t": time.time(), "method": "POST", "path": self.path, "body": req})
        if not path.endswith("/chat/completions"):
            return self._send({"error": {"message": f"fake: {path} is not served; Chat Completions only"}}, 404)
        msgs = req.get("messages") or []
        pt = sum(len(json.dumps(m)) for m in msgs) // 4 + sum(len(json.dumps(t)) for t in req.get("tools") or []) // 4 + 1
        last_user = next((text_of(m) for m in reversed(msgs) if m.get("role") == "user"), "")
        if req.get("tools") and req.get("tool_choice") == "none" and (
                last_user.startswith("[[Message from the context keeper") or last_user.startswith("Check these lines")
                or last_user.startswith("The turns mention these names") or last_user.startswith("Your reply did not use the layout")):
            msg, fr = {"role": "assistant", "content": "NEW RULES\n- Stub rule: answer politely.\nCHANGES\nstubitems: 1\nOPEN\n- nothing"}, "stop"
        elif req.get("tools"):
            msg, fr = reply_message(req)
        else:
            msg, fr = {"role": "assistant", "content": text_reply_for_untooled(req)}, "stop"
        full = {"role": "assistant", "content": None, "refusal": None, "annotations": None, "audio": None,
                "function_call": None, "tool_calls": [], "reasoning": None}
        full.update(msg)
        resp = {"id": "chatcmpl-%s" % uuid.uuid4().hex, "object": "chat.completion", "created": int(time.time()),
                "model": req.get("model") or MODEL,
                "choices": [{"index": 0, "message": full, "logprobs": None, "finish_reason": fr, "stop_reason": None}],
                "usage": {"prompt_tokens": pt, "completion_tokens": 20, "total_tokens": pt + 20, "prompt_tokens_details": None},
                "prompt_logprobs": None}
        sys.stderr.write("fake: %s msgs=%d tools=%d stream=%s -> %s\n" % (
            path, len(msgs), len(req.get("tools") or []), req.get("stream"),
            json.dumps(msg.get("tool_calls") or msg.get("content"))[:160]))
        if req.get("stream"):
            return self._send(sse(resp), ctype="text/event-stream")
        self._send(resp)


def main():
    global LOG
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", type=int)
    ap.add_argument("--log", required=True, help="append every request here (JSON lines)")
    a = ap.parse_args()
    if not 18300 <= a.port <= 18399:
        raise SystemExit("fake_agent_server: use a port in 18300-18399")
    LOG = open(a.log, "a")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    print(f"listening {a.port} pid {os.getpid()}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
