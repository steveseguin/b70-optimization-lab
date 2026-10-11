#!/usr/bin/env python3
"""CPU-only model admission from a loader tensor directory; never opens weights.

Input: sequence of {name, type, dimensions, bytes}. dimensions are GGUF order
(fastest axis first). The frozen census binds this particular quantized model;
runtime loader metadata must agree, rather than allowing a filename to pick a
quant format. Optional census annotations are checked, never trusted for routing.

Export: one whitespace-delimited record per tensor: name type comma-separated
dimensions bytes component. No header. This is the packet 3 C++ recorder's
directory adapter, not a payload loader. Each tensor has one owning location;
host tables are file-backed with bounded row gathering, not copied into RAM.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[5]
CENSUS = REPO / "experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json"
GIB = 1024**3
CAPACITY_PER_CARD = 68_484_595_712 // 2  # packet 1c historical capacity, not queried
ACTIVE_BYTES = 4_951_240_940


def census_directory() -> list[dict[str, Any]]:
    return json.loads(CENSUS.read_text())["tensors"]


def build_plan(directory: list[dict[str, Any]], context_tokens: int = 32768,
               capacity_per_card: int = CAPACITY_PER_CARD) -> dict[str, Any]:
    """Validate exact identity and produce a sequential two-card layer split.

    MTP is absent from these shards and is explicitly unavailable. No full
    dequantized shadow, duplicated HC matrices, or compressed KV is admitted.
    Capacity is an estimate until native allocation/peak tests pass.
    """
    if type(context_tokens) is not int or not 1 <= context_tokens <= 32768:
        raise ValueError("context_tokens must be an integer in [1, 32768]")
    if type(capacity_per_card) is not int or capacity_per_card <= 0:
        raise ValueError("capacity_per_card must be a positive integer")
    expected = {t["name"]: t for t in census_directory()}
    if not isinstance(directory, list):
        raise ValueError("directory must be a list")
    tensors = []
    seen = set()
    for t in directory:
        if not isinstance(t, dict) or not isinstance(t.get("name"), str):
            raise ValueError("every directory record requires a tensor name")
        name = t["name"]
        if name in seen:
            raise ValueError(f"duplicate tensor: {name}")
        seen.add(name)
        if name not in expected:
            raise ValueError(f"unexpected tensor: {name}")
        e = expected[name]
        dims = t.get("dimensions")
        if (not isinstance(dims, list) or not dims
                or any(type(d) is not int or d <= 0 for d in dims)):
            raise ValueError(f"invalid dimensions: {name}")
        if type(t.get("bytes")) is not int or t["bytes"] <= 0:
            raise ValueError(f"invalid byte extent: {name}")
        for key in ("type", "dimensions", "bytes"):
            if t.get(key) != e[key]:
                raise ValueError(f"{key} identity mismatch: {name}")
        for key in ("layer", "component"):
            if key in t and t[key] != e[key]:
                raise ValueError(f"{key} annotation mismatch: {name}")
        layer = e["layer"]
        component = e["component"]
        card = "host" if component in ("embedding", "ple_lookup") else (
            1 if layer is None else layer // 24)
        active = (t["bytes"] // 512 * 10 if component == "routed_experts"
                  else t["bytes"] // dims[-1] * (16 if component == "ple_lookup" else 1)
                  if card == "host" else t["bytes"])
        tensors.append({"name": name, "type": t["type"], "dimensions": list(dims),
                        "shape": list(reversed(dims)), "bytes": t["bytes"],
                        "component": component, "layer": layer, "card": card,
                        "active_bytes": active})
    if seen != set(expected):
        raise ValueError(f"missing tensors: {sorted(set(expected) - seen)}")
    tensors.sort(key=lambda t: t["name"])
    layers = []
    for index in range(48):
        members = [t for t in tensors if t["layer"] == index]
        # The two mutually exclusive projection names make the schedule data,
        # not a modulo guess copied from a model-family name.
        kinds = {"gdn" if t["component"] == "gdn" else "qsa"
                 for t in members if t["component"] in ("gdn", "qsa_attention")}
        if len(kinds) != 1:
            raise ValueError(f"ambiguous attention schedule at layer {index}")
        layers.append({"index": index, "kind": kinds.pop(), "card": index // 24,
                       "experts": 512, "top_k": 10, "shared_experts": 1,
                       "hyperconnection_streams": 4,
                       "ple": any(t["component"] == "ple_projection" for t in members),
                       "tensor_names": [t["name"] for t in members]})
    cards = []
    for card in range(2):
        owned_layers = [l for l in layers if l["card"] == card]
        gdn = sum(l["kind"] == "gdn" for l in owned_layers)
        qsa = sum(l["kind"] == "qsa" for l in owned_layers)
        ple = sum(l["ple"] for l in owned_layers)
        state = {
            "bf16_gdn": gdn * 48 * 128 * 128 * 2,
            "bf16_gdn_conv": gdn * 10240 * 3 * 2,
            # Four taps at dilation three require nine historical rows;
            # packet 1's provisional three-row PLE allowance was too small.
            "bf16_ple_conv": ple * 10240 * 9 * 2,
            "full16_kv": qsa * context_tokens * 2 * 2 * 256 * 2,
            "bf16_qsa_raw_index": qsa * context_tokens * 128 * 2,
            "bf16_qsa_pooled_index": qsa * ((context_tokens + 3) // 4) * 128 * 2,
        }
        state["rollback_gdn_conv_ple"] = sum(state[k] for k in
            ("bf16_gdn", "bf16_gdn_conv", "bf16_ple_conv"))
        # Cursor rollback for append-only KV/index is a future device gate.
        overhead = {"graphs_static_buffers": GIB, "operator_scratch": GIB,
                    "allocator_driver_reserve": GIB, "bounded_staging": GIB // 4,
                    "ple_control_metadata": 280 if ple else 0}
        weights = sum(t["bytes"] for t in tensors if t["card"] == card)
        used = weights + sum(state.values()) + sum(overhead.values())
        if used > capacity_per_card:
            raise ValueError(f"card {card} exceeds estimated budget by {used-capacity_per_card} bytes")
        cards.append({"card": card, "capacity_bytes": capacity_per_card,
                      "weight_bytes": weights, "state": state, "overhead": overhead,
                      "estimated_total_bytes": used,
                      "remaining_bytes": capacity_per_card - used})
    active = sum(t["active_bytes"] for t in tensors) + 280
    if active != ACTIVE_BYTES:
        raise ValueError("active-byte identity differs from packet 1c")
    return {"schema": "own-xpu-runtime.stage2.packet3.plan.v1", "tensors": tensors,
            "layers": layers, "per_card": cards, "context_tokens": context_tokens,
            "tensor_count": len(tensors), "decode_active_bytes": active,
            "decode_active_scope": "logical packed weights and lookup rows plus 280 metadata bytes; excludes KV/state/activations/transfers",
            "host_file_backed_bytes": sum(t["bytes"] for t in tensors if t["card"] == "host"),
            "host_gather": {"embedding_rows": 1, "ple_rows": 16,
                            "packed_bytes": 3540,
                            "contract": "device token/history selects host rows through an admitted stable device-addressable mapping; no host readback/callback in step; native mapping and bounded-residency proof pending, otherwise segmented execution only"},
            "mtp": {"available": False, "reason": "No MTP tensors in IQ3 shard directory"},
            "fit_status": "planning arithmetic only; native peak allocation unmeasured"}


def export_directory(plan: dict[str, Any], path: Path) -> None:
    path.write_text("".join(f'{t["name"]} {t["type"]} '
        f'{",".join(map(str, t["dimensions"]))} {t["bytes"]} {t["component"]}\n'
        for t in plan["tensors"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, help="loader JSON list or object containing tensors")
    parser.add_argument("--export-directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = json.loads(args.directory.read_text()) if args.directory else census_directory()
    plan = build_plan(raw["tensors"] if isinstance(raw, dict) else raw)
    if args.export_directory:
        export_directory(plan, args.export_directory)
    if args.output:
        args.output.write_text(json.dumps(plan, indent=2) + "\n")
    else:
        print(json.dumps({k: v for k, v in plan.items() if k not in ("tensors", "layers")}, indent=2))


if __name__ == "__main__":
    main()
