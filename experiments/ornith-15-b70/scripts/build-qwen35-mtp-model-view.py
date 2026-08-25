#!/usr/bin/env python3
"""Build a local, symlink-only Qwen3.5 MTP checkpoint view.

The standard in-checkpoint MTP path makes vLLM iterate every target-model
shard a second time.  Qwen3.5 MTP only consumes the native ``mtp.*`` tensors,
the input embedding, and the language-model head.  This tool creates a
fail-closed model directory whose safetensors index references only the files
containing those tensors.  It does not copy or modify model payloads.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


SHARED_WEIGHT_SUFFIXES = (
    ".embed_tokens.weight",
    "lm_head.weight",
)
METADATA_FILES = (
    "config.json",
    "generation_config.json",
    "quantization_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "chat_template.jinja",
    "preprocessor_config.json",
    "processor_config.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def selected_weight(name: str) -> bool:
    return name.startswith("mtp.") or name.endswith(SHARED_WEIGHT_SUFFIXES)


def main() -> int:
    args = parse_args()
    model = args.model.resolve(strict=True)
    output = args.output.absolute()
    if not model.is_dir():
        raise ValueError(f"model is not a directory: {model}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {output}")

    config_path = model / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    text_config = config.get("text_config") or {}
    model_type = text_config.get("model_type") or config.get("model_type")
    if not isinstance(model_type, str) or not model_type.startswith("qwen3_5"):
        raise ValueError(f"expected a Qwen3.5 checkpoint, got {model_type!r}")

    index_path = model / "model.safetensors.index.json"
    source_index = json.loads(index_path.read_text(encoding="utf-8"))
    source_map = source_index.get("weight_map")
    if not isinstance(source_map, dict):
        raise ValueError(f"invalid safetensors index: {index_path}")
    weight_map = {
        name: filename
        for name, filename in source_map.items()
        if selected_weight(name)
    }
    mtp_names = [name for name in weight_map if name.startswith("mtp.")]
    embed_names = [name for name in weight_map if name.endswith(".embed_tokens.weight")]
    head_names = [name for name in weight_map if name == "lm_head.weight"]
    if not mtp_names or len(embed_names) != 1 or len(head_names) != 1:
        raise ValueError(
            "checkpoint view requires native mtp.*, one embed_tokens.weight, "
            f"and one lm_head.weight; found {len(mtp_names)}, "
            f"{len(embed_names)}, {len(head_names)}"
        )

    weight_files = sorted(set(weight_map.values()))
    for filename in weight_files:
        if Path(filename).name != filename:
            raise ValueError(f"unsafe indexed weight filename: {filename!r}")
        if not (model / filename).is_file():
            raise FileNotFoundError(model / filename)

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent)
    )
    try:
        for filename in METADATA_FILES:
            source = model / filename
            if source.is_file():
                os.symlink(source, staging / filename)
        for filename in weight_files:
            os.symlink(model / filename, staging / filename)

        reduced_index = {"weight_map": weight_map}
        (staging / "model.safetensors.index.json").write_text(
            json.dumps(reduced_index, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema": "neural-download-qwen35-mtp-model-view-v1",
            "source_model": str(model),
            "model_type": model_type,
            "weight_entries": len(weight_map),
            "mtp_weight_entries": len(mtp_names),
            "weight_files": [
                {
                    "name": filename,
                    "size_bytes": (model / filename).stat().st_size,
                }
                for filename in weight_files
            ],
            "purpose": (
                "avoid a redundant full-checkpoint scan while loading the "
                "in-checkpoint Qwen3.5 MTP drafter"
            ),
        }
        (staging / "mtp-view-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging.rename(output)
    except BaseException:
        for child in staging.iterdir():
            child.unlink()
        staging.rmdir()
        raise

    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
