#!/usr/bin/env python3
"""Fail-closed manifest audit for Laguna's calibrated target FP8 KV scales."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from safetensors import safe_open

EXPECTED_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
EXPECTED_DIGEST = "3e6df440976ab2ed5229e1a39179cbc99d573c615386f223eeabc9de5ea9ddc0"
EXPECTED_LAYERS = 48


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")

    config = json.loads((args.model / "config.json").read_text())
    scheme = config.get("quantization_config", {}).get("kv_cache_scheme")
    required_scheme = {
        "dynamic": False,
        "num_bits": 8,
        "strategy": "tensor",
        "symmetric": True,
        "type": "float",
    }
    observed_scheme = {key: scheme.get(key) for key in required_scheme}
    if observed_scheme != required_scheme:
        raise SystemExit(f"unexpected KV scheme: {observed_scheme}")

    weight_map = json.loads(
        (args.model / "model.safetensors.index.json").read_text()
    )["weight_map"]
    keys = sorted(
        (
            key
            for key in weight_map
            if key.endswith((".self_attn.k_scale", ".self_attn.v_scale"))
        ),
        key=lambda key: (
            int(key.split(".")[2]),
            0 if key.endswith("k_scale") else 1,
        ),
    )
    expected_keys = [
        f"model.layers.{layer}.self_attn.{kind}_scale"
        for layer in range(EXPECTED_LAYERS)
        for kind in ("k", "v")
    ]
    if keys != expected_keys:
        raise SystemExit("target KV scale key set is not exactly 48 K/V pairs")

    digest = hashlib.sha256()
    values: list[float] = []
    for key in keys:
        with safe_open(
            args.model / weight_map[key], framework="pt", device="cpu"
        ) as handle:
            tensor = handle.get_tensor(key).float().contiguous()
        if tensor.numel() != 1:
            raise SystemExit(f"{key} is not a scalar: {tuple(tensor.shape)}")
        value = float(tensor.item())
        if not math.isfinite(value) or value <= 0:
            raise SystemExit(f"{key} has invalid scale {value}")
        values.append(value)
        raw = tensor.numpy().astype("<f4", copy=False).tobytes()
        key_bytes = key.encode()
        digest.update(len(key_bytes).to_bytes(4, "little"))
        digest.update(key_bytes)
        digest.update(len(raw).to_bytes(4, "little"))
        digest.update(raw)

    actual_digest = digest.hexdigest()
    if actual_digest != EXPECTED_DIGEST:
        raise SystemExit(
            f"target scale digest drift: {actual_digest} != {EXPECTED_DIGEST}"
        )
    result = {
        "schema": "laguna-fp8-kv-scale-manifest-v1",
        "model": str(args.model.resolve()),
        "revision": EXPECTED_REVISION,
        "scheme": observed_scheme,
        "layers": EXPECTED_LAYERS,
        "scale_tensors": len(keys),
        "all_finite_positive": True,
        "unit_scale_count": sum(value == 1.0 for value in values),
        "minimum": min(values),
        "maximum": max(values),
        "digest": actual_digest,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
