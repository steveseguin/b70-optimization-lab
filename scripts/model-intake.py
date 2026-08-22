#!/usr/bin/env python3
"""Plan, download, and verify revision-pinned model-intake artifacts.

The downloader is deliberately conservative: a writable, separately mounted
USB store with a B70 marker is required by default. Large artifacts are
downloaded to a resumable .part file, checked against the publisher's exact
byte count and SHA-256, atomically promoted, then checked through both direct
and ordinary reads by the repository's fail-closed verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPO_ROOT / "model-intake" / "catalog.json"
DEFAULT_ROOT = Path("/mnt/usb-models")
MARKER_NAME = ".b70-model-store.json"
MANIFEST_DIR = ".b70-manifests"
FORMAT = "b70-model-intake-v1"
STORE_FORMAT = "b70-model-store-v1"
DIRECT_VERIFIER = (
    REPO_ROOT
    / "repro"
    / "qwen38-27b-autoround-int4-b70"
    / "scripts"
    / "verify-model-direct.py"
)
GIB = 1024**3
HASH_CHUNK = 16 * 1024 * 1024


class IntakeError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_catalog(path: Path) -> dict[str, Any]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntakeError(f"cannot read catalog {path}: {exc}") from exc
    if catalog.get("format") != FORMAT:
        raise IntakeError(f"unsupported catalog format: {catalog.get('format')!r}")
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        raise IntakeError("catalog entries must be a list")
    seen: set[str] = set()
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", entry_id):
            raise IntakeError(f"invalid entry id: {entry_id!r}")
        if entry_id in seen:
            raise IntakeError(f"duplicate entry id: {entry_id}")
        seen.add(entry_id)
        revision = entry.get("revision")
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise IntakeError(f"{entry_id}: revision must be a 40-character commit")
        artifact = entry.get("artifact")
        if artifact is None:
            continue
        filename = artifact.get("filename")
        destination = entry.get("destination")
        if not safe_relative(filename) or not safe_relative(destination):
            raise IntakeError(f"{entry_id}: unsafe filename or destination")
        if not isinstance(artifact.get("size_bytes"), int) or artifact["size_bytes"] <= 0:
            raise IntakeError(f"{entry_id}: invalid artifact size")
        if not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256", ""))):
            raise IntakeError(f"{entry_id}: invalid artifact SHA-256")
    return catalog


def safe_relative(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.2f} {unit}"
        amount /= 1024
    raise AssertionError("unreachable")


def run_json(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        return json.loads(completed.stdout)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise IntakeError(f"failed to inspect storage with {' '.join(command)}: {exc}") from exc


def mount_info(root: Path) -> dict[str, str]:
    payload = run_json(["findmnt", "--json", "--target", str(root), "-o", "TARGET,SOURCE,FSTYPE,OPTIONS"])
    filesystems = payload.get("filesystems", [])
    if not filesystems:
        raise IntakeError(f"no filesystem contains {root}")
    item = filesystems[0]
    return {key: str(item.get(key, "")) for key in ("target", "source", "fstype", "options")}


def storage_identity(source: str) -> dict[str, str]:
    if not source.startswith("/dev/"):
        return {"transport": "unknown", "uuid": "", "label": "", "serial": ""}
    payload = run_json(
        ["lsblk", "--json", "--paths", "-o", "PATH,PKNAME,TRAN,TYPE,UUID,LABEL,SERIAL"]
    )
    flattened: dict[str, dict[str, Any]] = {}

    def visit(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            flattened[str(node.get("path", ""))] = node
            visit(node.get("children", []) or [])

    visit(payload.get("blockdevices", []))
    current = flattened.get(source)
    visited: set[str] = set()
    identity = {"transport": "unknown", "uuid": "", "label": "", "serial": ""}
    while current:
        path = str(current.get("path", ""))
        if path in visited:
            break
        visited.add(path)
        for source_key, target_key in (
            ("tran", "transport"), ("uuid", "uuid"),
            ("label", "label"), ("serial", "serial"),
        ):
            value = str(current.get(source_key) or "")
            if value and (
                (target_key == "transport" and identity[target_key] == "unknown")
                or (target_key != "transport" and not identity[target_key])
            ):
                identity[target_key] = value
        parent = str(current.get("pkname") or "")
        if parent and not parent.startswith("/dev/"):
            parent = f"/dev/{parent}"
        current = flattened.get(parent)
    return identity


def validate_store(root: Path, *, require_marker: bool, allow_non_usb: bool) -> tuple[dict[str, str], str]:
    root = root.resolve()
    if not root.is_dir():
        raise IntakeError(f"model store is not mounted or is not a directory: {root}")
    info = mount_info(root)
    if Path(info["target"]).resolve() != root:
        raise IntakeError(
            f"{root} is not a mount root (resolved filesystem target: {info['target']}); "
            "refusing to place model data in a parent filesystem"
        )
    if info["target"] == "/":
        raise IntakeError("refusing to use the operating-system filesystem")
    if "rw" not in info["options"].split(",") or not os.access(root, os.W_OK):
        raise IntakeError(f"model store is not writable: {root}")
    identity = storage_identity(info["source"])
    transport = identity["transport"]
    if transport != "usb" and not allow_non_usb:
        raise IntakeError(
            f"storage transport is {transport!r}, not 'usb'; pass --allow-non-usb only "
            "for an explicitly reviewed external store"
        )
    marker = root / MARKER_NAME
    if require_marker:
        try:
            marker_data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IntakeError(f"missing or invalid store marker {marker}: {exc}") from exc
        if marker_data.get("format") != STORE_FORMAT:
            raise IntakeError(f"unsupported store marker format in {marker}")
        for marker_key, current_key in (
            ("filesystem_uuid", "uuid"),
            ("filesystem_label", "label"),
            ("device_serial", "serial"),
        ):
            expected = str(marker_data.get(marker_key) or "")
            actual = identity[current_key]
            if expected and expected != actual:
                raise IntakeError(
                    f"store identity mismatch for {marker_key}: "
                    f"marker={expected!r}, mounted={actual!r}"
                )
    return info, transport


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as source:
        while chunk := source.read(HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def local_path(root: Path, entry: dict[str, Any]) -> Path:
    return root / entry["destination"] / entry["artifact"]["filename"]


def artifact_state(root: Path, entry: dict[str, Any]) -> str:
    artifact = entry.get("artifact")
    if not artifact:
        return "metadata-only"
    path = local_path(root, entry)
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "invalid-type"
    if path.stat().st_size != artifact["size_bytes"]:
        return "wrong-size"
    return "present-size-ok"


def selected_entries(catalog: dict[str, Any], ids: list[str], all_queued: bool) -> list[dict[str, Any]]:
    by_id = {entry["id"]: entry for entry in catalog["entries"]}
    requested = list(ids)
    if all_queued:
        requested.extend(entry["id"] for entry in catalog["entries"] if entry.get("status") == "queued")
    requested = list(dict.fromkeys(requested))
    if not requested:
        raise IntakeError("select at least one --id or pass --all-queued")
    unknown = [entry_id for entry_id in requested if entry_id not in by_id]
    if unknown:
        raise IntakeError(f"unknown catalog ids: {', '.join(unknown)}")
    entries = [by_id[entry_id] for entry_id in requested]
    for entry in entries:
        if "artifact" not in entry:
            raise IntakeError(f"{entry['id']} is metadata-only and cannot be downloaded")
    return sorted(entries, key=lambda entry: (entry.get("priority", 999), entry["id"]))


def verifier_manifest(entry: dict[str, Any]) -> dict[str, Any]:
    artifact = entry["artifact"]
    return {
        "repository": entry["repo_id"],
        "revision": entry["revision"],
        "lfs_files": [
            {
                "path": artifact["filename"],
                "bytes": artifact["size_bytes"],
                "sha256": artifact["sha256"],
            }
        ],
        "small_files": [],
    }


def manifest_path(root: Path, entry: dict[str, Any]) -> Path:
    return root / MANIFEST_DIR / f"{entry['id']}.json"


def write_verifier_manifest(root: Path, entry: dict[str, Any]) -> Path:
    path = manifest_path(root, entry)
    atomic_json(path, verifier_manifest(entry))
    return path


def direct_verify(root: Path, entry: dict[str, Any]) -> None:
    if not DIRECT_VERIFIER.is_file():
        raise IntakeError(f"direct verifier is missing: {DIRECT_VERIFIER}")
    manifest = write_verifier_manifest(root, entry)
    model_dir = root / entry["destination"]
    result_path = root / MANIFEST_DIR / f"{entry['id']}.verification.json"
    completed = subprocess.run(
        [sys.executable, str(DIRECT_VERIFIER), str(manifest), str(model_dir), "--json", str(result_path)]
    )
    if completed.returncode != 0:
        raise IntakeError(
            f"direct-and-ordinary verification failed for {entry['id']} "
            f"with exit {completed.returncode}; see {result_path}"
        )


def ordinary_verify(root: Path, entry: dict[str, Any]) -> None:
    path = local_path(root, entry)
    expected = entry["artifact"]
    if not path.is_file():
        raise IntakeError(f"missing artifact: {path}")
    actual_size = path.stat().st_size
    if actual_size != expected["size_bytes"]:
        raise IntakeError(f"wrong size for {path}: {actual_size} != {expected['size_bytes']}")
    actual_sha = sha256_file(path)
    if actual_sha != expected["sha256"]:
        raise IntakeError(f"SHA-256 mismatch for {path}: {actual_sha} != {expected['sha256']}")


def curl_download(entry: dict[str, Any], output: Path, token_file: Path) -> None:
    artifact = entry["artifact"]
    quoted_name = urllib.parse.quote(artifact["filename"], safe="/")
    url = f"https://huggingface.co/{entry['repo_id']}/resolve/{entry['revision']}/{quoted_name}?download=true"
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "curl", "--location", "--fail", "--continue-at", "-",
        "--retry", "20", "--retry-all-errors", "--connect-timeout", "30",
        "--speed-time", "120", "--speed-limit", "1024", "--output", str(output),
    ]
    auth_path: Path | None = None
    try:
        if token_file.is_file():
            token = token_file.read_text(encoding="utf-8").strip()
            if token:
                descriptor, name = tempfile.mkstemp(prefix="b70-hf-auth-")
                os.close(descriptor)
                auth_path = Path(name)
                auth_path.chmod(0o600)
                auth_path.write_text(f'header = "Authorization: Bearer {token}"\n', encoding="utf-8")
                command.extend(["--config", str(auth_path)])
        command.append(url)
        completed = subprocess.run(command)
        if completed.returncode != 0:
            raise IntakeError(f"curl failed for {entry['id']} with exit {completed.returncode}")
    finally:
        if auth_path is not None:
            auth_path.unlink(missing_ok=True)


def command_list(catalog: dict[str, Any]) -> int:
    print("priority\tstatus\tsize\tcards\tid\tmodel")
    for entry in sorted(catalog["entries"], key=lambda item: (item.get("priority", 999), item["id"])):
        size = entry.get("artifact", {}).get("size_bytes", entry.get("repository_size_bytes", 0))
        cards = ",".join(str(value) for value in entry.get("target_cards", [])) or "-"
        print(f"{entry.get('priority', '-')}\t{entry['status']}\t{human_bytes(size)}\t{cards}\t{entry['id']}\t{entry['model']}")
    return 0


def command_plan(catalog: dict[str, Any], root: Path) -> int:
    queued = [entry for entry in catalog["entries"] if entry.get("status") == "queued"]
    available = root.is_dir()
    total_missing = 0
    print(f"store: {root} ({'available' if available else 'not mounted'})")
    print("state\tsize\tid\tdestination")
    for entry in sorted(queued, key=lambda item: item["priority"]):
        state = artifact_state(root, entry) if available else "store-unavailable"
        if state not in ("present-size-ok",):
            total_missing += entry["artifact"]["size_bytes"]
        print(f"{state}\t{human_bytes(entry['artifact']['size_bytes'])}\t{entry['id']}\t{entry['destination']}")
    print(f"missing download bytes: {total_missing} ({human_bytes(total_missing)})")
    if available:
        print(f"store free bytes: {shutil.disk_usage(root).free} ({human_bytes(shutil.disk_usage(root).free)})")
    return 0


def command_init_store(root: Path, allow_non_usb: bool) -> int:
    info, transport = validate_store(root, require_marker=False, allow_non_usb=allow_non_usb)
    identity = storage_identity(info["source"])
    marker = root.resolve() / MARKER_NAME
    if marker.exists():
        raise IntakeError(f"store marker already exists: {marker}")
    atomic_json(
        marker,
        {
            "format": STORE_FORMAT,
            "created_at_utc": utc_now(),
            "mount_target": info["target"],
            "source_at_creation": info["source"],
            "filesystem_at_creation": info["fstype"],
            "transport_at_creation": transport,
            "filesystem_uuid": identity["uuid"],
            "filesystem_label": identity["label"],
            "device_serial": identity["serial"],
        },
    )
    (root / "llm-models").mkdir(exist_ok=True)
    (root / MANIFEST_DIR).mkdir(exist_ok=True)
    print(marker)
    return 0


def command_download(
    catalog: dict[str, Any], root: Path, entries: list[dict[str, Any]], reserve_gib: int,
    token_file: Path, allow_non_usb: bool, ordinary_only: bool,
) -> int:
    validate_store(root, require_marker=True, allow_non_usb=allow_non_usb)
    missing_bytes = sum(
        entry["artifact"]["size_bytes"]
        for entry in entries
        if artifact_state(root, entry) != "present-size-ok"
    )
    free = shutil.disk_usage(root).free
    required = missing_bytes + reserve_gib * GIB
    if free < required:
        raise IntakeError(
            f"insufficient free space: {human_bytes(free)} available, "
            f"{human_bytes(required)} required including {reserve_gib} GiB reserve"
        )
    for entry in entries:
        final = local_path(root, entry)
        part = final.with_name(f"{final.name}.part")
        if artifact_state(root, entry) == "present-size-ok":
            print(f"verify existing: {entry['id']}")
        else:
            if final.exists():
                raise IntakeError(f"existing destination is invalid; inspect manually: {final}")
            print(f"download: {entry['id']} -> {part}")
            if not (part.is_file() and part.stat().st_size == entry["artifact"]["size_bytes"]):
                curl_download(entry, part, token_file)
            ordinary_verify(root, {**entry, "artifact": {**entry["artifact"], "filename": part.name}})
            os.replace(part, final)
        if ordinary_only:
            ordinary_verify(root, entry)
        else:
            direct_verify(root, entry)
        atomic_json(
            final.with_name(f"{final.name}.intake.json"),
            {
                "format": FORMAT,
                "id": entry["id"],
                "repo_id": entry["repo_id"],
                "revision": entry["revision"],
                "filename": entry["artifact"]["filename"],
                "size_bytes": entry["artifact"]["size_bytes"],
                "sha256": entry["artifact"]["sha256"],
                "verified_at_utc": utc_now(),
                "verification": "ordinary-only" if ordinary_only else "direct-and-ordinary",
            },
        )
        print(f"complete: {entry['id']} ({final})")
    return 0


def command_verify(
    root: Path, entries: list[dict[str, Any]], allow_non_usb: bool, ordinary_only: bool
) -> int:
    validate_store(root, require_marker=True, allow_non_usb=allow_non_usb)
    for entry in entries:
        print(f"verify: {entry['id']}")
        if ordinary_only:
            ordinary_verify(root, entry)
        else:
            direct_verify(root, entry)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    plan = subparsers.add_parser("plan")
    plan.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    init_store = subparsers.add_parser("init-store")
    init_store.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    init_store.add_argument("--allow-non-usb", action="store_true")
    for name in ("download", "verify"):
        action = subparsers.add_parser(name)
        action.add_argument("--root", type=Path, default=DEFAULT_ROOT)
        action.add_argument("--id", action="append", default=[])
        action.add_argument("--all-queued", action="store_true")
        action.add_argument("--allow-non-usb", action="store_true")
        action.add_argument(
            "--ordinary-only", action="store_true",
            help="skip the fail-closed direct-I/O check (not suitable for promotion)",
        )
        if name == "download":
            action.add_argument("--reserve-gib", type=int, default=100)
            action.add_argument(
                "--token-file", type=Path,
                default=Path("/home/steve/.config/huggingface/token"),
            )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        catalog = load_catalog(args.catalog)
        if args.command == "list":
            return command_list(catalog)
        if args.command == "plan":
            return command_plan(catalog, args.root)
        if args.command == "init-store":
            return command_init_store(args.root, args.allow_non_usb)
        entries = selected_entries(catalog, args.id, args.all_queued)
        if args.command == "verify":
            return command_verify(args.root, entries, args.allow_non_usb, args.ordinary_only)
        if args.reserve_gib < 0:
            raise IntakeError("--reserve-gib cannot be negative")
        return command_download(
            catalog, args.root, entries, args.reserve_gib, args.token_file,
            args.allow_non_usb, args.ordinary_only,
        )
    except IntakeError as exc:
        print(f"model-intake: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
