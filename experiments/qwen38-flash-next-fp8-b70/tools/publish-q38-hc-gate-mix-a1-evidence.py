#!/usr/bin/env python3
"""Transactionally publish checksummed HC gate-mix A1 evidence.

A pass receipt exists only inside the hidden staging directory until every
manifest entry verifies.  The whole directory is then renamed without replace,
so a prior result can never be overwritten or replayed as the current run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable


FINAL_PATH = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/"
    "20260901-hc-gate-mix-exact-staged-a1"
)
STAGE_PATH = FINAL_PATH.with_name(FINAL_PATH.name + ".staging")


class PublicationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


def evidence_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PublicationError(f"evidence contains a symlink: {path}")
        if path.is_file() and path.name not in {"SHA256SUMS", "SHA256SUMS.tmp"}:
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def create_manifest(root: Path) -> Path:
    temporary = root / "SHA256SUMS.tmp"
    if temporary.exists() or temporary.is_symlink():
        raise PublicationError("temporary checksum manifest already exists")
    with temporary.open("x", encoding="utf-8") as output:
        for path in evidence_files(root):
            relative = path.relative_to(root).as_posix()
            output.write(f"{sha256(path)}  {relative}\n")
    return temporary


def verify_manifest(root: Path, manifest: Path) -> None:
    seen: set[str] = set()
    lines = manifest.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise PublicationError("checksum manifest is empty")
    for line in lines:
        if len(line) < 67 or line[64:66] != "  ":
            raise PublicationError("checksum manifest syntax is invalid")
        expected = line[:64]
        relative = line[66:]
        if (
            any(character not in "0123456789abcdef" for character in expected)
            or not relative
            or relative in seen
        ):
            raise PublicationError("checksum manifest entry is invalid or duplicated")
        seen.add(relative)
        path = root / relative
        if path.is_symlink() or not path.is_file() or sha256(path) != expected:
            raise PublicationError(f"checksum verification failed: {relative}")
    expected_files = {
        path.relative_to(root).as_posix() for path in evidence_files(root)
    }
    if seen != expected_files:
        raise PublicationError("checksum manifest coverage mismatch")


def publish_no_clobber(stage: Path, final: Path) -> None:
    """Claim the final root exclusively and move verified pass health last.

    The evidence filesystem is NTFS/FUSE and rejects RENAME_NOREPLACE.  An
    exclusive mkdir provides the no-clobber claim.  All directories and files
    are then moved within that claimed root, with final-health.json strictly
    last.  A crash can therefore leave only an obvious incomplete root without
    a pass receipt; it can never expose pass before the verified manifest and
    every covered payload are already present.
    """
    try:
        final.mkdir(mode=0o700)
    except FileExistsError:
        raise FileExistsError(final) from None

    directories = sorted(
        (path for path in stage.rglob("*") if path.is_dir()),
        key=lambda path: (len(path.relative_to(stage).parts), path.as_posix()),
    )
    for directory in directories:
        (final / directory.relative_to(stage)).mkdir(mode=0o700)

    health = stage / "final-health.json"
    files = [path for path in evidence_files(stage) if path != health]
    files.append(stage / "SHA256SUMS")
    for source in files:
        destination = final / source.relative_to(stage)
        if destination.exists() or destination.is_symlink():
            raise PublicationError(
                f"claimed evidence destination exists: {destination}"
            )
        os.rename(source, destination)

    # Commit marker: this is deliberately the final evidence move.
    destination_health = final / "final-health.json"
    if destination_health.exists() or destination_health.is_symlink():
        raise PublicationError("final health destination already exists")
    os.rename(health, destination_health)

    for directory in reversed(directories):
        directory.rmdir()
    stage.rmdir()
    final.chmod(0o500)


def publish(
    stage: Path,
    final: Path,
    health: dict[str, Any],
    *,
    verify_hook: Callable[[Path, Path], None] | None = None,
) -> dict[str, Any]:
    if stage.is_symlink() or not stage.is_dir():
        raise PublicationError("staging evidence directory is missing or linked")
    if final.exists() or final.is_symlink():
        raise FileExistsError(final)
    if stage.parent != final.parent or stage.name != final.name + ".staging":
        raise PublicationError("staging and final paths do not form a transaction")
    require = {
        "schema_version",
        "status",
        "classification",
        "runner_exit_code",
        "local_nvme_corrected",
        "root_port_corrected",
        "failure_reason",
    }
    if set(health) != require:
        raise PublicationError("health receipt keys are not exact")
    if health["status"] not in {"pass", "failed_closed"}:
        raise PublicationError("health status is invalid")

    health_path = stage / "final-health.json"
    manifest_path = stage / "SHA256SUMS"
    if health_path.exists() or health_path.is_symlink():
        raise PublicationError("final health already exists")
    if manifest_path.exists() or manifest_path.is_symlink():
        raise PublicationError("checksum manifest already exists")
    requested_status = health["status"]

    def attempt(value: dict[str, Any], *, run_hook: bool) -> None:
        write_json_exclusive(health_path, value)
        temporary = create_manifest(stage)
        if run_hook and verify_hook is not None:
            verify_hook(stage, temporary)
        verify_manifest(stage, temporary)
        os.rename(temporary, manifest_path)
        verify_manifest(stage, manifest_path)

    try:
        attempt(health, run_hook=True)
    except Exception as exc:
        if requested_status != "pass":
            raise
        health_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        (stage / "SHA256SUMS.tmp").unlink(missing_ok=True)
        failure = dict(health)
        failure["status"] = "failed_closed"
        failure["runner_exit_code"] = 70
        failure["failure_reason"] = f"pre-publication checksum failure: {exc}"
        attempt(failure, run_hook=False)
        health = failure

    # final-health.json is the commit marker and is moved strictly last.
    publish_no_clobber(stage, final)
    verify_manifest(final, final / "SHA256SUMS")
    return {
        "status": health["status"],
        "runner_exit_code": health["runner_exit_code"],
        "requested_status": requested_status,
        "final_path": str(final),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-dir", type=Path, required=True)
    parser.add_argument("--final-dir", type=Path, required=True)
    parser.add_argument("--status", choices=("pass", "failed_closed"), required=True)
    parser.add_argument("--runner-exit-code", type=int, required=True)
    parser.add_argument("--nvme-baseline", type=int, required=True)
    parser.add_argument("--nvme-final", type=int, required=True)
    parser.add_argument("--nvme-delta", type=int, required=True)
    parser.add_argument("--root-baseline", type=int, required=True)
    parser.add_argument("--root-final", type=int, required=True)
    parser.add_argument("--root-delta", type=int, required=True)
    parser.add_argument("--failure-reason", default="")
    args = parser.parse_args()
    if args.stage_dir != STAGE_PATH or args.final_dir != FINAL_PATH:
        raise SystemExit("fixed HC gate-mix publication paths drifted")
    health = {
        "schema_version": 1,
        "status": args.status,
        "classification": "qwen38_hc_gate_mix_exact_staged_a1_host_health",
        "runner_exit_code": args.runner_exit_code,
        "local_nvme_corrected": {
            "baseline": args.nvme_baseline,
            "final": args.nvme_final,
            "delta": args.nvme_delta,
            "required_delta": 0,
        },
        "root_port_corrected": {
            "baseline": args.root_baseline,
            "final": args.root_final,
            "delta": args.root_delta,
            "required_delta": 0,
        },
        "failure_reason": args.failure_reason or None,
    }
    outcome = publish(args.stage_dir, args.final_dir, health)
    print(json.dumps(outcome, sort_keys=True))
    if outcome["status"] != args.status:
        raise SystemExit(70)


if __name__ == "__main__":
    main()
