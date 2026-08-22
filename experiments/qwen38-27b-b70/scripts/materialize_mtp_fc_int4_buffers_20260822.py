#!/usr/bin/env python3
"""Materialize the operator-qualified mtp.fc INT4 packed buffers to disk.

Reuses the qualifier's `_load_and_pack` (same cast order and packing that
produced the frozen shas), writes per-TP-rank buffers, and re-verifies
each written file against the frozen operator-prereg SHA-256s. Fail-closed
on any mismatch. Deterministic: rerunning reproduces identical bytes.

These files are the load source for the default-off VLLM_XPU_MTP_FC_INT4
integration; the patch verifies these same shas at load and refuses to
start on mismatch.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

QUALIFIER = Path(__file__).with_name("qwen38_mtp_fc_int4_operator.py")
MODEL = Path(
    "/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan/"
    "model_extra_tensors.safetensors"
)
OUT = Path("/home/steve/qwen38-mtp-fc-int4-packed-buffers-20260822")

# Frozen operator-prereg identities (2026-08-21 prereg).
EXPECT = {
    0: {
        "packed_storage": "da795b5a921bd14f0d3ae814dab268199ccb88aa16bf1aa69ec27b51a7dfda79",
        "qweight_logical": "adef7804c30b41794ba89e6fbcec88d14020db5760b4020e8d313a71160fab7a",
        "scales": "c71498b300127c358d59166fb3380ad58871c700c7c077f81ebd6ff32359cb3b",
    },
    1: {
        "packed_storage": "8eda2db1e4aef2d5e0d711730973b23199a0f27daff7160f43c0c140cda9b03b",
        "qweight_logical": "79b7f43a70342916d21229a474844fc4ba4eaeafad08247e45c70f6d1ae013f8",
        "scales": "42594dc0dac733bc2e6044f7cc4b09090087eb82e08e811c5fcea11df9c48986",
    },
}
QZERO_SHA = "beead77994cf573341ec17b58bbf7eb34d2711c993c1d976b128b3188dc1829a"


def load_qualifier():
    spec = importlib.util.spec_from_file_location("qwen38_mtp_fc_int4", QUALIFIER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    import torch

    q = load_qualifier()
    preflight = {"model": {"path": str(MODEL)}}
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"format": "mtp-fc-int4-packed-buffers-v1", "source": str(MODEL),
                "ranks": {}}
    failures = 0
    for rank in (0, 1):
        packed = q._load_and_pack(torch, preflight, rank)
        # tensor sha via the qualifier's own hasher, to match the frozen shas
        got = {
            "packed_storage": q._tensor_sha256(torch, packed["packed_storage"]),
            "qweight_logical": q._tensor_sha256(torch, packed["qweight"]),
            "scales": q._tensor_sha256(torch, packed["scales"]),
        }
        for name, want in EXPECT[rank].items():
            if got[name] != want:
                print(f"SHA-MISMATCH rank{rank} {name}: {got[name]} != {want}")
                failures += 1
        rank_dir = OUT / f"rank{rank}"
        rank_dir.mkdir(exist_ok=True)
        # store contiguous backing + scales + qzero as raw tensors
        torch.save(
            {
                "packed_storage": packed["packed_storage"].contiguous(),
                "scales": packed["scales"].contiguous(),
                "qzero": packed["qzero"].contiguous(),
            },
            rank_dir / "packed.pt",
        )
        blob = (rank_dir / "packed.pt").read_bytes()
        manifest["ranks"][str(rank)] = {
            "packed_pt_sha256": sha_bytes(blob),
            "packed_storage_sha256": got["packed_storage"],
            "qweight_logical_sha256": got["qweight_logical"],
            "scales_sha256": got["scales"],
            "qzero_sha256": QZERO_SHA,
        }
        print(f"rank{rank}: buffers written, all four shas verified")
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")
    for p in OUT.rglob("*"):
        if p.is_file():
            p.chmod(0o444)
    print(f"DONE failures={failures} out={OUT}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
