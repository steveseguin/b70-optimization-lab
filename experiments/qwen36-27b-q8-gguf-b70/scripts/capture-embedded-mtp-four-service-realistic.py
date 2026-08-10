#!/usr/bin/env python3
"""Capture the fixed realistic suite once across four synchronized services.

This helper deliberately reuses the sealed once-only OpenAI stream parser.  It
contains no retry path: prompt ``wave * 4 + service`` is sent to that service
once, in each of three four-request waves.  A durable JSONL intent/completion
journal survives a partial failure so the outer lifecycle runner can retain an
honest request-attempt ledger.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any


CORE_PATH = Path(__file__).with_name("capture-openai-completions-once.py")
CORE_SPEC = importlib.util.spec_from_file_location("qwen36_once_capture", CORE_PATH)
if CORE_SPEC is None or CORE_SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"cannot load once-only capture helper: {CORE_PATH}")
core = importlib.util.module_from_spec(CORE_SPEC)
CORE_SPEC.loader.exec_module(core)

SCHEMA = "qwen36-embedded-mtp-four-service-realistic-capture-v1"
CONFIG_SCHEMA = "qwen36-embedded-mtp-four-service-config-v1"
PROMPT_COUNT = 12
SERVICE_COUNT = 4
WAVE_COUNT = 3


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def load_config(path: Path) -> list[dict[str, Any]]:
    value = read_object(path)
    services = value.get("services")
    if value.get("schema") != CONFIG_SCHEMA or not isinstance(services, list):
        raise ValueError("four-service config schema mismatch")
    if len(services) != SERVICE_COUNT:
        raise ValueError("four-service config must contain exactly four services")
    result: list[dict[str, Any]] = []
    for expected, item in enumerate(services):
        if not isinstance(item, dict):
            raise ValueError("service config entry is not an object")
        service = item.get("service_index")
        gpu = item.get("gpu_index")
        base_url = item.get("base_url")
        model = item.get("model")
        if (
            service != expected
            or gpu != expected
            or not isinstance(base_url, str)
            or core.validate_base_url(base_url) != base_url.rstrip("/")
            or not isinstance(model, str)
            or model != f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{expected}"
        ):
            raise ValueError(f"service {expected} identity mismatch")
        result.append(
            {
                "service_index": service,
                "gpu_index": gpu,
                "base_url": base_url.rstrip("/"),
                "model": model,
            }
        )
    if len({item["base_url"] for item in result}) != SERVICE_COUNT:
        raise ValueError("service base URLs must be distinct")
    return result


def prepare(args: argparse.Namespace) -> int:
    services = load_config(args.config)
    suite_meta, prompts = core.load_suite(args.suite)
    if len(prompts) != PROMPT_COUNT:
        raise ValueError("fixed realistic suite must contain exactly 12 prompts")

    def render(index: int) -> dict[str, Any]:
        service_index = index % SERVICE_COUNT
        service = services[service_index]
        item = prompts[index]
        rendered = core.post_json(
            f"{service['base_url']}/apply-template",
            {"messages": [{"role": "user", "content": item["prompt"]}]},
            args.timeout,
        ).get("prompt")
        if not isinstance(rendered, str) or not rendered:
            raise ValueError(f"empty rendered prompt for {item['id']}")
        return {
            "prompt_index": index,
            "prompt_id": item["id"],
            "prompt_sha256": core.sha256_bytes(item["prompt"].encode()),
            "rendered_prompt": rendered,
            "rendered_prompt_sha256": core.sha256_bytes(rendered.encode()),
            "wave_index": index // SERVICE_COUNT,
            "service_index": service_index,
            "gpu_index": service["gpu_index"],
            "base_url": service["base_url"],
            "model": service["model"],
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=SERVICE_COUNT) as pool:
        rows = list(pool.map(render, range(PROMPT_COUNT)))
    rows.sort(key=lambda row: row["prompt_index"])
    core.atomic_output(
        args.output,
        {
            "schema": f"{SCHEMA}-prepared",
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "suite_path": str(args.suite.resolve()),
            "suite_sha256": core.SUITE_SHA256,
            "suite": suite_meta,
            "config_path": str(args.config.resolve()),
            "config_sha256": core.sha256_bytes(args.config.read_bytes()),
            "service_count": SERVICE_COUNT,
            "wave_count": WAVE_COUNT,
            "generation_requests": 0,
            "rows": rows,
        },
    )
    return 0


class Journal:
    def __init__(self, path: Path) -> None:
        if path.exists():
            raise ValueError(f"refusing to overwrite journal: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.Lock()

    def record(self, value: dict[str, Any]) -> None:
        line = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        with self.lock:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())


def validate_prepared(path: Path, config: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prepared = read_object(path)
    rows = prepared.get("rows")
    suite_path_raw = prepared.get("suite_path")
    if (
        prepared.get("schema") != f"{SCHEMA}-prepared"
        or prepared.get("suite_sha256") != core.SUITE_SHA256
        or not isinstance(suite_path_raw, str)
        or not Path(suite_path_raw).is_absolute()
        or prepared.get("config_path") != str(config.resolve())
        or prepared.get("config_sha256") != core.sha256_bytes(config.read_bytes())
        or prepared.get("service_count") != SERVICE_COUNT
        or prepared.get("wave_count") != WAVE_COUNT
        or prepared.get("generation_requests") != 0
        or not isinstance(rows, list)
        or len(rows) != PROMPT_COUNT
    ):
        raise ValueError("prepared four-service suite artifact is invalid")
    _, prompts = core.load_suite(Path(suite_path_raw))
    services = load_config(config)
    for index, row in enumerate(rows):
        item = prompts[index]
        service = services[index % SERVICE_COUNT]
        if (
            not isinstance(row, dict)
            or row.get("prompt_index") != index
            or row.get("prompt_id") != item["id"]
            or row.get("prompt_sha256")
            != core.sha256_bytes(item["prompt"].encode())
            or row.get("wave_index") != index // SERVICE_COUNT
            or row.get("service_index") != index % SERVICE_COUNT
            or row.get("gpu_index") != index % SERVICE_COUNT
            or row.get("base_url") != service["base_url"]
            or row.get("model") != service["model"]
            or not isinstance(row.get("rendered_prompt"), str)
            or not row["rendered_prompt"]
            or row.get("rendered_prompt_sha256")
            != core.sha256_bytes(row["rendered_prompt"].encode())
        ):
            raise ValueError("prepared wave partition is invalid")
    return prepared, rows


def run(args: argparse.Namespace) -> int:
    services = load_config(args.config)
    prepared, rows_in = validate_prepared(args.prepared, args.config)
    journal = Journal(args.journal)
    captured: list[dict[str, Any]] = []
    wave_records: list[dict[str, Any]] = []
    suite_id = (prepared.get("suite") or {}).get("suite_id")

    for wave_index in range(WAVE_COUNT):
        wave_rows = rows_in[wave_index * SERVICE_COUNT : (wave_index + 1) * SERVICE_COUNT]
        barrier = threading.Barrier(SERVICE_COUNT)

        def capture(item: dict[str, Any]) -> dict[str, Any]:
            service_index = int(item["service_index"])
            service = services[service_index]
            request_id = core.safe_id(
                f"scale-{suite_id}-w{wave_index}-s{service_index}-{item['prompt_id']}"
            )
            barrier.wait(timeout=30)
            intent_epoch = time.time()
            journal.record(
                {
                    "event": "request_started",
                    "epoch_s": intent_epoch,
                    "wave_index": wave_index,
                    "service_index": service_index,
                    "gpu_index": service["gpu_index"],
                    "prompt_index": item["prompt_index"],
                    "prompt_id": item["prompt_id"],
                    "request_id": request_id,
                }
            )
            try:
                row = core.stream_once(
                    service["base_url"],
                    service["model"],
                    item["rendered_prompt"],
                    request_id,
                    args.timeout,
                )
            except BaseException as exc:
                journal.record(
                    {
                        "event": "request_failed",
                        "epoch_s": time.time(),
                        "wave_index": wave_index,
                        "service_index": service_index,
                        "prompt_index": item["prompt_index"],
                        "prompt_id": item["prompt_id"],
                        "request_id": request_id,
                        "error_type": type(exc).__name__,
                    }
                )
                raise
            journal.record(
                {
                    "event": "request_completed",
                    "epoch_s": time.time(),
                    "wave_index": wave_index,
                    "service_index": service_index,
                    "prompt_index": item["prompt_index"],
                    "prompt_id": item["prompt_id"],
                    "request_id": request_id,
                }
            )
            row.update(
                {
                    "prompt_index": item["prompt_index"],
                    "prompt_id": item["prompt_id"],
                    "prompt_sha256": item["prompt_sha256"],
                    "rendered_prompt_sha256": item["rendered_prompt_sha256"],
                    "wave_index": wave_index,
                    "service_index": service_index,
                    "gpu_index": service["gpu_index"],
                    "base_url": service["base_url"],
                    "model": service["model"],
                    "intent_epoch_s": intent_epoch,
                    "request_ended_epoch_s": row["request_started_epoch_s"]
                    + row["elapsed_s"],
                    "token_timing_source": "llamacpp_oai_completion_verbose_token_ids",
                }
            )
            return row

        wave_wall_started = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=SERVICE_COUNT) as pool:
            futures = [pool.submit(capture, item) for item in wave_rows]
            wave_result = [future.result() for future in futures]
        wave_wall_ended = time.time()
        wave_result.sort(key=lambda row: row["service_index"])
        latest_start = max(float(row["request_started_epoch_s"]) for row in wave_result)
        earliest_end = min(float(row["request_ended_epoch_s"]) for row in wave_result)
        wave_records.append(
            {
                "wave_index": wave_index,
                "prompt_indices": [row["prompt_index"] for row in wave_result],
                "service_indices": [row["service_index"] for row in wave_result],
                "request_ids": [row["request_id"] for row in wave_result],
                "wall_started_epoch_s": wave_wall_started,
                "wall_ended_epoch_s": wave_wall_ended,
                "latest_request_start_epoch_s": latest_start,
                "earliest_request_end_epoch_s": earliest_end,
                "four_way_overlap_s": earliest_end - latest_start,
            }
        )
        captured.extend(wave_result)

    captured.sort(key=lambda row: row["prompt_index"])
    request_ids = [row["request_id"] for row in captured]
    cache_zero = all(row.get("cached_tokens") == 0 for row in captured)
    enough = all(row.get("stream_token_id_count", 0) >= 100 for row in captured)
    full_positions = all(
        isinstance(row.get("completion_tokens"), int)
        and not isinstance(row.get("completion_tokens"), bool)
        and row["completion_tokens"] >= 100
        and row.get("stream_complete_positions")
        == list(range(row["completion_tokens"]))
        for row in captured
    )
    result = {
        "schema": SCHEMA,
        "run_identity": {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "api_mode": "completions",
            "suite_path": prepared.get("suite_path"),
            "suite": prepared.get("suite"),
            "suite_sha256": core.SUITE_SHA256,
            "prepared_path": str(args.prepared.resolve()),
            "prepared_sha256": core.sha256_bytes(args.prepared.read_bytes()),
            "config_path": str(args.config.resolve()),
            "config_sha256": core.sha256_bytes(args.config.read_bytes()),
            "journal_path": str(args.journal.resolve()),
            "prompt_count": PROMPT_COUNT,
            "service_count": SERVICE_COUNT,
            "wave_count": WAVE_COUNT,
            "requests_per_wave": SERVICE_COUNT,
            "generation_requests_per_prompt": 1,
            "generation_requests_total": PROMPT_COUNT,
            "replay_requests": 0,
            "max_tokens": 512,
            "seed": 1,
            "temperature": 0,
            "top_p": 1,
            "ignore_eos": False,
            "request_extra": {
                "cache_prompt": False,
                "id_slot": 0,
                "ignore_eos": False,
                "return_tokens": True,
                "verbose": True,
            },
            "partition": "prompt_index = wave_index * 4 + service_index",
        },
        "fresh_response_validity": {
            "valid": len(captured) == PROMPT_COUNT
            and len(set(request_ids)) == PROMPT_COUNT
            and cache_zero
            and enough,
            "each_prompt_run_once": True,
            "cached_tokens_all_zero": cache_zero,
            "history_acceleration": False,
            "ngram_history_acceleration": False,
            "response_reuse": False,
            "context_checkpoints_or_prefix_reuse": False,
        },
        "stream_position_evidence": {
            "all_generated_positions_present": full_positions,
            "policy": "fail closed; no forensic replay or token reconstruction",
        },
        "metric_accounting": {
            "schema": "realistic-window-accounting-v2-oracle-aligned",
            "timestamped_events": 100,
            "inter_token_intervals": 99,
            "timing_source": "llamacpp_oai_completion_verbose_token_ids",
        },
        "waves": wave_records,
        "rows": captured,
    }
    core.atomic_output(args.output, result)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--config", type=Path, required=True)
    prep.add_argument("--suite", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--timeout", type=int, default=900)
    prep.set_defaults(handler=prepare)
    capture = commands.add_parser("run")
    capture.add_argument("--config", type=Path, required=True)
    capture.add_argument("--prepared", type=Path, required=True)
    capture.add_argument("--journal", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--timeout", type=int, default=900)
    capture.set_defaults(handler=run)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        if args.timeout <= 0:
            raise ValueError("timeout must be positive")
        return args.handler(args)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"four-service realistic capture failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
