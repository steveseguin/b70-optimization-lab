"""Sequential transport for one already-launched ownrt native owner.

No launch, restart, kill, model selection or checkpoint policy lives here.
An unexpected event or deadline poisons the channel; later requests refuse.
"""
from __future__ import annotations

import json
import os
import re
import selectors
import time


PROTOCOL = "ownrt.request-front.v1"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z", re.ASCII)


def valid_id(value):
    return isinstance(value, str) and ID.fullmatch(value) and not value.endswith(".lock")


def encode_request(request_id, tokens, max_new, *, context, vocab, restore=None, save=None):
    if not valid_id(request_id):
        raise ValueError("invalid request id")
    if any(value is not None and not valid_id(value) for value in (restore, save)):
        raise ValueError("invalid checkpoint id")
    if restore is not None and restore == save:
        raise ValueError("restore-then-save requires a fresh checkpoint id")
    if type(max_new) is not int or not 1 <= max_new <= 512:
        raise ValueError("max_new must be 1..512")
    if not isinstance(tokens, (list, tuple)) or not tokens or len(tokens) + max_new > context:
        raise ValueError("prompt and completion exceed admitted context")
    if any(type(token) is not int or not 0 <= token < vocab for token in tokens):
        raise ValueError("invalid token id")
    frame = (f"RUN\t{request_id}\t{max_new}\t{restore or '-'}\t{save or '-'}\t"
             + " ".join(map(str, tokens)) + "\n").encode("ascii")
    if len(frame) > 262144:
        raise ValueError("request frame exceeds native bound")
    return frame


class NativeFront:
    """Attach to a Popen owner with binary stdin/stdout; stderr must be logged.

    Deadlines are observation bounds, never kill deadlines. After a transport
    failure the coordinator retains the process and owns the incident drain.
    """

    def __init__(self, process, *, context, vocab, max_requests, startup_timeout=600, request_timeout=1800):
        self.process = process
        self.context, self.vocab = context, vocab
        if type(max_requests) is not int or not 1 <= max_requests <= 1024:
            raise ValueError("max_requests must be 1..1024")
        self.max_requests, self.completed = max_requests, 0
        self.request_timeout = request_timeout
        self.state = "starting"
        self.seen = set()
        self.buffer = bytearray()
        self.selector = selectors.DefaultSelector()
        self.selector.register(process.stdout, selectors.EVENT_READ)
        os.set_blocking(process.stdin.fileno(), False)
        try:
            row = self._read(time.monotonic() + startup_timeout)
            if row.get("event") != "ready" or row.get("protocol") != PROTOCOL:
                raise RuntimeError("native readiness protocol mismatch")
            for key, wanted in (("context", context), ("vocab", vocab), ("max_requests", max_requests), ("model_loads", 1)):
                if type(row.get(key)) is not int or row[key] != wanted:
                    raise RuntimeError("native readiness admission mismatch: " + key)
            if row.get("experimental") is not True:
                raise RuntimeError("native experimental qualification scope mismatch")
            self.ready = row
            self.state = "ready"
        except BaseException:
            self.state = "halted"
            self.selector.close()
            raise

    def _write(self, frame, deadline):
        with selectors.DefaultSelector() as writable:
            writable.register(self.process.stdin, selectors.EVENT_WRITE)
            view = memoryview(frame)
            while view:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not writable.select(remaining):
                    raise TimeoutError("native input deadline; owner retained for coordinator drain")
                try:
                    count = os.write(self.process.stdin.fileno(), view)
                except BlockingIOError:
                    continue
                view = view[count:]

    def _read(self, deadline):
        if time.monotonic() >= deadline:
            raise TimeoutError("native event deadline; owner retained for coordinator drain")
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise TimeoutError("native event deadline; owner retained for coordinator drain")
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError("native event stream ended before terminal receipt")
            self.buffer.extend(chunk)
            if len(self.buffer) > 1_048_576:
                raise RuntimeError("native event exceeds transport bound")
        line, _, tail = self.buffer.partition(b"\n")
        self.buffer = bytearray(tail)
        row = json.loads(line)
        if not isinstance(row, dict):
            raise RuntimeError("native event is not an object")
        if row.get("event") == "fatal":
            raise RuntimeError("native owner halted: " + str(row.get("error", "unspecified")))
        return row

    def request(self, request_id, tokens, max_new, *, restore=None, save=None, on_token=None):
        if self.state != "ready":
            raise RuntimeError("native channel is not ready; no retry")
        if request_id in self.seen:
            raise ValueError("duplicate request id")
        encoded = encode_request(request_id, tokens, max_new, context=self.context,
                                 vocab=self.vocab, restore=restore, save=save)
        self.seen.add(request_id)
        self.state = "running"
        deadline = time.monotonic() + self.request_timeout
        emitted = []
        try:
            self._write(encoded, deadline)
            start = self._read(deadline)
            if start.get("event") != "request-start" or start.get("id") != request_id:
                raise RuntimeError("native request-start identity mismatch")
            while True:
                row = self._read(deadline)
                if row.get("id") != request_id:
                    raise RuntimeError("native response belongs to another request")
                if row.get("event") == "token":
                    token = row.get("token_id")
                    if (type(row.get("index")) is not int or row["index"] != len(emitted)
                            or type(token) is not int or not 0 <= token < self.vocab or len(emitted) >= max_new):
                        raise RuntimeError("invalid native token sequence")
                    emitted.append(token)
                    if on_token:
                        on_token(token)
                elif row.get("event") == "request-complete":
                    if not emitted or row.get("result") != f"requests/{request_id}/result.json":
                        raise RuntimeError("native completion receipt mismatch")
                    if (type(row.get("generated_tokens")) is not int or row["generated_tokens"] != len(emitted)
                            or row.get("owner_resident") is not True or row.get("request_quiesced") is not True):
                        raise RuntimeError("native completion count or quiescence mismatch")
                    self.completed += 1
                    self.state = "draining" if self.completed == self.max_requests else "ready"
                    return {"tokens": emitted, "completion": row}
                else:
                    raise RuntimeError("unexpected native request event")
        except BaseException:
            self.state = "halted"
            raise

    def close(self, timeout=120):
        if self.state not in ("ready", "draining"):
            raise RuntimeError("channel cannot close normally; coordinator must inspect/drain owner")
        draining = self.state == "draining"
        self.state = "closing"
        deadline = time.monotonic() + timeout
        try:
            # The owner also exits at its explicit request/idle/time bounds.
            # At the request limit it is already draining. On an idle-close
            # race, a broken pipe is acceptable only with a valid final receipt.
            if not draining and not self.buffer and not self.selector.select(0):
                try:
                    self._write(b"QUIT\n", deadline)
                except BrokenPipeError:
                    pass
            self.process.stdin.close()
            row = self._read(deadline)
            if (row.get("event") != "stopped" or row.get("safe_to_exit") is not True
                    or row.get("reason") not in ("quit", "eof", "request-limit", "idle-timeout", "deadline", "signal")
                    or type(row.get("completed_requests")) is not int or row["completed_requests"] != self.completed):
                raise RuntimeError("native drain receipt missing")
            if self.process.wait(timeout=max(0.001, deadline-time.monotonic())) != 0:
                raise RuntimeError("native exit failed after drain receipt")
            self.state = "closed"
            return row
        except BaseException:
            self.state = "halted"
            raise
        finally:
            self.selector.close()
