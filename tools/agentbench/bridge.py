#!/usr/bin/env python3
"""bridge.py: a byte-level forwarder between a TCP port and a Unix socket, the only way out of an agent container.

The agent container runs with `--network none`, so it cannot reach anything. The runner mounts one directory that
holds one Unix socket; this script runs twice:

  host:       bridge.py --listen unix:/run/user/1000/agentbench/JOB/proxy.sock --connect tcp:127.0.0.1:18200 \
                        --tap requests.jsonl [--tap-mode summary|full]
  container:  bridge.py --listen tcp:127.0.0.1:18200 --connect unix:/run/agentbench/proxy.sock

so an agent configured for http://127.0.0.1:18200/v1 inside the container reaches the ctxkeeper proxy on the host's
127.0.0.1:18200 and nothing else. Bytes pass through unchanged in both directions.

--tap (host side only) also parses the client-to-server bytes as HTTP/1.1 requests and writes one JSON line per
request: method, path, whether the body was chunked (ctxkeeper refuses chunked bodies), and for chat completions a
summary (model, stream, n, tools, message count, the ctxkeeper-style fingerprint of every message, whether the
messages extend the previous request of the same conversation). --tap-mode full also stores the whole body.
Standard library only (Python 3.8+), so the same file runs on the host and in any agent image.
"""
import argparse, asyncio, hashlib, json, os, sys, time

CHUNK = 65536


def parse_addr(s):
    kind, _, rest = s.partition(":")
    if kind == "unix":
        return ("unix", rest)
    if kind == "tcp":
        host, _, port = rest.rpartition(":")
        return ("tcp", (host or "127.0.0.1", int(port)))
    raise SystemExit(f"bridge: bad address {s!r} (unix:PATH or tcp:HOST:PORT)")


def msg_fp(m):
    """ctxkeeper's per-message fingerprint rule: role, whitespace-collapsed text, tool calls by name + arguments
    (thinking and call ids are ignored, as ctxkeeper ignores them)."""
    c = m.get("content")
    if isinstance(c, list):
        c = "".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in c)
    calls = [[(t.get("function") or {}).get("name"), (t.get("function") or {}).get("arguments")]
             for t in m.get("tool_calls") or [] if isinstance(t, dict)]
    row = [m.get("role"), " ".join(str(c or "").split()), calls]
    return hashlib.sha256(json.dumps(row).encode()).hexdigest()[:12]


def head_length(msgs):
    i = 0
    while i < len(msgs) and msgs[i].get("role") in ("system", "developer"):
        i += 1
    if i < len(msgs) and msgs[i].get("role") == "user":
        i += 1
    return i


class Tap:
    def __init__(self, path, mode):
        self.f = open(path, "a", buffering=1)
        self.mode = mode
        self.n = 0
        self.prev = {}          # conversation key -> list of message fingerprints of its last request

    def record(self, conn, method, path, headers, body, chunked):
        self.n += 1
        rec = {"i": self.n, "t": round(time.time(), 3), "conn": conn, "method": method, "path": path,
               "chunked": chunked, "bytes": len(body)}
        if method == "POST":
            try:
                req = json.loads(body or b"{}")
            except ValueError:
                req = None
                rec["json_error"] = True
            if isinstance(req, dict):
                msgs = req.get("messages") or []
                if isinstance(msgs, list) and msgs and all(isinstance(m, dict) for m in msgs):
                    h = head_length(msgs)
                    fps = [msg_fp(m) for m in msgs]
                    key = hashlib.sha256(json.dumps([str(req.get("model"))] + fps[:h]).encode()).hexdigest()[:12]
                    prev = self.prev.get(key)
                    if prev is None:
                        ext = None
                    else:
                        same = 0
                        while same < min(len(prev), len(fps)) and prev[same] == fps[same]:
                            same += 1
                        ext = {"prev_n": len(prev), "kept": same, "extends": same == len(prev)}
                    self.prev[key] = fps
                    tools = req.get("tools") or []
                    rec.update(model=req.get("model"), stream=req.get("stream"), n=req.get("n"),
                               n_messages=len(msgs), head=h, conv=key, roles="".join((m.get("role") or "?")[0] for m in msgs),
                               tools=[(t.get("function") or {}).get("name") or t.get("name") for t in tools if isinstance(t, dict)],
                               tool_choice=req.get("tool_choice"), max_tokens=req.get("max_tokens") or req.get("max_completion_tokens"),
                               extra_keys=sorted(k for k in req if k not in ("model", "messages", "tools", "stream")),
                               fps=fps, extends_previous=ext,
                               session_header=headers.get("x-ctx-session"))
                elif "input" in req:
                    rec.update(model=req.get("model"), responses_api=True, stream=req.get("stream"))
            if self.mode == "full":
                rec["body"] = body.decode("utf-8", "replace")
        rec["user_agent"] = headers.get("user-agent")
        self.f.write(json.dumps(rec) + "\n")


class ReqParser:
    """Incremental HTTP/1.1 request parser for the tap (client-to-server direction only)."""

    def __init__(self, tap, conn):
        self.tap, self.conn, self.buf, self.state = tap, conn, b"", "head"
        self.need = 0
        self.req = None

    def feed(self, data):
        self.buf += data
        try:
            while self._step():
                pass
        except Exception as e:                      # never let the tap break the forwarding
            sys.stderr.write(f"bridge tap: parse error {e!r}; tap off for this connection\n")
            self.state = "off"
            self.buf = b""

    def _step(self):
        if self.state == "off":
            self.buf = b""
            return False
        if self.state == "head":
            i = self.buf.find(b"\r\n\r\n")
            if i < 0:
                return False
            head, self.buf = self.buf[:i].decode("latin-1"), self.buf[i + 4:]
            lines = head.split("\r\n")
            parts = lines[0].split(" ")
            hdr = {}
            for ln in lines[1:]:
                k, _, v = ln.partition(":")
                hdr[k.strip().lower()] = v.strip()
            self.req = {"method": parts[0], "path": parts[1] if len(parts) > 1 else "", "headers": hdr, "body": b"",
                        "chunked": "chunked" in hdr.get("transfer-encoding", "").lower()}
            if self.req["chunked"]:
                self.state = "chunk-size"
            else:
                self.need = int(hdr.get("content-length") or 0)
                self.state = "body"
            return True
        if self.state == "body":
            if len(self.buf) < self.need:
                return False
            self.req["body"], self.buf = self.buf[:self.need], self.buf[self.need:]
            self._done()
            return True
        if self.state == "chunk-size":
            i = self.buf.find(b"\r\n")
            if i < 0:
                return False
            size = int(self.buf[:i].split(b";")[0].strip() or b"0", 16)
            self.buf = self.buf[i + 2:]
            if size == 0:
                self.state = "trailer"
            else:
                self.need, self.state = size, "chunk-data"
            return True
        if self.state == "chunk-data":
            if len(self.buf) < self.need + 2:
                return False
            self.req["body"] += self.buf[:self.need]
            self.buf = self.buf[self.need + 2:]
            self.state = "chunk-size"
            return True
        if self.state == "trailer":
            i = self.buf.find(b"\r\n")
            if i < 0:
                return False
            line, self.buf = self.buf[:i], self.buf[i + 2:]
            if line == b"":
                self._done()
            return True
        return False

    def _done(self):
        r = self.req
        self.tap.record(self.conn, r["method"], r["path"], r["headers"], r["body"], r["chunked"])
        self.state, self.req = "head", None


async def pump(reader, writer, parser=None):
    try:
        while True:
            data = await reader.read(CHUNK)
            if not data:
                break
            if parser is not None:
                parser.feed(data)
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            if writer.can_write_eof():
                writer.write_eof()
        except (OSError, RuntimeError):
            pass


async def main_async(a):
    lkind, laddr = parse_addr(a.listen)
    ckind, caddr = parse_addr(a.connect)
    tap = Tap(a.tap, a.tap_mode) if a.tap else None
    counter = {"n": 0}

    async def handle(r1, w1):
        counter["n"] += 1
        conn = counter["n"]
        try:
            if ckind == "unix":
                r2, w2 = await asyncio.open_unix_connection(caddr)
            else:
                r2, w2 = await asyncio.open_connection(*caddr)
        except OSError as e:
            sys.stderr.write(f"bridge: cannot reach {a.connect}: {e}\n")
            w1.close()
            return
        parser = ReqParser(tap, conn) if tap else None
        await asyncio.gather(pump(r1, w2, parser), pump(r2, w1))
        for w in (w1, w2):
            try:
                w.close()
            except OSError:
                pass

    if lkind == "unix":
        if os.path.exists(laddr):
            os.unlink(laddr)
        srv = await asyncio.start_unix_server(handle, laddr)
        os.chmod(laddr, 0o666)
    else:
        srv = await asyncio.start_server(handle, *laddr)
    print(f"bridge: {a.listen} -> {a.connect}" + (f", tap {a.tap} ({a.tap_mode})" if tap else ""), flush=True)
    async with srv:
        await srv.serve_forever()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", required=True)
    ap.add_argument("--connect", required=True)
    ap.add_argument("--tap", help="write one JSON line per HTTP request seen (host side)")
    ap.add_argument("--tap-mode", choices=("summary", "full"), default="summary")
    a = ap.parse_args()
    try:
        asyncio.run(main_async(a))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
