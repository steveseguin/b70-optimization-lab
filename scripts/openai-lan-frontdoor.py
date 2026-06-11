#!/usr/bin/env python3
"""No-auth LAN frontdoor for a local OpenAI-compatible vLLM server.

This proxy keeps the public LAN URL stable while limiting active generation
requests before they reach vLLM. Model-slot wrappers set profile metadata and
concurrency from the active profile.
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit


PAUSE_FILE = os.environ.get(
    "FRONTDOOR_PAUSE_FILE",
    "/home/steve/llm-optimizations/.pause-minimax-production",
)

BACKEND_BASE_URL = os.environ.get("FRONTDOOR_BACKEND_URL", "http://127.0.0.1:18080")
HOST = os.environ.get("FRONTDOOR_HOST", "0.0.0.0")
PORT = int(os.environ.get("FRONTDOOR_PORT", "8000"))
MAX_ACTIVE_GENERATIONS = int(os.environ.get("FRONTDOOR_MAX_ACTIVE_GENERATIONS", "1"))
QUEUE_TIMEOUT_S = float(os.environ.get("FRONTDOOR_QUEUE_TIMEOUT_S", "3600"))
BACKEND_TIMEOUT_S = float(os.environ.get("FRONTDOOR_BACKEND_TIMEOUT_S", "7200"))
DRAIN_TIMEOUT_S = float(os.environ.get("FRONTDOOR_DRAIN_TIMEOUT_S", "3600"))
FRONTDOOR_CORS_ALLOW_ORIGIN = os.environ.get("FRONTDOOR_CORS_ALLOW_ORIGIN", "*")
FRONTDOOR_LOG_EVENTS = os.environ.get("FRONTDOOR_LOG_EVENTS", "1") not in {
    "0",
    "false",
    "False",
}
FRONTDOOR_PAUSE_ALLOW_LOCAL = os.environ.get(
    "FRONTDOOR_PAUSE_ALLOW_LOCAL", "1"
) not in {"0", "false", "False"}
FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON = os.environ.get(
    "FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON", '{"enable_thinking":false}'
)
FRONTDOOR_SERVED_MODEL_NAME = os.environ.get("FRONTDOOR_SERVED_MODEL_NAME", "")
FRONTDOOR_REWRITE_REQUEST_MODEL = os.environ.get(
    "FRONTDOOR_REWRITE_REQUEST_MODEL", "1"
) not in {"0", "false", "False"}
FRONTDOOR_DEFAULT_MAX_OUTPUT_TOKENS = int(
    os.environ.get("FRONTDOOR_DEFAULT_MAX_OUTPUT_TOKENS", "2048")
)
FRONTDOOR_MAX_OUTPUT_TOKENS = int(
    os.environ.get("FRONTDOOR_MAX_OUTPUT_TOKENS", "4096")
)
MODEL_SLOT_NAME = os.environ.get("MODEL_SLOT_NAME", "")
MODEL_SLOT_TITLE = os.environ.get("MODEL_SLOT_TITLE", "")
MODEL_SLOT_HF_ID = os.environ.get("MODEL_SLOT_HF_ID", "")
MODEL_SLOT_MODALITIES = os.environ.get("MODEL_SLOT_MODALITIES", "")
MODEL_SLOT_STATUS = os.environ.get("MODEL_SLOT_STATUS", "")

GENERATION_PATHS = {
    "/v1/completions",
    "/v1/chat/completions",
    "/v1/responses",
    "/v1/messages",
    "/inference/v1/generate",
    "/generative_scoring",
}

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

backend = urlsplit(BACKEND_BASE_URL)
if backend.scheme != "http" or not backend.hostname or not backend.port:
    raise SystemExit(
        "FRONTDOOR_BACKEND_URL must be an http URL with an explicit port, "
        f"got {BACKEND_BASE_URL!r}"
    )

generation_slots = threading.BoundedSemaphore(MAX_ACTIVE_GENERATIONS)
state_lock = threading.Lock()
log_lock = threading.Lock()
active_generations = 0
queued_generations = 0
total_generation_requests = 0
default_chat_template_kwargs: dict[str, Any] = {}

if FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON:
    parsed = json.loads(FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON)
    if not isinstance(parsed, dict):
        raise SystemExit("FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON must decode to an object")
    default_chat_template_kwargs = parsed


def now_ms() -> int:
    return int(time.time() * 1000)


def log_event(event: dict[str, Any]) -> None:
    if not FRONTDOOR_LOG_EVENTS:
        return
    event.setdefault("ts_ms", now_ms())
    line = json.dumps(event, sort_keys=True)
    with log_lock:
        print(line, flush=True)


def is_generation_path(path: str, method: str) -> bool:
    return method.upper() == "POST" and path in GENERATION_PATHS


def is_paused() -> bool:
    return bool(PAUSE_FILE and os.path.exists(PAUSE_FILE))


def is_loopback_client(address: str) -> bool:
    return address in {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


def status_payload() -> dict[str, Any]:
    with state_lock:
        active = active_generations
        queued = queued_generations
        total = total_generation_requests
    return {
        "ok": True,
        "model_slot": {
            "name": MODEL_SLOT_NAME,
            "title": MODEL_SLOT_TITLE,
            "hf_id": MODEL_SLOT_HF_ID,
            "modalities": MODEL_SLOT_MODALITIES,
            "status": MODEL_SLOT_STATUS,
        },
        "frontdoor": {
            "host": HOST,
            "port": PORT,
            "backend": BACKEND_BASE_URL,
            "max_active_generations": MAX_ACTIVE_GENERATIONS,
            "queue_timeout_s": QUEUE_TIMEOUT_S,
            "drain_timeout_s": DRAIN_TIMEOUT_S,
            "active_generations": active,
            "queued_generations": queued,
            "total_generation_requests": total,
            "event_logging": FRONTDOOR_LOG_EVENTS,
            "auth": "none",
            "pause_file": PAUSE_FILE,
            "paused": is_paused(),
            "pause_allow_local": FRONTDOOR_PAUSE_ALLOW_LOCAL,
            "served_model_name": FRONTDOOR_SERVED_MODEL_NAME,
            "rewrite_request_model": FRONTDOOR_REWRITE_REQUEST_MODEL,
            "default_max_output_tokens": FRONTDOOR_DEFAULT_MAX_OUTPUT_TOKENS,
            "max_output_tokens": FRONTDOOR_MAX_OUTPUT_TOKENS,
            "chat_template_kwargs": default_chat_template_kwargs,
        },
    }


def acquire_generation_slot() -> tuple[bool, float]:
    global active_generations, queued_generations, total_generation_requests
    started = time.perf_counter()
    with state_lock:
        queued_generations += 1
        total_generation_requests += 1
    acquired = generation_slots.acquire(timeout=QUEUE_TIMEOUT_S)
    waited = time.perf_counter() - started
    with state_lock:
        queued_generations -= 1
        if acquired:
            active_generations += 1
    return acquired, waited


def release_generation_slot() -> None:
    global active_generations
    with state_lock:
        active_generations -= 1
    generation_slots.release()


def apply_request_defaults(path: str, body: bytes | None) -> bytes | None:
    if body is None:
        return body

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body
    if not isinstance(payload, dict):
        return body

    changed = False

    if (
        path in GENERATION_PATHS
        and FRONTDOOR_REWRITE_REQUEST_MODEL
        and FRONTDOOR_SERVED_MODEL_NAME
    ):
        requested_model = payload.get("model")
        if requested_model != FRONTDOOR_SERVED_MODEL_NAME:
            payload["model"] = FRONTDOOR_SERVED_MODEL_NAME
            changed = True

    if path == "/v1/chat/completions" and default_chat_template_kwargs:
        existing = payload.get("chat_template_kwargs")
        if existing is None:
            payload["chat_template_kwargs"] = dict(default_chat_template_kwargs)
            changed = True
        elif isinstance(existing, dict):
            merged = dict(default_chat_template_kwargs)
            merged.update(existing)
            if merged != existing:
                payload["chat_template_kwargs"] = merged
                changed = True
        else:
            return body

    output_token_fields = {
        "/v1/chat/completions": ("max_completion_tokens", "max_tokens"),
        "/v1/completions": ("max_tokens",),
        "/v1/responses": ("max_output_tokens",),
        "/v1/messages": ("max_tokens",),
        "/inference/v1/generate": ("max_tokens",),
    }.get(path, ())
    if output_token_fields and FRONTDOOR_DEFAULT_MAX_OUTPUT_TOKENS > 0:
        active_field = next(
            (field for field in output_token_fields if field in payload),
            None,
        )
        requested_tokens = None
        applied_tokens = None
        applied_field = active_field or output_token_fields[0]

        if active_field is None:
            applied_tokens = FRONTDOOR_DEFAULT_MAX_OUTPUT_TOKENS
            payload[applied_field] = applied_tokens
            changed = True
        else:
            try:
                requested_tokens = int(payload[active_field])
            except (TypeError, ValueError):
                requested_tokens = None
            if requested_tokens is None or requested_tokens <= 0:
                applied_tokens = FRONTDOOR_DEFAULT_MAX_OUTPUT_TOKENS
                payload[active_field] = applied_tokens
                changed = True
            elif (
                FRONTDOOR_MAX_OUTPUT_TOKENS > 0
                and requested_tokens > FRONTDOOR_MAX_OUTPUT_TOKENS
            ):
                applied_tokens = FRONTDOOR_MAX_OUTPUT_TOKENS
                payload[active_field] = applied_tokens
                changed = True

        if applied_tokens is not None:
            log_event(
                {
                    "event": "output_token_limit_applied",
                    "path": path,
                    "field": active_field or applied_field,
                    "requested": requested_tokens,
                    "applied": applied_tokens,
                }
            )

    if not changed:
        return body

    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class FrontdoorHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "MiniMaxOpenAIFrontdoor/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        log_event(
            {
                "event": "access",
                "client": self.client_address[0],
                "message": fmt % args,
            }
        )

    def do_GET(self) -> None:
        self.handle_request()

    def do_POST(self) -> None:
        self.handle_request()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.add_cors_headers()
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def do_HEAD(self) -> None:
        self.handle_request()

    def handle_request(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/status", "/frontdoor/status"} and self.command == "GET":
            self.write_json(200, status_payload())
            return
        if path in {"/drain", "/frontdoor/drain"} and self.command == "GET":
            self.handle_drain()
            return

        queued = False
        acquired = False
        queue_wait_s = 0.0
        generation = is_generation_path(path, self.command)
        if generation:
            paused = is_paused()
            local_pause_bypass = (
                paused
                and FRONTDOOR_PAUSE_ALLOW_LOCAL
                and is_loopback_client(self.client_address[0])
            )
            if paused and not local_pause_bypass:
                payload = status_payload()
                payload["error"] = {
                    "message": "frontdoor paused; generation requests are temporarily disabled",
                    "type": "frontdoor_paused",
                }
                log_event(
                    {
                        "event": "generation_rejected_paused",
                        "client": self.client_address[0],
                        "path": path,
                        "pause_file": PAUSE_FILE,
                    }
                )
                self.write_json(503, payload)
                return
            if local_pause_bypass:
                log_event(
                    {
                        "event": "generation_pause_bypass_local",
                        "client": self.client_address[0],
                        "path": path,
                        "pause_file": PAUSE_FILE,
                    }
                )
            queued = True
            acquired, queue_wait_s = acquire_generation_slot()
            if not acquired:
                self.write_json(
                    503,
                    {
                        "error": {
                            "message": "server busy; queue timeout",
                            "type": "queue_timeout",
                        }
                    },
                )
                return

        started = time.perf_counter()
        status = 502
        error: str | None = None
        try:
            status = self.forward_to_backend()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.write_json(
                502,
                {
                    "error": {
                        "message": "backend request failed",
                        "type": "backend_error",
                        "detail": error,
                    }
                },
            )
        finally:
            if acquired:
                release_generation_slot()
            if generation:
                log_event(
                    {
                        "event": "generation_request",
                        "client": self.client_address[0],
                        "path": path,
                        "status": status,
                        "queued": queued,
                        "queue_wait_s": round(queue_wait_s, 3),
                        "elapsed_s": round(time.perf_counter() - started, 3),
                        "error": error,
                    }
                )

    def handle_drain(self) -> None:
        started = time.perf_counter()
        while True:
            with state_lock:
                active = active_generations
                queued = queued_generations
            if active == 0 and queued == 0:
                payload = status_payload()
                payload["drained"] = True
                payload["waited_s"] = round(time.perf_counter() - started, 3)
                self.write_json(200, payload)
                return
            if time.perf_counter() - started >= DRAIN_TIMEOUT_S:
                payload = status_payload()
                payload["drained"] = False
                payload["waited_s"] = round(time.perf_counter() - started, 3)
                payload["error"] = {
                    "message": "frontdoor drain timeout",
                    "type": "drain_timeout",
                }
                self.write_json(503, payload)
                return
            time.sleep(0.25)

    def forward_to_backend(self) -> int:
        path = self.path.split("?", 1)[0]
        body = self.read_body()
        headers = self.forward_headers()
        body = apply_request_defaults(path, body)
        if body is not None:
            headers["Content-Length"] = str(len(body))
        target_path = self.path
        connection = http.client.HTTPConnection(
            backend.hostname,
            backend.port,
            timeout=BACKEND_TIMEOUT_S,
        )
        try:
            connection.request(self.command, target_path, body=body, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status, response.reason)

            content_type = response.getheader("Content-Type", "")
            stream_response = content_type.lower().startswith("text/event-stream")
            has_length = False
            for name, value in response.getheaders():
                lower = name.lower()
                if lower in HOP_BY_HOP_HEADERS:
                    continue
                if lower.startswith("access-control-"):
                    continue
                if lower == "content-length":
                    has_length = True
                self.send_header(name, value)
            self.add_cors_headers()
            if not has_length:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()

            if self.command != "HEAD":
                if stream_response:
                    self.forward_stream_response(response)
                else:
                    self.forward_buffered_response(response)
            return response.status
        finally:
            connection.close()

    def forward_stream_response(self, response: http.client.HTTPResponse) -> None:
        while True:
            line = response.readline(65536)
            if not line:
                break
            self.wfile.write(line)
            self.wfile.flush()

    def forward_buffered_response(self, response: http.client.HTTPResponse) -> None:
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()

    def read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return None
        return self.rfile.read(length)

    def forward_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        for name, value in self.headers.items():
            lower = name.lower()
            if lower in HOP_BY_HOP_HEADERS or lower in {"host", "content-length"}:
                continue
            headers[name] = value
        headers["Host"] = f"{backend.hostname}:{backend.port}"
        headers["X-Forwarded-For"] = self.client_address[0]
        headers["X-Forwarded-Host"] = self.headers.get("Host", "")
        headers["X-Forwarded-Proto"] = "http"
        return headers

    def write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.add_cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def add_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", FRONTDOOR_CORS_ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, OpenAI-Beta, X-Requested-With",
        )


class FrontdoorServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64


def main() -> int:
    socket.setdefaulttimeout(BACKEND_TIMEOUT_S)
    server = FrontdoorServer((HOST, PORT), FrontdoorHandler)
    log_event(
        {
            "event": "frontdoor_start",
            "host": HOST,
            "port": PORT,
            "backend": BACKEND_BASE_URL,
            "max_active_generations": MAX_ACTIVE_GENERATIONS,
            "auth": "none",
            "pause_file": PAUSE_FILE,
            "paused": is_paused(),
            "drain_timeout_s": DRAIN_TIMEOUT_S,
            "pause_allow_local": FRONTDOOR_PAUSE_ALLOW_LOCAL,
            "served_model_name": FRONTDOOR_SERVED_MODEL_NAME,
            "rewrite_request_model": FRONTDOOR_REWRITE_REQUEST_MODEL,
            "chat_template_kwargs": default_chat_template_kwargs,
        }
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        log_event({"event": "frontdoor_stop"})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(1)
