#!/usr/bin/env python3
"""Validate and install a frozen offline wheelhouse into a new virtualenv.

The tracked Flash-Next contract is intentionally not installable yet.  This
tool therefore exits before creating anything unless both contracts explicitly
declare a complete, hash-addressed binary wheelhouse.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_DEPENDENCY_CONTRACT = HERE / "dependency-contract.json"
DEFAULT_WHEELHOUSE_CONTRACT = HERE / "wheelhouse-contract.json"
DEFAULT_LOCK = HERE / "requirements-runtime.lock"
LOCK_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[^\s]+)"
    r"(?P<hashes>(?:\s+--hash=sha256:[0-9a-f]{64})+)$"
)


class ContractError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read JSON contract {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON contract must be an object: {path}")
    return value


def parse_lock(path: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ContractError(f"cannot read lock {path}: {exc}") from exc
    for line_number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-e ", "--editable ", "git+", "http:", "https:", "file:")):
            raise ContractError(f"lock line {line_number} uses a mutable or direct source")
        match = LOCK_RE.fullmatch(line)
        if match is None:
            raise ContractError(
                f"lock line {line_number} must be exact name==version plus SHA-256 hash"
            )
        name = match.group("name")
        normalized = normalize_name(name)
        if normalized in entries:
            raise ContractError(f"duplicate locked distribution: {name}")
        hashes = re.findall(r"--hash=sha256:([0-9a-f]{64})", match.group("hashes"))
        entries[normalized] = {
            "name": name,
            "version": match.group("version"),
            "hashes": sorted(set(hashes)),
        }
    if not entries:
        raise ContractError("lock has no installable entries")
    return entries


def validate_python(contract: dict[str, Any]) -> None:
    wanted = contract.get("python", {})
    implementation = wanted.get("implementation")
    major_minor = wanted.get("major_minor")
    actual_implementation = sys.implementation.name
    actual_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    if implementation != actual_implementation or major_minor != actual_major_minor:
        raise ContractError(
            "interpreter mismatch: expected "
            f"{implementation} {major_minor}, got {actual_implementation} {actual_major_minor}"
        )


def validate_contract_status(
    dependency_contract: dict[str, Any], wheelhouse_contract: dict[str, Any]
) -> None:
    if dependency_contract.get("status") != "dependency-installable":
        raise ContractError(
            "dependency contract is observed-only; no portable install is authorized"
        )
    if wheelhouse_contract.get("status") != "complete-binary-wheelhouse":
        raise ContractError("wheelhouse contract is not complete and installable")


def validate_wheelhouse(
    wheelhouse: Path,
    wheelhouse_contract: dict[str, Any],
    lock_entries: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not wheelhouse.is_dir():
        raise ContractError(f"wheelhouse is not a directory: {wheelhouse}")
    declared = wheelhouse_contract.get("files")
    if not isinstance(declared, list) or not declared:
        raise ContractError("wheelhouse contract has no files")

    actual_paths = sorted(path for path in wheelhouse.iterdir() if path.is_file())
    non_files = sorted(path.name for path in wheelhouse.iterdir() if not path.is_file())
    if non_files:
        raise ContractError(f"wheelhouse contains non-files: {', '.join(non_files)}")
    actual_names = [path.name for path in actual_paths]
    declared_names = [item.get("name") for item in declared if isinstance(item, dict)]
    if len(declared_names) != len(declared) or len(set(declared_names)) != len(declared_names):
        raise ContractError("wheelhouse contract has malformed or duplicate file entries")
    if sorted(declared_names) != actual_names:
        missing = sorted(set(declared_names) - set(actual_names))
        extra = sorted(set(actual_names) - set(declared_names))
        raise ContractError(f"wheelhouse inventory mismatch; missing={missing}, extra={extra}")

    seen_distributions: set[str] = set()
    verified: list[dict[str, Any]] = []
    for item in declared:
        name = item["name"]
        if not name.endswith(".whl"):
            raise ContractError(f"non-wheel artifact is forbidden: {name}")
        path = wheelhouse / name
        expected_size = item.get("size_bytes")
        expected_sha = item.get("sha256")
        distribution = normalize_name(str(item.get("distribution", "")))
        version = item.get("version")
        if not distribution or distribution in seen_distributions:
            raise ContractError(f"missing or duplicate distribution for {name}")
        seen_distributions.add(distribution)
        locked = lock_entries.get(distribution)
        if locked is None or locked["version"] != version:
            raise ContractError(f"wheel {name} does not match the exact lock")
        actual_size = path.stat().st_size
        actual_sha = sha256_file(path)
        if expected_size != actual_size or expected_sha != actual_sha:
            raise ContractError(f"wheel identity mismatch: {name}")
        if actual_sha not in locked["hashes"]:
            raise ContractError(f"wheel hash is absent from lock: {name}")
        verified.append(
            {
                "name": name,
                "distribution": distribution,
                "version": version,
                "size_bytes": actual_size,
                "sha256": actual_sha,
            }
        )
    if seen_distributions != set(lock_entries):
        missing = sorted(set(lock_entries) - seen_distributions)
        raise ContractError(f"locked distributions missing from wheelhouse: {missing}")
    return verified


def run_checked(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def install_offline(
    output_venv: Path,
    wheelhouse: Path,
    lock: Path,
    lock_entries: dict[str, dict[str, Any]],
    dependency_contract: dict[str, Any],
) -> list[dict[str, str]]:
    env = os.environ.copy()
    env.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    run_checked([sys.executable, "-m", "venv", str(output_venv)], env)
    python = output_venv / "bin" / "python"
    run_checked(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--only-binary=:all:",
            "--require-hashes",
            "--find-links",
            str(wheelhouse),
            "--requirement",
            str(lock),
        ],
        env,
    )
    probe = run_checked(
        [
            str(python),
            "-c",
            (
                "import importlib.metadata as m,json;"
                "print(json.dumps(sorted([{'name':d.metadata['Name'],'version':d.version} "
                "for d in m.distributions()],key=lambda x:x['name'].lower())))"
            ),
        ],
        env,
    )
    installed = json.loads(probe.stdout)
    installed_by_name = {
        normalize_name(item["name"]): item["version"] for item in installed
    }
    for name, item in lock_entries.items():
        if installed_by_name.get(name) != item["version"]:
            raise ContractError(f"installed version mismatch for {item['name']}")
    allowed = {
        normalize_name(name)
        for name in dependency_contract.get("allowed_unlocked_distributions", [])
    }
    extras = sorted(set(installed_by_name) - set(lock_entries) - allowed)
    if extras:
        raise ContractError(f"fresh environment contains unlocked distributions: {extras}")
    return installed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--output-venv", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--dependency-contract", type=Path, default=DEFAULT_DEPENDENCY_CONTRACT)
    parser.add_argument("--wheelhouse-contract", type=Path, default=DEFAULT_WHEELHOUSE_CONTRACT)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args(argv)

    try:
        if args.output_venv.exists():
            raise ContractError(f"refusing existing output virtualenv: {args.output_venv}")
        if args.receipt.exists():
            raise ContractError(f"refusing existing receipt: {args.receipt}")
        dependency_contract = load_json(args.dependency_contract)
        wheelhouse_contract = load_json(args.wheelhouse_contract)
        validate_contract_status(dependency_contract, wheelhouse_contract)
        validate_python(dependency_contract)
        lock_sha = sha256_file(args.lock)
        if dependency_contract.get("requirements_runtime_lock_sha256") != lock_sha:
            raise ContractError("dependency contract does not bind the lock")
        if wheelhouse_contract.get("requirements_runtime_lock_sha256") != lock_sha:
            raise ContractError("wheelhouse contract does not bind the lock")
        lock_entries = parse_lock(args.lock)
        wheels = validate_wheelhouse(args.wheelhouse, wheelhouse_contract, lock_entries)
        try:
            installed = install_offline(
                args.output_venv,
                args.wheelhouse,
                args.lock,
                lock_entries,
                dependency_contract,
            )
        except (subprocess.CalledProcessError, ContractError):
            if args.output_venv.exists():
                shutil.rmtree(args.output_venv)
            raise
        receipt = {
            "format": "qwen38-flash-next-dependency-install-receipt-v1",
            "status": "offline-install-complete",
            "dependency_contract_sha256": sha256_file(args.dependency_contract),
            "wheelhouse_contract_sha256": sha256_file(args.wheelhouse_contract),
            "requirements_runtime_lock_sha256": lock_sha,
            "python": {
                "implementation": sys.implementation.name,
                "major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
            },
            "wheel_count": len(wheels),
            "wheels": wheels,
            "installed_distributions": installed,
            "native_imports_attempted": False,
            "gpu_access_attempted": False,
        }
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ContractError, OSError, subprocess.CalledProcessError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr.rstrip(), file=sys.stderr)
        return 2
    print(f"PASS: installed {len(wheels)} exact wheels into {args.output_venv}")
    print(f"receipt: {args.receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
