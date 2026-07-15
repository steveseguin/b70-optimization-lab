#!/usr/bin/env python3
"""Fail-closed validation for a real DeepSeek V4 TP4/MHC decode capture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch


WORLD = 4
ALLREDUCES = 87
POST_PRE_BOUNDARIES = 85
HIDDEN = 4096
HC = 4


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            result.update(block)
    return result.hexdigest()


def load(path: Path) -> dict:
    return torch.load(path, map_location="cpu", weights_only=False)


def expected_slot(index: int) -> tuple[str, str, bool]:
    if index == 0:
        return "model.layers.0", "ffn", False
    layer = (index + 1) // 2
    boundary = "attn" if index % 2 else "ffn"
    aliases_outputs = index >= 2 and index % 2 == 0
    return f"model.layers.{layer}", boundary, aliases_outputs


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def tensor_shape(row: dict, name: str, shape: tuple[int, ...]) -> None:
    require(tuple(row["tensors"][name].shape) == shape, f"{name}: wrong shape")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.capture_dir.resolve()

    files: list[Path] = []
    allreduces: list[list[dict]] = []
    for rank in range(WORLD):
        rank_dir = root / f"rank{rank}"
        ar_paths = sorted((rank_dir / "allreduce").glob("*.pt"))
        mhc_paths = sorted((rank_dir / "mhc").glob("*.pt"))
        require(len(ar_paths) == ALLREDUCES, f"rank {rank}: allreduce count")
        require(
            len(mhc_paths) == POST_PRE_BOUNDARIES,
            f"rank {rank}: MHC boundary count",
        )
        require((rank_dir / "final_post.pt").is_file(), f"rank {rank}: final post")
        require(
            [path.stem for path in ar_paths]
            == [f"{index:03d}" for index in range(ALLREDUCES)],
            f"rank {rank}: allreduce indices",
        )
        require(
            [path.stem for path in mhc_paths]
            == [f"{index:03d}" for index in range(POST_PRE_BOUNDARIES)],
            f"rank {rank}: MHC indices",
        )
        rows = [load(path) for path in ar_paths]
        allreduces.append(rows)
        files.extend(ar_paths)
        files.extend(mhc_paths)
        files.append(rank_dir / "final_post.pt")
        for index, row in enumerate(rows):
            require(row["index"] == index, f"rank {rank}: allreduce index {index}")
            require(row["global_rank"] == rank, f"rank {rank}: global rank")
            require(row["rank_in_group"] == rank, f"rank {rank}: TP rank")
            require(row["group_name"].startswith("tp:"), f"rank {rank}: TP group")
            require(
                tuple(row["input_before"].shape) == (1, HIDDEN),
                f"rank {rank}: allreduce input shape {index}",
            )
            require(
                row["input_before"].dtype == torch.bfloat16,
                f"rank {rank}: allreduce input dtype {index}",
            )
            require(
                tuple(row["output_after"].shape) == (1, HIDDEN),
                f"rank {rank}: allreduce output shape {index}",
            )

    for index in range(ALLREDUCES):
        expected = allreduces[0][index]["output_after"]
        for rank in range(1, WORLD):
            require(
                torch.equal(allreduces[rank][index]["output_after"], expected),
                f"allreduce {index}: rank {rank} output differs",
            )

    alias_boundaries = 0
    canonical_outputs: list[list[dict[str, torch.Tensor]]] = [[] for _ in range(WORLD)]
    for rank in range(WORLD):
        for index in range(POST_PRE_BOUNDARIES):
            path = root / f"rank{rank}" / "mhc" / f"{index:03d}.pt"
            row = load(path)
            layer_prefix, boundary, expect_alias = expected_slot(index)
            require(row["index"] == index, f"rank {rank}: MHC index {index}")
            require(row["rank"] == rank, f"rank {rank}: MHC rank {index}")
            require(
                row["layer_prefix"] == layer_prefix,
                f"rank {rank}: layer map {index}",
            )
            require(row["boundary"] == boundary, f"rank {rank}: phase map {index}")
            tensor_shape(row, "x_reduced", (1, HIDDEN))
            tensor_shape(row, "residual", (1, HC, HIDDEN))
            tensor_shape(row, "post", (1, HC, 1))
            tensor_shape(row, "comb", (1, HC, HC))
            tensor_shape(row, "fn", (24, HC * HIDDEN))
            tensor_shape(row, "hc_scale", (3,))
            tensor_shape(row, "hc_base", (24,))
            tensor_shape(row, "residual_out", (1, HC, HIDDEN))
            tensor_shape(row, "post_out", (1, HC, 1))
            tensor_shape(row, "comb_out", (1, HC, HC))
            tensor_shape(row, "layer_input", (1, HIDDEN))
            require(
                torch.equal(
                    row["tensors"]["x_reduced"],
                    allreduces[rank][index + 1]["output_after"],
                ),
                f"rank {rank}: allreduce-to-MHC link {index}",
            )
            metadata = row["tensor_metadata"]
            aliases = [
                metadata[source]["storage_data_ptr"]
                == metadata[target]["storage_data_ptr"]
                for source, target in (
                    ("residual", "residual_out"),
                    ("post", "post_out"),
                    ("comb", "comb_out"),
                )
            ]
            require(
                aliases == [expect_alias] * 3,
                f"rank {rank}: alias map {index}: {aliases}",
            )
            if rank == 0 and expect_alias:
                alias_boundaries += 1
            canonical_outputs[rank].append(
                {
                    name: row["tensors"][name]
                    for name in (
                        "residual_out",
                        "post_out",
                        "comb_out",
                        "layer_input",
                    )
                }
            )

    require(
        alias_boundaries == 42, f"expected 42 alias boundaries, got {alias_boundaries}"
    )
    for index in range(POST_PRE_BOUNDARIES):
        for name in canonical_outputs[0][index]:
            expected = canonical_outputs[0][index][name]
            for rank in range(1, WORLD):
                require(
                    torch.equal(canonical_outputs[rank][index][name], expected),
                    f"MHC {index} {name}: rank {rank} differs",
                )

    for rank in range(WORLD):
        row = load(root / f"rank{rank}" / "final_post.pt")
        require(row["rank"] == rank, f"rank {rank}: final-post rank")
        require(row["layer_prefix"] == "model.layers.42", f"rank {rank}: final layer")
        tensor_shape(row, "x_reduced", (1, HIDDEN))
        tensor_shape(row, "residual", (1, HC, HIDDEN))
        tensor_shape(row, "post", (1, HC, 1))
        tensor_shape(row, "comb", (1, HC, HC))
        tensor_shape(row, "residual_out", (1, HC, HIDDEN))
        require(
            torch.equal(
                row["tensors"]["x_reduced"], allreduces[rank][86]["output_after"]
            ),
            f"rank {rank}: final allreduce-to-post link",
        )
        for name, prior_name in (
            ("residual", "residual_out"),
            ("post", "post_out"),
            ("comb", "comb_out"),
        ):
            require(
                torch.equal(
                    row["tensors"][name], canonical_outputs[rank][84][prior_name]
                ),
                f"rank {rank}: final recurrent state {name}",
            )

    file_rows = [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(files)
    ]
    aggregate = hashlib.sha256()
    for row in file_rows:
        aggregate.update(row["path"].encode())
        aggregate.update(b"\0")
        aggregate.update(row["sha256"].encode())
        aggregate.update(b"\n")
    summary = {
        "status": "passed",
        "capture_dir": str(root),
        "world_size": WORLD,
        "allreduces_per_rank": ALLREDUCES,
        "post_pre_boundaries_per_rank": POST_PRE_BOUNDARIES,
        "final_posts_per_rank": 1,
        "alias_boundaries": alias_boundaries,
        "allreduce_outputs_equal_across_ranks": True,
        "allreduce_to_mhc_links_exact": True,
        "mhc_outputs_equal_across_ranks": True,
        "final_recurrent_links_exact": True,
        "file_count": len(file_rows),
        "total_bytes": sum(row["bytes"] for row in file_rows),
        "aggregate_sha256": aggregate.hexdigest(),
        "files": file_rows,
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered)
        temporary.replace(args.output)
    print(rendered, end="")


if __name__ == "__main__":
    main()
