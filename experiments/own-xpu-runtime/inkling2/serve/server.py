#!/usr/bin/env python3
"""Inkling-2-Mini on one Arc Pro B70 card: an OpenAI-compatible LAN server around our own engine (ink_run INK_SERVE=1).

Adapted from /home/steve/dsv41-serve (the DeepSeek server): one engine process holds the model and one conversation.
A request whose conversation extends the held one is read from where the engine stopped; any other conversation
starts over in the engine (milliseconds), from the longest saved prompt in the library that it starts with (a long
document loads in seconds), else from position 0. Answers are the model's greedy text (guessing only makes them
faster and never changes them), so temperature and the other sampling settings are accepted and ignored.

The model always writes a thinking part first; "reasoning_effort" (none / minimal / low / medium / high / xhigh / max
or 0-0.99) sets how much (the chat template's "Thinking effort level"; default 0.9, the template's own), and the
"-chat" model name uses "none". Earlier answers' thinking stays in the conversation (the template renders it), which
is what lets a follow-up turn continue the held conversation instead of reading everything again.

Config: config.json next to this file. Logs: logs/. Health: GET /health. Library: POST /admin/save {"name": ...}
saves what the engine has read; GET /admin/library lists the saved prompts.
"""
import asyncio
import hashlib
import json
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import jinja2
from aiohttp import web

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text())
LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)
MODEL = CFG.get("model_name", "inkling-2-mini")
LIB = Path(CFG.get("library", "/mnt/fast-ai/inkling-cache/lib"))

# special tokens (the GGUF's vocabulary)
EOS = 200006         # <|content_model_end_sampling|>: the end of the model's turn
MSG_MODEL = 200001   # <|message_model|>
C_TEXT = 200004      # <|content_text|>
C_THINK = 200008     # <|content_thinking|>
END_MSG = 200010     # <|end_message|>
C_TOOL_JSON = 200049 # <|content_invoke_tool_json|>
C_TOOL_TEXT = 200057 # <|content_invoke_tool_text|>


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
    """llama.cpp's tokenizer for this model (bin/tokhelper, vocabulary only; Unsloth's b12588-mix release)."""

    def __init__(self):
        import subprocess
        self.p = subprocess.Popen([str(HERE / "bin" / "tokhelper"), CFG["gguf"]], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE)
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
# (the {% generation %} marks are a training-time extension; they change nothing in the text)
_TPL = re.sub(r"\{%-?\s*(end)?generation\s*-?%\}", "", (HERE / "chat_template.jinja").read_text())
TEMPLATE = _jenv.from_string(_TPL)
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def render(messages, effort, tools=None) -> str:
    kw = dict(messages=messages)
    if effort is not None:
        kw["reasoning_effort"] = effort
    if tools:
        kw["tools"] = tools
    return TEMPLATE.render(**kw)


# ---------------------------------------------------------------------------------------------- answers
class Parts:
    """The model's turn as it is written, by its special tokens: <|message_model|>[name]<|content_...|> ...
    <|end_message|> parts (thinking, text, tool calls), then the end token."""

    def __init__(self):
        self.kind = None        # None (between parts), "head", "think", "text", "tool", "tooltext", "other"
        self.head = b""
        self.reasoning = ""
        self.content = ""
        self.calls = []         # OpenAI tool calls
        self.raw_calls = []     # (name, json text) as written
        self.tool_buf = b""
        self.rt, self.ct = StreamText(), StreamText()
        self.ended = False

    def take(self, toks, pieces):
        """Returns (new reasoning text, new content text)."""
        r, c = "", ""
        for t in toks:
            if t == EOS:
                self.ended = True
                r += self.rt.flush()
                c += self.ct.flush()
                continue
            if t == MSG_MODEL:
                self.kind, self.head = "head", b""
                continue
            if t == C_THINK:
                self.kind = "think"
                continue
            if t == C_TEXT:
                self.kind = "text"
                continue
            if t in (C_TOOL_JSON, C_TOOL_TEXT):
                self.kind, self.tool_buf = ("tool" if t == C_TOOL_JSON else "tooltext"), b""
                continue
            if t == END_MSG:
                if self.kind == "think":
                    r += self.rt.flush()
                elif self.kind == "text":
                    c += self.ct.flush()
                elif self.kind in ("tool", "tooltext"):
                    self._call(self.head.decode("utf-8", "replace"), self.tool_buf.decode("utf-8", "replace"))
                self.kind = None
                continue
            b = pieces[t]
            if self.kind == "head":
                self.head += b
            elif self.kind == "think":
                r += self.rt.add(b)
            elif self.kind == "text":
                c += self.ct.add(b)
            elif self.kind in ("tool", "tooltext"):
                self.tool_buf += b
        self.reasoning += r
        self.content += c
        return r, c

    def _call(self, name, text):
        self.raw_calls.append((name, text))
        args = {}
        try:
            j = json.loads(text)
            if isinstance(j, dict):
                name = j.get("name", name) or name
                a = j.get("args", j.get("arguments", {}))
                args = a if isinstance(a, dict) else {"arguments": a}
        except ValueError:
            args = {"arguments": text}
        self.calls.append({"id": "call_" + uuid.uuid4().hex[:24], "type": "function",
                           "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}})


# ---------------------------------------------------------------------------------------------- engine
class EngineError(Exception):
    pass


class Engine:
    def __init__(self, card):
        self.card = int(card)
        self.proc = None
        self.state = "stopped"  # stopped | loading | ready | fault
        self.detail = ""
        self.queues = {}
        self.reader = None
        self.starts = []
        # context sizes the engine runs at (ctx_tiers): the smallest that holds the conversation and its answer. A
        # smaller context takes bigger prompt steps (4,096 tokens up to 64K, 2,048 to 128K, 1,024 to 300K, else 512);
        # a conversation that outgrows the size is saved, the engine restarted larger, and the save loaded back
        self.tiers = sorted(int(t) for t in (CFG.get("ctx_tiers") or [CFG["max_ctx"]]))
        self.max_ctx = self.tiers[-1]
        self.ctx = self.tiers[0]
        self.load_s = None
        self.errlog = None
        self.last_fatal = ""

    async def start(self):
        self.last_fatal = ""
        now = time.time()
        self.starts = [t for t in self.starts if now - t < 900] + [now]
        if len(self.starts) > CFG.get("max_starts_15min", 4):
            self.state, self.detail = "fault", "the engine was started too often in 15 minutes; see logs/ (restart the service after checking)"
            raise EngineError(self.detail)
        env = dict(os.environ)
        env.update({k: str(v) for k, v in CFG["engine_env"].items()})
        ts = time.strftime("%Y%m%dT%H%M%S")
        for old in sorted(LOG_DIR.glob(f"engine-c{self.card}-*.log"))[:-30]:
            old.unlink(missing_ok=True)
        if self.errlog:
            self.errlog.close()
        self.errlog = open(LOG_DIR / f"engine-c{self.card}-{ts}.log", "w")
        self.state, self.detail = "loading", "loading the model"
        t0 = time.time()
        card = str(self.card)
        log(f"engine start (card {card}, context {self.ctx}), log engine-c{card}-{ts}.log")
        self.proc = await asyncio.create_subprocess_exec(
            CFG["on_card"], card, CFG["engine_bin"], CFG["gguf"], card, "/dev/null", "0", str(self.ctx),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=self.errlog, env=env, cwd=str(HERE),
            limit=1 << 24)
        while True:
            try:
                line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=CFG.get("load_timeout_s", 300))
            except asyncio.TimeoutError:
                await self.kill()
                self.state, self.detail = "stopped", "the engine did not load in time"
                raise EngineError(self.detail)
            if not line:
                rc = await self.proc.wait()
                self.proc = None
                self.errlog.flush()
                try:
                    txt = (LOG_DIR / f"engine-c{self.card}-{ts}.log").read_text(errors="replace").splitlines()
                    fat = [l for l in txt if l.startswith("error:") or l.startswith("on-card:")]
                    self.last_fatal = fat[-1] if fat else ""
                except OSError:
                    self.last_fatal = ""
                self.state, self.detail = "stopped", f"the engine exited while loading (code {rc}): {self.last_fatal or f'see logs/engine-c{self.card}-{ts}.log'}"
                raise EngineError(self.detail)
            if line.startswith(b"@@READY"):
                break
        self.load_s = time.time() - t0
        self.state, self.detail = "ready", ""
        log(f"engine on card {self.card} ready in {self.load_s:.1f} s")
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
            log(f"engine on card {self.card} exited with code {rc}; see the newest logs/engine-c{self.card}-*.log")
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
            await asyncio.wait_for(proc.wait(), timeout=60)
        except asyncio.TimeoutError:
            log("engine did not quit in 60 s: terminating it")
            await self._kill_proc(proc)
        self.state = "stopped"
        log(f"engine on card {self.card} stopped")

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


TOK = None
STATS = {"waiting": 0, "requests": 0, "new_conversations": 0, "context_changes": 0}


class Session:
    """What the engine holds: the token ids (the last answer token included) and the conversation behind them."""

    def __init__(self):
        self.clear()

    def clear(self):
        self.ids = []
        self.raw = b""
        self.mode = None


class Slot:
    """One card: its engine, the conversation it holds, and a lock (one request at a time per card)."""

    def __init__(self, card):
        self.engine = Engine(card)
        self.session = Session()
        self.lock = asyncio.Lock()
        self.last_used = 0.0
        self.requests = 0
        self.pending = 0  # requests routed here that have not taken the lock yet


SLOTS = [Slot(c) for c in (CFG.get("cards") or [CFG["card"]])]
MAX_CTX = SLOTS[0].engine.max_ctx


def pick_slot(raw_msgs, mode, make_prompt):
    """The card for a request: the one whose held conversation this one extends (the longest), else a free card
    (an empty one first, then the one used least recently), else the least recently used. Returns (slot, messages,
    prompt) with our exact earlier answers merged in for that card's conversation."""
    msgs = merge_known(raw_msgs, mode) if raw_msgs is not None else None
    prompt = make_prompt(msgs)
    pb = prompt.encode()
    best = None
    for sl in SLOTS:
        ss = sl.session
        if ss.mode != mode or not ss.ids or sl.engine.state == "fault":
            continue
        if pb.startswith(ss.raw) and len(pb) > len(ss.raw) and (best is None or len(ss.raw) > len(best.session.raw)):
            best = sl
    if best is None:
        ok = [sl for sl in SLOTS if sl.engine.state != "fault"] or SLOTS
        best = min(ok, key=lambda x: (x.pending + x.lock.locked(), bool(x.session.ids), x.last_used))
    best.pending += 1
    return best, msgs, prompt


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


# Our recent answers, exact (thinking, text, tool calls), keyed by the conversation before them as the client sends it
# and the part of the answer the client saw. Clients often drop the thinking, trim the text or re-encode tool calls;
# putting ours back makes a follow-up render the same on any card, whether or not a card still holds the conversation,
# so an answer depends only on its conversation, never on the order requests came in.
KNOWN = OrderedDict()
KNOWN_CHARS = [0]
KNOWN_MAX_CHARS = int(CFG.get("known_answers_max_chars", 64_000_000))


def _msg_key(m):
    return [m.get("role"), _text_of(m.get("content")).strip(), _calls_key(m.get("tool_calls")), m.get("name") or ""]


def _known_key(mode, before, visible, calls):
    h = hashlib.sha256(json.dumps([list(mode), [_msg_key(m) for m in before], (visible or "").strip(),
                                   _calls_key(calls)], ensure_ascii=False, default=str).encode())
    return h.hexdigest()


def remember_answer(mode, raw_msgs, ours):
    k = _known_key(mode, raw_msgs, ours["visible"], ours.get("visible_calls"))
    size = len(ours.get("content") or "") + len(ours.get("reasoning_content") or "") + 200
    old = KNOWN.pop(k, None)
    if old is not None:
        KNOWN_CHARS[0] -= old[1]
    KNOWN[k] = (ours, size)
    KNOWN_CHARS[0] += size
    while KNOWN and KNOWN_CHARS[0] > KNOWN_MAX_CHARS:
        _, (_, sz) = KNOWN.popitem(last=False)
        KNOWN_CHARS[0] -= sz


def merge_known(raw_msgs, mode):
    """The request's messages with our exact earlier answers put back."""
    out = list(raw_msgs)
    for i, m in enumerate(raw_msgs):
        if m.get("role") != "assistant":
            continue
        hit = KNOWN.get(_known_key(mode, raw_msgs[:i], _text_of(m.get("content")), m.get("tool_calls")))
        if hit is not None:
            out[i] = hit[0]  # (the template reads only role, content, reasoning_content and tool_calls)
    return out


async def _engine_job(slot, prompt_bytes: bytes, mode, max_new: int, on_event, ctl):
    ENGINE, SESSION, LOCK = slot.engine, slot.session, slot.lock
    STATS["waiting"] += 1
    try:
        await LOCK.acquire()
    finally:
        STATS["waiting"] -= 1
        slot.pending = max(0, slot.pending - 1)
    try:
        if not ctl["alive"]():
            raise EngineError("the client left before its turn")
        if ENGINE.state == "fault":
            raise EngineError(ENGINE.detail)
        STATS["requests"] += 1
        slot.requests += 1
        slot.last_used = time.time()
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
        tier = next(t for t in ENGINE.tiers if t >= len(ids) + max_new + 16)
        if ENGINE.state == "ready" and tier > ENGINE.ctx:
            t_g = time.time()
            if extend:  # keep what the engine has read: the restarted engine loads it as the longest saved prompt
                kind, data = await _engine_save(slot, LIB / f"_held-c{ENGINE.card}.inkc")
                if kind != "W":
                    log("could not save the held conversation before growing: " + " ".join(data))
            await ENGINE.stop()
            log(f"card {ENGINE.card}: context {ENGINE.ctx} -> {tier} for a conversation of {len(ids)} + {max_new} tokens")
            ENGINE.ctx = tier
            await ENGINE.start()
            STATS["context_changes"] += 1
            log(f"context change took {time.time() - t_g:.1f} s before the request")
        elif ENGINE.state == "ready" and not extend and tier < ENGINE.ctx and len(ids) >= CFG.get("shrink_min_prompt", 8192):
            await ENGINE.stop()
            log(f"card {ENGINE.card}: context {ENGINE.ctx} -> {tier} for a new conversation of {len(ids)} tokens")
            ENGINE.ctx = tier
            STATS["context_changes"] += 1
        if not extend:
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
                elif kind == "R":
                    STATS["new_conversations"] += 1
                elif kind == "D":
                    done = data
                elif kind == "E":
                    SESSION.clear()
                    raise EngineError("the engine refused the request: " + " ".join(data))
                elif kind == "X":
                    SESSION.clear()
                    raise EngineError("the engine stopped during the request (code " + data[0] + "); it restarts with the next request")
        finally:
            ENGINE.queues.pop(rid, None)
        SESSION.ids = ids + gen
        SESSION.raw = TOK.bytes_of(SESSION.ids)
        SESSION.mode = mode
        tm = {"prompt_tokens": len(ids), "read_tokens": int(done[1]), "read_s": float(done[3]), "answer_tokens": len(gen),
              "answer_s": float(done[4]), "rounds": int(done[5]), "guesses": int(done[6]), "kept_guesses": int(done[7]),
              "context_used": int(done[8]), "total_s": round(time.time() - t0, 3)}
        tm["answer_tok_per_s"] = round(max(0, len(gen) - 1) / max(1e-6, tm["answer_s"]), 2)
        tm["read_tok_per_s"] = round(tm["read_tokens"] / max(1e-6, tm["read_s"]), 1)
        log(f"card {ENGINE.card}: conversation {len(ids)} tokens, read {tm['read_tokens']} in {tm['read_s']:.2f} s, "
            f"answered {len(gen)} in {tm['answer_s']:.2f} s ({tm['answer_tok_per_s']} tok/s), end {done[0]}")
        return done[0], gen, tm
    finally:
        LOCK.release()


async def run_request(request, slot, prompt_bytes: bytes, mode, max_new: int, on_event):
    """Runs the engine job as its own task: a client that leaves stops the answer at the next round, and the
    conversation the engine holds stays consistent."""
    ctl = {"alive": lambda: request.transport is not None and not request.transport.is_closing()}
    job = asyncio.create_task(_engine_job(slot, prompt_bytes, mode, max_new, on_event, ctl))
    try:
        return await asyncio.shield(job)
    except asyncio.CancelledError:
        ctl["alive"] = lambda: False
        raise


def finish_reason(r, has_calls=False):
    if has_calls:
        return "tool_calls"
    return {"eos": "stop", "max": "length", "stop": "stop"}.get(r, "stop")


def parse_effort(body):
    kw = body.get("chat_template_kwargs") or {}
    effort = kw.get("reasoning_effort", body.get("reasoning_effort"))
    if isinstance(body.get("reasoning"), dict) and body["reasoning"].get("effort"):
        effort = body["reasoning"]["effort"]
    off = body.get("enable_thinking") is False or kw.get("enable_thinking") is False or body.get("thinking") is False or \
        (isinstance(body.get("thinking"), dict) and body["thinking"].get("type") == "disabled")
    if off or str(body.get("model", "")).endswith("-chat"):
        effort = "none"
    if isinstance(effort, str) and effort.strip() in EFFORTS:
        return effort.strip()
    if isinstance(effort, (int, float)) and not isinstance(effort, bool) and 0.0 <= float(effort) <= 0.99:
        return float(effort)
    return None  # the template's default (0.9)


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
                    raise jerr(web.HTTPBadRequest, "images are not supported by this server")
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
        if m.get("content") is None:
            m["content"] = ""
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
    effort = parse_effort(body)
    tools = body.get("tools") or None
    if body.get("tool_choice") == "none":
        tools = None
    mode = (str(effort), json.dumps(tools, sort_keys=True))
    raw_msgs = norm_messages(msgs)
    try:
        slot, msgs, prompt = pick_slot(raw_msgs, mode, lambda m: render(m, effort, tools))
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
    parts = Parts()
    st = {"content": "", "sent": 0, "stop_hit": False}
    resp = None
    hold = max(len(s) for s in stops) if stops else 0

    def chunk(delta, fin=None):
        return {"id": cid, "object": "chat.completion.chunk", "created": created, "model": MODEL,
                "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}

    def take(toks):
        r, c = parts.take(toks, TOK.pieces)
        if not st["stop_hit"]:
            st["content"] += c
            for s in stops:
                j = st["content"].find(s)
                if j >= 0:
                    st["content"] = st["content"][:j]
                    st["stop_hit"] = True
        return r

    def visible_upto():
        c = st["content"]
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
        reason, gen, tm = await run_request(request, slot, prompt.encode(), mode, max_new, on_event)
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
    content, calls = st["content"], parts.calls
    # our exact answer, kept so the next turn continues the held conversation (see merge_known): the template
    # renders an answer as its thinking part, its text part, its tool calls, then the end token
    if not st["stop_hit"] and reason == "eos":
        ours = {"role": "assistant", "content": parts.content, "visible": content, "visible_calls": calls}
        if parts.reasoning:
            ours["reasoning_content"] = parts.reasoning
        if calls:
            ours["tool_calls"] = [dict(c, function=dict(c["function"], arguments=json.loads(c["function"]["arguments"])))
                                  for c in calls]
        remember_answer(mode, raw_msgs, ours)
    usage = {"prompt_tokens": tm["prompt_tokens"], "completion_tokens": len(gen),
             "total_tokens": tm["prompt_tokens"] + len(gen),
             "prompt_tokens_details": {"cached_tokens": tm["prompt_tokens"] - tm["read_tokens"]}}
    fin = "stop" if st["stop_hit"] else finish_reason(reason, bool(calls))
    if stream:
        try:
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
    msg = {"role": "assistant", "content": content if (content or not calls) else None,
           "reasoning_content": parts.reasoning}
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
        slot, _, _ = pick_slot(None, ("raw",), lambda m: prompt)
        reason, gen, tm = await run_request(request, slot, prompt.encode(), ("raw",), max_new, on_event)
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


# ---------------------------------------------------------------------------------------------- library
def _lib_path(body):
    name = re.sub(r"[^A-Za-z0-9._-]", "_", str(body.get("name") or time.strftime("conv-%Y%m%dT%H%M%S")))[:80]
    return LIB / (name + ".inkc")


async def _engine_save(slot, path):
    """W (the caller holds slot.lock): the engine saves what it has read (the held conversation without its last
    token, which is decided but not read). Written beside the library and renamed when complete, so the other cards'
    engines (which pick saved prompts from the same folder) never see a half-written file."""
    LIB.mkdir(parents=True, exist_ok=True)
    part = path.parent / (path.name + ".part")
    rid = uuid.uuid4().hex[:12]
    q = asyncio.Queue()
    slot.engine.queues[rid] = q
    try:
        await slot.engine.send(f"W {rid} {part}")
        kind, data = await q.get()
    finally:
        slot.engine.queues.pop(rid, None)
    if kind == "W":
        os.replace(part, path)
    else:
        part.unlink(missing_ok=True)
    return kind, data


async def _save_held(slot, path, expect_ids=None):
    async with slot.lock:
        sess = slot.session
        if slot.engine.state != "ready" or not sess.ids:
            raise jerr(web.HTTPConflict, "the engine holds no conversation")
        if expect_ids is not None and sess.ids[:len(expect_ids)] != expect_ids:
            raise jerr(web.HTTPConflict, "another conversation came in first; try again")
        kind, data = await _engine_save(slot, path)
        n = len(sess.ids) - 1
    if kind != "W":
        raise jerr(web.HTTPInternalServerError, "save failed: " + " ".join(data), "server_error")
    log(f"card {slot.engine.card}: saved {n} tokens to {path} ({int(data[0]) / 1e9:.2f} GB in {float(data[1]):.1f} s)")
    return web.json_response({"path": str(path), "tokens": n, "bytes": int(data[0]), "seconds": float(data[1]),
                              "card": slot.engine.card})


async def admin_save(request):
    """Saves a held conversation as a library prompt: a later conversation that starts with it loads in seconds.
    Body: {"name", ["card"]} (default: the card used last)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if body.get("card") is not None:
        cand = [sl for sl in SLOTS if sl.engine.card == int(body["card"])]
        if not cand:
            raise jerr(web.HTTPBadRequest, f"no engine on card {body['card']}")
        slot = cand[0]
    else:
        slot = max(SLOTS, key=lambda x: x.last_used)
    return await _save_held(slot, _lib_path(body))


async def admin_prefill(request):
    """Reads messages (e.g. a system message holding a long document) and saves the result as a library prompt, so
    every later conversation that starts with the same messages (and the same reasoning_effort / tools) reads only
    what follows them, on any card. Body: {"name", "messages", ["reasoning_effort" | "model", "tools"]}."""
    try:
        body = await request.json()
    except Exception:
        raise jerr(web.HTTPBadRequest, "invalid JSON")
    msgs = body.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise jerr(web.HTTPBadRequest, "messages required")
    effort = parse_effort(body)
    tools = body.get("tools") or None
    mode = (str(effort), json.dumps(tools, sort_keys=True))
    try:
        slot, _, prompt = pick_slot(norm_messages(msgs), mode, lambda m: render(m, effort, tools))
    except jinja2.exceptions.TemplateError as e:
        raise jerr(web.HTTPBadRequest, f"template: {e}")

    async def on_event(kind, data):
        return False

    try:
        _, gen, tm = await run_request(request, slot, prompt.encode(), mode, 1, on_event)
    except EngineError as e:
        raise jerr(web.HTTPServiceUnavailable, str(e), "server_error")
    r = await _save_held(slot, _lib_path(body), slot.session.ids[:tm["prompt_tokens"]])
    log(f"prefill: read {tm['read_tokens']} of {tm['prompt_tokens']} tokens in {tm['read_s']:.1f} s")
    return r


async def admin_library(request):
    items = []
    for p in sorted(LIB.glob("*.inkc")):
        try:
            with open(p, "rb") as f:
                hd = f.read(16)
            n = int.from_bytes(hd[8:16], "little") if hd[:8] == b"INKC0001" else None
        except OSError:
            n = None
        items.append({"name": p.stem, "tokens": n, "bytes": p.stat().st_size})
    return web.json_response({"library": str(LIB), "prompts": items})


async def tokenize(request):
    body = await request.json()
    ids = await asyncio.get_running_loop().run_in_executor(None, TOK.encode, str(body.get("content", "")).encode())
    return web.json_response({"tokens": ids})


async def models(request):
    return web.json_response({"object": "list", "data": [
        {"id": MODEL, "object": "model", "owned_by": "local", "context_length": MAX_CTX},
        {"id": MODEL + "-chat", "object": "model", "owned_by": "local", "context_length": MAX_CTX}]})


async def health(request):
    cards = [{"card": sl.engine.card, "status": sl.engine.state, "detail": sl.engine.detail, "context": sl.engine.ctx,
              "held_conversation_tokens": len(sl.session.ids), "busy": sl.lock.locked(), "routed": sl.pending,
              "requests": sl.requests,
              "last_load_s": sl.engine.load_s} for sl in SLOTS]
    sts = {c["status"] for c in cards}
    status = "ready" if "ready" in sts else ("fault" if sts == {"fault"} else cards[0]["status"])
    return web.json_response({"status": status, "model": MODEL, "max_context": MAX_CTX, "cards": cards,
                              "waiting": STATS["waiting"], "requests": STATS["requests"],
                              "new_conversations": STATS["new_conversations"],
                              "context_changes": STATS["context_changes"]})


async def index(request):
    return web.FileResponse(HERE / "chat.html")


async def on_startup(app):
    global TOK
    TOK = Tokenizer()
    log(f"server up on {CFG.get('host', '0.0.0.0')}:{CFG.get('port', 8001)}, model {MODEL}, cards {[sl.engine.card for sl in SLOTS]}, contexts {SLOTS[0].engine.tiers}")
    if CFG.get("load_at_start", True):
        async def first():  # one engine at a time (host memory and disk reads at load)
            for sl in SLOTS:
                async with sl.lock:
                    try:
                        await sl.engine.start()
                    except EngineError as e:
                        log(f"engine start on card {sl.engine.card} failed: {e}")
        app["first"] = asyncio.create_task(first())


async def on_shutdown(app):
    log("server stopping")
    await asyncio.gather(*(sl.engine.stop() for sl in SLOTS))


def main():
    app = web.Application(client_max_size=512 << 20)
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", chat_completions)
    app.router.add_post("/v1/completions", completions)
    app.router.add_post("/tokenize", tokenize)
    app.router.add_post("/admin/save", admin_save)
    app.router.add_post("/admin/prefill", admin_prefill)
    app.router.add_get("/admin/library", admin_library)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host=CFG.get("host", "0.0.0.0"), port=int(CFG.get("port", 8001)), access_log=None,
                handle_signals=True, shutdown_timeout=5)


if __name__ == "__main__":
    main()
