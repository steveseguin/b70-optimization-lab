"""Lean stand-in for the part of litellm the lab's context clients use (opt-in: LEAN_CLIENT=1, run-context-job.sh).

Operator tooling (2026-10-18; notes/2026-10-17-hostile-history-poison.md, campaign 37). Importing litellm costs about
190 MB of host memory in the Harbor client process; beside the two-card server the room above the memory guard's floor
is about 0.2 GiB, and the guard stopped the 2M hostile run. The clients use five names: `completion` (an `openai/<model>`
at an `api_base`), `exceptions`, `completion_cost`, `register_model` and `model_cost`. This module implements that one
path with the standard library and reproduces what litellm sends and returns on it:

- the request body: `messages` (each message with its top-level null fields dropped), `model` without the `openai/`
  prefix, then `max_tokens`, `temperature`, `tools`, then the `extra_body` keys, as compact UTF-8 JSON;
- the response: `choices[i].message.model_dump()` with litellm's keys and order (content, role, tool_calls,
  function_call, reasoning_content when there is thinking, provider_specific_fields with the server's extra message
  fields), and `usage` with attribute access (prompt_tokens_details.cached_tokens included);
- errors as litellm's exception classes (same names, so run records and the harness's retry rules stay the same).

`lean-client-check.sh` runs one job with each client against the recording fake server and requires every request body
and the saved trajectory to be identical. Anything outside the checked path raises NotImplementedError instead of
guessing.
"""
from __future__ import annotations

import http.client
import json
import socket
import time
import urllib.parse
from typing import Any

from . import exceptions

__all__ = ["completion", "completion_cost", "register_model", "model_cost", "exceptions"]
__lean__ = True

model_cost: dict[str, Any] = {}

# the request fields this stand-in has been checked on, in litellm's order on the wire
_PARAMS = ("max_tokens", "temperature", "tools", "tool_choice")
_IGNORED = ("api_base", "timeout", "request_timeout", "num_retries", "drop_params", "extra_body", "api_key")
# litellm 1.104's Message.model_fields (convert_dict_to_response._MESSAGE_FIELDS): a served message's other fields go to
# provider_specific_fields, in the order of the set `message.keys() - _MESSAGE_FIELDS` (so, like litellm's, it follows
# PYTHONHASHSEED; the order never reaches the model, the chat template does not read these fields)
_MESSAGE_FIELDS = frozenset({"annotations", "audio", "content", "function_call", "images", "provider_specific_fields",
                             "reasoning_content", "reasoning_items", "role", "thinking_blocks", "tool_calls"})


def register_model(model_cost_map: dict[str, Any]) -> dict[str, Any]:
    model_cost.update(model_cost_map)
    return model_cost


def completion_cost(completion_response: Any = None, model: str | None = None, **_: Any) -> float:
    # litellm raises for a model it has no price for (every served local model here); callers fall back to their table
    raise exceptions.NotFoundError(f"This model isn't mapped yet. model={model}", model=model, llm_provider="openai")


class _Obj:
    """Attribute and mapping access over a dict, like litellm's pydantic objects for the fields the clients read."""

    def __init__(self, data: dict[str, Any]):
        self.__dict__["_data"] = data

    def __getattr__(self, name: str) -> Any:
        try:
            v = self._data[name]
        except KeyError:
            raise AttributeError(name) from None
        return _wrap(v)

    def __getitem__(self, key: str) -> Any:
        return _wrap(self._data[key])

    def get(self, key: str, default: Any = None) -> Any:
        return _wrap(self._data.get(key, default))

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return json.loads(json.dumps(self._data))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._data!r})"


def _wrap(v: Any) -> Any:
    if isinstance(v, dict):
        return _Obj(v)
    if isinstance(v, list):
        return [_wrap(x) for x in v]
    return v


class Message(_Obj):
    pass


class Choices(_Obj):
    def __getattr__(self, name: str) -> Any:
        if name == "message":
            return self._data["message"]
        return super().__getattr__(name)


class ModelResponse(_Obj):
    def __getattr__(self, name: str) -> Any:
        if name == "choices":
            return self._data["choices"]
        return super().__getattr__(name)


# openai 2.x ChatCompletionMessage fields: litellm reads the reply through the OpenAI SDK, whose model_dump() writes these
# first (None when the server left one out, e.g. tool_calls) and the server's extra fields after them
_OPENAI_MESSAGE_FIELDS = ("content", "refusal", "role", "annotations", "audio", "function_call", "tool_calls")


def _litellm_message(served: dict[str, Any]) -> dict[str, Any]:
    """The served message as litellm's Message.model_dump() writes it."""
    m = {f: served.get(f) for f in _OPENAI_MESSAGE_FIELDS}
    m.update((k, v) for k, v in served.items() if k not in m)
    out: dict[str, Any] = {"content": m.get("content"), "role": m.get("role", "assistant")}
    tcs = m.get("tool_calls")
    out["tool_calls"] = ([{"function": {"arguments": tc["function"]["arguments"], "name": tc["function"]["name"]},
                           "id": tc.get("id"), "type": tc.get("type", "function")} for tc in tcs] if tcs else None)
    out["function_call"] = m.get("function_call")
    # litellm's _extract_reasoning_content: reasoning_content, else reasoning, else <think> parsing of the content
    if "reasoning_content" in m:
        reasoning = m["reasoning_content"]
    elif "reasoning" in m:
        reasoning = m["reasoning"]
    else:
        raise NotImplementedError("lean litellm: a reply without a reasoning field (vLLM always sends one)")
    if reasoning is not None:
        out["reasoning_content"] = reasoning
    if "thinking_blocks" in m:
        raise NotImplementedError("lean litellm: thinking_blocks")
    extra = dict(m.get("provider_specific_fields") or {})
    for f in m.keys() - _MESSAGE_FIELDS:
        extra[f] = m[f]
    if extra:
        out["provider_specific_fields"] = extra
    return out


def _response(r: dict[str, Any]) -> ModelResponse:
    data = dict(r)
    data["choices"] = [Choices(dict(ch, message=Message(_litellm_message(ch.get("message") or {}))))
                       for ch in r.get("choices") or []]
    return ModelResponse(data)


def _wire_message(m: Any) -> dict[str, Any]:
    if not isinstance(m, dict):
        raise NotImplementedError(f"lean litellm: a message of type {type(m).__name__}")
    return {k: v for k, v in m.items() if v is not None}


def _error(status: int, text: str, model: str) -> Exception:
    msg = f"OpenAIException - {text}"
    if status == 400:
        low = text.lower()
        if "context length" in low or "maximum context" in low or "too many tokens" in low:
            return exceptions.ContextWindowExceededError(msg, model=model, llm_provider="openai")
        return exceptions.BadRequestError(msg, model=model, llm_provider="openai")
    cls = {401: exceptions.AuthenticationError, 403: exceptions.PermissionDeniedError, 404: exceptions.NotFoundError,
           408: exceptions.Timeout, 422: exceptions.UnprocessableEntityError, 429: exceptions.RateLimitError,
           500: exceptions.InternalServerError, 502: exceptions.BadGatewayError,
           503: exceptions.ServiceUnavailableError}.get(status)
    if cls is None:
        err = exceptions.APIError(msg, model=model, llm_provider="openai")
        err.status_code = status
        return err
    return cls(msg, model=model, llm_provider="openai")


def _post(url: str, payload: bytes, timeout: float, model: str) -> dict[str, Any]:
    u = urllib.parse.urlsplit(url)
    conn_cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(u.hostname, u.port, timeout=timeout)
    try:
        conn.request("POST", u.path, body=payload, headers={"Content-Type": "application/json",
                                                             "Accept": "application/json",
                                                             "Authorization": "Bearer fake-api-key"})
        resp = conn.getresponse()
        text = resp.read().decode("utf-8", "replace")
        if resp.status >= 400:
            raise _error(resp.status, text, model)
        return json.loads(text)
    except (socket.timeout, TimeoutError) as exc:
        raise exceptions.Timeout(f"Request timed out. {exc}", model=model, llm_provider="openai") from None
    except (ConnectionError, OSError, http.client.HTTPException) as exc:
        if isinstance(exc, exceptions.APIError):
            raise
        # litellm reports the OpenAI SDK's connection error as an InternalServerError
        raise exceptions.InternalServerError(f"OpenAIException - Connection error. {type(exc).__name__}: {exc}",
                                             model=model, llm_provider="openai") from None
    finally:
        conn.close()


def completion(model: str | None = None, messages: list[dict[str, Any]] | None = None, **kw: Any) -> ModelResponse:
    if not model or not model.startswith("openai/"):
        raise NotImplementedError(f"lean litellm: only openai/<model> at an api_base (got {model!r})")
    unknown = [k for k in kw if k not in _PARAMS and k not in _IGNORED and k != "top_p"]
    if unknown or kw.get("top_p") is not None or kw.get("api_key"):
        raise NotImplementedError(f"lean litellm: unchecked arguments {unknown or ['top_p' if kw.get('top_p') is not None else 'api_key']}")
    api_base = kw.get("api_base")
    if not api_base:
        raise NotImplementedError("lean litellm: an api_base is required")
    body: dict[str, Any] = {"messages": [_wire_message(m) for m in messages or []], "model": model[len("openai/"):]}
    for k in _PARAMS:
        if kw.get(k) is not None:
            body[k] = kw[k]
    for k, v in (kw.get("extra_body") or {}).items():
        body[k] = v
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    timeout = float(kw.get("timeout") or kw.get("request_timeout") or 600.0)
    retries = int(kw.get("num_retries") or 0)
    url = api_base.rstrip("/") + "/chat/completions"
    for attempt in range(retries + 1):
        try:
            return _response(_post(url, payload, timeout, model))
        except (exceptions.Timeout, exceptions.RateLimitError,
                exceptions.InternalServerError, exceptions.ServiceUnavailableError, exceptions.BadGatewayError):
            if attempt == retries:
                raise
            time.sleep(min(8.0, 0.5 * 2 ** attempt))
    raise AssertionError("unreachable")
