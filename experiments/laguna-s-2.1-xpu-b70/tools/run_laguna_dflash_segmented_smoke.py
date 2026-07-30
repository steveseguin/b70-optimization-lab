#!/usr/bin/env python3
"""Bounded, non-scored live gate for Laguna's segmented DFlash graph."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import time
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

_PRIOR_FAILURE_CYCLE = 33
_MAX_EMITTED_PER_CYCLE = 12
_SMOKE_TOKENS = 400


def load_benchmark(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("laguna_smoke_benchmark", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import benchmark helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_metrics(base_url: str) -> str:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/metrics", timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def metric_value(text: str, name: str, *, position: int | None = None) -> float:
    rows = []
    for line in text.splitlines():
        if not line.startswith(name + "{"):
            continue
        if position is not None and f'position="{position}"' not in line:
            continue
        rows.append(float(line.rsplit(" ", 1)[1]))
    if len(rows) != 1:
        raise RuntimeError(
            f"expected exactly one {name} metric"
            + ("" if position is None else f" at position {position}")
            + f", saw {len(rows)}"
        )
    return rows[0]


def speculation_delta(before: str, after: str) -> dict[str, Any]:
    names = {
        "drafts": "vllm:spec_decode_num_drafts_total",
        "draft_tokens": "vllm:spec_decode_num_draft_tokens_total",
        "accepted_tokens": "vllm:spec_decode_num_accepted_tokens_total",
    }
    result = {
        key: metric_value(after, name) - metric_value(before, name)
        for key, name in names.items()
    }
    per_position = [
        metric_value(
            after,
            "vllm:spec_decode_num_accepted_tokens_per_pos_total",
            position=index,
        )
        - metric_value(
            before,
            "vllm:spec_decode_num_accepted_tokens_per_pos_total",
            position=index,
        )
        for index in range(11)
    ]
    result["accepted_per_position"] = per_position
    return result


def validate_speculation(delta: dict[str, Any], request_index: int) -> None:
    drafts = int(delta["drafts"])
    draft_tokens = int(delta["draft_tokens"])
    accepted = int(delta["accepted_tokens"])
    per_position = [int(value) for value in delta["accepted_per_position"]]
    if drafts <= _PRIOR_FAILURE_CYCLE:
        raise RuntimeError(
            f"request {request_index} did not cross the prior cycle-33 boundary"
        )
    if draft_tokens != drafts * 11:
        raise RuntimeError(
            f"request {request_index} draft topology drifted: "
            f"drafts={drafts} tokens={draft_tokens}"
        )
    if not 0 < accepted < draft_tokens:
        raise RuntimeError(
            f"request {request_index} has zero or flat-full acceptance: "
            f"{accepted}/{draft_tokens}"
        )
    if (
        any(left < right for left, right in zip(per_position, per_position[1:]))
        or per_position[0] >= drafts
        or per_position[-1] >= per_position[0]
    ):
        raise RuntimeError(
            f"request {request_index} acceptance curve is not normally decaying: "
            f"{per_position}, drafts={drafts}"
        )


def validate_response(
    result: dict[str, Any],
    expected: dict[str, Any],
    prompt: dict[str, str],
    request_index: int,
) -> None:
    actual_ids = [int(value) for value in result["token_ids"]]
    expected_ids = [int(value) for value in expected["token_ids"][:_SMOKE_TOKENS]]
    prompt_sha = hashlib.sha256(prompt["prompt"].encode()).hexdigest()
    if (
        expected.get("prompt_index") != request_index
        or expected.get("prompt_id") != prompt["id"]
        or expected.get("prompt_sha256") != prompt_sha
        or result.get("completion_tokens") != _SMOKE_TOKENS
        or actual_ids != expected_ids
        or result.get("usage", {})
        .get("prompt_tokens_details", {})
        .get("cached_tokens")
        != 0
    ):
        raise RuntimeError(
            f"request {request_index} failed its {_SMOKE_TOKENS}-token "
            "q=1 prefix/cache gate"
        )


def graph_rows(lines: list[str], action: str, shape: str) -> tuple[int, set[tuple[int, int]]]:
    rank_pattern = re.compile(r"Worker_TP([0-3])_EP([0-3])")
    rows = [
        line
        for line in lines
        if f"{action} audited breakable cudagraph" in line and shape in line
    ]
    ranks = {
        tuple(map(int, match.groups()))
        for line in rows
        if (match := rank_pattern.search(line))
    }
    return len(rows), ranks


def expected_graph_topologies(
    replicated_embedding: bool,
) -> tuple[tuple[int, int], tuple[int, int]]:
    return (
        (145, 144) if replicated_embedding else (146, 145),
        (19, 18) if replicated_embedding else (20, 19),
    )


def validate_graph_log(server_log: Path, *, replicated_embedding: bool) -> None:
    expected = {(0, 0), (1, 1), (2, 2), (3, 3)}
    target_topology, draft_topology = expected_graph_topologies(replicated_embedding)
    target_shape = (
        f"(graphs={target_topology[0]}, eager_breaks={target_topology[1]})"
    )
    draft_shape = f"(graphs={draft_topology[0]}, eager_breaks={draft_topology[1]})"
    deadline = time.monotonic() + 15
    while True:
        lines = server_log.read_text(encoding="utf-8", errors="replace").splitlines()
        checks = []
        for action in ("Captured", "Replayed"):
            checks.append(graph_rows(lines, action, target_shape))
            checks.append(graph_rows(lines, action, draft_shape))
        if all(count == 4 and ranks == expected for count, ranks in checks):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f"audited target/draft graph topology mismatch: {checks}")
        time.sleep(0.5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--teacher", type=Path, required=True)
    parser.add_argument("--benchmark-helper", type=Path, required=True)
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--replicated-embedding",
        type=int,
        choices=(0, 1),
        required=True,
    )
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    teacher = json.loads(args.teacher.read_text(encoding="utf-8"))
    prompts = suite["prompts"][:2]
    expected_rows = teacher["rows"][:2]
    if len(prompts) != 2 or len(expected_rows) != 2:
        raise RuntimeError("smoke requires the first two fixed suite/teacher rows")
    if _SMOKE_TOKENS <= _PRIOR_FAILURE_CYCLE * _MAX_EMITTED_PER_CYCLE:
        raise RuntimeError("smoke length cannot guarantee crossing cycle 33")

    benchmark = load_benchmark(args.benchmark_helper)
    before = fetch_metrics(args.base_url)
    records = []
    for index, (prompt, expected) in enumerate(zip(prompts, expected_rows, strict=True)):
        result = benchmark.post_stream(
            base_url=args.base_url,
            model=args.model,
            prompt=prompt["prompt"],
            max_tokens=_SMOKE_TOKENS,
            timeout=600,
            api_mode="chat",
            seed=1,
            request_extra={"chat_template_kwargs": {"enable_thinking": False}},
            return_token_ids=True,
            request_id=f"laguna-segmented-smoke-{index}",
        )
        after = fetch_metrics(args.base_url)
        delta = speculation_delta(before, after)
        validate_response(result, expected, prompt, index)
        validate_speculation(delta, index)
        records.append(
            {
                "request_index": index,
                "prompt_id": prompt["id"],
                "completion_tokens": result["completion_tokens"],
                "cached_tokens": result["usage"]["prompt_tokens_details"][
                    "cached_tokens"
                ],
                "token_prefix_exact": True,
                "speculation": delta,
            }
        )
        before = after

    replicated_embedding = bool(args.replicated_embedding)
    target_topology, draft_topology = expected_graph_topologies(replicated_embedding)
    validate_graph_log(
        args.server_log,
        replicated_embedding=replicated_embedding,
    )
    output = {
        "schema": "laguna-dflash-segmented-smoke-v2",
        "status": "PASS",
        "scored_measurement": False,
        "requests": records,
        "replicated_embedding": replicated_embedding,
        "target_graph_topology": (
            f"{target_topology[0]}/{target_topology[1]} on 4/4 ranks"
        ),
        "draft_graph_topology": (
            f"{draft_topology[0]}/{draft_topology[1]} on 4/4 ranks"
        ),
    }
    args.out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
