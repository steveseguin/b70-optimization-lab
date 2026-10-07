#!/usr/bin/env python3
"""Six sequential practical checks against an already running server; never retry.

This is limited task acceptance and same-process repeat evidence. It is not a
quality benchmark, performance promotion gate, long-context test, or soak.
The conversation fixture supplies a fixed prior exchange, not another API call.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


SYSTEM = "Follow the user's instructions. Return only the requested JSON object, without Markdown fences or commentary."
TASKS = [
    {"id": "conversation", "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Plan our picnic for Saturday at shelter B. There will be four guests, and all food must be vegetarian."},
        {"role": "assistant", "content": "The picnic is planned for Saturday at shelter B, with four guests and vegetarian food."},
        {"role": "user", "content": "Change the guest count to six. Keep everything else the same. Return JSON with exactly these keys: day (string), shelter (string containing only its letter), guests (integer), vegetarian (boolean)."},
    ]},
    {"id": "code", "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "A Python function is meant to sum the integers from 1 through n inclusive, for positive integer n. Its return expression is sum(range(1, n)). Identify the off-by-one bug and fix only that expression. Return JSON with exactly these keys: bug (use the string off_by_one), fixed_expression (the corrected Python expression, keeping sum and range), result_for_n_5 (integer). Do not run code."},
    ]},
    {"id": "document", "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Extract the final approved information from this brief.\nProject: Cedar. Owner: Maya Chen. Original delivery: 2026-10-04. Revision approved on 2026-09-12: delivery moves to 2026-10-07; owner unchanged. Approved budget: USD 4800. A suggested increase to USD 5200 was rejected. Open risks: supplier delay; rain.\nReturn JSON with exactly these keys: project (string), owner (string), delivery (YYYY-MM-DD string), budget_usd (integer), risks (array of strings). Use the approved revision, not the original delivery or rejected budget."},
    ]},
]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def payload_for(task, model):
    return {"model": model, "messages": task["messages"], "temperature": 0,
            "top_p": 1, "seed": 42, "max_tokens": 256, "n": 1,
            "stream": True, "stream_options": {"include_usage": True},
            "return_token_ids": True,
            "chat_template_kwargs": {"enable_thinking": False}}


def strict_object(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    result = json.loads(text, object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise ValueError("answer must be a JSON object")
    return result


def check_task(task_id, text):
    obj = strict_object(text)
    if task_id == "conversation":
        expected = {"day": "Saturday", "shelter": "B", "guests": 6, "vegetarian": True}
        passed = (obj == expected and type(obj.get("guests")) is int
                  and type(obj.get("vegetarian")) is bool)
    elif task_id == "code":
        # Parse syntax only. Never compile or execute model-supplied code.
        expression = obj.get("fixed_expression")
        try:
            actual = ast.dump(ast.parse(expression.strip(), mode="eval")) if isinstance(expression, str) else None
        except (SyntaxError, ValueError):
            actual = None
        expected = ast.dump(ast.parse("sum(range(1, n + 1))", mode="eval"))
        passed = (set(obj) == {"bug", "fixed_expression", "result_for_n_5"}
                  and obj.get("bug") == "off_by_one" and actual == expected
                  and type(obj.get("result_for_n_5")) is int and obj["result_for_n_5"] == 15)
    elif task_id == "document":
        expected = {"project": "Cedar", "owner": "Maya Chen", "delivery": "2026-10-07", "budget_usd": 4800}
        risks = obj.get("risks")
        passed = (set(obj) == set(expected) | {"risks"}
                  and all(obj.get(k) == v for k, v in expected.items())
                  and type(obj.get("budget_usd")) is int
                  and isinstance(risks, list) and len(risks) == 2
                  and all(isinstance(r, str) for r in risks)
                  and sorted(risks) == ["rain", "supplier delay"])
    else:
        raise ValueError("unknown task: " + task_id)
    if not passed:
        raise ValueError("objective check failed for " + task_id)
    return {"passed": True, "parsed_answer": obj}


def consume_stream(lines, raw_file, started, clock=time.perf_counter):
    """Parse SSE frames and preserve every received byte even when parsing fails."""
    text_parts, reasoning_parts, token_ids, token_offsets, text_offsets = [], [], [], [], []
    usage, finish_reasons, frames = {}, [], []
    done = False
    response_ids = []

    def consume_frame():
        nonlocal usage, done
        if not frames:
            return
        data = "\n".join(frames)
        frames.clear()
        if data == "[DONE]":
            done = True
            return
        event = json.loads(data)
        if not isinstance(event, dict):
            raise ValueError("SSE event is not an object")
        if event.get("error"):
            raise ValueError("server error: " + json.dumps(event["error"]))
        if event.get("id") and event["id"] not in response_ids:
            response_ids.append(event["id"])
        if event.get("usage") is not None:
            usage = event["usage"]
        choices = event.get("choices", [])
        if not isinstance(choices, list) or len(choices) > 1:
            raise ValueError("expected at most one streamed choice")
        for choice in choices:
            if choice.get("index", 0) != 0:
                raise ValueError("unexpected choice index")
            offset = clock() - started
            if choice.get("finish_reason") is not None:
                finish_reasons.append(choice["finish_reason"])
            ids = choice.get("token_ids")
            if ids is not None:
                if not isinstance(ids, list) or any(type(i) is not int or i < 0 for i in ids):
                    raise ValueError("invalid stream token IDs")
                token_ids.extend(ids)
                token_offsets.extend([offset] * len(ids))
            delta = choice.get("delta") or {}
            content = delta.get("content")
            if content:
                if not isinstance(content, str):
                    raise ValueError("non-text content")
                text_parts.append(content)
                text_offsets.append(offset)
            reasoning = delta.get("reasoning") or delta.get("reasoning_content")
            if reasoning:
                reasoning_parts.append(reasoning)

    for raw in lines:
        raw_file.write(raw)
        raw_file.flush()
        if clock() - started > 120:
            raise TimeoutError("request exceeded 120-second total stream limit")
        line = raw.decode("utf-8").rstrip("\r\n")
        if line == "":
            consume_frame()
            if done:
                break
        elif line.startswith("data:"):
            frames.append(line[5:].removeprefix(" "))
        elif line.startswith(":") or line.startswith(("event:", "id:", "retry:")):
            continue
        else:
            raise ValueError("unexpected non-SSE response line")
    if frames:
        consume_frame()
    if not done:
        raise ValueError("truncated stream: missing [DONE]")
    if finish_reasons != ["stop"]:
        raise ValueError("expected natural stop, received " + repr(finish_reasons))
    if reasoning_parts:
        raise ValueError("unexpected reasoning content with thinking disabled")
    if not isinstance(usage, dict):
        raise ValueError("missing usage object")
    prompt_count, output_count = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if type(prompt_count) is not int or prompt_count < 1 or type(output_count) is not int or output_count < 1:
        raise ValueError("missing or invalid prompt/output token counts")
    details = usage.get("prompt_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, dict) else None
    if type(cached) is not int or cached != 0:
        raise ValueError("cached_tokens must be explicitly zero")
    if token_ids and len(token_ids) != output_count:
        raise ValueError("stream token IDs do not cover reported output tokens")
    if not text_parts:
        raise ValueError("empty answer")
    offsets = token_offsets if token_ids else text_offsets
    duration = offsets[-1] - offsets[0]
    rate = (len(token_offsets) - 1) / duration if token_ids and duration > 0 else None
    text = "".join(text_parts)
    return {"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "token_ids": token_ids, "token_ids_available": bool(token_ids),
            "token_offsets_s": token_offsets, "content_chunk_offsets_s": text_offsets,
            "usage": usage, "prompt_tokens": prompt_count, "completion_tokens": output_count,
            "cached_tokens": cached, "finish_reasons": finish_reasons,
            "response_ids": response_ids, "elapsed_s": clock() - started,
            "http_ttft_s": offsets[0],
            "http_ttft_definition": "request start to first received token-ID chunk, or first content chunk if IDs unavailable",
            "decode_stream_proxy_tokens_s": rate,
            "decode_stream_proxy_definition": "(stream token IDs - 1) / (last minus first token-ID chunk arrival); network chunks can contain multiple tokens; not server decode timing",
            "server_prefill_duration_s": None,
            "server_prefill_note": "not exposed by this chat stream; HTTP TTFT is not server prefill"}


def request_one(base_url, payload, directory, opener=urllib.request.urlopen):
    write_json(directory / "request.json", payload)
    base = base_url.rstrip("/")
    url = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with (directory / "response.sse").open("wb") as raw:
        started = time.perf_counter()
        try:
            with opener(req, timeout=120) as response:
                write_json(directory / "response-headers.json", dict(response.headers))
                return consume_stream(response, raw, started)
        except urllib.error.HTTPError as exc:
            raw.write(exc.read())
            raise


def run_session(base_url, model, out_dir, requester=request_one):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    summary = {"schema": "neural.download.fp8-practical-session.v1", "passed": False,
               "base_url": base_url, "model": model, "requests_planned": 6,
               "concurrent_users": 1, "same_persistent_server_required": True,
               "scope": "three fixed tasks repeated twice in one process; supplied multi-turn history; limited practical acceptance only",
               "not_established": ["broad model quality", "long-context retrieval", "multi-hour stability", "fresh-server determinism", "performance promotion"],
               "started_epoch_s": time.time(), "rows": [], "errors": []}
    write_json(out_dir / "summary.json", summary)
    references = {}
    for repeat in (1, 2):
        for task in TASKS:
            name = f"{repeat}-{task['id']}"
            directory = out_dir / name
            directory.mkdir()
            row = {"task": task["id"], "repeat": repeat, "directory": name, "passed": False}
            try:
                row.update(requester(base_url, payload_for(task, model), directory))
                row["objective_check"] = check_task(task["id"], row["text"])
                if repeat == 1:
                    references[task["id"]] = row
                else:
                    reference = references[task["id"]]
                    row["repeat_identity"] = {
                        "text_exact": reference["text"] == row["text"],
                        "token_ids_available_both": reference["token_ids_available"] and row["token_ids_available"],
                        "token_ids_exact": reference["token_ids"] == row["token_ids"] if row["token_ids_available"] and reference["token_ids_available"] else None,
                    }
                    if (not row["repeat_identity"]["text_exact"]
                            or reference["token_ids_available"] != row["token_ids_available"]
                            or row["repeat_identity"]["token_ids_exact"] is False):
                        raise ValueError("same-process repeat identity failed")
                row["passed"] = True
            except Exception as exc:
                row["error"] = type(exc).__name__ + ": " + str(exc)
                summary["errors"].append({"request": name, "error": row["error"]})
            write_json(directory / "result.json", row)
            summary["rows"].append(row)
            summary["requests_attempted"] = len(summary["rows"])
            summary["ended_epoch_s"] = time.time()
            write_json(out_dir / "summary.json", summary)
            print(json.dumps({"request": name, "passed": row["passed"], "error": row.get("error")}), flush=True)
            if not row["passed"]:
                return summary
    summary["passed"] = True
    summary["all_stream_token_ids_available"] = all(row["token_ids_available"] for row in summary["rows"])
    write_json(out_dir / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    result = run_session(args.base_url, args.model, args.out_dir)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
