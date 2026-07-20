#!/usr/bin/env python3
"""Validate and index an Option-4 M1 attention oracle packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch

RANKS = range(4)
LAYERS = range(43)
BUCKETS = {64: "swa-resident-anchor64", 512: "compressed-swa-full-anchor512"}
REQUIRED_STAGES = {
    "m1_boundary_ingress",
    "mhc_attn_out",
    "attn_in",
    "attn_input_gemm",
    "attn_qkv_norm",
    "attn_mqa_inputs",
    "attn_sparse_bindings",
    "swa_kv_before",
    "swa_kv_after",
    "swa_kv_selected",
    "attn_qk_lse_pv",
    "attn_mqa_out",
    "attn_wo_a",
    "attn_wo_b_local",
    "attn_wo_b_reduced",
    "attn_o_proj_out",
    "attn_out",
}


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def tensor_raw_sha(path: Path) -> tuple[str, list[int]]:
    tensor = torch.load(path, map_location="cpu", weights_only=True).contiguous()
    raw = tensor.view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest(), tensor.tolist()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw_dir = args.packet / "raw"
    source_manifests = sorted(raw_dir.glob("rank*.jsonl"))
    if len(source_manifests) != 4:
        raise SystemExit(f"expected 4 rank JSONL files, found {len(source_manifests)}")

    by_rank_forward: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    shared_static: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    global_static: dict[int, list[dict[str, Any]]] = defaultdict(list)
    position_by_rank_forward: dict[tuple[int, int], int] = {}
    payload_count = 0
    payload_bytes = 0
    payload_failures: list[str] = []
    source_rows = 0

    for source in source_manifests:
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        source_rows += len(rows)
        ranks = {int(row["rank"]) for row in rows}
        if len(ranks) != 1:
            raise SystemExit(f"mixed ranks in {source}: {sorted(ranks)}")
        rank = ranks.pop()
        for row in rows:
            forward = int(row["forward"])
            by_rank_forward[rank, forward].append(row)
            if row["stage"] == "attn_static_binding" and row["layer"] is not None:
                shared_static[rank, int(row["layer"])].append(row)
            if row["stage"] == "attn_global_static_binding":
                global_static[rank].append(row)
            tensor_path = row.get("tensor_path")
            if not tensor_path:
                payload_failures.append(f"missing tensor_path: {source.name}:{row}")
                continue
            path = raw_dir / tensor_path
            if not path.is_file():
                payload_failures.append(f"missing payload: {path}")
                continue
            actual_sha, values = tensor_raw_sha(path)
            payload_count += 1
            payload_bytes += path.stat().st_size
            if actual_sha != row["raw_sha256"]:
                payload_failures.append(
                    f"raw checksum mismatch: {path.name} {actual_sha} != {row['raw_sha256']}"
                )
            if row["stage"] == "forward_input" and row["tensor_name"] == "positions":
                if not isinstance(values, list) or len(values) != 1:
                    raise SystemExit(f"non-singleton capture position in {path}")
                position_by_rank_forward[rank, forward] = int(values[0])

    if payload_failures:
        raise SystemExit("\n".join(payload_failures[:20]))

    requests = json.loads(args.requests.read_text())
    if requests.get("anchors") != [64, 512]:
        raise SystemExit("capture request anchors are not exactly [64, 512]")
    if not requests.get("warmup_completed_before_arm"):
        raise SystemExit("two-bucket pre-arm warmup was not completed")
    if not requests.get("cached_tokens_all_zero"):
        raise SystemExit("armed capture requests were not all cache-zero")

    log_lines = args.server_log.read_text(errors="replace").splitlines()
    posts = [
        index
        for index, line in enumerate(log_lines)
        if '"POST /v1/completions HTTP/1.1" 200 OK' in line
    ]
    if len(posts) < 5:
        raise SystemExit(f"expected at least five successful requests, found {len(posts)}")
    posts = posts[-5:]
    armed_jit = [
        line
        for line in log_lines[posts[1] + 1 : posts[3] + 1]
        if "JIT compilation during inference" in line
    ]
    if armed_jit:
        raise SystemExit("lazy compilation in armed window:\n" + "\n".join(armed_jit))
    prearm_jit = [
        line
        for line in log_lines[: posts[1] + 1]
        if "JIT compilation during inference" in line
    ]
    postarm_jit = [
        line
        for line in log_lines[posts[3] + 1 :]
        if "JIT compilation during inference" in line
    ]

    instance_dir = args.packet / "manifests"
    if instance_dir.exists():
        raise SystemExit(f"refusing to overwrite manifest directory: {instance_dir}")
    instance_dir.mkdir()
    instance_rows: list[dict[str, Any]] = []
    for rank in RANKS:
        forwards = {
            position: forward
            for (seen_rank, forward), position in position_by_rank_forward.items()
            if seen_rank == rank
        }
        if set(forwards) != set(BUCKETS):
            raise SystemExit(f"rank {rank} positions are {sorted(forwards)}, expected 64,512")
        rotary = [
            row
            for row in global_static[rank]
            if row["tensor_name"] == "attn_rotary_cos_sin_cache"
        ]
        if len(rotary) != 1:
            raise SystemExit(
                f"rank {rank} expected one shared RoPE table binding, found {len(rotary)}"
            )
        for position, bucket in BUCKETS.items():
            forward = forwards[position]
            forward_rows = by_rank_forward[rank, forward]
            for layer in LAYERS:
                dynamic = [row for row in forward_rows if row["layer"] == layer]
                stages = {str(row["stage"]) for row in dynamic}
                missing = sorted(REQUIRED_STAGES - stages)
                static = shared_static[rank, layer]
                if missing or not static:
                    raise SystemExit(
                        f"rank={rank} layer={layer} position={position} "
                        f"missing_stages={missing} static_records={len(static)}"
                    )
                record_refs = [
                    {
                        "stage": row["stage"],
                        "tensor_name": row["tensor_name"],
                        "raw_sha256": row["raw_sha256"],
                        "tensor_path": row["tensor_path"],
                    }
                    for row in dynamic
                ]
                static_refs = [
                    {
                        "stage": row["stage"],
                        "tensor_name": row["tensor_name"],
                        "raw_sha256": row["raw_sha256"],
                        "tensor_path": row["tensor_path"],
                        "binding": row["binding"],
                    }
                    for row in static
                ]
                manifest = {
                    "schema": "option4-m1-attention-boundary-instance-v1",
                    "rank": rank,
                    "layer": layer,
                    "position": position,
                    "bucket": bucket,
                    "forward": forward,
                    "records": record_refs,
                    "shared_static_records": static_refs,
                    "global_static_records": [
                        {
                            "stage": row["stage"],
                            "tensor_name": row["tensor_name"],
                            "raw_sha256": row["raw_sha256"],
                            "tensor_path": row["tensor_path"],
                            "binding": row["binding"],
                        }
                        for row in rotary
                    ],
                }
                manifest["manifest_sha256"] = canonical_sha(manifest)
                path = instance_dir / f"rank{rank}-layer{layer:02d}-{bucket}.json"
                path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                instance_rows.append(
                    {
                        "path": str(path.relative_to(args.packet)),
                        "rank": rank,
                        "layer": layer,
                        "position": position,
                        "bucket": bucket,
                        "manifest_sha256": manifest["manifest_sha256"],
                    }
                )

    aggregate = {
        "schema": "option4-m1-attention-boundary-packet-v1",
        "passed": len(instance_rows) == 344,
        "coverage": {
            "instances": len(instance_rows),
            "required_instances": 344,
            "ranks": 4,
            "layers": 43,
            "buckets": list(BUCKETS.values()),
        },
        "checksums": {
            "payloads_verified": payload_count,
            "payload_file_bytes": payload_bytes,
            "source_rows": source_rows,
            "aggregate_instance_sha256": canonical_sha(instance_rows),
        },
        "jit": {
            "prearm_compilations": len(prearm_jit),
            "armed_window_compilations": len(armed_jit),
            "postarm_flush_compilations": len(postarm_jit),
            "request_post_line_numbers": [value + 1 for value in posts],
        },
        "instances": instance_rows,
    }
    aggregate["packet_manifest_sha256"] = canonical_sha(aggregate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: aggregate[key] for key in ("passed", "coverage", "checksums", "jit", "packet_manifest_sha256")}, indent=2, sort_keys=True))
    return 0 if aggregate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
