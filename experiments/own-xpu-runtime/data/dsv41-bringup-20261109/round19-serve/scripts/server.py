#!/usr/bin/env python3
"""DeepSeek V4.1 Flash on six Arc Pro B70 cards: an OpenAI-compatible LAN server around the own engine (serve-1).

One engine process holds the model and one conversation. A request whose conversation extends the held one is read
from where the engine stopped; any other conversation clears the engine (a restart: a load takes about a minute)
and is read from the start. Answers are the model's greedy text (guessing only makes them faster), so temperature
and the other sampling settings are accepted and ignored. Thinking is on by default ("thinking" / "enable_thinking"
/ "reasoning_effort" / the "-chat" model name change it); earlier answers' thinking stays in the conversation (the
template's drop_thinking=false), which is what lets a follow-up turn continue the held conversation instead of
reading everything again.

Config: config.json next to this file. Logs: logs/. Health: GET /health.
"""
import asyncio
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

import jinja2
from aiohttp import web

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text())
LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)
MODEL = CFG.get("model_name", "deepseek-v4.1-flash")
THINK_END = 128822  # </think>
EOS = 1
SIX_ACTIVE = Path("/home/steve/dsv41-work/six.active")


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOG_DIR / "server.log", "a") as f:
        f.write(line + "\n")


def jerr(cls, msg, typ="invalid_request_error", code=None):
    e = {"message": msg, "type": typ}
    if code:
        e["code"] = code
    return cls(text=json.dumps({"error": e}), content_type="application/json")


# ---------------------------------------------------------------------------------------------- tokenizer
class Tokenizer:
    """llama.cpp's tokenizer for this model (bin/tokhelper, vocabulary only)."""

    def __init__(self):
        import subprocess
        env = dict(os.environ, LD_LIBRARY_PATH=str(HERE / "lib"))
        self.p = subprocess.Popen([str(HERE / "bin" / "tokhelper"), CFG["gguf"]], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, env=env)
        self.lock = threading.Lock()
        self.p.stdin.write(b"V\n")
        self.p.stdin.flush()
        n = int(self.p.stdout.readline().split()[1])
        self.pieces = [bytes.fromhex(self.p.stdout.readline().strip().decode()) for _ in range(n)]

    def encode(self, text_bytes: bytes):
        with self.lock:
            self.p.stdin.write(b"T " + text_bytes.hex().encode() + b"\n")
            self.p.stdin.flush()
            r = self.p.stdout.readline().split()
        if not r or r[0] != b"I":
            raise RuntimeError("tokenizer failed")
        return [int(x) for x in r[1:]]

    def bytes_of(self, ids):
        return b"".join(self.pieces[i] for i in ids)


class StreamText:
    """Token bytes in, whole UTF-8 text out (a character split over tokens waits for its last byte)."""

    def __init__(self):
        self.buf = b""

    def add(self, b: bytes) -> str:
        self.buf += b
        for cut in range(len(self.buf), max(-1, len(self.buf) - 4), -1):
            try:
                s = self.buf[:cut].decode("utf-8")
            except UnicodeDecodeError:
                continue
            self.buf = self.buf[cut:]
            return s
        return ""

    def flush(self) -> str:
        s = self.buf.decode("utf-8", "replace")
        self.buf = b""
        return s


# ---------------------------------------------------------------------------------------------- template
def _tojson(x, ensure_ascii=False, indent=None, separators=None, sort_keys=False):
    return json.dumps(x, ensure_ascii=ensure_ascii, indent=indent, separators=separators, sort_keys=sort_keys)


def _raise(msg):
    raise jinja2.exceptions.TemplateError(msg)


_jenv = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, extensions=["jinja2.ext.loopcontrols"])
_jenv.filters["tojson"] = _tojson
_jenv.globals["raise_exception"] = _raise
TEMPLATE = _jenv.from_string((HERE / "chat_template.jinja").read_text())


def render(messages, thinking: bool, effort, tools=None, response_format=None) -> str:
    kw = dict(messages=messages, add_generation_prompt=True, thinking_mode="thinking" if thinking else "chat",
              drop_thinking=False, reasoning_effort=effort)
    if tools:
        kw["tools"] = tools
    if response_format:
        kw["response_format"] = response_format
    return TEMPLATE.render(**kw)


# ---------------------------------------------------------------------------------------------- tool calls
DSML = "｜DSML｜"
CALLS_OPEN = "\n\n<" + DSML + " calls>"
RE_CALLS = re.compile(r"<" + DSML + r" calls>\n?(.*?)\n?</" + DSML + r" calls>", re.S)
RE_INVOKE = re.compile(r"<" + DSML + r' invoke name="([^"]*)">\n?(.*?)\n?</' + DSML + r" invoke>", re.S)
RE_PARAM = re.compile(r"<" + DSML + r' parameter name="([^"]*)" string="(true|false)">(.*?)</' + DSML + r" parameter>", re.S)


def split_tool_calls(text):
    """(content before the calls block, [tool calls]) for an answer that may end with a DSML calls block."""
    i = text.find("<" + DSML + " calls>")
    if i < 0:
        return text, []
    m = RE_CALLS.search(text, i)
    body = m.group(1) if m else text[i:]
    calls = []
    for inv in RE_INVOKE.finditer(body):
        args = {}
        for p in RE_PARAM.finditer(inv.group(2)):
            k, is_str, v = p.group(1), p.group(2) == "true", p.group(3)
            if is_str:
                args[k] = v
            else:
                try:
                    args[k] = json.loads(v)
                except ValueError:
                    args[k] = v
        if list(args) == ["arguments"] and isinstance(args["arguments"], str):
            arg_s = args["arguments"]
        else:
            arg_s = json.dumps(args, ensure_ascii=False)
        calls.append({"id": "call_" + uuid.uuid4().hex[:24], "type": "function",
                      "function": {"name": inv.group(1), "arguments": arg_s}})
    content = text[:i]
    if content.endswith("\n\n"):
        content = content[:-2]
    return content, calls


# ---------------------------------------------------------------------------------------------- engine
class EngineError(Exception):
    pass


def release_cards():
    """Remove six.active if this server holds it (the research runs' card lock)."""
    try:
        if SIX_ACTIVE.read_text().strip() == "dsv41-server":
            SIX_ACTIVE.unlink()
            os.sync()
    except FileNotFoundError:
        pass


class Engine:
    def __init__(self):
        self.proc = None
        self.state = "stopped"  # stopped | loading | ready | fault
        self.detail = ""
        self.queues = {}
        self.reader = None
        self.starts = []
        self.max_ctx = int(CFG["max_ctx"])
        self.load_s = None
        self.errlog = None
        self.last_fatal = ""

    async def preflight(self):
        cmd = CFG.get("preflight")
        if not cmd:
            return True, ""
        p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await p.communicate()
        return p.returncode == 0, out.decode(errors="replace").strip()[-600:]

    async def start(self):
        """Start the engine; a load refused by the engine's host-memory floor (memory not yet given back after the
        previous engine) is tried again after a pause, up to load_retries times."""
        for attempt in range(1 + int(CFG.get("load_retries", 3))):
            try:
                return await self._start_once()
            except EngineError as e:
                if self.state == "fault" or "floor" not in self.last_fatal or attempt == int(CFG.get("load_retries", 3)):
                    raise
                log(f"engine load refused by the host-memory floor ({self.last_fatal}); trying again in 60 s")
                self.state, self.detail = "loading", "waiting for host memory, then loading again"
                await asyncio.sleep(60)

    async def _start_once(self):
        self.last_fatal = ""
        now = time.time()
        self.starts = [t for t in self.starts if now - t < 900] + [now]
        if len(self.starts) > CFG.get("max_starts_15min", 4):
            self.state, self.detail = "fault", "the engine was started too often in 15 minutes; see logs/ (restart the service after checking)"
            raise EngineError(self.detail)
        self.state, self.detail = "loading", "safety checks"
        ok, msg = await self.preflight()
        log("preflight: " + msg.replace("\n", " | "))
        if not ok:
            self.state, self.detail = "fault", "preflight failed: " + msg
            raise EngineError(self.detail)
        env = dict(os.environ)
        env.update({k: str(v) for k, v in CFG["engine_env"].items()})
        ts = time.strftime("%Y%m%dT%H%M%S")
        for old in sorted(LOG_DIR.glob("engine-*.log"))[:-30]:
            old.unlink(missing_ok=True)
        if self.errlog:
            self.errlog.close()
        self.errlog = open(LOG_DIR / f"engine-{ts}.log", "w")
        self.state, self.detail = "loading", "loading the model (about a minute)"
        t0 = time.time()
        log(f"engine start (context {self.max_ctx}), log engine-{ts}.log")
        self.proc = await asyncio.create_subprocess_exec(
            CFG["engine_bin"], "-", "1", "/dev/null", str(self.max_ctx), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=self.errlog, env=env, cwd=str(HERE), limit=1 << 24)
        while True:
            try:
                line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=CFG.get("load_timeout_s", 1200))
            except asyncio.TimeoutError:
                await self.kill()
                release_cards()
                self.state, self.detail = "stopped", "the engine did not load in time"
                raise EngineError(self.detail)
            if not line:
                rc = await self.proc.wait()
                self.proc = None
                release_cards()
                self.errlog.flush()
                try:
                    fat = [l for l in (LOG_DIR / f"engine-{ts}.log").read_text(errors="replace").splitlines() if l.startswith("fatal:")]
                    self.last_fatal = fat[-1] if fat else ""
                except OSError:
                    self.last_fatal = ""
                self.state, self.detail = "stopped", f"the engine exited while loading (code {rc}): {self.last_fatal or 'see logs/engine-' + ts + '.log'}"
                raise EngineError(self.detail)
            if line.startswith(b"@@READY"):
                break
        self.load_s = time.time() - t0
        self.state, self.detail = "ready", ""
        log(f"engine ready in {self.load_s:.0f} s")
        self.reader = asyncio.create_task(self._read(self.proc))

    async def _read(self, proc):
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            if not line.startswith(b"@@"):
                continue
            parts = line.decode(errors="replace").split()
            kind, rid = parts[0][2:], parts[1] if len(parts) > 1 else "-"
            q = self.queues.get(rid)
            if q is not None:
                q.put_nowait((kind, parts[2:]))
        rc = await proc.wait()
        if self.proc is proc:  # (not a stop we asked for)
            self.proc = None
            if self.state != "fault":
                self.state, self.detail = "stopped", f"the engine exited (code {rc})"
            log(f"engine exited with code {rc}; see the newest logs/engine-*.log")
            release_cards()
            for q in self.queues.values():
                q.put_nowait(("X", [str(rc)]))

    async def stop(self):
        proc = self.proc
        if not proc:
            return
        self.proc = None
        try:
            proc.stdin.write(b"Q\n")
            await proc.stdin.drain()
            proc.stdin.close()
        except Exception:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=180)
        except asyncio.TimeoutError:
            log("engine did not quit in 180 s: terminating it")
            await self._kill_proc(proc)
        self.state = "stopped"
        release_cards()
        log("engine stopped")

    async def _kill_proc(self, proc):
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=60)
        except Exception:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass

    async def kill(self):
        if self.proc:
            p, self.proc = self.proc, None
            await self._kill_proc(p)

    async def send(self, line: str):
        if not self.proc:
            raise EngineError("the engine is not running")
        self.proc.stdin.write(line.encode() + b"\n")
        await self.proc.stdin.drain()


ENGINE = Engine()
TOK = None
LOCK = asyncio.Lock()
STATS = {"waiting": 0, "requests": 0, "new_conversations": 0, "restarts_for_new_conversation": 0}


class Session:
    """What the engine holds: the token ids (the last answer token included) and the conversation behind them."""

    def __init__(self):
        self.clear()

    def clear(self):
        self.ids = []
        self.raw = b""
        self.msgs = []  # the last request's messages + our answer (exact thinking and text)
        self.mode = None


SESSION = Session()


def _text_of(c):
    if isinstance(c, list):
        return "".join(b.get("text", "") for b in c if isinstance(b, dict))
    return c or ""


def _calls_key(tcs):
    out = []
    for tc in tcs or []:
        fn = tc.get("function", tc)
        a = fn.get("arguments")
        if isinstance(a, str):
            try:
                a = json.loads(a)
            except ValueError:
                pass
        out.append((fn.get("name"), json.dumps(a, sort_keys=True, ensure_ascii=False)))
    return out


def merge_known(msgs, mode):
    """The request's messages with our exact earlier answers put back (clients often drop the thinking, trim the
    text, or re-encode tool calls), so the rendered conversation extends what the engine holds. Each answer of ours
    is kept as {content, reasoning_content (exact), visible, exact_calls}; the template reads only the first two."""
    if SESSION.mode != mode or not SESSION.msgs:
        return msgs
    out = list(msgs)
    for i, ours in enumerate(SESSION.msgs[:len(msgs)]):
        if ours.get("role") != "assistant" or "visible" not in ours:
            continue
        m = msgs[i]
        if m.get("role") != "assistant":
            return msgs  # (another conversation)
        if _text_of(m.get("content")).strip() != (ours["visible"] or "").strip():
            continue
        if _calls_key(m.get("tool_calls")) != _calls_key(ours.get("exact_calls")):
            continue
        out[i] = ours
    return out


async def _engine_job(prompt_bytes: bytes, mode, max_new: int, on_event, ctl):
    STATS["waiting"] += 1
    try:
        await LOCK.acquire()
    finally:
        STATS["waiting"] -= 1
    try:
        if not ctl["alive"]():
            raise EngineError("the client left before its turn")
        if ENGINE.state == "fault":
            raise EngineError(ENGINE.detail)
        STATS["requests"] += 1
        loop = asyncio.get_running_loop()
        extend = bool(SESSION.mode == mode and SESSION.ids and ENGINE.state == "ready" and
                      prompt_bytes.startswith(SESSION.raw) and len(prompt_bytes) > len(SESSION.raw))
        if extend:
            tail = await loop.run_in_executor(None, TOK.encode, prompt_bytes[len(SESSION.raw):])
            ids = SESSION.ids + tail
        else:
            ids = await loop.run_in_executor(None, TOK.encode, prompt_bytes)
        room = ENGINE.max_ctx - 16 - len(ids)
        if room < 1:
            raise jerr(web.HTTPBadRequest, f"the conversation ({len(ids)} tokens) does not fit the context "
                       f"({ENGINE.max_ctx} tokens)", code="context_length_exceeded")
        max_new = max(1, min(max_new, room))
        if not extend and SESSION.ids:
            if ENGINE.state == "ready" and not CFG.get("reset_in_engine", True):
                STATS["restarts_for_new_conversation"] += 1
                log(f"new conversation ({len(ids)} tokens): restarting the engine to clear the held one ({len(SESSION.ids)} tokens)")
                await ENGINE.stop()
            elif ENGINE.state == "ready":  # reset-1: the engine clears the held conversation itself (@@R)
                STATS["new_conversations"] += 1
                log(f"new conversation ({len(ids)} tokens): the engine clears the held one ({len(SESSION.ids)} tokens)")
            SESSION.clear()
        if ENGINE.state != "ready":
            SESSION.clear()
            await ENGINE.start()
        rid = uuid.uuid4().hex[:12]
        q = asyncio.Queue()
        ENGINE.queues[rid] = q
        gen = []
        t0 = time.time()
        stopped = False
        try:
            await ENGINE.send(f"G {rid} {max_new} 1 {EOS} {len(ids)} " + " ".join(map(str, ids)))
            done = None
            while done is None:
                kind, data = await q.get()
                if kind in ("T", "P"):
                    vals = [int(x) for x in data] if kind == "T" else data
                    if kind == "T":
                        gen.extend(vals)
                    if not stopped:
                        try:
                            if not ctl["alive"]():
                                raise ConnectionResetError
                            want_stop = await on_event(kind, vals)
                        except (ConnectionResetError, RuntimeError, asyncio.CancelledError):
                            want_stop = True
                        if want_stop:
                            stopped = True
                            await ENGINE.send(f"S {rid}")
                elif kind == "D":
                    done = data
                elif kind == "E":
                    SESSION.clear()
                    await ENGINE.stop()
                    raise EngineError("the engine refused the request: " + " ".join(data))
                elif kind == "X":
                    SESSION.clear()
                    raise EngineError("the engine stopped during the request (code " + data[0] + "); it restarts with the next request")
        finally:
            ENGINE.queues.pop(rid, None)
        SESSION.ids = ids + gen
        SESSION.raw = TOK.bytes_of(SESSION.ids)
        SESSION.mode = mode
        SESSION.msgs = []
        tm = {"prompt_tokens": len(ids), "read_tokens": int(done[1]), "read_s": float(done[3]), "answer_tokens": len(gen),
              "answer_s": float(done[4]), "cycles": int(done[5]), "guesses": int(done[6]), "kept_guesses": int(done[7]),
              "context_used": int(done[8]), "total_s": round(time.time() - t0, 3)}
        tm["answer_tok_per_s"] = round(len(gen) / max(1e-6, tm["answer_s"]), 2)
        tm["read_tok_per_s"] = round(tm["read_tokens"] / max(1e-6, tm["read_s"]), 1)
        log(f"request: conversation {len(ids)} tokens, read {tm['read_tokens']} in {tm['read_s']:.1f} s, "
            f"answered {len(gen)} in {tm['answer_s']:.1f} s ({tm['answer_tok_per_s']} tok/s), end {done[0]}")
        return done[0], gen, tm
    finally:
        LOCK.release()


async def run_request(request, prompt_bytes: bytes, mode, max_new: int, on_event):
    """Runs the engine job as its own task: a client that leaves stops the answer at the next cycle, and the
    conversation the engine holds stays consistent."""
    ctl = {"alive": lambda: request.transport is not None and not request.transport.is_closing()}
    job = asyncio.create_task(_engine_job(prompt_bytes, mode, max_new, on_event, ctl))
    try:
        return await asyncio.shield(job)
    except asyncio.CancelledError:
        ctl["alive"] = lambda: False
        raise


def finish_reason(r, has_calls=False):
    if has_calls:
        return "tool_calls"
    return {"eos": "stop", "max": "length", "stop": "stop"}.get(r, "stop")


def parse_mode(body):
    thinking = True
    kw = body.get("chat_template_kwargs") or {}
    t = body.get("thinking")
    if isinstance(t, dict):
        thinking = t.get("type", "enabled") != "disabled"
    elif isinstance(t, bool):
        thinking = t
    if "enable_thinking" in body:
        thinking = bool(body["enable_thinking"])
    if "enable_thinking" in kw:
        thinking = bool(kw["enable_thinking"])
    if isinstance(kw.get("thinking"), bool):
        thinking = kw["thinking"]
    if kw.get("thinking_mode") in ("chat", "thinking"):
        thinking = kw["thinking_mode"] == "thinking"
    effort = kw.get("reasoning_effort", body.get("reasoning_effort"))
    if isinstance(body.get("reasoning"), dict) and body["reasoning"].get("effort"):
        effort = body["reasoning"]["effort"]
    if effort == "none":
        thinking, effort = False, "high"
    elif effort == "minimal":
        effort = "low"
    elif effort == "xhigh":
        effort = "max"
    if not (effort in ("low", "medium", "high", "max") or (isinstance(effort, int) and 1 <= effort <= 100)):
        effort = "high"
    if str(body.get("model", "")).endswith("-chat"):
        thinking = False
    return thinking, effort


def norm_messages(msgs):
    out = []
    for m in msgs:
        if not isinstance(m, dict) or "role" not in m:
            raise jerr(web.HTTPBadRequest, "each message needs a role")
        m = dict(m)
        c = m.get("content")
        if isinstance(c, list):
            parts = []
            for b in c:
                if isinstance(b, dict) and b.get("type") in ("image_url", "image", "input_image"):
                    raise jerr(web.HTTPBadRequest, "images are not supported by this server yet")
                if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text"):
                    parts.append(b.get("text", ""))
                elif isinstance(b, str):
                    parts.append(b)
            m["content"] = "\n\n".join(parts)
        if m.get("role") == "developer":
            m["role"] = "system"
        if m.get("role") == "assistant" and m.get("tool_calls"):
            tcs = []
            for tc in m["tool_calls"]:
                fn = dict(tc.get("function", tc))
                a = fn.get("arguments")
                if isinstance(a, str):
                    try:
                        fn["arguments"] = json.loads(a) if a.strip() else {}
                    except ValueError:
                        fn["arguments"] = {"arguments": a}
                tcs.append(dict(tc, function=fn))
            m["tool_calls"] = tcs
        out.append(m)
    return out


def sse(obj):
    return b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\n\n"


async def chat_completions(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        raise jerr(web.HTTPBadRequest, "invalid JSON")
    msgs = body.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise jerr(web.HTTPBadRequest, "messages required")
    thinking, effort = parse_mode(body)
    tools = body.get("tools") or None
    if body.get("tool_choice") == "none":
        tools = None
    mode = ("thinking" if thinking else "chat", str(effort), json.dumps(tools, sort_keys=True))
    raw_msgs = norm_messages(msgs)
    msgs = merge_known(raw_msgs, mode)
    try:
        prompt = render(msgs, thinking, effort, tools, body.get("response_format"))
    except jinja2.exceptions.TemplateError as e:
        raise jerr(web.HTTPBadRequest, f"template: {e}")
    max_new = int(body.get("max_completion_tokens") or body.get("max_tokens") or CFG.get("default_max_tokens", 32768))
    stops = body.get("stop") or []
    if isinstance(stops, str):
        stops = [stops]
    stops = [s for s in stops if isinstance(s, str) and s]
    stream = bool(body.get("stream"))
    cid = "chatcmpl-" + uuid.uuid4().hex[:24]
    created = int(time.time())
    rtext, ctext = StreamText(), StreamText()
    st = {"in_think": thinking, "reasoning": "", "content": "", "sent": 0, "stop_hit": False}
    resp = None
    hold = max([len(CALLS_OPEN)] + [len(s) for s in stops]) if (tools or stops) else 0

    def chunk(delta, fin=None):
        return {"id": cid, "object": "chat.completion.chunk", "created": created, "model": MODEL,
                "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}

    def take(toks):
        r = ""
        for t in toks:
            if t == EOS:
                continue
            if st["in_think"]:
                if t == THINK_END:
                    st["in_think"] = False
                    r += rtext.flush()
                    continue
                r += rtext.add(TOK.pieces[t])
            elif not st["stop_hit"]:
                st["content"] += ctext.add(TOK.pieces[t])
        st["reasoning"] += r
        if stops and not st["stop_hit"]:
            for s in stops:
                j = st["content"].find(s)
                if j >= 0:
                    st["content"] = st["content"][:j]
                    st["stop_hit"] = True
        return r

    def visible_upto():
        """How much of the content can be sent now (a possible tool-call block or stop string start is held)."""
        c = st["content"]
        if tools:
            j = c.find("<" + DSML + " calls>")
            if j >= 0:
                return max(st["sent"], j - 2 if c[max(0, j - 2):j] == "\n\n" else j)
        if st["stop_hit"] or not hold:
            return len(c)
        return max(st["sent"], len(c) - hold)

    async def on_event(kind, data):
        if kind != "T":
            return False
        r = take(data)
        if stream:
            if r:
                await resp.write(sse(chunk({"reasoning_content": r})))
            n = visible_upto()
            if n > st["sent"]:
                await resp.write(sse(chunk({"content": st["content"][st["sent"]:n]})))
                st["sent"] = n
        return st["stop_hit"]

    if stream:
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache",
                                           "X-Accel-Buffering": "no"})
        await resp.prepare(request)
        await resp.write(sse(chunk({"role": "assistant", "content": ""})))
    try:
        reason, gen, tm = await run_request(request, prompt.encode(), mode, max_new, on_event)
    except EngineError as e:
        log(f"error: {e}")
        if stream:
            try:
                await resp.write(sse({"error": {"message": str(e), "type": "server_error"}}))
                await resp.write(b"data: [DONE]\n\n")
            except Exception:
                pass
            return resp
        raise jerr(web.HTTPServiceUnavailable, str(e), "server_error")
    except web.HTTPException as e:
        if stream:
            try:
                await resp.write(sse(json.loads(e.text)))
                await resp.write(b"data: [DONE]\n\n")
            except Exception:
                pass
            return resp
        raise
    tail_r = rtext.flush()
    st["reasoning"] += tail_r
    if not st["stop_hit"]:
        st["content"] += ctext.flush()
    content, calls = split_tool_calls(st["content"]) if tools else (st["content"], [])
    # our exact answer, kept so the next turn continues the held conversation (see merge_known)
    raw_answer = TOK.bytes_of([t for t in gen if t != EOS]).decode("utf-8", "replace")
    if thinking:
        j = raw_answer.find("</think>")
        exact_r, exact_c = (raw_answer[:j], raw_answer[j + len("</think>"):]) if j >= 0 else (raw_answer, "")
    else:
        exact_r, exact_c = None, raw_answer
    if not st["stop_hit"] and reason != "stop":
        SESSION.msgs = list(msgs) + [{"role": "assistant", "content": exact_c, "reasoning_content": exact_r,
                                      "visible": content, "exact_calls": calls}]
    usage = {"prompt_tokens": tm["prompt_tokens"], "completion_tokens": len(gen),
             "total_tokens": tm["prompt_tokens"] + len(gen),
             "prompt_tokens_details": {"cached_tokens": tm["prompt_tokens"] - tm["read_tokens"]}}
    fin = "stop" if st["stop_hit"] else finish_reason(reason, bool(calls))
    if stream:
        try:
            if tail_r:
                await resp.write(sse(chunk({"reasoning_content": tail_r})))
            if len(content) > st["sent"]:
                await resp.write(sse(chunk({"content": content[st["sent"]:]})))
            if calls:
                await resp.write(sse(chunk({"tool_calls": [dict(c, index=i) for i, c in enumerate(calls)]})))
            await resp.write(sse(chunk({}, fin)))
            if (body.get("stream_options") or {}).get("include_usage"):
                await resp.write(sse({"id": cid, "object": "chat.completion.chunk", "created": created, "model": MODEL,
                                      "choices": [], "usage": usage, "timings": tm}))
            await resp.write(b"data: [DONE]\n\n")
        except (ConnectionResetError, RuntimeError):
            pass
        return resp
    msg = {"role": "assistant", "content": content if (content or not calls) else None}
    if thinking:
        msg["reasoning_content"] = st["reasoning"]
    if calls:
        msg["tool_calls"] = calls
    return web.json_response({"id": cid, "object": "chat.completion", "created": created, "model": MODEL,
                              "choices": [{"index": 0, "message": msg, "finish_reason": fin}], "usage": usage,
                              "timings": tm}, dumps=lambda o: json.dumps(o, ensure_ascii=False))


async def completions(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        raise jerr(web.HTTPBadRequest, "invalid JSON")
    prompt = body.get("prompt")
    if isinstance(prompt, list):
        prompt = prompt[0] if prompt else ""
    if not isinstance(prompt, str) or not prompt:
        raise jerr(web.HTTPBadRequest, "prompt (text) required")
    max_new = int(body.get("max_tokens") or 256)
    text = StreamText()
    acc = []
    stream = bool(body.get("stream"))
    cid = "cmpl-" + uuid.uuid4().hex[:24]
    created = int(time.time())
    resp = None
    if stream:
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
        await resp.prepare(request)

    async def on_event(kind, data):
        if kind != "T":
            return False
        s = "".join(text.add(TOK.pieces[t]) for t in data if t != EOS)
        acc.append(s)
        if stream and s:
            await resp.write(sse({"id": cid, "object": "text_completion", "created": created, "model": MODEL,
                                  "choices": [{"index": 0, "text": s, "finish_reason": None}]}))
        return False

    try:
        reason, gen, tm = await run_request(request, prompt.encode(), ("raw",), max_new, on_event)
    except EngineError as e:
        if stream:
            await resp.write(sse({"error": {"message": str(e), "type": "server_error"}}))
            await resp.write(b"data: [DONE]\n\n")
            return resp
        raise jerr(web.HTTPServiceUnavailable, str(e), "server_error")
    acc.append(text.flush())
    usage = {"prompt_tokens": tm["prompt_tokens"], "completion_tokens": len(gen), "total_tokens": tm["prompt_tokens"] + len(gen)}
    if stream:
        await resp.write(sse({"id": cid, "object": "text_completion", "created": created, "model": MODEL,
                              "choices": [{"index": 0, "text": "", "finish_reason": finish_reason(reason)}], "usage": usage}))
        await resp.write(b"data: [DONE]\n\n")
        return resp
    return web.json_response({"id": cid, "object": "text_completion", "created": created, "model": MODEL,
                              "choices": [{"index": 0, "text": "".join(acc), "finish_reason": finish_reason(reason)}],
                              "usage": usage, "timings": tm}, dumps=lambda o: json.dumps(o, ensure_ascii=False))


async def tokenize(request):
    body = await request.json()
    ids = await asyncio.get_running_loop().run_in_executor(None, TOK.encode, str(body.get("content", "")).encode())
    return web.json_response({"tokens": ids})


async def models(request):
    return web.json_response({"object": "list", "data": [
        {"id": MODEL, "object": "model", "owned_by": "local", "context_length": ENGINE.max_ctx},
        {"id": MODEL + "-chat", "object": "model", "owned_by": "local", "context_length": ENGINE.max_ctx}]})


async def health(request):
    return web.json_response({"status": ENGINE.state, "detail": ENGINE.detail, "model": MODEL, "context": ENGINE.max_ctx,
                              "held_conversation_tokens": len(SESSION.ids), "busy": LOCK.locked(),
                              "waiting": STATS["waiting"], "requests": STATS["requests"],
                              "new_conversations": STATS["new_conversations"],
                              "restarts_for_new_conversation": STATS["restarts_for_new_conversation"],
                              "last_load_s": ENGINE.load_s})


async def index(request):
    return web.FileResponse(HERE / "chat.html")


async def on_startup(app):
    global TOK
    TOK = Tokenizer()
    log(f"server up on {CFG.get('host', '0.0.0.0')}:{CFG.get('port', 8000)}, model {MODEL}, context {ENGINE.max_ctx}")
    if CFG.get("load_at_start", True):
        async def first():
            async with LOCK:
                try:
                    await ENGINE.start()
                except EngineError as e:
                    log(f"engine start failed: {e}")
        app["first"] = asyncio.create_task(first())


async def on_shutdown(app):
    log("server stopping")
    await ENGINE.stop()


def main():
    app = web.Application(client_max_size=512 << 20)
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", chat_completions)
    app.router.add_post("/v1/completions", completions)
    app.router.add_post("/tokenize", tokenize)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host=CFG.get("host", "0.0.0.0"), port=int(CFG.get("port", 8000)), access_log=None,
                handle_signals=True, shutdown_timeout=5)


if __name__ == "__main__":
    main()
