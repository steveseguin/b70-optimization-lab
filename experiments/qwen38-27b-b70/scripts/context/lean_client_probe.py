#!/usr/bin/env python3
"""Call `litellm.completion` the way the context clients do and record what comes back (lean-client-check.sh).

Run once with the real litellm and once with `lean_litellm/` first on PYTHONPATH, each against a fresh
`fake_openai_server.py` (FAKE_VLLM_SHAPE=1 FAKE_DETERMINISTIC=1 FAKE_REASONING=alt FAKE_BODY_LOG=...). Writes a JSON
report: per call the message's model_dump(), the usage fields the harness reads, the response attributes it reads,
and per error status the exception class name and whether the harness's context-overflow test matches. The two
reports and the two body logs must be identical.

  lean_client_probe.py <api_base> <errors_base> <out.json>
"""
import json
import sys

import litellm

USAGE_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cache_read_input_tokens",
              "cache_creation_input_tokens", "cached_tokens")
SYSTEM = {"role": "system", "content": "You are a helpful assistant that can interact with a computer."}
TOOL = {"type": "function", "function": {"name": "bash", "description": "Run a command.", "parameters": {
    "type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}


def usage_view(resp):
    u = getattr(resp, "usage", None)
    out = {k: getattr(u, k, None) for k in USAGE_KEYS}
    d = getattr(u, "prompt_tokens_details", None)
    out["details.cached_tokens"] = getattr(d, "cached_tokens", None) if d is not None else None
    return out


def call(api_base, messages, **extra):
    kw = {"model": "openai/qwen38-27b-fp8", "messages": messages, "tools": [TOOL], "max_tokens": 8192,
          "api_base": api_base, "timeout": 30, "request_timeout": 30, "num_retries": 0, "drop_params": True,
          "temperature": 0.0, "extra_body": {"chat_template_kwargs": {"enable_thinking": True}}}
    kw.update(extra)
    return litellm.completion(**kw)


def main():
    api_base, err_base, out = sys.argv[1], sys.argv[2], sys.argv[3]
    report = {"calls": [], "errors": {}}
    messages = [SYSTEM, {"role": "user", "content": "Run `next` to read the stream. Unicode: — “quotes” é 中"}]
    for i in range(6):
        resp = call(api_base, messages)
        msg = resp.choices[0].message.model_dump()
        row = {"model_dump": json.loads(json.dumps(msg)), "usage": usage_view(resp), "finish_reason": resp.choices[0].finish_reason,
               "model": getattr(resp, "model", None), "id": getattr(resp, "id", None)}
        report["calls"].append(row)
        msg["content"] = msg.get("content") or ""
        tcs = msg.get("tool_calls")
        if tcs:
            msg["tool_calls"] = [tcs[0]]
            messages.append(msg)
            messages.append({"role": "tool", "tool_call_id": tcs[0].get("id"), "content": f"ITEM {i + 1}/6\nok"})
        else:
            msg.pop("tool_calls", None)
            messages.append(msg)
            messages.append({"role": "user", "content": "(No tool call in your last turn.)"})
    # a no-tools call (a summary-style request) and a temperature given as an int
    resp = litellm.completion(model="openai/qwen38-27b-fp8", messages=[SYSTEM, {"role": "user", "content": "x"}],
                              max_tokens=64, api_base=api_base, timeout=30, num_retries=0, drop_params=True,
                              temperature=0)
    report["calls"].append({"model_dump": resp.choices[0].message.model_dump(), "usage": usage_view(resp)})
    for status in (400, 401, 404, 429, 500, 502, 503):
        try:
            call(err_base + f"/status{status}", [SYSTEM, {"role": "user", "content": "x"}])
            report["errors"][str(status)] = "no error"
        except Exception as exc:  # noqa: BLE001
            report["errors"][str(status)] = {"class": type(exc).__name__,
                                             "is_bad_request": "BadRequestError" in [c.__name__ for c in type(exc).__mro__],
                                             "overflow": "maximum context length" in str(exc)}
    try:
        call("http://127.0.0.1:9/v1", [SYSTEM, {"role": "user", "content": "x"}])
    except Exception as exc:  # noqa: BLE001
        report["errors"]["refused"] = {"class": type(exc).__name__}
    report["lean"] = bool(getattr(litellm, "__lean__", False))
    json.dump(report, open(out, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
