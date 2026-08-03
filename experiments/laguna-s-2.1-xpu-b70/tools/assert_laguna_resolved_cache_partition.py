#!/usr/bin/env python3
"""Prove the resolved cache and prefill-partition settings from a server log.

The launcher passes ``--no-enable-prefix-caching`` and never passes
``--max-num-partial-prefills``, but argv only records what was requested. Both
settings silently destroy the 8182 + 8182 + 8182 + 8094 partition that the
long-context rows depend on, and the failure looks exactly like a null result
rather than an error, so the evidence has to come from what vLLM resolved.

Every claim below is read out of vLLM's own resolved-config logging:

``enable_prefix_caching``
    ``VllmConfig.__str__`` embeds the resolved ``CacheConfig`` value in the
    engine-core startup line, so the value is quoted directly.

``max_num_partial_prefills``
    The resolved value is not logged when it is the default. It is pinned by
    elimination instead: ``SchedulerConfig`` declares ``default=1``, its
    ``__post_init__`` emits a ``Concurrent partial prefills enabled`` line
    whenever the value exceeds one, and any command-line override would appear
    in the ``non-default args`` record. A log with neither marker cannot have a
    value other than one.

``max_num_batched_tokens`` / ``max_num_scheduled_tokens``
    The chunked-prefill line carries the resolved batched budget and the
    speculative-decoding notice carries the derived per-step budget, which is
    what actually partitions a long prompt.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ENGINE_CONFIG_MARKER = "Initializing a V1 LLM engine"
PREFIX_CACHING_PATTERN = re.compile(r"enable_prefix_caching=(True|False|None)")
CHUNKED_PREFILL_PATTERN = re.compile(
    r"Chunked prefill is enabled with max_num_batched_tokens=(\d+)\."
)
SCHEDULED_TOKENS_PATTERN = re.compile(
    r"max_num_scheduled_tokens is set to (\d+) based on"
)
CONCURRENT_PARTIAL_PREFILLS_MARKER = "Concurrent partial prefills enabled with"
NON_DEFAULT_ARGS_MARKER = "non-default args:"
PARTIAL_PREFILLS_KEY = "max_num_partial_prefills"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_match(text: str, pattern: re.Pattern[str], label: str) -> str:
    values = set(pattern.findall(text))
    require(bool(values), f"{label} was never logged")
    require(len(values) == 1, f"{label} was logged with conflicting values: {values}")
    return values.pop()


def analyze(
    log_text: str,
    *,
    expected_batched_tokens: int,
    expected_scheduled_tokens: int,
) -> dict[str, Any]:
    require(
        ENGINE_CONFIG_MARKER in log_text,
        "server log has no resolved engine configuration line",
    )
    prefix_caching = unique_match(
        log_text, PREFIX_CACHING_PATTERN, "resolved enable_prefix_caching"
    )
    require(
        prefix_caching == "False",
        f"resolved enable_prefix_caching is {prefix_caching}, not False",
    )

    require(
        CONCURRENT_PARTIAL_PREFILLS_MARKER not in log_text,
        "resolved max_num_partial_prefills is above one",
    )
    non_default_lines = [
        line for line in log_text.splitlines() if NON_DEFAULT_ARGS_MARKER in line
    ]
    require(bool(non_default_lines), "server log has no non-default args record")
    overridden = [line for line in non_default_lines if PARTIAL_PREFILLS_KEY in line]
    require(
        not overridden,
        "max_num_partial_prefills was overridden on the command line",
    )

    batched_tokens = int(
        unique_match(log_text, CHUNKED_PREFILL_PATTERN, "resolved batched-token budget")
    )
    require(
        batched_tokens == expected_batched_tokens,
        f"resolved max_num_batched_tokens is {batched_tokens},"
        f" not {expected_batched_tokens}",
    )
    scheduled_tokens = int(
        unique_match(
            log_text, SCHEDULED_TOKENS_PATTERN, "derived scheduled-token budget"
        )
    )
    require(
        scheduled_tokens == expected_scheduled_tokens,
        f"derived max_num_scheduled_tokens is {scheduled_tokens},"
        f" not {expected_scheduled_tokens}",
    )

    return {
        "schema": "laguna-resolved-cache-partition-v1",
        "status": "PASS_RESOLVED_SETTINGS_PROVED",
        "resolved": {
            "enable_prefix_caching": False,
            "max_num_partial_prefills": 1,
            "max_num_batched_tokens": batched_tokens,
            "max_num_scheduled_tokens": scheduled_tokens,
        },
        "evidence": {
            "enable_prefix_caching": "engine-core resolved VllmConfig line",
            "max_num_partial_prefills": (
                "field default of one, no concurrent-partial-prefill notice, and "
                "no command-line override in the non-default args record"
            ),
            "max_num_batched_tokens": "chunked-prefill notice",
            "max_num_scheduled_tokens": "speculative-decoding budget notice",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-batched-tokens", type=int, default=8192)
    parser.add_argument("--expected-scheduled-tokens", type=int, default=8182)
    args = parser.parse_args()

    result = analyze(
        args.server_log.read_text(encoding="utf-8", errors="replace"),
        expected_batched_tokens=args.expected_batched_tokens,
        expected_scheduled_tokens=args.expected_scheduled_tokens,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
