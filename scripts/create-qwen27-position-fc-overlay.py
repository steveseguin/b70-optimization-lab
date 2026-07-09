#!/usr/bin/env python3
"""Create a Qwen27 model overlay with position-specific intrinsic-MTP FCs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from safetensors import safe_open


POSITION_FC_KEY_RE = re.compile(r"^mtp\.position_fcs\.(\d+)\.weight$")
POSITION_ADAPTER_KEY_RE = re.compile(
    r"^mtp\.position_adapters\.(\d+)\.(down|up)\.weight$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model-dir", required=True)
    parser.add_argument("--model-extra", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--num-position-fcs", required=True, type=int)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    base = Path(args.base_model_dir).resolve()
    model_extra = Path(args.model_extra).resolve()
    out = Path(args.out_dir).resolve()
    count = args.num_position_fcs
    if count < 1:
        raise ValueError("--num-position-fcs must be at least 1")
    if not (base / "config.json").is_file():
        raise FileNotFoundError(base / "config.json")
    if not model_extra.is_file():
        raise FileNotFoundError(model_extra)

    expected = {f"mtp.position_fcs.{idx}.weight" for idx in range(count)}
    with safe_open(model_extra, framework="pt", device="cpu") as handle:
        keys = set(handle.keys())
        missing = sorted(expected - keys)
        actual_position_fcs = {
            key for key in keys if POSITION_FC_KEY_RE.fullmatch(key) is not None
        }
        unexpected = sorted(actual_position_fcs - expected)
        if missing or unexpected:
            raise ValueError(
                "candidate model-extra position FC keys do not match "
                f"--num-position-fcs={count}: missing={missing}, "
                f"unexpected={unexpected}"
            )
        shapes = {
            key: list(handle.get_slice(key).get_shape()) for key in sorted(expected)
        }
        adapter_parts: dict[int, dict[str, str]] = {}
        for key in keys:
            match = POSITION_ADAPTER_KEY_RE.fullmatch(key)
            if match is None:
                continue
            index = int(match.group(1))
            direction = match.group(2)
            adapter_parts.setdefault(index, {})[direction] = key
        adapter_shapes = {
            key: list(handle.get_slice(key).get_shape())
            for parts in adapter_parts.values()
            for key in parts.values()
        }
    unique_position_fc_shapes = {tuple(shape) for shape in shapes.values()}
    if len(unique_position_fc_shapes) != 1:
        raise ValueError(f"position-specific FC shapes disagree: {shapes}")
    position_fc_shape = next(iter(unique_position_fc_shapes))
    if len(position_fc_shape) != 2:
        raise ValueError(
            "position-specific FC weights must be two-dimensional, got "
            f"{position_fc_shape}"
        )

    adapter_count = 0
    adapter_rank = 0
    if adapter_parts:
        adapter_indices = sorted(adapter_parts)
        expected_adapter_indices = list(range(count))
        if adapter_indices != expected_adapter_indices:
            raise ValueError(
                "position adapter count/indices must match position FC count; "
                f"found {adapter_indices}, expected {expected_adapter_indices}"
            )
        hidden_size = position_fc_shape[0]
        for index in expected_adapter_indices:
            parts = adapter_parts[index]
            missing_parts = sorted({"down", "up"} - set(parts))
            if missing_parts:
                raise ValueError(
                    f"position adapter {index} is missing {missing_parts} "
                    "weight key(s)"
                )
            down_key = parts["down"]
            up_key = parts["up"]
            down_shape = tuple(adapter_shapes[down_key])
            up_shape = tuple(adapter_shapes[up_key])
            if len(down_shape) != 2 or down_shape[0] < 1:
                raise ValueError(
                    f"{down_key} must have shape [rank, H], got {down_shape}"
                )
            rank = down_shape[0]
            if down_shape != (rank, hidden_size):
                raise ValueError(
                    f"{down_key} must have shape [{rank}, {hidden_size}], "
                    f"got {down_shape}"
                )
            if up_shape != (hidden_size, rank):
                raise ValueError(
                    f"{up_key} must have shape [{hidden_size}, {rank}], "
                    f"got {up_shape}"
                )
            if adapter_rank and rank != adapter_rank:
                raise ValueError(
                    "position adapter ranks disagree: "
                    f"adapter 0 has rank {adapter_rank}, adapter {index} has "
                    f"rank {rank}"
                )
            adapter_rank = rank
        adapter_count = len(adapter_parts)

    out.mkdir(parents=True, exist_ok=True)
    for source in base.iterdir():
        if source.name in ("config.json", "model_extra_tensors.safetensors"):
            continue
        destination = out / source.name
        if destination.is_symlink() or destination.exists():
            if destination.is_symlink() and Path(os.readlink(destination)) == source:
                continue
            raise FileExistsError(destination)
        destination.symlink_to(source)

    config = json.loads((base / "config.json").read_text(encoding="utf-8"))
    text_config = config.get("text_config")
    if not isinstance(text_config, dict):
        text_config = config
    text_config["xpu_mtp_num_position_fcs"] = count
    if adapter_count:
        text_config["xpu_mtp_position_adapter_count"] = adapter_count
        text_config["xpu_mtp_position_adapter_rank"] = adapter_rank
    else:
        text_config.pop("xpu_mtp_position_adapter_count", None)
        text_config.pop("xpu_mtp_position_adapter_rank", None)
    (out / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    destination_extra = out / "model_extra_tensors.safetensors"
    if destination_extra.is_symlink() or destination_extra.exists():
        destination_extra.unlink()
    destination_extra.symlink_to(model_extra)

    metadata = {
        "purpose": "qwen27_position_specific_intrinsic_mtp_fc_overlay",
        "base_model_dir": str(base),
        "model_extra": str(model_extra),
        "model_extra_sha256": sha256(model_extra),
        "num_position_fcs": count,
        "position_fc_shapes": shapes,
        "position_adapter_count": adapter_count,
        "position_adapter_rank": adapter_rank,
        "position_adapter_shapes": adapter_shapes,
        "target_model_unchanged": True,
        "headline_warning": (
            "Candidate overlay only; strict fresh endpoint throughput and quality "
            "validation are required before promotion or submission."
        ),
    }
    (out / "position_fc_overlay.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
