#!/usr/bin/env python3
"""Teacher-force saved K160 greedy trajectories through guarded capture."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def metrics(base_url: str, timeout: int) -> dict[str, float]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/metrics", timeout=timeout) as r:
        text = r.read().decode()
    result = {"running": 0.0, "waiting": 0.0}
    names = {
        "vllm:num_requests_running": "running",
        "vllm:num_requests_waiting": "waiting",
    }
    for line in text.splitlines():
        for metric_name, key in names.items():
            if line.startswith(metric_name + "{") or line.startswith(metric_name + " "):
                result[key] += float(line.rsplit(" ", 1)[-1])
    return result


def replay(
    base_url: str,
    model: str,
    token_ids: list[int],
    prompt_len: int,
    continuation_len: int,
    request_index: int,
    timeout: int,
) -> dict[str, Any]:
    request_id = (
        f"eaglereplay-{prompt_len}-{continuation_len}-{request_index:06d}"
    )
    payload = {
        "model": model,
        "prompt": token_ids,
        "max_tokens": 1,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "stream": False,
        "request_id": request_id,
        "cache_salt": f"replay-{request_index:06d}",
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)
    return {
        "request_id": request_id,
        "response_id": raw["id"],
        "elapsed_s": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="deepseek-v4-flash-k160")
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--arm-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    trajectories = load_jsonl(args.trajectories)
    if not trajectories:
        raise RuntimeError("trajectory manifest is empty")
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.arm_file.parent.mkdir(parents=True, exist_ok=True)
    args.arm_file.touch(exist_ok=False)
    started = time.time()
    rows = 0
    with args.output.open("x") as stream:
        for index, trajectory in enumerate(trajectories):
            before = metrics(args.base_url, args.timeout)
            if before["running"] != 0 or before["waiting"] != 0:
                raise RuntimeError(f"endpoint busy before replay {index}: {before}")
            prompt_ids = [int(x) for x in trajectory["prompt_token_ids"]]
            output_ids = [int(x) for x in trajectory["response"]["output_token_ids"]]
            if not output_ids:
                raise RuntimeError(f"trajectory {index} lacks output token IDs")
            full_ids = prompt_ids + output_ids
            result = replay(
                args.base_url,
                args.model,
                full_ids,
                len(prompt_ids),
                len(output_ids),
                index,
                args.timeout,
            )
            after = metrics(args.base_url, args.timeout)
            if after["running"] != 0 or after["waiting"] != 0:
                raise RuntimeError(f"endpoint not idle after replay {index}: {after}")
            rows += len(output_ids)
            stream.write(
                json.dumps(
                    {
                        "trajectory_request_id": trajectory["request_id"],
                        "prompt_id": trajectory["prompt_id"],
                        "prompt_tokens": len(prompt_ids),
                        "continuation_tokens": len(output_ids),
                        **result,
                    }
                )
                + "\n"
            )
            stream.flush()
            if (index + 1) % 20 == 0:
                print(
                    json.dumps(
                        {
                            "replayed_requests": index + 1,
                            "captured_rows": rows,
                            "elapsed_s": time.time() - started,
                        }
                    ),
                    flush=True,
                )
    args.arm_file.unlink()
    print(
        json.dumps(
            {
                "replayed_requests": len(trajectories),
                "captured_rows": rows,
                "elapsed_s": time.time() - started,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
