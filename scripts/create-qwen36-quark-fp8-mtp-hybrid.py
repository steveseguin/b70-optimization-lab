#!/usr/bin/env python3
"""Create a disposable Quark INT8 + official FP8 MTP hybrid checkpoint.

The target weights, tokenizer, and config come from the current Quark W8A8 INT8
checkpoint. Only `mtp.*` tensor index entries and `mtp.safetensors` are borrowed
from the official FP8 checkpoint. This is intended for verifier-preserving MTP
mechanics tests where the Quark model remains the final verifier.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


DEFAULT_QUARK = Path(
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118"
)
DEFAULT_FP8 = Path(
    "/mnt/fast-ai/llm-cache/hf/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/95a723d08a9490559dae23d0cff1d9466213d989"
)
DEFAULT_OUT = Path("/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid")


def link_file(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    os.symlink(src, dst)


def load_index(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quark", type=Path, default=DEFAULT_QUARK)
    parser.add_argument("--fp8", type=Path, default=DEFAULT_FP8)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove an existing output directory before recreating it.",
    )
    args = parser.parse_args()

    quark = args.quark.resolve()
    fp8 = args.fp8.resolve()
    out = args.out

    for required in [
        quark / "model.safetensors.index.json",
        fp8 / "model.safetensors.index.json",
        fp8 / "mtp.safetensors",
    ]:
        if not required.exists():
            raise FileNotFoundError(required)

    if out.exists() and args.force:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    for child in quark.iterdir():
        if child.name == "model.safetensors.index.json":
            continue
        if child.is_file() or child.is_symlink():
            link_file(child.resolve(), out / child.name)

    link_file((fp8 / "mtp.safetensors").resolve(), out / "mtp.safetensors")

    quark_index = load_index(quark / "model.safetensors.index.json")
    fp8_index = load_index(fp8 / "model.safetensors.index.json")
    quark_map = dict(quark_index["weight_map"])
    fp8_mtp_map = {
        name: "mtp.safetensors"
        for name, filename in fp8_index["weight_map"].items()
        if name.startswith("mtp.") and filename == "mtp.safetensors"
    }
    if not fp8_mtp_map:
        raise RuntimeError("No mtp.* weights mapped to mtp.safetensors in FP8 index")

    merged = dict(quark_index)
    merged_map = dict(quark_map)
    merged_map.update(fp8_mtp_map)
    merged["weight_map"] = dict(sorted(merged_map.items()))
    metadata = dict(merged.get("metadata") or {})
    metadata["hybrid_quark_source"] = str(quark)
    metadata["hybrid_mtp_source"] = str(fp8 / "mtp.safetensors")
    metadata["hybrid_mtp_weight_count"] = len(fp8_mtp_map)
    metadata["hybrid_note"] = (
        "Quark verifier weights plus official FP8 mtp.* proposer tensors."
    )
    merged["metadata"] = metadata

    index_path = out / "model.safetensors.index.json"
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2, sort_keys=True)
        handle.write("\n")

    summary = {
        "output": str(out),
        "quark_source": str(quark),
        "fp8_source": str(fp8),
        "quark_weight_count": len(quark_map),
        "mtp_weight_count": len(fp8_mtp_map),
        "merged_weight_count": len(merged_map),
        "mtp_file": os.readlink(out / "mtp.safetensors"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
