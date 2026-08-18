#!/usr/bin/env python3
"""No-auth LAN frontdoor for a local OpenAI-compatible vLLM server.

This proxy keeps the public LAN URL stable while limiting active generation
requests before they reach vLLM. Model-slot wrappers set profile metadata and
concurrency from the active profile.
"""

from __future__ import annotations

import http.client
import hashlib
import json
import math
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit


def env_truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default) not in {"0", "false", "False"}


def parse_csv_ints(raw: str) -> list[int]:
    return [
        int(item.strip())
        for item in raw.replace("\n", ",").split(",")
        if item.strip()
    ]


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
BACKEND_SLOTS_TIMEOUT_S = float(
    os.environ.get("FRONTDOOR_BACKEND_SLOTS_TIMEOUT_S", "5")
)
FRONTDOOR_CORS_ALLOW_ORIGIN = os.environ.get("FRONTDOOR_CORS_ALLOW_ORIGIN", "*")
FRONTDOOR_LOG_EVENTS = env_truthy("FRONTDOOR_LOG_EVENTS", "1")
FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON = os.environ.get(
    "FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON", ""
)
FRONTDOOR_STICKY_ROUTING = env_truthy("FRONTDOOR_STICKY_ROUTING", "0")
FRONTDOOR_STICKY_HEADERS = [
    item.strip().lower()
    for item in os.environ.get(
        "FRONTDOOR_STICKY_HEADERS",
        "x-agent-id,x-session-id,x-conversation-id",
    ).split(",")
    if item.strip()
]
FRONTDOOR_STICKY_JSON_FIELDS = [
    item.strip()
    for item in os.environ.get(
        "FRONTDOOR_STICKY_JSON_FIELDS",
        "user,session_id,conversation_id,metadata.agent_id,metadata.session_id",
    ).split(",")
    if item.strip()
]
MODEL_SLOT_NAME = os.environ.get("MODEL_SLOT_NAME", "")
MODEL_SLOT_API_MODEL = os.environ.get("MODEL_SLOT_API_MODEL", MODEL_SLOT_NAME)
MODEL_SLOT_TITLE = os.environ.get("MODEL_SLOT_TITLE", "")
MODEL_SLOT_HF_ID = os.environ.get("MODEL_SLOT_HF_ID", "")
MODEL_SLOT_MODALITIES = os.environ.get("MODEL_SLOT_MODALITIES", "")
MODEL_SLOT_STATUS = os.environ.get("MODEL_SLOT_STATUS", "")
FRONTDOOR_PUBLIC_BASE_URL_HINT = os.environ.get(
    "FRONTDOOR_PUBLIC_BASE_URL_HINT",
    f"http://<server-lan-ip>:{PORT}/v1",
)
FRONTDOOR_CONTEXT_TOKENS_PER_REQUEST = int(
    os.environ.get("FRONTDOOR_CONTEXT_TOKENS_PER_REQUEST", "0") or "0"
)
FRONTDOOR_TOTAL_CONTEXT_TOKENS_PER_BACKEND = int(
    os.environ.get("FRONTDOOR_TOTAL_CONTEXT_TOKENS_PER_BACKEND", "0") or "0"
)
FRONTDOOR_RECOMMENDED_MAX_OUTPUT_TOKENS = int(
    os.environ.get("FRONTDOOR_RECOMMENDED_MAX_OUTPUT_TOKENS", "0") or "0"
)
FRONTDOOR_PROMPT_CACHE_RAM_MIB = int(
    os.environ.get("FRONTDOOR_PROMPT_CACHE_RAM_MIB", "0") or "0"
)
FRONTDOOR_KV_CACHE_DTYPE = os.environ.get("FRONTDOOR_KV_CACHE_DTYPE", "")
FRONTDOOR_SPECULATION = os.environ.get("FRONTDOOR_SPECULATION", "")
FRONTDOOR_SLOT_PROFILE = os.environ.get("FRONTDOOR_SLOT_PROFILE", "")
FRONTDOOR_BACKEND_CONTEXT_TOKENS_RAW = os.environ.get(
    "FRONTDOOR_BACKEND_CONTEXT_TOKENS", ""
)
FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS = int(
    os.environ.get("FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS", "0") or "0"
)
FRONTDOOR_TOKEN_ESTIMATE_CHARS_PER_TOKEN = float(
    os.environ.get("FRONTDOOR_TOKEN_ESTIMATE_CHARS_PER_TOKEN", "3.0") or "3.0"
)
FRONTDOOR_TOKEN_ESTIMATE_FIXED_OVERHEAD = int(
    os.environ.get("FRONTDOOR_TOKEN_ESTIMATE_FIXED_OVERHEAD", "512") or "512"
)
FRONTDOOR_TOKEN_ESTIMATE_PER_MESSAGE_OVERHEAD = int(
    os.environ.get("FRONTDOOR_TOKEN_ESTIMATE_PER_MESSAGE_OVERHEAD", "8") or "8"
)
FRONTDOOR_SHORT_CAN_OVERFLOW_TO_LONG = env_truthy(
    "FRONTDOOR_SHORT_CAN_OVERFLOW_TO_LONG", "1"
)
FRONTDOOR_STRICT_STICKY_BY_DEFAULT = env_truthy(
    "FRONTDOOR_STRICT_STICKY_BY_DEFAULT", "0"
)
FRONTDOOR_RETRY_AFTER_S = int(
    os.environ.get("FRONTDOOR_RETRY_AFTER_S", "15") or "15"
)

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
    BACKEND_CAPACITIES = parse_csv_ints(BACKEND_CAPACITIES_RAW)
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

if FRONTDOOR_BACKEND_CONTEXT_TOKENS_RAW:
    BACKEND_CONTEXT_TOKENS = parse_csv_ints(FRONTDOOR_BACKEND_CONTEXT_TOKENS_RAW)
    if len(BACKEND_CONTEXT_TOKENS) != len(backends):
        raise SystemExit(
            "FRONTDOOR_BACKEND_CONTEXT_TOKENS must have one entry per backend: "
            f"{len(BACKEND_CONTEXT_TOKENS)} contexts for {len(backends)} backends"
        )
else:
    default_context_tokens = FRONTDOOR_CONTEXT_TOKENS_PER_REQUEST or 0
    BACKEND_CONTEXT_TOKENS = [default_context_tokens for _ in backends]

if any(context < 0 for context in BACKEND_CONTEXT_TOKENS):
    raise SystemExit("backend context tokens must be non-negative integers")

VISION_BACKEND_INDICES_RAW = os.environ.get("FRONTDOOR_VISION_BACKEND_INDICES", "")
if VISION_BACKEND_INDICES_RAW.strip():
    VISION_BACKEND_INDICES = parse_csv_ints(VISION_BACKEND_INDICES_RAW)
    if any(i < 0 or i >= len(backends) for i in VISION_BACKEND_INDICES):
        raise SystemExit(
            "FRONTDOOR_VISION_BACKEND_INDICES entries must be valid backend indices"
        )
else:
    VISION_BACKEND_INDICES = list(range(len(backends)))


def payload_has_image(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    for message in payload.get("messages") or []:
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and (
                    part.get("type") in {"image_url", "input_image", "image"}
                    or "image_url" in part
                ):
                    return True
    return False

MAX_BACKEND_CONTEXT_TOKENS = max(BACKEND_CONTEXT_TOKENS) if BACKEND_CONTEXT_TOKENS else 0
if not FRONTDOOR_CONTEXT_TOKENS_PER_REQUEST and MAX_BACKEND_CONTEXT_TOKENS:
    FRONTDOOR_CONTEXT_TOKENS_PER_REQUEST = MAX_BACKEND_CONTEXT_TOKENS
if not FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS and MAX_BACKEND_CONTEXT_TOKENS:
    distinct_contexts = sorted({value for value in BACKEND_CONTEXT_TOKENS if value > 0})
    if len(distinct_contexts) > 1:
        FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS = distinct_contexts[0]

USE_GLOBAL_GENERATION_LIMIT = MAX_ACTIVE_GENERATIONS < sum(BACKEND_CAPACITIES)
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


def parse_json_body(headers: Any, body: bytes | None) -> dict[str, Any] | None:
    if body is None:
        return None
    content_type = headers.get("Content-Type", "")
    if "json" not in content_type.lower():
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def int_from_headers(headers: Any, names: tuple[str, ...]) -> tuple[int | None, str | None]:
    for name in names:
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            value = int(str(raw).strip())
        except ValueError:
            continue
        if value >= 0:
            return value, f"header:{name.lower()}"
    return None, None


def collect_prompt_text(value: Any, parts: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        parts.append(value)
        return
    if isinstance(value, (int, float, bool)):
        parts.append(str(value))
        return
    if isinstance(value, list):
        for item in value:
            collect_prompt_text(item, parts)
        return
    if isinstance(value, dict):
        for item in value.values():
            collect_prompt_text(item, parts)


def json_size_text(value: Any) -> str:
    try:
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def get_nested_value(payload: dict[str, Any], field_path: str) -> Any:
    current: Any = payload
    for part in field_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def estimate_prompt_tokens(
    headers: Any,
    payload: dict[str, Any] | None,
) -> tuple[int | None, str, int]:
    header_value, header_source = int_from_headers(
        headers,
        ("X-Prompt-Tokens", "X-Estimated-Prompt-Tokens"),
    )
    if header_value is not None and header_source is not None:
        return header_value, header_source, 0

    if payload is None:
        return None, "unavailable", 0

    for field in (
        "prompt_tokens",
        "estimated_prompt_tokens",
        "metadata.prompt_tokens",
        "metadata.estimated_prompt_tokens",
    ):
        value = get_nested_value(payload, field)
        if isinstance(value, int) and value >= 0:
            return value, f"json:{field}", 0
        if isinstance(value, str):
            try:
                parsed = int(value)
            except ValueError:
                continue
            if parsed >= 0:
                return parsed, f"json:{field}", 0

    parts: list[str] = []
    message_count = 0
    messages = payload.get("messages")
    if isinstance(messages, list):
        message_count = len(messages)
        for message in messages:
            if isinstance(message, dict):
                for key in (
                    "role",
                    "name",
                    "content",
                    "tool_calls",
                    "function_call",
                    "tool_call_id",
                ):
                    collect_prompt_text(message.get(key), parts)
            else:
                collect_prompt_text(message, parts)

    for key in ("prompt", "input", "instructions", "suffix"):
        if key in payload:
            collect_prompt_text(payload.get(key), parts)

    for key in ("tools", "functions", "response_format"):
        if key in payload:
            parts.append(json_size_text(payload.get(key)))

    char_count = sum(len(part) for part in parts)
    estimated = math.ceil(char_count / FRONTDOOR_TOKEN_ESTIMATE_CHARS_PER_TOKEN)
    estimated += FRONTDOOR_TOKEN_ESTIMATE_FIXED_OVERHEAD
    estimated += message_count * FRONTDOOR_TOKEN_ESTIMATE_PER_MESSAGE_OVERHEAD
    return max(0, estimated), "heuristic", char_count


def requested_max_output_tokens(payload: dict[str, Any] | None) -> int:
    if payload is None:
        return FRONTDOOR_RECOMMENDED_MAX_OUTPUT_TOKENS or 4096
    for key in ("max_completion_tokens", "max_tokens", "n_predict"):
        value = payload.get(key)
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str):
            try:
                parsed = int(value)
            except ValueError:
                continue
            if parsed >= 0:
                return parsed
    return FRONTDOOR_RECOMMENDED_MAX_OUTPUT_TOKENS or 4096


def ordered_backend_indices(indices: list[int], sticky_key: str | None) -> list[int]:
    if not indices:
        return []
    if not sticky_key:
        return indices
    digest = hashlib.sha256(sticky_key.encode("utf-8")).digest()
    start = int.from_bytes(digest[:8], "big") % len(indices)
    return indices[start:] + indices[:start]


def request_route_info(
    headers: Any,
    payload: dict[str, Any] | None,
    sticky_key: str | None,
) -> dict[str, Any]:
    prompt_tokens, estimate_source, estimated_chars = estimate_prompt_tokens(
        headers,
        payload,
    )
    max_output_tokens = requested_max_output_tokens(payload)
    required_tokens = None
    if prompt_tokens is not None:
        required_tokens = prompt_tokens + max_output_tokens

    tier_override = (headers.get("X-Context-Tier") or "").strip().lower()
    if tier_override not in {"short", "long", "auto"}:
        tier_override = ""
    if not tier_override and payload is not None:
        metadata_tier = get_nested_value(payload, "metadata.context_tier")
        if isinstance(metadata_tier, str) and metadata_tier.lower() in {
            "short",
            "long",
            "auto",
        }:
            tier_override = metadata_tier.lower()

    all_indices = list(range(len(backends)))
    needs_vision = payload_has_image(payload)
    if needs_vision and len(VISION_BACKEND_INDICES) < len(backends):
        all_indices = list(VISION_BACKEND_INDICES)
    if required_tokens is None or not any(BACKEND_CONTEXT_TOKENS):
        eligible = all_indices
    else:
        eligible = [
            index
            for index, context_tokens in enumerate(BACKEND_CONTEXT_TOKENS)
            if index in all_indices
            and (context_tokens <= 0 or context_tokens >= required_tokens)
        ]

    estimate_exact = estimate_source.startswith(("header:", "json:"))
    estimate_exceeds_context = (
        required_tokens is not None
        and MAX_BACKEND_CONTEXT_TOKENS > 0
        and required_tokens > MAX_BACKEND_CONTEXT_TOKENS
    )
    if not eligible and estimate_exceeds_context and not estimate_exact:
        eligible = [
            index
            for index, context_tokens in enumerate(BACKEND_CONTEXT_TOKENS)
            if index in all_indices
            and context_tokens == MAX_BACKEND_CONTEXT_TOKENS
        ]

    short_indices = [
        index
        for index in eligible
        if FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS
        and BACKEND_CONTEXT_TOKENS[index] > 0
        and BACKEND_CONTEXT_TOKENS[index] <= FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS
    ]
    long_indices = [
        index
        for index in eligible
        if not FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS
        or BACKEND_CONTEXT_TOKENS[index] == 0
        or BACKEND_CONTEXT_TOKENS[index] > FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS
    ]

    if tier_override == "long":
        preferred = long_indices or eligible
        fallback: list[int] = []
        selected_tier = "long"
    elif tier_override == "short":
        preferred = short_indices or eligible
        fallback = []
        selected_tier = "short"
    elif (
        required_tokens is not None
        and FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS
        and required_tokens <= FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS
        and short_indices
    ):
        preferred = short_indices
        fallback = [
            index
            for index in long_indices
            if FRONTDOOR_SHORT_CAN_OVERFLOW_TO_LONG
        ]
        selected_tier = "short"
    else:
        preferred = long_indices or eligible
        fallback = []
        selected_tier = "long" if preferred else "none"

    return {
        "prompt_tokens_estimated": prompt_tokens,
        "prompt_tokens_estimate_source": estimate_source,
        "prompt_chars_estimated": estimated_chars,
        "max_output_tokens": max_output_tokens,
        "required_context_tokens_estimated": required_tokens,
        "estimate_exceeds_public_context": estimate_exceeds_context,
        "estimate_exact": estimate_exact,
        "context_tier": selected_tier,
        "context_tier_override": tier_override or None,
        "sticky_key_present": bool(sticky_key),
        "preferred_backend_indices": ordered_backend_indices(preferred, sticky_key),
        "fallback_backend_indices": ordered_backend_indices(fallback, sticky_key),
        "eligible_backend_indices": eligible,
    }


def backend_slots(backend_index: int) -> list[dict[str, Any]] | None:
    """Fetch /slots from one backend. Returns None if it is unreachable."""
    backend = backends[backend_index]
    connection = http.client.HTTPConnection(
        backend.hostname, backend.port, timeout=BACKEND_SLOTS_TIMEOUT_S
    )
    try:
        connection.request("GET", "/slots")
        response = connection.getresponse()
        if response.status != 200:
            return None
        parsed = json.loads(response.read())
    except (OSError, http.client.HTTPException, ValueError):
        return None
    finally:
        connection.close()
    if not isinstance(parsed, list):
        return None
    return parsed


def aggregated_slots_payload() -> list[dict[str, Any]]:
    """Merge every backend's slots into one fleet-wide list.

    llama.cpp numbers slots per process, so proxying /slots to a single backend
    reports that backend's slot count instead of the fleet total. Slots are
    renumbered globally and tagged with their backend.
    """
    results: list[list[dict[str, Any]] | None] = [None] * len(backends)
    threads = []

    def fetch(index: int) -> None:
        results[index] = backend_slots(index)

    for index in range(len(backends)):
        thread = threading.Thread(target=fetch, args=(index,), daemon=True)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join(BACKEND_SLOTS_TIMEOUT_S + 1.0)

    merged: list[dict[str, Any]] = []
    for index, slots in enumerate(results):
        backend = backends[index]
        backend_url = f"http://{backend.hostname}:{backend.port}"
        if slots is None:
            # Keep unreachable backends visible so the count stays the fleet
            # total rather than silently shrinking.
            for offset in range(BACKEND_CAPACITIES[index]):
                merged.append(
                    {
                        "id": len(merged),
                        "slot_id_on_backend": offset,
                        "backend_index": index,
                        "backend_url": backend_url,
                        "available": False,
                        "error": "backend unreachable",
                    }
                )
            continue
        for slot in slots:
            entry = dict(slot)
            entry["slot_id_on_backend"] = entry.get("id")
            entry["backend_index"] = index
            entry["backend_url"] = backend_url
            entry["id"] = len(merged)
            merged.append(entry)
    return merged


def status_payload() -> dict[str, Any]:
    with state_lock:
        active = active_generations
        queued = queued_generations
        total = total_generation_requests
        backend_active = list(backend_active_generations)
        backend_total = list(backend_total_generation_requests)
    short_slot_count = sum(
        capacity
        for capacity, context_tokens in zip(BACKEND_CAPACITIES, BACKEND_CONTEXT_TOKENS)
        if FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS
        and context_tokens > 0
        and context_tokens <= FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS
    )
    long_slot_count = sum(BACKEND_CAPACITIES) - short_slot_count
    if short_slot_count and long_slot_count:
        routing_behavior = (
            "Requests estimated to fit the short tier prefer short-context "
            "backends; larger requests route to long-context backends. "
            "Requests with the same sticky key prefer the same backend "
            "within the selected tier. X-Sticky-Mode: strict waits for "
            "that backend instead of spilling to another backend."
        )
        context_note = (
            "The public service contract remains 64K context; common short "
            "requests may run on denser 32K slots."
        )
    else:
        routing_behavior = (
            "Requests with the same sticky key prefer the same backend. "
            "X-Sticky-Mode: strict waits for that backend instead of spilling "
            "to another backend."
        )
        context_note = (
            "Each active request has the advertised context window; token "
            "hints are used for early over-window rejection."
        )
    return {
        "ok": True,
        "model_slot": {
            "name": MODEL_SLOT_NAME,
            "api_model": MODEL_SLOT_API_MODEL,
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
                    "context_tokens_per_slot": (
                        BACKEND_CONTEXT_TOKENS[i] or None
                    ),
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
            "sticky_routing": FRONTDOOR_STICKY_ROUTING,
            "sticky_headers": FRONTDOOR_STICKY_HEADERS,
            "sticky_json_fields": FRONTDOOR_STICKY_JSON_FIELDS,
            "strict_sticky_by_default": FRONTDOOR_STRICT_STICKY_BY_DEFAULT,
            "backend_context_tokens": BACKEND_CONTEXT_TOKENS,
            "short_context_limit_tokens": (
                FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS or None
            ),
            "auth": "none",
        },
        "client_hints": {
            "api": {
                "type": "openai-compatible",
                "base_url": FRONTDOOR_PUBLIC_BASE_URL_HINT,
                "status_endpoint": "/status",
                "base_url_relative_status_endpoint": "/v1/frontdoor/status",
                "models_endpoint": "/v1/models",
                "chat_completions_endpoint": "/v1/chat/completions",
                "completions_endpoint": "/v1/completions",
                "model": MODEL_SLOT_API_MODEL,
                "auth": "none",
            },
            "recommended": {
                "max_concurrent_generation_requests": MAX_ACTIVE_GENERATIONS,
                "max_agents": MAX_ACTIVE_GENERATIONS,
                "max_strict_affinity_generation_requests": MAX_ACTIVE_GENERATIONS,
                "max_strict_short_context_agents": short_slot_count or None,
                "max_long_context_generation_requests": long_slot_count or None,
                "max_output_tokens": (
                    FRONTDOOR_RECOMMENDED_MAX_OUTPUT_TOKENS or None
                ),
                "send_sticky_identifier": FRONTDOOR_STICKY_ROUTING,
            },
            "limits": {
                "context_tokens_per_request": (
                    FRONTDOOR_CONTEXT_TOKENS_PER_REQUEST or None
                ),
                "total_context_tokens_per_backend": (
                    FRONTDOOR_TOTAL_CONTEXT_TOKENS_PER_BACKEND or None
                ),
                "backend_context_tokens_per_slot": BACKEND_CONTEXT_TOKENS,
                "short_context_limit_tokens": (
                    FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS or None
                ),
                "backend_count": len(backends),
                "slots_per_backend": BACKEND_CAPACITIES,
                "total_generation_slots": MAX_ACTIVE_GENERATIONS,
                "queue_timeout_s": QUEUE_TIMEOUT_S,
                "backend_timeout_s": BACKEND_TIMEOUT_S,
            },
            "prompt_cache": {
                "enabled": FRONTDOOR_PROMPT_CACHE_RAM_MIB > 0,
                "cache_ram_mib_per_backend": (
                    FRONTDOOR_PROMPT_CACHE_RAM_MIB or None
                ),
                "sticky_routing_required_for_best_reuse": FRONTDOOR_STICKY_ROUTING,
                "avoid_request_overrides": [
                    {
                        "field": "cache_prompt",
                        "value": False,
                        "reason": "This disables llama.cpp prompt caching for the request.",
                    }
                ],
                "headers": {
                    "X-Agent-Id": "<stable-agent-id>",
                    "X-Session-Id": "<stable-session-id>",
                    "X-Conversation-Id": "<stable-conversation-id>",
                    "X-Sticky-Mode": "strict",
                    "X-Estimated-Prompt-Tokens": "<optional exact-or-client-estimated prompt token count>",
                },
                "json_fields": FRONTDOOR_STICKY_JSON_FIELDS,
            },
            "routing": {
                "sticky_routing": FRONTDOOR_STICKY_ROUTING,
                "sticky_headers": FRONTDOOR_STICKY_HEADERS,
                "sticky_json_fields": FRONTDOOR_STICKY_JSON_FIELDS,
                "strict_sticky_header": "X-Sticky-Mode: strict",
                "context_tier_header": "X-Context-Tier: short|long|auto",
                "prompt_token_hint_headers": [
                    "X-Prompt-Tokens",
                    "X-Estimated-Prompt-Tokens",
                ],
                "short_context_overflows_to_long": (
                    FRONTDOOR_SHORT_CAN_OVERFLOW_TO_LONG
                ),
                "token_estimator": {
                    "chars_per_token": FRONTDOOR_TOKEN_ESTIMATE_CHARS_PER_TOKEN,
                    "fixed_overhead": FRONTDOOR_TOKEN_ESTIMATE_FIXED_OVERHEAD,
                    "per_message_overhead": (
                        FRONTDOOR_TOKEN_ESTIMATE_PER_MESSAGE_OVERHEAD
                    ),
                },
                "behavior": routing_behavior,
            },
            "runtime": {
                "profile": FRONTDOOR_SLOT_PROFILE or None,
                "kv_cache_dtype": FRONTDOOR_KV_CACHE_DTYPE or None,
                "speculation": FRONTDOOR_SPECULATION or None,
                "notes": [
                    "Use a stable sticky key per agent or conversation to benefit from prompt caching.",
                    "Keep client-side generation concurrency at or below the advertised max.",
                    context_note,
                ],
            },
            "example_request": {
                "method": "POST",
                "path": "/v1/chat/completions",
                "headers": {
                    "Content-Type": "application/json",
                    "X-Agent-Id": "bug-agent-0",
                    "X-Sticky-Mode": "strict",
                },
                "json": {
                    "model": MODEL_SLOT_API_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Inspect this code path and report likely bugs.",
                        }
                    ],
                    "max_tokens": FRONTDOOR_RECOMMENDED_MAX_OUTPUT_TOKENS or 4096,
                    "temperature": 0,
                },
            },
        },
    }


def acquire_backend_slot(
    timeout_s: float,
    preferred_indices: list[int],
    fallback_indices: list[int],
    strict_sticky: bool = False,
    round_robin: bool = False,
) -> int | None:
    global next_backend_index
    if not preferred_indices and not fallback_indices:
        return None
    deadline = time.perf_counter() + timeout_s
    while True:
        with backend_select_lock:
            preferred_search = preferred_indices
            fallback_search = fallback_indices
            if strict_sticky and preferred_indices:
                preferred_search = preferred_indices[:1]
                fallback_search = []

            if round_robin and len(preferred_search) > 1:
                if next_backend_index in preferred_search:
                    start = preferred_search.index(next_backend_index)
                else:
                    start = next_backend_index % len(preferred_search)
                preferred_search = preferred_search[start:] + preferred_search[:start]
            if round_robin and len(fallback_search) > 1:
                if next_backend_index in fallback_search:
                    start = fallback_search.index(next_backend_index)
                else:
                    start = next_backend_index % len(fallback_search)
                fallback_search = fallback_search[start:] + fallback_search[:start]

            for index in preferred_search + fallback_search:
                if backend_generation_slots[index].acquire(blocking=False):
                    if round_robin:
                        next_backend_index = (index + 1) % len(backend_generation_slots)
                    return index

        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return None
        time.sleep(min(0.05, remaining))


def acquire_generation_slot(
    route_info: dict[str, Any],
    strict_sticky: bool = False,
) -> tuple[bool, int | None, float]:
    global active_generations, queued_generations, total_generation_requests
    started = time.perf_counter()
    deadline = started + QUEUE_TIMEOUT_S
    with state_lock:
        queued_generations += 1
        total_generation_requests += 1

    acquired = True
    if USE_GLOBAL_GENERATION_LIMIT:
        acquired = generation_slots.acquire(timeout=QUEUE_TIMEOUT_S)
    backend_index: int | None = None
    if acquired:
        backend_index = acquire_backend_slot(
            max(0.0, deadline - time.perf_counter()),
            preferred_indices=route_info["preferred_backend_indices"],
            fallback_indices=route_info["fallback_backend_indices"],
            strict_sticky=strict_sticky,
            round_robin=not route_info["sticky_key_present"],
        )
        if backend_index is None:
            if USE_GLOBAL_GENERATION_LIMIT:
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
    if USE_GLOBAL_GENERATION_LIMIT:
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


def extract_json_field(payload: Any, field_path: str) -> str | None:
    current = payload
    for part in field_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, str) and current:
        return current
    if isinstance(current, (int, float, bool)):
        return str(current)
    return None


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
        body = self.read_body()
        if (
            path
            in {
                "/status",
                "/frontdoor/status",
                "/v1/status",
                "/v1/frontdoor/status",
            }
            and self.command == "GET"
        ):
            self.write_json(200, status_payload())
            return

        if path in {"/slots", "/v1/slots"} and self.command == "GET":
            self.write_json(200, aggregated_slots_payload())
            return

        queued = False
        acquired = False
        backend_index: int | None = 0
        queue_wait_s = 0.0
        generation = is_generation_path(path, self.command)
        payload = parse_json_body(self.headers, body) if generation else None
        route_info: dict[str, Any] | None = None
        sticky_key, sticky_source = (
            self.sticky_key_for_request(body, payload) if generation else (None, None)
        )
        strict_sticky = (
            self.strict_sticky_for_request() and bool(sticky_key)
            if generation
            else False
        )
        if generation:
            route_info = request_route_info(self.headers, payload, sticky_key)
            if (
                not route_info["preferred_backend_indices"]
                and not route_info["fallback_backend_indices"]
            ):
                self.write_json(
                    413,
                    {
                        "error": {
                            "message": "estimated request context exceeds available context windows",
                            "type": "context_window_exceeded",
                            "estimate": {
                                key: route_info[key]
                                for key in (
                                    "prompt_tokens_estimated",
                                    "prompt_tokens_estimate_source",
                                    "max_output_tokens",
                                    "required_context_tokens_estimated",
                                )
                            },
                            "backend_context_tokens_per_slot": BACKEND_CONTEXT_TOKENS,
                        }
                    },
                )
                return
            queued = True
            acquired, backend_index, queue_wait_s = acquire_generation_slot(
                route_info,
                strict_sticky=strict_sticky,
            )
            if not acquired:
                self.write_json(
                    503,
                    {
                        "error": {
                            "message": "server busy; queue timeout",
                            "type": "queue_timeout",
                        }
                    },
                    extra_headers={"Retry-After": str(FRONTDOOR_RETRY_AFTER_S)},
                )
                return

        started = time.perf_counter()
        status = 502
        error: str | None = None
        try:
            status = self.forward_to_backend(backend_index or 0, body)
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
                        "backend_context_tokens": (
                            BACKEND_CONTEXT_TOKENS[backend_index or 0]
                            if BACKEND_CONTEXT_TOKENS
                            else None
                        ),
                        "context_tier": (
                            route_info.get("context_tier") if route_info else None
                        ),
                        "required_context_tokens_estimated": (
                            route_info.get("required_context_tokens_estimated")
                            if route_info
                            else None
                        ),
                        "prompt_tokens_estimated": (
                            route_info.get("prompt_tokens_estimated")
                            if route_info
                            else None
                        ),
                        "prompt_tokens_estimate_source": (
                            route_info.get("prompt_tokens_estimate_source")
                            if route_info
                            else None
                        ),
                        "strict_sticky": strict_sticky,
                        "sticky": bool(sticky_key),
                        "sticky_source": sticky_source,
                        "sticky_hash": (
                            hashlib.sha256(sticky_key.encode("utf-8")).hexdigest()[:12]
                            if sticky_key
                            else None
                        ),
                        "queued": queued,
                        "queue_wait_s": round(queue_wait_s, 3),
                        "elapsed_s": round(time.perf_counter() - started, 3),
                        "error": error,
                    }
                )

    def forward_to_backend(self, backend_index: int, body: bytes | None) -> int:
        path = self.path.split("?", 1)[0]
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

    def strict_sticky_for_request(self) -> bool:
        mode = (self.headers.get("X-Sticky-Mode") or "").strip().lower()
        if mode in {"strict", "affinity", "cache"}:
            return True
        if mode in {"loose", "prefer", "spill", "auto"}:
            return False
        return FRONTDOOR_STRICT_STICKY_BY_DEFAULT

    def sticky_key_for_request(
        self,
        body: bytes | None,
        payload: dict[str, Any] | None = None,
    ) -> tuple[str | None, str | None]:
        if not FRONTDOOR_STICKY_ROUTING:
            return None, None

        for name, value in self.headers.items():
            if name.lower() in FRONTDOOR_STICKY_HEADERS and value.strip():
                return f"header:{name.lower()}:{value.strip()}", f"header:{name.lower()}"

        if body is None or not FRONTDOOR_STICKY_JSON_FIELDS:
            return None, None
        if payload is None:
            payload = parse_json_body(self.headers, body)
        if payload is None:
            return None, None

        for field in FRONTDOOR_STICKY_JSON_FIELDS:
            value = extract_json_field(payload, field)
            if value:
                return f"json:{field}:{value}", f"json:{field}"
        return None, None

    def write_json(
        self,
        status: int,
        payload: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.add_cors_headers()
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
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
            "Authorization, Content-Type, OpenAI-Beta, X-Requested-With, "
            "X-Agent-Id, X-Session-Id, X-Conversation-Id, X-Sticky-Mode, "
            "X-Context-Tier, X-Prompt-Tokens, X-Estimated-Prompt-Tokens",
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
            "backend_capacities": BACKEND_CAPACITIES,
            "backend_context_tokens": BACKEND_CONTEXT_TOKENS,
            "short_context_limit_tokens": (
                FRONTDOOR_SHORT_CONTEXT_LIMIT_TOKENS or None
            ),
            "short_can_overflow_to_long": FRONTDOOR_SHORT_CAN_OVERFLOW_TO_LONG,
            "sticky_routing": FRONTDOOR_STICKY_ROUTING,
            "sticky_headers": FRONTDOOR_STICKY_HEADERS,
            "sticky_json_fields": FRONTDOOR_STICKY_JSON_FIELDS,
            "strict_sticky_by_default": FRONTDOOR_STRICT_STICKY_BY_DEFAULT,
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
