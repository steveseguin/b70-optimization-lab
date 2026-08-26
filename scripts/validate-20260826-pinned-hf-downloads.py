#!/usr/bin/env python3
"""Fail-closed validation for the two revision-pinned 2026-08-26 downloads.

Without --execute this only prints the frozen plan.  It never reads or passes a
Hugging Face token.  Validation is deliberately sequential to avoid competing
reads on the USB/NTFS model store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPO_ROOT / "data/model-intake/post-download-validation-20260826"
ACK = "VALIDATE_PINNED_DOWNLOADS_20260826"
CHUNK = 16 * 1024 * 1024
TARGETS = (
    {
        "id": "qwen38-flash-next-fp8",
        "repo_id": "Qwen/Qwen3.8-Flash-Next-FP8",
        "revision": "bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
        "root": Path("/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"),
        "tree_sha256": "4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2",
        "file_count": 144,
        "total_bytes": 185_563_783_127,
        "lfs_count": 133,
        "lfs_bytes": 185_553_536_918,
        "shard_count": 131,
        "shard_bytes": 185_523_317_458,
        "tensor_count": 152_089,
        "index_total_size": 185_502_232_570,
        "publisher_manifest": None,
    },
    {
        "id": "deepseek-v4-flash-0731-reap",
        "repo_id": "0xSero/DeepSeek-V4-Flash-0731-REAP",
        "revision": "ddc04540efda3d2a0788b129f1fad828ddc19b60",
        "root": Path("/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-REAP"),
        "tree_sha256": "443198b60bf8215efe1e487644e4b3d67cf4069ea572b5795630f76c6f47ea6b",
        "file_count": 80,
        "total_bytes": 107_818_438_413,
        "lfs_count": 48,
        "lfs_bytes": 107_808_354_264,
        "shard_count": 48,
        "shard_bytes": 107_808_354_264,
        "tensor_count": 45_821,
        "index_total_size": 107_803_320_952,
        "publisher_manifest": "SHA256SUMS",
    },
)


class ValidationError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read strict JSON {path}: {exc}") from exc


def safe_relative(name: object) -> bool:
    if not isinstance(name, str) or not name or "\0" in name or "\\" in name:
        return False
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def digest_file(path: Path, *, sha256: bool, git_blob: bool) -> tuple[str | None, str | None]:
    size = path.stat().st_size
    h256 = hashlib.sha256() if sha256 else None
    hblob = hashlib.sha1(f"blob {size}\0".encode()) if git_blob else None
    with path.open("rb", buffering=0) as source:
        while chunk := source.read(CHUNK):
            if h256:
                h256.update(chunk)
            if hblob:
                hblob.update(chunk)
    return (h256.hexdigest() if h256 else None, hblob.hexdigest() if hblob else None)


def tree_path(target: dict[str, Any]) -> Path:
    return target["root"] / ".cache/huggingface/trees" / f"{target['revision']}.json"


def expected_shards(count: int) -> set[str]:
    return {f"model-{number:05d}-of-{count:05d}.safetensors" for number in range(1, count + 1)}


def load_and_pin_tree(target: dict[str, Any]) -> dict[str, dict[str, Any]]:
    path = tree_path(target)
    actual_tree_sha, _ = digest_file(path, sha256=True, git_blob=False)
    if actual_tree_sha != target["tree_sha256"]:
        raise ValidationError(f"{target['id']}: pinned tree SHA-256 mismatch")
    payload = load_json(path)
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict) or payload.get("format_version") != 1:
        raise ValidationError(f"{target['id']}: invalid Hugging Face tree metadata")
    for name, meta in files.items():
        if not safe_relative(name) or not isinstance(meta, dict):
            raise ValidationError(f"{target['id']}: unsafe tree entry {name!r}")
        if not isinstance(meta.get("size"), int) or meta["size"] < 0:
            raise ValidationError(f"{target['id']}: invalid size for {name}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(meta.get("blob_id", ""))):
            raise ValidationError(f"{target['id']}: invalid blob ID for {name}")
    lfs = {name: meta for name, meta in files.items() if meta.get("lfs_sha256") is not None}
    shards = expected_shards(target["shard_count"])
    checks = {
        "file_count": len(files),
        "total_bytes": sum(meta["size"] for meta in files.values()),
        "lfs_count": len(lfs),
        "lfs_bytes": sum(meta["size"] for meta in lfs.values()),
        "shard_bytes": sum(files[name]["size"] for name in shards if name in files),
    }
    for key, actual in checks.items():
        if actual != target[key]:
            raise ValidationError(f"{target['id']}: tree {key}={actual}, expected {target[key]}")
    if not shards <= files.keys():
        raise ValidationError(f"{target['id']}: tree lacks one or more pinned shards")
    return files


def active_downloads(
    proc_root: Path = Path("/proc"), targets: tuple[dict[str, Any], ...] | None = None
) -> list[str]:
    targets = TARGETS if targets is None else targets
    matches: list[str] = []
    for cmdline in proc_root.glob("[0-9]*/cmdline"):
        try:
            args = [part.decode("utf-8", "replace") for part in cmdline.read_bytes().split(b"\0") if part]
        except OSError:
            continue
        has_hf_download = any(Path(arg).name == "hf" and index + 1 < len(args) and args[index + 1] == "download" for index, arg in enumerate(args))
        if not has_hf_download:
            continue
        joined = "\0".join(args)
        if any(target["repo_id"] in joined or str(target["root"]) in joined for target in targets):
            matches.append(cmdline.parent.name)
    return sorted(matches)


def reject_live_downloads(
    proc_root: Path = Path("/proc"), targets: tuple[dict[str, Any], ...] | None = None
) -> None:
    targets = TARGETS if targets is None else targets
    live = active_downloads(proc_root, targets)
    incomplete = [
        path
        for target in targets
        for path in (target["root"] / ".cache/huggingface/download").rglob("*.incomplete")
    ]
    if live or incomplete:
        raise ValidationError(
            f"download still active: pids={live or 'none'}, incomplete_files={len(incomplete)}"
        )


def validate_inventory(target: dict[str, Any], files: dict[str, dict[str, Any]]) -> None:
    root = target["root"]
    actual: set[str] = set()
    for base, dirs, names in os.walk(root, followlinks=False):
        base_path = Path(base)
        dirs[:] = [name for name in dirs if not (base_path == root and name == ".cache")]
        for name in names:
            path = base_path / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                raise ValidationError(f"{target['id']}: non-regular artifact {rel}")
            actual.add(rel)
    expected = set(files)
    if actual != expected:
        raise ValidationError(
            f"{target['id']}: inventory mismatch missing={sorted(expected-actual)} extra={sorted(actual-expected)}"
        )
    for name, meta in files.items():
        if (root / name).stat().st_size != meta["size"]:
            raise ValidationError(f"{target['id']}: wrong byte size for {name}")

    metadata_root = root / ".cache/huggingface/download"
    metadata = {path.relative_to(metadata_root).as_posix()[:-9]: path for path in metadata_root.rglob("*.metadata")}
    if set(metadata) != expected:
        raise ValidationError(f"{target['id']}: completion metadata set does not match tree")
    for name, path in metadata.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        expected_etag = files[name].get("lfs_sha256") or files[name]["blob_id"]
        if len(lines) < 2 or lines[0] != target["revision"] or lines[1] != expected_etag:
            raise ValidationError(f"{target['id']}: bad completion metadata for {name}")


def tokenless_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_HUB_TOKEN"):
        env.pop(key, None)
    env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    return env


def validate_dry_run(target: dict[str, Any], hf_command: str, out: Path) -> None:
    command = shlex.split(hf_command) + [
        "download", target["repo_id"], "--revision", target["revision"],
        "--local-dir", str(target["root"]), "--dry-run", "--format", "json", "--max-workers", "1",
    ]
    if any("token" in item.lower() for item in command):
        raise ValidationError("refusing a dry-run command containing a token argument")
    completed = subprocess.run(command, capture_output=True, text=True, env=tokenless_env())
    (out / f"{target['id']}-dry-run.stdout.json").write_text(completed.stdout, encoding="utf-8")
    (out / f"{target['id']}-dry-run.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise ValidationError(f"{target['id']}: pinned hf dry-run failed with {completed.returncode}")
    try:
        rows = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{target['id']}: hf dry-run did not return JSON") from exc
    if not isinstance(rows, list) or len(rows) != target["file_count"]:
        raise ValidationError(f"{target['id']}: dry-run inventory count mismatch")
    if {row.get("file") for row in rows if isinstance(row, dict)} != set(load_and_pin_tree(target)):
        raise ValidationError(f"{target['id']}: dry-run file set mismatch")
    if any(row.get("size") != "-" for row in rows):
        raise ValidationError(f"{target['id']}: dry-run says one or more files need download")


def publisher_hashes(target: dict[str, Any], files: dict[str, dict[str, Any]]) -> dict[str, str]:
    manifest = target["publisher_manifest"]
    if manifest is None:
        return {}
    result: dict[str, str] = {}
    pattern = re.compile(r"^([0-9a-f]{64})  (.+)$")
    for line in (target["root"] / manifest).read_text(encoding="utf-8").splitlines():
        match = pattern.fullmatch(line)
        if not match or not safe_relative(match.group(2)) or match.group(2) in result:
            raise ValidationError(f"{target['id']}: malformed publisher checksum manifest")
        result[match.group(2)] = match.group(1)
    if set(result) != set(files) - {manifest}:
        raise ValidationError(f"{target['id']}: publisher checksum coverage is not exact")
    return result


def validate_hashes(target: dict[str, Any], files: dict[str, dict[str, Any]], out: Path) -> None:
    publisher = publisher_hashes(target, files)
    log = out / f"{target['id']}-hashes.jsonl"
    with log.open("w", encoding="utf-8") as stream:
        for name in sorted(files):
            meta = files[name]
            lfs_expected = meta.get("lfs_sha256")
            publisher_expected = publisher.get(name)
            sha256, blob = digest_file(
                target["root"] / name,
                sha256=bool(lfs_expected or publisher_expected),
                git_blob=not bool(lfs_expected),
            )
            if lfs_expected and sha256 != lfs_expected:
                raise ValidationError(f"{target['id']}: LFS SHA-256 mismatch for {name}")
            if publisher_expected and sha256 != publisher_expected:
                raise ValidationError(f"{target['id']}: publisher SHA-256 mismatch for {name}")
            if not lfs_expected and blob != meta["blob_id"]:
                raise ValidationError(f"{target['id']}: Git blob mismatch for {name}")
            stream.write(json.dumps({"file": name, "status": "pass"}, sort_keys=True) + "\n")


def read_safetensors_header(path: Path) -> dict[str, dict[str, Any]]:
    size = path.stat().st_size
    with path.open("rb", buffering=0) as source:
        raw = source.read(8)
        if len(raw) != 8:
            raise ValidationError(f"short safetensors file: {path}")
        header_size = struct.unpack("<Q", raw)[0]
        if header_size <= 0 or 8 + header_size > size:
            raise ValidationError(f"invalid safetensors header length: {path}")
        try:
            header = json.loads(source.read(header_size), object_pairs_hook=strict_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"invalid safetensors header JSON: {path}") from exc
    tensors = {key: value for key, value in header.items() if key != "__metadata__"}
    payload_size = size - 8 - header_size
    ranges: list[tuple[int, int]] = []
    for key, value in tensors.items():
        if not isinstance(value, dict) or not isinstance(value.get("dtype"), str) or not isinstance(value.get("shape"), list):
            raise ValidationError(f"invalid tensor header entry {key} in {path}")
        offsets = value.get("data_offsets")
        if not isinstance(offsets, list) or len(offsets) != 2 or not all(isinstance(item, int) for item in offsets):
            raise ValidationError(f"invalid tensor offsets {key} in {path}")
        start, end = offsets
        if start < 0 or end < start or end > payload_size:
            raise ValidationError(f"out-of-range tensor offsets {key} in {path}")
        if end > start:
            ranges.append((start, end))
    cursor = 0
    for start, end in sorted(ranges):
        if start != cursor:
            raise ValidationError(f"gap or overlap in safetensors payload: {path}")
        cursor = end
    if cursor != payload_size:
        raise ValidationError(f"unindexed safetensors payload bytes: {path}")
    return tensors


def validate_index_and_headers(target: dict[str, Any], files: dict[str, dict[str, Any]], out: Path) -> None:
    index = load_json(target["root"] / "model.safetensors.index.json")
    weight_map = index.get("weight_map") if isinstance(index, dict) else None
    if not isinstance(weight_map, dict) or len(weight_map) != target["tensor_count"]:
        raise ValidationError(f"{target['id']}: index tensor count mismatch")
    if index.get("metadata", {}).get("total_size") != target["index_total_size"]:
        raise ValidationError(f"{target['id']}: index total_size mismatch")
    shards = expected_shards(target["shard_count"])
    if set(weight_map.values()) != shards:
        raise ValidationError(f"{target['id']}: index shard closure mismatch")
    if any(name not in files for name in shards):
        raise ValidationError(f"{target['id']}: an indexed shard is absent from the pinned tree")
    assigned = {shard: {key for key, value in weight_map.items() if value == shard} for shard in shards}
    tensor_bytes = 0
    with (out / f"{target['id']}-headers.jsonl").open("w", encoding="utf-8") as stream:
        for shard in sorted(shards):
            header = read_safetensors_header(target["root"] / shard)
            if set(header) != assigned[shard]:
                raise ValidationError(f"{target['id']}: index/header tensor mismatch in {shard}")
            tensor_bytes += sum(value["data_offsets"][1] - value["data_offsets"][0] for value in header.values())
            stream.write(json.dumps({"file": shard, "tensors": len(header), "status": "pass"}, sort_keys=True) + "\n")
    if tensor_bytes != target["index_total_size"]:
        raise ValidationError(f"{target['id']}: safetensors payload total mismatch")


def frozen_plan(targets: tuple[dict[str, Any], ...] = TARGETS) -> dict[str, Any]:
    return {
        "ack": ACK,
        "evidence_root": str(EVIDENCE_ROOT),
        "sequential": True,
        "targets": [
            {key: (str(value) if isinstance(value, Path) else value) for key, value in target.items()}
            for target in targets
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="run the frozen validation")
    parser.add_argument("--ack", default="", help=f"must equal {ACK!r} with --execute")
    parser.add_argument(
        "--hf-command", default="uv tool uvx --from huggingface_hub hf",
        help="tokenless hf CLI prefix used only for the pinned dry-run",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=[target["id"] for target in TARGETS],
        help="validate only the selected pinned target; repeat to select more than one",
    )
    args = parser.parse_args(argv)
    selected_ids = set(args.target or ())
    targets = tuple(target for target in TARGETS if not selected_ids or target["id"] in selected_ids)
    if not args.execute:
        print(json.dumps(frozen_plan(targets), indent=2, sort_keys=True))
        return 0
    if args.ack != ACK:
        raise ValidationError(f"--execute requires --ack {ACK}")

    # Fail before creating evidence or doing any expensive reads.
    # Validation scope may be narrowed, but model-store I/O remains globally
    # serialized: any pinned download on the shared USB device blocks hashing.
    reject_live_downloads()
    trees = [(target, load_and_pin_tree(target)) for target in targets]
    for target, files in trees:
        validate_inventory(target, files)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = EVIDENCE_ROOT / stamp
    out.mkdir(parents=True, exist_ok=False)
    summary: dict[str, Any] = {"format": "b70-pinned-hf-post-download-validation-v1", "status": "running", "plan": frozen_plan(targets)}
    try:
        for target, files in trees:
            validate_dry_run(target, args.hf_command, out)
            validate_hashes(target, files, out)
            validate_index_and_headers(target, files, out)
        summary["status"] = "pass"
        summary["completed_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    except Exception as exc:
        summary["status"] = "fail"
        summary["error"] = str(exc)
        (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
