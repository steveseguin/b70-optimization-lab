#!/usr/bin/env python3
"""Validate the XPU block-table dirty commit patch without endpoint downtime."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULT_VLLM_SRC = "/home/steve/src/vllm"


def make_block_table(vllm_src: str) -> Any:
    os.environ["VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT"] = "1"
    sys.path.insert(0, vllm_src)

    import torch
    from vllm.v1.worker.block_table import BlockTable

    return BlockTable(
        block_size=64,
        max_num_reqs=4,
        max_num_blocks_per_req=8,
        max_num_batched_tokens=256,
        pin_memory=False,
        device=torch.device("cpu"),
        kernel_block_size=64,
        cp_kv_cache_interleave_size=1,
    )


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def run_check(vllm_src: str) -> dict[str, Any]:
    bt = make_block_table(vllm_src)

    bt.commit_block_table(2)
    assert_equal(bt._dirty_commit_skipped, 1, "initial skip count")

    bt.add_row([10, 11], 0)
    bt.commit_block_table(2)
    assert_equal(bt.block_table.gpu[0, :2].tolist(), [10, 11], "row0 add")
    assert_equal(bt._dirty_commit_partial, 1, "partial count after row0 add")

    bt.commit_block_table(2)
    assert_equal(bt._dirty_commit_skipped, 2, "second skip count")

    bt.append_row([12], 0)
    bt.add_row([20], 1)
    bt.commit_block_table(2)
    assert_equal(bt.block_table.gpu[0, :3].tolist(), [10, 11, 12], "row0 append")
    assert_equal(bt.block_table.gpu[1, :1].tolist(), [20], "row1 add")
    assert_equal(bt._dirty_commit_full, 1, "full count after rows 0 and 1")

    bt.clear_row(0)
    bt.commit_block_table(2)
    assert_equal(bt.block_table.gpu[0, :3].tolist(), [0, 0, 0], "row0 clear")

    bt.move_row(1, 2)
    bt.commit_block_table(3)
    assert_equal(bt.block_table.gpu[2, :1].tolist(), [20], "row1 move to row2")

    bt.swap_row(1, 2)
    bt.commit_block_table(3)
    assert_equal(bt.block_table.gpu[1, :1].tolist(), [20], "row2 swap to row1")

    return {
        "ok": True,
        "vllm_src": vllm_src,
        "stats": {
            "total": bt._dirty_commit_total,
            "skipped": bt._dirty_commit_skipped,
            "full": bt._dirty_commit_full,
            "partial": bt._dirty_commit_partial,
            "copied_rows": bt._dirty_commit_rows,
        },
        "row0": bt.block_table.gpu[0, :4].tolist(),
        "row1": bt.block_table.gpu[1, :4].tolist(),
        "row2": bt.block_table.gpu[2, :4].tolist(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vllm-src", default=DEFAULT_VLLM_SRC)
    parser.add_argument("--output-json")
    args = parser.parse_args()

    result = run_check(args.vllm_src)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        Path(args.output_json).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
