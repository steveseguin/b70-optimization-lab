#!/usr/bin/env python3
"""Create a validated DFlash checkpoint with an offline adapter overlaid."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from safetensors import safe_open
from safetensors.torch import save_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()
    adapter_path = Path(args.adapter).resolve()
    out_dir = Path(args.out_dir).resolve()
    base_model = base_dir / "model.safetensors"
    out_model = out_dir / "model.safetensors"
    out_tmp = out_dir / "model.safetensors.tmp"

    if not base_model.is_file():
        raise FileNotFoundError(base_model)
    if not adapter_path.is_file():
        raise FileNotFoundError(adapter_path)
    if out_dir == base_dir:
        raise ValueError("--out-dir must not be the base checkpoint directory")
    if out_model.exists() or out_tmp.exists():
        raise FileExistsError(f"Refusing to overwrite {out_model} or {out_tmp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    with (
        safe_open(base_model, framework="pt", device="cpu") as base_handle,
        safe_open(adapter_path, framework="pt", device="cpu") as adapter_handle,
    ):
        base_keys = set(base_handle.keys())
        adapter_keys = set(adapter_handle.keys())
        if not adapter_keys:
            raise ValueError("Adapter contains no tensors")
        unknown = sorted(adapter_keys - base_keys)
        if unknown:
            raise KeyError(f"Adapter contains unknown base keys: {unknown[:8]}")

        merged = {}
        replacements = []
        for name in sorted(base_keys):
            base_tensor = base_handle.get_tensor(name)
            if name in adapter_keys:
                adapter_tensor = adapter_handle.get_tensor(name)
                if adapter_tensor.shape != base_tensor.shape:
                    raise ValueError(
                        f"Shape mismatch for {name}: "
                        f"adapter={tuple(adapter_tensor.shape)} "
                        f"base={tuple(base_tensor.shape)}"
                    )
                if adapter_tensor.dtype != base_tensor.dtype:
                    raise ValueError(
                        f"Dtype mismatch for {name}: "
                        f"adapter={adapter_tensor.dtype} base={base_tensor.dtype}"
                    )
                merged[name] = adapter_tensor
                replacements.append(name)
            else:
                merged[name] = base_tensor
        metadata = base_handle.metadata()
        save_file(merged, str(out_tmp), metadata=metadata)

    os.replace(out_tmp, out_model)
    copied_files = []
    for filename in ("config.json", "README.md", ".gitattributes"):
        source = base_dir / filename
        if source.is_file():
            shutil.copy2(source, out_dir / filename)
            copied_files.append(filename)

    manifest = {
        "classification": "derived_qwen27_dflash_checkpoint_not_benchmark",
        "base_dir": str(base_dir),
        "base_model_sha256": sha256_file(base_model),
        "adapter": str(adapter_path),
        "adapter_sha256": sha256_file(adapter_path),
        "output_dir": str(out_dir),
        "output_model_sha256": sha256_file(out_model),
        "base_tensor_count": len(base_keys),
        "replaced_tensor_count": len(replacements),
        "replaced_tensor_names": replacements,
        "copied_files": copied_files,
        "note": (
            "Derived draft only. Any speed or quality claim still requires "
            "target-verified strict fresh endpoint validation."
        ),
    }
    (out_dir / "merge-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
