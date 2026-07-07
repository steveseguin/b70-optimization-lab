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
if os.path.exists(PAUSE_FILE):
    print(f"OpenAI LAN frontdoor paused by {PAUSE_FILE}", flush=True)
    raise SystemExit(0)

BACKEND_BASE_URL = os.environ.get("FRONTDOOR_BACKEND_URL", "http://127.0.0.1:18080")
BACKEND_BASE_URLS_RAW = os.environ.get("FRONTDOOR_BACKEND_URLS", "")
HOST = os.environ.get("FRONTDOOR_HOST", "0.0.0.0")
PORT = int(os.environ.get("FRONTDOOR_PORT", "8000"))
MAX_ACTIVE_GENERATIONS = int(os.environ.get("FRONTDOOR_MAX_ACTIVE_GENERATIONS", "1"))
BACKEND_MAX_ACTIVE_GENERATIONS_RAW = os.environ.get(
    "FRONTDOOR_BACKEND_MAX_ACTIVE_GENERATIONS", ""
)
BACKEND_CAPACITIES_RAW = os.environ.get("FRONTDOOR_BACKEND_CAPACITIES", "")
QUEUE_TIMEOUT_S = float(os.environ.get("FRONTDOOR_QUEUE_TIMEOUT_S", "3600"))
BACKEND_TIMEOUT_S = float(os.environ.get("FRONTDOOR_BACKEND_TIMEOUT_S", "7200"))
FRONTDOOR_CORS_ALLOW_ORIGIN = os.environ.get("FRONTDOOR_CORS_ALLOW_ORIGIN", "*")
FRONTDOOR_LOG_EVENTS = os.environ.get("FRONTDOOR_LOG_EVENTS", "1") not in {
    "0",
    "false",
    "False",
}
FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON = os.environ.get(
    "FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON", ""
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

if BACKEND_BASE_URLS_RAW:
    BACKEND_BASE_URLS = [
        item.strip()
        for item in BACKEND_BASE_URLS_RAW.replace("\n", ",").split(",")
        if item.strip()
    ]
else:
    BACKEND_BASE_URLS = [BACKEND_BASE_URL]

if not BACKEND_BASE_URLS:
    raise SystemExit("at least one backend URL is required")

backends = []
for backend_url in BACKEND_BASE_URLS:
    parsed_backend = urlsplit(backend_url)
    if (
        parsed_backend.scheme != "http"
        or not parsed_backend.hostname
        or not parsed_backend.port
    ):
        raise SystemExit(
            "FRONTDOOR_BACKEND_URLS/FRONTDOOR_BACKEND_URL entries must be "
            f"http URLs with explicit ports, got {backend_url!r}"
        )
    backends.append(parsed_backend)

if BACKEND_CAPACITIES_RAW:
    BACKEND_CAPACITIES = [
        int(item.strip())
        for item in BACKEND_CAPACITIES_RAW.replace("\n", ",").split(",")
        if item.strip()
    ]
    if len(BACKEND_CAPACITIES) != len(backends):
        raise SystemExit(
            "FRONTDOOR_BACKEND_CAPACITIES must have one entry per backend: "
            f"{len(BACKEND_CAPACITIES)} capacities for {len(backends)} backends"
        )
elif BACKEND_MAX_ACTIVE_GENERATIONS_RAW:
    BACKEND_CAPACITIES = [int(BACKEND_MAX_ACTIVE_GENERATIONS_RAW)] * len(backends)
else:
    default_backend_capacity = 1 if len(backends) > 1 else MAX_ACTIVE_GENERATIONS
    BACKEND_CAPACITIES = [default_backend_capacity] * len(backends)

if any(capacity <= 0 for capacity in BACKEND_CAPACITIES):
    raise SystemExit("backend capacities must be positive integers")

generation_slots = threading.BoundedSemaphore(MAX_ACTIVE_GENERATIONS)
backend_generation_slots = [
    threading.BoundedSemaphore(capacity) for capacity in BACKEND_CAPACITIES
]
state_lock = threading.Lock()
log_lock = threading.Lock()
backend_select_lock = threading.Lock()
active_generations = 0
queued_generations = 0
total_generation_requests = 0
backend_active_generations = [0 for _ in backends]
backend_total_generation_requests = [0 for _ in backends]
next_backend_index = 0
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


def status_payload() -> dict[str, Any]:
    with state_lock:
        active = active_generations
        queued = queued_generations
        total = total_generation_requests
        backend_active = list(backend_active_generations)
        backend_total = list(backend_total_generation_requests)
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
            "backend": BACKEND_BASE_URLS[0],
            "backends": [
                {
                    "url": BACKEND_BASE_URLS[i],
                    "max_active_generations": BACKEND_CAPACITIES[i],
                    "active_generations": backend_active[i],
                    "total_generation_requests": backend_total[i],
                }
                for i in range(len(backends))
            ],
            "max_active_generations": MAX_ACTIVE_GENERATIONS,
            "queue_timeout_s": QUEUE_TIMEOUT_S,
            "active_generations": active,
            "queued_generations": queued,
            "total_generation_requests": total,
            "event_logging": FRONTDOOR_LOG_EVENTS,
            "auth": "none",
        },
    }


def acquire_backend_slot(timeout_s: float) -> int | None:
    global next_backend_index
    deadline = time.perf_counter() + timeout_s
    while True:
        with backend_select_lock:
            start = next_backend_index
            for offset in range(len(backend_generation_slots)):
                index = (start + offset) % len(backend_generation_slots)
                if backend_generation_slots[index].acquire(blocking=False):
                    next_backend_index = (index + 1) % len(backend_generation_slots)
                    return index

        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return None
        time.sleep(min(0.05, remaining))


def acquire_generation_slot() -> tuple[bool, int | None, float]:
    global active_generations, queued_generations, total_generation_requests
    started = time.perf_counter()
    deadline = started + QUEUE_TIMEOUT_S
    with state_lock:
        queued_generations += 1
        total_generation_requests += 1

    acquired = generation_slots.acquire(timeout=QUEUE_TIMEOUT_S)
    backend_index: int | None = None
    if acquired:
        backend_index = acquire_backend_slot(max(0.0, deadline - time.perf_counter()))
        if backend_index is None:
            generation_slots.release()
            acquired = False

    waited = time.perf_counter() - started
    with state_lock:
        queued_generations -= 1
        if acquired:
            active_generations += 1
            assert backend_index is not None
            backend_active_generations[backend_index] += 1
            backend_total_generation_requests[backend_index] += 1
    return acquired, backend_index, waited


def release_generation_slot(backend_index: int | None) -> None:
    global active_generations
    with state_lock:
        active_generations -= 1
        if backend_index is not None:
            backend_active_generations[backend_index] -= 1
    if backend_index is not None:
        backend_generation_slots[backend_index].release()
    generation_slots.release()


def apply_request_defaults(path: str, body: bytes | None) -> bytes | None:
    if (
        path != "/v1/chat/completions"
        or not default_chat_template_kwargs
        or body is None
    ):
        return body

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body
    if not isinstance(payload, dict):
        return body

    existing = payload.get("chat_template_kwargs")
    if existing is None:
        payload["chat_template_kwargs"] = dict(default_chat_template_kwargs)
    elif isinstance(existing, dict):
        merged = dict(default_chat_template_kwargs)
        merged.update(existing)
        payload["chat_template_kwargs"] = merged
    else:
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

        queued = False
        acquired = False
        backend_index: int | None = 0
        queue_wait_s = 0.0
        generation = is_generation_path(path, self.command)
        if generation:
            queued = True
            acquired, backend_index, queue_wait_s = acquire_generation_slot()
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
            status = self.forward_to_backend(backend_index or 0)
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
                release_generation_slot(backend_index)
            if generation:
                log_event(
                    {
                        "event": "generation_request",
                        "client": self.client_address[0],
                        "path": path,
                        "status": status,
                        "backend": BACKEND_BASE_URLS[backend_index or 0],
                        "queued": queued,
                        "queue_wait_s": round(queue_wait_s, 3),
                        "elapsed_s": round(time.perf_counter() - started, 3),
                        "error": error,
                    }
                )

    def forward_to_backend(self, backend_index: int) -> int:
        path = self.path.split("?", 1)[0]
        body = self.read_body()
        selected_backend = backends[backend_index]
        headers = self.forward_headers(selected_backend)
        body = apply_request_defaults(path, body)
        if body is not None:
            headers["Content-Length"] = str(len(body))
        target_path = self.path
        connection = http.client.HTTPConnection(
            selected_backend.hostname,
            selected_backend.port,
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

    def forward_headers(self, selected_backend: Any) -> dict[str, str]:
        headers: dict[str, str] = {}
        for name, value in self.headers.items():
            lower = name.lower()
            if lower in HOP_BY_HOP_HEADERS or lower in {"host", "content-length"}:
                continue
            headers[name] = value
        headers["Host"] = f"{selected_backend.hostname}:{selected_backend.port}"
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
            "backend": BACKEND_BASE_URLS[0],
            "backends": BACKEND_BASE_URLS,
            "max_active_generations": MAX_ACTIVE_GENERATIONS,
            "auth": "none",
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
