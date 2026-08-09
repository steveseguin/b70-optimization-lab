#!/usr/bin/env python3
"""Capture exact sequential or synchronized c2 native completions."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import math
import socket
import threading
import time
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlparse


_FAILURE_OUTPUT: Path | None = None


def is_json_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def integer_equals(value: Any, expected: int) -> bool:
    return is_json_integer(value) and value == expected


def is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def is_token_id(value: Any) -> bool:
    return is_json_integer(value) and value >= 0


def is_token_id_list(value: Any, expected_length: int | None = None) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and (expected_length is None or len(value) == expected_length)
        and all(is_token_id(token) for token in value)
    )


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pair(suite: dict[str, Any], band: str) -> list[dict[str, Any]]:
    matches = [pair for pair in suite["pairs"] if pair.get("band") == band]
    if len(matches) != 1 or len(matches[0].get("cases", [])) != 2:
        raise SystemExit(f"suite must contain exactly one two-case pair for {band}")
    return list(matches[0]["cases"])


def capture_idle_slots(base_url: str, timeout: int) -> list[dict[str, Any]]:
    deadline = time.monotonic() + 5
    while True:
        with urllib.request.urlopen(f"{base_url}/slots", timeout=timeout) as response:
            value = json.load(response)
        if not isinstance(value, list):
            raise RuntimeError("/slots did not return a list")
        if (
            len(value) != 2
            or any(not isinstance(slot, dict) for slot in value)
            or any(not is_json_integer(slot.get("id")) for slot in value)
            or {slot["id"] for slot in value} != {0, 1}
            or any(not integer_equals(slot.get("n_ctx"), 32768) for slot in value)
        ):
            raise RuntimeError("/slots topology is not two 32768-token slots")
        if all(slot.get("is_processing") is False for slot in value):
            return value
        if time.monotonic() >= deadline:
            raise RuntimeError("/slots did not become idle within five seconds")
        time.sleep(0.1)


def capture_metrics(base_url: str, timeout: int) -> dict[str, float]:
    with urllib.request.urlopen(f"{base_url}/metrics", timeout=timeout) as response:
        text_value = response.read().decode("utf-8", errors="strict")
    wanted = {
        "tokens_predicted_total",
        "n_decode_total",
        "n_busy_slots_per_decode",
    }
    values: dict[str, float] = {}
    for line in text_value.splitlines():
        if line.startswith("#") or " " not in line:
            continue
        raw_name, raw_value = line.split(None, 1)
        name = raw_name.removeprefix("llamacpp:").split("{", 1)[0]
        if name in wanted:
            values[name] = float(raw_value.split()[0])
    if set(values) != wanted:
        raise RuntimeError(f"/metrics omitted required c2 counters: {sorted(wanted - set(values))}")
    return values


def stream_preconnected(
    base_url: str,
    payload: dict[str, Any],
    timeout: int,
    barrier: threading.Barrier,
    connections: list[http.client.HTTPConnection],
    connections_lock: threading.Lock,
) -> dict[str, Any]:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
        raise RuntimeError("c2 validation requires a loopback HTTP endpoint")
    connection = http.client.HTTPConnection(
        parsed.hostname, parsed.port or 80, timeout=timeout
    )
    with connections_lock:
        connections.append(connection)
    try:
        connection.connect()
        connected_perf_s = time.perf_counter()
        body = json.dumps({**payload, "stream": True}).encode("utf-8")
        barrier.wait(timeout=30)
        started = time.perf_counter()
        connection.request(
            "POST",
            "/completion",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"native completion returned HTTP {response.status}")

        token_ids: list[int] = []
        token_offsets_s: list[float] = []
        content_parts: list[str] = []
        final: dict[str, Any] | None = None
        while True:
            raw = response.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if not isinstance(event, dict):
                raise RuntimeError("non-object SSE event from native completion")
            tokens = event.get("tokens")
            if isinstance(tokens, list) and tokens:
                if not is_token_id_list(tokens):
                    raise RuntimeError("non-integer native completion token ID")
                now = time.perf_counter() - started
                token_ids.extend(tokens)
                token_offsets_s.extend([now] * len(tokens))
            content = event.get("content")
            if isinstance(content, str) and content:
                content_parts.append(content)
            if event.get("stop") is True:
                final = event
        ended = time.perf_counter()
        if final is None:
            raise RuntimeError("native completion stream did not return a final event")
        return {
            "token_ids": token_ids,
            "token_offsets_s": token_offsets_s,
            "content": "".join(content_parts),
            "final": final,
            "connected_perf_s": connected_perf_s,
            "request_started_perf_s": started,
            "request_ended_perf_s": ended,
            "elapsed_s": ended - started,
        }
    finally:
        with connections_lock:
            if connection in connections:
                connections.remove(connection)
        connection.close()


def prepare_cases(
    base_url: str,
    cases: list[dict[str, Any]],
    make_prompt: Any,
    common: ModuleType,
    timeout: int,
    max_tokens: int,
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for slot_id, case in enumerate(cases):
        prompt = make_prompt(case)
        rendered = common.post_json(
            f"{base_url}/apply-template",
            {"messages": [{"role": "user", "content": prompt}]},
            timeout,
        ).get("prompt")
        if not isinstance(rendered, str) or not rendered:
            raise RuntimeError(f"empty rendered prompt for {case['id']}")
        prepared.append(
            {
                "case": case,
                "slot_id": slot_id,
                "prompt": prompt,
                "rendered": rendered,
                "payload": {
                    "prompt": rendered,
                    "n_predict": max_tokens,
                    "temperature": 0,
                    "top_p": 1,
                    "seed": 1,
                    "cache_prompt": False,
                    "return_tokens": True,
                    "ignore_eos": True,
                    "id_slot": slot_id,
                },
            }
        )
    return prepared


def capture_streams(
    mode: str,
    base_url: str,
    prepared: list[dict[str, Any]],
    common: ModuleType,
    timeout: int,
) -> tuple[list[dict[str, Any]], float | None]:
    if mode == "sequential-oracle":
        return [
            common.stream_completion(
                f"{base_url}/completion", {**item["payload"], "stream": True}, timeout
            )
            for item in prepared
        ], None

    release_times: list[float] = []
    barrier = threading.Barrier(3, action=lambda: release_times.append(time.perf_counter()))
    results: list[dict[str, Any] | None] = [None, None]
    errors: list[BaseException] = []
    error_lock = threading.Lock()
    connections: list[http.client.HTTPConnection] = []
    connections_lock = threading.Lock()

    def abort_connections() -> None:
        with connections_lock:
            active = list(connections)
        for connection in active:
            try:
                if connection.sock is not None:
                    connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()

    def worker(index: int) -> None:
        try:
            results[index] = stream_preconnected(
                base_url,
                prepared[index]["payload"],
                timeout,
                barrier,
                connections,
                connections_lock,
            )
        except BaseException as exc:
            with error_lock:
                errors.append(exc)
            try:
                barrier.abort()
            except BaseException:
                pass
            abort_connections()

    threads = [
        threading.Thread(target=worker, args=(index,), daemon=True)
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    try:
        barrier.wait(timeout=30)
    except threading.BrokenBarrierError as exc:
        errors.append(exc)
        abort_connections()
    for thread in threads:
        thread.join(timeout=timeout + 30)
    if any(thread.is_alive() for thread in threads):
        abort_connections()
        for thread in threads:
            thread.join(timeout=10)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("one or more c2 clients did not terminate after socket abort")
    if errors:
        raise RuntimeError(f"c2 client failure: {errors!r}")
    if any(result is None for result in results):
        raise RuntimeError("one or more c2 clients returned no result")
    if len(release_times) != 1:
        raise RuntimeError("c2 barrier did not record exactly one release timestamp")
    return [result for result in results if result is not None], release_times[0]


def capture_canaries(
    base_url: str,
    prepared: list[dict[str, Any]],
    common: ModuleType,
    timeout: int,
) -> list[dict[str, Any]]:
    canaries: list[dict[str, Any]] = []
    for item in prepared:
        response = common.post_json(
            f"{base_url}/completion",
            {
                **item["payload"],
                "n_predict": 128,
                "stream": False,
            },
            timeout,
        )
        tokens = response.get("tokens")
        timings = response.get("timings")
        content = response.get("content")
        observed_slot_id = response.get("id_slot")
        passed = (
            is_token_id_list(tokens, 128)
            and isinstance(content, str)
            and integer_equals(observed_slot_id, item["slot_id"])
            and response.get("stop_type") == "limit"
            and response.get("truncated") is False
            and isinstance(timings, dict)
            and integer_equals(timings.get("cache_n"), 0)
            and integer_equals(timings.get("predicted_n"), 128)
        )
        canaries.append(
            {
                "case_id": item["case"]["id"],
                "slot_id": item["slot_id"],
                "observed_slot_id": observed_slot_id,
                "rendered_prompt_sha256": hashlib.sha256(
                    item["rendered"].encode()
                ).hexdigest(),
                "token_ids": tokens,
                "token_ids_sha256": hashlib.sha256(
                    json.dumps(tokens, separators=(",", ":")).encode()
                ).hexdigest()
                if is_token_id_list(tokens)
                else None,
                "content_sha256": hashlib.sha256(
                    content.encode()
                ).hexdigest()
                if isinstance(content, str)
                else None,
                "cache_n": timings.get("cache_n") if isinstance(timings, dict) else None,
                "predicted_n": (
                    timings.get("predicted_n") if isinstance(timings, dict) else None
                ),
                "stop_type": response.get("stop_type"),
                "truncated": response.get("truncated"),
                "timings": timings if isinstance(timings, dict) else None,
                "passed": passed,
            }
        )
    return canaries


def capture_semantic_retrieval(
    base_url: str,
    prepared: list[dict[str, Any]],
    forced_replays: list[dict[str, Any]],
    prompt_builder: ModuleType,
    common: ModuleType,
    timeout: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if len(prepared) != len(forced_replays):
        raise RuntimeError("semantic retrieval inputs do not match forced-512 rows")
    for item, forced_replay in zip(prepared, forced_replays):
        response = common.post_json(
            f"{base_url}/completion",
            {
                **item["payload"],
                "n_predict": 128,
                "stream": False,
                "ignore_eos": False,
            },
            timeout,
        )
        tokens = response.get("tokens")
        content = response.get("content")
        timings = response.get("timings")
        validation = (
            prompt_builder.validate(item["case"], content)
            if isinstance(content, str)
            else {
                "pass": False,
                "error": "native completion content is not a string",
            }
        )
        token_ids_valid = is_token_id_list(tokens) and len(tokens) <= 128
        forced_tokens = forced_replay.get("tokens")
        forced_content = forced_replay.get("content")
        forced_pre_eos_prefix_exact = (
            token_ids_valid
            and is_token_id_list(forced_tokens, 512)
            and len(tokens) >= 2
            and tokens[:-1] == forced_tokens[: len(tokens) - 1]
        )
        forced_content_prefix_exact = (
            isinstance(content, str)
            and isinstance(forced_content, str)
            and forced_content.startswith(content)
        )
        passed = (
            token_ids_valid
            and forced_pre_eos_prefix_exact
            and forced_content_prefix_exact
            and isinstance(content, str)
            and integer_equals(response.get("id_slot"), item["slot_id"])
            and response.get("stop_type") == "eos"
            and response.get("truncated") is False
            and isinstance(timings, dict)
            and integer_equals(timings.get("cache_n"), 0)
            and integer_equals(timings.get("predicted_n"), len(tokens))
            and integer_equals(
                timings.get("prompt_n"),
                int(item["case"]["calibrated_prompt_tokens"]),
            )
            and isinstance(validation, dict)
            and validation.get("pass") is True
        )
        rows.append(
            {
                "case_id": item["case"]["id"],
                "slot_id": item["slot_id"],
                "observed_slot_id": response.get("id_slot"),
                "prompt_sha256": hashlib.sha256(
                    item["prompt"].encode()
                ).hexdigest(),
                "rendered_prompt_sha256": hashlib.sha256(
                    item["rendered"].encode()
                ).hexdigest(),
                "token_ids": tokens if token_ids_valid else None,
                "token_count": len(tokens) if token_ids_valid else None,
                "token_ids_sha256": (
                    hashlib.sha256(
                        json.dumps(tokens, separators=(",", ":")).encode()
                    ).hexdigest()
                    if token_ids_valid
                    else None
                ),
                "forced_512_pre_eos_token_prefix_exact": (
                    forced_pre_eos_prefix_exact
                ),
                "forced_512_content_prefix_exact": forced_content_prefix_exact,
                "natural_terminal_token_id": (
                    tokens[-1] if token_ids_valid else None
                ),
                "forced_token_at_natural_stop_position": (
                    forced_tokens[len(tokens) - 1]
                    if token_ids_valid
                    and is_token_id_list(forced_tokens, 512)
                    else None
                ),
                "forced_512_token_ids_sha256": (
                    hashlib.sha256(
                        json.dumps(
                            forced_tokens, separators=(",", ":")
                        ).encode()
                    ).hexdigest()
                    if is_token_id_list(forced_tokens, 512)
                    else None
                ),
                "content": content if isinstance(content, str) else None,
                "content_sha256": (
                    hashlib.sha256(content.encode()).hexdigest()
                    if isinstance(content, str)
                    else None
                ),
                "cache_n": (
                    timings.get("cache_n") if isinstance(timings, dict) else None
                ),
                "predicted_n": (
                    timings.get("predicted_n")
                    if isinstance(timings, dict)
                    else None
                ),
                "prompt_n": (
                    timings.get("prompt_n") if isinstance(timings, dict) else None
                ),
                "stop_type": response.get("stop_type"),
                "truncated": response.get("truncated"),
                "validation": validation,
                "timings": timings if isinstance(timings, dict) else None,
                "passed": passed,
            }
        )
    return rows


def analyze_row(
    item: dict[str, Any],
    stream: dict[str, Any],
    replay: dict[str, Any],
    common: ModuleType,
) -> dict[str, Any]:
    tokens = replay.get("tokens")
    stream_tokens = stream.get("token_ids")
    if not is_token_id_list(tokens) or not is_token_id_list(stream_tokens):
        raise RuntimeError(f"missing replay token IDs for {item['case']['id']}")
    stream_positions = common.unique_subsequence_positions(tokens, stream_tokens)
    complete_offsets: list[float | None] = [None] * len(tokens)
    if stream_positions is not None and len(stream_positions) == len(
        stream["token_offsets_s"]
    ):
        for complete_i, offset in zip(stream_positions, stream["token_offsets_s"]):
            complete_offsets[complete_i] = offset
    primary = common.interval_metric(
        complete_offsets, 0, 99, "tok_s_1_100_intervals_after_ttft"
    )
    sustained = common.interval_metric(
        complete_offsets, 0, 511, "tok_s_1_512_intervals_after_ttft"
    )
    stream_final = stream["final"]
    stream_timings = stream_final.get("timings")
    replay_timings = replay.get("timings")
    ttft_s = complete_offsets[0] if complete_offsets else None
    start_perf_s = stream["request_started_perf_s"]
    t1_perf_s = start_perf_s + ttft_s if isinstance(ttft_s, (int, float)) else None
    t100_perf_s = (
        start_perf_s + complete_offsets[99]
        if len(complete_offsets) >= 100 and complete_offsets[99] is not None
        else None
    )
    t512_perf_s = (
        start_perf_s + complete_offsets[511]
        if len(complete_offsets) >= 512 and complete_offsets[511] is not None
        else None
    )
    ended_perf_s = stream["request_ended_perf_s"]
    request_elapsed_s = ended_perf_s - start_perf_s
    prompt_tokens = (
        stream_timings.get("prompt_n") if isinstance(stream_timings, dict) else None
    )
    prompt_ms = (
        stream_timings.get("prompt_ms") if isinstance(stream_timings, dict) else None
    )
    prompt_per_second = (
        stream_timings.get("prompt_per_second")
        if isinstance(stream_timings, dict)
        else None
    )
    expected_prompt_tokens = int(item["case"]["calibrated_prompt_tokens"])
    content = replay.get("content")
    passed = (
        len(tokens) == 512
        and integer_equals(replay.get("id_slot"), item["slot_id"])
        and integer_equals(stream_final.get("id_slot"), item["slot_id"])
        and replay.get("stop_type") == "limit"
        and stream_final.get("stop_type") == "limit"
        and replay.get("truncated") is False
        and stream_final.get("truncated") is False
        and isinstance(replay_timings, dict)
        and isinstance(stream_timings, dict)
        and integer_equals(replay_timings.get("cache_n"), 0)
        and integer_equals(stream_timings.get("cache_n"), 0)
        and integer_equals(replay_timings.get("predicted_n"), 512)
        and integer_equals(stream_timings.get("predicted_n"), 512)
        and integer_equals(replay_timings.get("prompt_n"), expected_prompt_tokens)
        and integer_equals(stream_timings.get("prompt_n"), expected_prompt_tokens)
        and stream_positions is not None
        and stream.get("content") == content
        and primary["interval_count"] == 99
        and sustained["interval_count"] == 511
        and isinstance(primary["tok_s"], (int, float))
        and primary["tok_s"] > 0
        and isinstance(sustained["tok_s"], (int, float))
        and sustained["tok_s"] > 0
    )
    return {
        "case_id": item["case"]["id"],
        "slot_id": item["slot_id"],
        "calibrated_prompt_tokens": expected_prompt_tokens,
        "prompt_tokens": prompt_tokens,
        "prompt_ms": prompt_ms,
        "native_prompt_tok_s": prompt_per_second,
        "service_prompt_tok_s_to_first_token": (
            prompt_tokens / ttft_s
            if is_json_integer(prompt_tokens)
            and isinstance(ttft_s, (int, float))
            and not isinstance(ttft_s, bool)
            and ttft_s > 0
            else None
        ),
        "prompt_sha256": hashlib.sha256(item["prompt"].encode()).hexdigest(),
        "rendered_prompt_sha256": hashlib.sha256(item["rendered"].encode()).hexdigest(),
        "token_ids": tokens,
        "token_count": len(tokens),
        "token_ids_sha256": hashlib.sha256(
            json.dumps(tokens, separators=(",", ":")).encode()
        ).hexdigest(),
        "content_sha256": hashlib.sha256(str(content).encode()).hexdigest(),
        "stream_token_ids": stream["token_ids"],
        "stream_alignment_unique": stream_positions is not None,
        "stream_to_complete_positions": stream_positions,
        "primary_metric": primary,
        "sustained_metric": sustained,
        "request_started_perf_s": start_perf_s,
        "request_ended_perf_s": ended_perf_s,
        "request_elapsed_s": request_elapsed_s,
        "ttft_s": ttft_s,
        "t1_perf_s": t1_perf_s,
        "t100_perf_s": t100_perf_s,
        "t512_perf_s": t512_perf_s,
        "full_512_after_ttft_wall_tok_s": (
            512 / (ended_perf_s - t1_perf_s)
            if isinstance(t1_perf_s, (int, float)) and ended_perf_s > t1_perf_s
            else None
        ),
        "full_512_request_wall_tok_s": (
            512 / request_elapsed_s if request_elapsed_s > 0 else None
        ),
        "stream_id_slot": stream_final.get("id_slot"),
        "replay_id_slot": replay.get("id_slot"),
        "stream_cache_n": stream_timings.get("cache_n"),
        "replay_cache_n": replay_timings.get("cache_n"),
        "stream_predicted_n": stream_timings.get("predicted_n"),
        "replay_predicted_n": replay_timings.get("predicted_n"),
        "stream_stop_type": stream_final.get("stop_type"),
        "replay_stop_type": replay.get("stop_type"),
        "stream_truncated": stream_final.get("truncated"),
        "replay_truncated": replay.get("truncated"),
        "stream_timings": stream_timings,
        "replay_timings": replay_timings,
        "passed": passed,
    }


def compare_oracle(
    identity: dict[str, Any],
    rows: list[dict[str, Any]],
    canaries: list[dict[str, Any]],
    semantic_retrieval: list[dict[str, Any]],
    oracle: dict[str, Any],
) -> dict[str, Any]:
    oracle_identity = oracle.get("run_identity") or {}
    oracle_intrinsic = oracle.get("intrinsic_gate") or {}
    oracle_comparison = oracle.get("oracle_comparison") or {}
    identity_keys = (
        "suite_sha256",
        "band",
        "model_sha256",
        "ctx_size_total",
        "ctx_size_per_slot",
        "parallel_slots",
        "cache_type_k",
        "cache_type_v",
        "max_tokens",
        "ignore_eos",
        "seed",
        "server_benchmark_identity",
    )
    identity_fields = {
        key: identity.get(key) == oracle_identity.get(key) for key in identity_keys
    }
    oracle_row_list = oracle.get("rows", [])
    oracle_canary_list = oracle.get("canaries", [])
    oracle_semantic_list = oracle.get("semantic_retrieval", [])
    expected_case_ids = {row["case_id"] for row in rows}
    oracle_case_ids = [
        row.get("case_id") for row in oracle_row_list if isinstance(row, dict)
    ]
    oracle_row_slot_ids = [
        row.get("slot_id") for row in oracle_row_list if isinstance(row, dict)
    ]
    oracle_slot_ids = [
        row.get("slot_id") for row in oracle_canary_list if isinstance(row, dict)
    ]
    expected_canary_case_ids = {row["case_id"] for row in canaries}
    oracle_canary_case_ids = [
        row.get("case_id") for row in oracle_canary_list if isinstance(row, dict)
    ]
    expected_semantic_case_ids = {row["case_id"] for row in semantic_retrieval}
    oracle_semantic_case_ids = [
        row.get("case_id")
        for row in oracle_semantic_list
        if isinstance(row, dict)
    ]
    oracle_valid = (
        oracle_identity.get("mode") == "sequential-oracle"
        and oracle_intrinsic.get("passed") is True
        and oracle_comparison.get("status") == "BASELINE_CAPTURE_READY"
        and len(oracle_row_list) == 2
        and len(oracle_case_ids) == 2
        and len(set(oracle_case_ids)) == 2
        and set(oracle_case_ids) == expected_case_ids
        and len(oracle_row_slot_ids) == 2
        and all(is_json_integer(slot_id) for slot_id in oracle_row_slot_ids)
        and len(set(oracle_row_slot_ids)) == 2
        and set(oracle_row_slot_ids) == {0, 1}
        and all(
            isinstance(row, dict)
            and row.get("passed") is True
            and is_json_integer(row.get("slot_id"))
            and is_token_id_list(row.get("token_ids"))
            for row in oracle_row_list
        )
        and len(oracle_canary_list) == 2
        and len(oracle_slot_ids) == 2
        and all(is_json_integer(slot_id) for slot_id in oracle_slot_ids)
        and len(set(oracle_slot_ids)) == 2
        and set(oracle_slot_ids) == {0, 1}
        and len(oracle_canary_case_ids) == 2
        and len(set(oracle_canary_case_ids)) == 2
        and set(oracle_canary_case_ids) == expected_canary_case_ids
        and all(
            isinstance(row, dict)
            and row.get("passed") is True
            and is_json_integer(row.get("slot_id"))
            and is_token_id_list(row.get("token_ids"))
            for row in oracle_canary_list
        )
        and len(oracle_semantic_list) == 2
        and len(oracle_semantic_case_ids) == 2
        and len(set(oracle_semantic_case_ids)) == 2
        and set(oracle_semantic_case_ids) == expected_semantic_case_ids
        and all(
            isinstance(row, dict)
            and row.get("passed") is True
            and is_json_integer(row.get("slot_id"))
            and is_token_id_list(row.get("token_ids"))
            and isinstance(row.get("content"), str)
            and row.get("forced_512_pre_eos_token_prefix_exact") is True
            and row.get("forced_512_content_prefix_exact") is True
            and (row.get("validation") or {}).get("pass") is True
            for row in oracle_semantic_list
        )
    )
    oracle_rows = {
        row["case_id"]: row
        for row in oracle_row_list
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    row_results = []
    for row in rows:
        expected = oracle_rows.get(row["case_id"])
        row_results.append(
            {
                "case_id": row["case_id"],
                "oracle_slot_id_same": bool(expected)
                and row["slot_id"] == expected.get("slot_id"),
                "prompt_exact": bool(expected)
                and row["prompt_sha256"] == expected.get("prompt_sha256")
                and row["rendered_prompt_sha256"]
                == expected.get("rendered_prompt_sha256"),
                "tokens_exact": bool(expected)
                and row["token_ids"] == expected.get("token_ids"),
                "content_exact": bool(expected)
                and row["content_sha256"] == expected.get("content_sha256"),
            }
        )
    oracle_canaries = {
        row["case_id"]: row
        for row in oracle_canary_list
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    canary_results = []
    for canary in canaries:
        expected = oracle_canaries.get(canary["case_id"])
        canary_results.append(
            {
                "slot_id": canary["slot_id"],
                "case_id_exact": bool(expected)
                and canary["case_id"] == expected.get("case_id"),
                "oracle_slot_id_same": bool(expected)
                and canary["slot_id"] == expected.get("slot_id"),
                "tokens_exact": bool(expected)
                and canary["token_ids"] == expected.get("token_ids"),
                "content_exact": bool(expected)
                and canary["content_sha256"] == expected.get("content_sha256"),
                "rendered_prompt_exact": bool(expected)
                and canary["rendered_prompt_sha256"]
                == expected.get("rendered_prompt_sha256"),
            }
        )
    oracle_semantic = {
        row["case_id"]: row
        for row in oracle_semantic_list
        if isinstance(row, dict) and isinstance(row.get("case_id"), str)
    }
    semantic_results = []
    for row in semantic_retrieval:
        expected = oracle_semantic.get(row["case_id"])
        semantic_results.append(
            {
                "case_id": row["case_id"],
                "prompt_exact": bool(expected)
                and row["prompt_sha256"] == expected.get("prompt_sha256")
                and row["rendered_prompt_sha256"]
                == expected.get("rendered_prompt_sha256"),
                "tokens_exact": bool(expected)
                and row["token_ids"] == expected.get("token_ids"),
                "content_exact": bool(expected)
                and row["content"] == expected.get("content"),
            }
        )
    passed = (
        oracle_valid
        and all(
            row.get("passed") is True
            and is_json_integer(row.get("slot_id"))
            and is_token_id_list(row.get("token_ids"))
            for row in rows
        )
        and all(
            row.get("passed") is True
            and is_json_integer(row.get("slot_id"))
            and integer_equals(row.get("observed_slot_id"), row["slot_id"])
            and integer_equals(row.get("cache_n"), 0)
            and integer_equals(row.get("predicted_n"), 128)
            and is_token_id_list(row.get("token_ids"), 128)
            for row in canaries
        )
        and len(semantic_retrieval) == 2
        and all(
            row.get("passed") is True
            and is_json_integer(row.get("slot_id"))
            and is_token_id_list(row.get("token_ids"))
            and isinstance(row.get("content"), str)
            and row.get("forced_512_pre_eos_token_prefix_exact") is True
            and row.get("forced_512_content_prefix_exact") is True
            and (row.get("validation") or {}).get("pass") is True
            for row in semantic_retrieval
        )
        and all(identity_fields.values())
        and len(row_results) == 2
        and all(
            row["prompt_exact"] and row["tokens_exact"] and row["content_exact"]
            for row in row_results
        )
        and len(canary_results) == 2
        and all(
            row["case_id_exact"]
            and row["tokens_exact"]
            and row["content_exact"]
            and row["rendered_prompt_exact"]
            for row in canary_results
        )
        and len(semantic_results) == 2
        and all(
            row["prompt_exact"] and row["tokens_exact"] and row["content_exact"]
            for row in semantic_results
        )
    )
    return {
        "passed": passed,
        "status": "PASS_ORACLE_EXACT" if passed else "FAIL_ORACLE_EXACT",
        "oracle_valid_sequential_baseline": oracle_valid,
        "identity_fields": identity_fields,
        "runtime_sha256_same": (
            identity.get("runtime_sha256") == oracle_identity.get("runtime_sha256")
        ),
        "rows": row_results,
        "canaries": canary_results,
        "semantic_retrieval": semantic_results,
    }


def main() -> int:
    global _FAILURE_OUTPUT
    _FAILURE_OUTPUT = None
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("sequential-oracle", "concurrent"), required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--band", choices=("short", "middle", "near32k"), required=True)
    parser.add_argument("--case-order", choices=("forward", "reverse"), default="forward")
    parser.add_argument("--prompt-builder", type=Path, required=True)
    parser.add_argument("--common-script", type=Path, required=True)
    parser.add_argument("--server-attestation", type=Path, required=True)
    parser.add_argument("--oracle-json", type=Path)
    parser.add_argument("--baseline-canary-suite", type=Path, required=True)
    parser.add_argument("--baseline-canary-oracle", type=Path, required=True)
    parser.add_argument("--baseline-canary-oracle-sha256", required=True)
    parser.add_argument("--baseline-canary-prompt-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--runtime-sha256", required=True)
    parser.add_argument("--cache-type-k", default="f16")
    parser.add_argument("--cache-type-v", default="f16")
    parser.add_argument("--ctx-size-total", type=int, default=65536)
    parser.add_argument("--ctx-size-per-slot", type=int, default=32768)
    args = parser.parse_args()

    protected_inputs = [
        args.suite,
        args.prompt_builder,
        args.common_script,
        args.server_attestation,
        args.baseline_canary_suite,
        args.baseline_canary_oracle,
    ]
    if args.oracle_json is not None:
        protected_inputs.append(args.oracle_json)
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.out}")
    out_resolved = args.out.resolve()
    if any(out_resolved == path.resolve() for path in protected_inputs):
        raise SystemExit("output path must not overwrite an input or oracle")
    for path in protected_inputs:
        if not path.is_file():
            raise SystemExit(f"required input is not a file: {path}")
    _FAILURE_OUTPUT = args.out
    parsed_base = urlparse(args.base_url)
    if (
        parsed_base.scheme != "http"
        or parsed_base.hostname not in ("127.0.0.1", "localhost")
        or parsed_base.port is None
        or parsed_base.path not in ("", "/")
        or parsed_base.query
        or parsed_base.fragment
    ):
        raise SystemExit("--base-url must be a loopback HTTP origin with an explicit port")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    for label, value in (
        ("model", args.model_sha256),
        ("runtime", args.runtime_sha256),
        ("baseline-canary-oracle", args.baseline_canary_oracle_sha256),
    ):
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise SystemExit(f"--{label}-sha256 must be a lowercase SHA-256 digest")
    if (
        hashlib.sha256(args.baseline_canary_oracle.read_bytes()).hexdigest()
        != args.baseline_canary_oracle_sha256
    ):
        raise SystemExit("baseline canary oracle SHA-256 mismatch")

    if args.mode == "concurrent" and args.oracle_json is None:
        raise SystemExit("concurrent mode requires --oracle-json")
    if args.mode == "sequential-oracle" and args.oracle_json is not None:
        raise SystemExit("sequential-oracle mode does not accept --oracle-json")
    if (args.cache_type_k, args.cache_type_v) != ("f16", "f16"):
        raise SystemExit("the sealed c2 Goal-1 lane requires F16 K and V")
    if args.ctx_size_total != 65536 or args.ctx_size_per_slot != 32768:
        raise SystemExit("the sealed c2 Goal-1 lane requires 65536 total / 32768 per slot")

    attestation = json.loads(args.server_attestation.read_text())
    if (
        not isinstance(attestation, dict)
        or attestation.get("passed") is not True
        or not all((attestation.get("identity_fields") or {}).values())
        or not all((attestation.get("argv_fields") or {}).values())
        or not all((attestation.get("runtime_fields") or {}).values())
        or not isinstance(attestation.get("expected_identity"), dict)
    ):
        raise SystemExit("server attestation is absent, incomplete, or failed")
    server_attestation_sha256 = hashlib.sha256(
        args.server_attestation.read_bytes()
    ).hexdigest()

    common = load_module(args.common_script, "capture_exact_common")
    prompt_builder = load_module(args.prompt_builder, "long_context_builder")
    baseline_canary_oracle = json.loads(args.baseline_canary_oracle.read_text())
    baseline_canary_prepared = common.prepare_post_512_canary(
        args.baseline_canary_suite,
        baseline_canary_oracle,
        args.baseline_canary_prompt_id,
        args.model_sha256,
        1,
    )
    suite = json.loads(args.suite.read_text())
    cases = load_pair(suite, args.band)
    canary_cases = load_pair(suite, "short")
    if args.case_order == "reverse":
        cases.reverse()
        canary_cases.reverse()
    base_url = args.base_url.rstrip("/")
    prepared = prepare_cases(
        base_url, cases, prompt_builder.make_prompt, common, args.timeout, 512
    )
    prepared_canaries = prepare_cases(
        base_url, canary_cases, prompt_builder.make_prompt, common, args.timeout, 128
    )

    slots_before = capture_idle_slots(base_url, args.timeout)
    metrics_before = capture_metrics(base_url, args.timeout)
    streams, barrier_release_perf_s = capture_streams(
        args.mode, base_url, prepared, common, args.timeout
    )
    metrics_after_streams = capture_metrics(base_url, args.timeout)
    canaries = capture_canaries(base_url, prepared_canaries, common, args.timeout)
    replays = [
        common.post_json(
            f"{base_url}/completion",
            {**item["payload"], "stream": False},
            args.timeout,
        )
        for item in prepared
    ]
    rows = [
        analyze_row(item, stream, replay, common)
        for item, stream, replay in zip(prepared, streams, replays)
    ]
    semantic_retrieval = capture_semantic_retrieval(
        base_url, prepared, replays, prompt_builder, common, args.timeout
    )
    baseline_canaries: list[dict[str, Any]] = []
    for slot_id in (0, 1):
        baseline_canary = common.capture_post_512_canary(
            base_url, args.timeout, 1, baseline_canary_prepared, slot_id
        )
        baseline_canary.update(
            {
                "suite_path": str(args.baseline_canary_suite),
                "suite_sha256": baseline_canary_prepared["suite_sha256"],
                "oracle_path": str(args.baseline_canary_oracle),
                "oracle_sha256": args.baseline_canary_oracle_sha256,
                "execution_order": (
                    "after_timed streams, deterministic main replays, and "
                    "selected-band semantic retrieval"
                ),
            }
        )
        baseline_canaries.append(baseline_canary)
    slots_after = capture_idle_slots(base_url, args.timeout)

    suite_sha256 = hashlib.sha256(args.suite.read_bytes()).hexdigest()
    identity = {
        "mode": args.mode,
        "base_url": base_url,
        "suite_path": str(args.suite),
        "suite_sha256": suite_sha256,
        "band": args.band,
        "case_order": args.case_order,
        "model_sha256": args.model_sha256,
        "runtime_sha256": args.runtime_sha256,
        "ctx_size_total": args.ctx_size_total,
        "ctx_size_per_slot": args.ctx_size_per_slot,
        "parallel_slots": 2,
        "cache_type_k": args.cache_type_k,
        "cache_type_v": args.cache_type_v,
        "max_tokens": 512,
        "ignore_eos": True,
        "seed": 1,
        "cache_prompt": False,
        "slot_ids": [0, 1],
        "server_attestation_path": str(args.server_attestation),
        "server_attestation_sha256": server_attestation_sha256,
        "server_benchmark_identity": attestation["expected_identity"],
        "baseline_canary_suite_path": str(args.baseline_canary_suite),
        "baseline_canary_suite_sha256": baseline_canary_prepared["suite_sha256"],
        "baseline_canary_oracle_path": str(args.baseline_canary_oracle),
        "baseline_canary_oracle_sha256": args.baseline_canary_oracle_sha256,
        "baseline_canary_prompt_id": args.baseline_canary_prompt_id,
        "baseline_canary_slot_ids": [0, 1],
    }

    aggregate: dict[str, Any] | None = None
    overlap_passed = True
    timing_endpoints_present = True
    predicted_delta = (
        metrics_after_streams["tokens_predicted_total"]
        - metrics_before["tokens_predicted_total"]
    )
    decode_delta = (
        metrics_after_streams["n_decode_total"] - metrics_before["n_decode_total"]
    )
    predicted_per_decode = predicted_delta / decode_delta if decode_delta > 0 else None
    decode_occupancy = {
        "metrics_before": metrics_before,
        "metrics_after_streaming_rows": metrics_after_streams,
        "tokens_predicted_delta": predicted_delta,
        "llama_decode_calls_delta": decode_delta,
        "predicted_tokens_per_llama_decode": predicted_per_decode,
        "concurrent_minimum": 1.5,
        "note": "Prompt evaluation adds decode calls but no predicted tokens; a ratio above one therefore proves generation batching across occupied slots.",
        "passed": predicted_delta == 1024 and decode_delta > 0,
    }
    if args.mode == "concurrent":
        starts = [row["request_started_perf_s"] for row in rows]
        ends = [row["request_ended_perf_s"] for row in rows]
        t1s = [row["t1_perf_s"] for row in rows]
        t100s = [row["t100_perf_s"] for row in rows]
        t512s = [row["t512_perf_s"] for row in rows]
        send_skew_s = max(starts) - min(starts)
        timing_endpoints_present = all(
            is_finite_number(value) for value in t1s + t100s + t512s
        )
        missing_timing_endpoints = [
            {
                "case_id": row["case_id"],
                "slot_id": row["slot_id"],
                "missing": [
                    name
                    for name in ("t1_perf_s", "t100_perf_s", "t512_perf_s")
                    if not is_finite_number(row.get(name))
                ],
            }
            for row in rows
            if any(
                not is_finite_number(row.get(name))
                for name in ("t1_perf_s", "t100_perf_s", "t512_perf_s")
            )
        ]
        if timing_endpoints_present:
            broad_decode_overlap = max(t100s) < min(t512s)
            both_decode_overlap_s = min(t512s) - max(t1s)
            conventional_window_s = max(t512s) - min(t1s)
            wall_s = max(ends) - barrier_release_perf_s  # type: ignore[operator]
            pp_wall_s = max(t1s) - barrier_release_perf_s  # type: ignore[operator]
            sustained_rates = [row["sustained_metric"]["tok_s"] for row in rows]
            aggregate = {
                "barrier_release_perf_s": barrier_release_perf_s,
                "send_skew_s": send_skew_s,
                "send_skew_limit_s": 0.025,
                "timing_endpoints_present": True,
                "missing_timing_endpoints": [],
                "broad_decode_overlap": broad_decode_overlap,
                "both_decode_overlap_s": both_decode_overlap_s,
                "conventional_decode_window_s": conventional_window_s,
                "aggregate_tok_s_1_512_intervals": 1022 / conventional_window_s,
                "request_wall_s": wall_s,
                "aggregate_full_512_wall_tok_s": 1024 / wall_s,
                "aggregate_pp_wall_s": pp_wall_s,
                "aggregate_prompt_tok_s_wall": sum(
                    row["prompt_tokens"] for row in rows
                )
                / pp_wall_s,
                "fairness_min_over_max": min(sustained_rates) / max(sustained_rates),
            }
            overlap_passed = send_skew_s <= 0.025 and broad_decode_overlap
        else:
            aggregate = {
                "barrier_release_perf_s": barrier_release_perf_s,
                "send_skew_s": send_skew_s,
                "send_skew_limit_s": 0.025,
                "timing_endpoints_present": False,
                "missing_timing_endpoints": missing_timing_endpoints,
                "broad_decode_overlap": None,
                "both_decode_overlap_s": None,
                "conventional_decode_window_s": None,
                "aggregate_tok_s_1_512_intervals": None,
                "request_wall_s": None,
                "aggregate_full_512_wall_tok_s": None,
                "aggregate_pp_wall_s": None,
                "aggregate_prompt_tok_s_wall": None,
                "fairness_min_over_max": None,
            }
            overlap_passed = False
        decode_occupancy["passed"] = (
            predicted_delta == 1024
            and is_finite_number(predicted_per_decode)
            and predicted_per_decode >= 1.5
        )
        overlap_passed = overlap_passed and bool(decode_occupancy["passed"])

    intrinsic_passed = (
        len(rows) == 2
        and all(row["passed"] for row in rows)
        and len(canaries) == 2
        and all(canary["passed"] for canary in canaries)
        and len(semantic_retrieval) == 2
        and all(row["passed"] for row in semantic_retrieval)
        and len(baseline_canaries) == 2
        and all(canary.get("passed") is True for canary in baseline_canaries)
        and overlap_passed
        and decode_occupancy["passed"] is True
    )
    comparison: dict[str, Any]
    if args.oracle_json is None:
        comparison = {
            "status": "BASELINE_CAPTURE_READY" if intrinsic_passed else "FAIL_BASELINE_CAPTURE",
            "passed": None,
        }
        passed = intrinsic_passed
    else:
        oracle = json.loads(args.oracle_json.read_text())
        comparison = compare_oracle(
            identity, rows, canaries, semantic_retrieval, oracle
        )
        comparison["oracle_json"] = str(args.oracle_json)
        comparison["oracle_sha256"] = hashlib.sha256(
            args.oracle_json.read_bytes()
        ).hexdigest()
        passed = intrinsic_passed and comparison["passed"]

    result = {
        "run_identity": identity,
        "intrinsic_gate": {
            "passed": intrinsic_passed,
            "rows_passed": all(row["passed"] for row in rows),
            "canaries_passed": all(canary["passed"] for canary in canaries),
            "semantic_retrieval_passed": (
                len(semantic_retrieval) == 2
                and all(row["passed"] for row in semantic_retrieval)
            ),
            "external_baseline_canary_passed": (
                len(baseline_canaries) == 2
                and all(
                    canary.get("passed") is True for canary in baseline_canaries
                )
            ),
            "timing_endpoints_present": timing_endpoints_present,
            "overlap_passed": overlap_passed,
        },
        "oracle_comparison": comparison,
        "aggregate": aggregate,
        "decode_occupancy": decode_occupancy,
        "slot_topology": {
            "before": slots_before,
            "after": slots_after,
            "passed": True,
            "official_timing_polled_slots": False,
        },
        "rows": rows,
        "canaries": canaries,
        "semantic_retrieval": semantic_retrieval,
        "external_baseline_canaries": baseline_canaries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(args.out), "passed": passed}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as exc:
        if _FAILURE_OUTPUT is not None and not _FAILURE_OUTPUT.exists():
            try:
                _FAILURE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
                _FAILURE_OUTPUT.write_text(
                    json.dumps(
                        {
                            "passed": False,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                )
            except OSError:
                pass
        raise
