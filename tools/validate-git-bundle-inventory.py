#!/usr/bin/env python3
"""Fail-closed inventory and portability guard for published Git bundles.

The repository contains historical bundles with several portability shapes.
Their exact bytes and headers are frozen as a legacy allowlist.  Every bundle
outside that frozen set must be backed by a provenance manifest.  The base
guard is offline: it verifies the complete repository census, exact hashes,
bundle headers, and the manifest's prerequisite/recovery contract.

Self-contained manifest-backed bundles are restored into an empty disposable
bare repository.  ``--verify-public-remotes`` makes the publication CI gate
fetch every declared thin prerequisite, prove its ancestry and tree, restore
the bundle in that minimally seeded repository, and independently verify all
exact public recovery refs.  Unit tests can exercise the contract offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


SCHEMA = "neural.download.git-bundle-inventory.v1"
MANIFEST_SCHEMA = "neural.download.git-bundle-provenance.v1"
FROZEN_LEGACY_ALLOWLIST_SHA256 = "328b186620ae3bc778f01a34500aa5d0df41432d2ec68db4f94f1e963a8257f1"
OID = re.compile(r"^[0-9a-f]{40,64}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
LEGACY_CLASSIFICATIONS = {
    "legacy-self-contained",
    "legacy-thin-audited-recoverable",
    "legacy-thin-public-recovery-tag",
    "legacy-thin-transitive-tracked-full",
    "legacy-thin-fork-public-prerequisite",
}
MANIFEST_CLASSIFICATIONS = {
    "manifest-backed-self-contained": "self-contained",
    "manifest-backed-thin-public-prerequisite": "thin-public-prerequisite",
}


class ValidationError(RuntimeError):
    """The checked inventory is not an exact, portable publication census."""


def _run(
    args: list[str], *, cwd: Path | None = None, timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise ValidationError(f"command failed ({completed.returncode}): {' '.join(args)}: {detail}")
    return completed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_oid(value: object, label: str) -> str:
    if not isinstance(value, str) or not OID.fullmatch(value):
        raise ValidationError(f"{label} must be a lowercase 40-64 character Git object ID")
    return value


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ValidationError(f"{label} must be a lowercase SHA-256")
    return value


def _safe_relative(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValidationError(f"{label} must be a normalized repository-relative path")
    return path


def _bundle_header(path: Path) -> tuple[str, list[str], list[dict[str, str]]]:
    with path.open("rb") as handle:
        header = bytearray()
        while len(header) <= 1024 * 1024:
            line = handle.readline()
            if not line:
                raise ValidationError(f"{path}: bundle header has no terminating blank line")
            if line in {b"\n", b"\r\n"}:
                break
            header.extend(line)
    try:
        lines = header.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{path}: non-UTF-8 bundle header: {exc}") from exc
    if not lines or lines[0] not in {"# v2 git bundle", "# v3 git bundle"}:
        raise ValidationError(f"{path}: unsupported bundle signature")

    prerequisites: list[str] = []
    refs: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    for line in lines[1:]:
        if not line or line.startswith("@"):
            continue
        if line.startswith("-"):
            prerequisites.append(_require_oid(line[1:].split(" ", 1)[0], "bundle prerequisite"))
            continue
        tip, separator, ref = line.partition(" ")
        if not separator or (ref != "HEAD" and not ref.startswith("refs/")):
            raise ValidationError(f"{path}: invalid bundle header line: {line!r}")
        if ref in seen_refs:
            raise ValidationError(f"{path}: duplicate advertised ref {ref}")
        seen_refs.add(ref)
        refs.append({"ref": ref, "tip": _require_oid(tip, f"bundle ref {ref}")})
    if not refs:
        raise ValidationError(f"{path}: bundle advertises no refs")
    return lines[0], prerequisites, refs


def _canonical_legacy(entries: list[dict[str, Any]]) -> str:
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be a JSON object: {path}")
    return value


def _validate_manifest_contract(
    repo_root: Path, entry: dict[str, Any], bundle: Path
) -> dict[str, Any]:
    manifest_meta = entry.get("manifest")
    if not isinstance(manifest_meta, dict):
        raise ValidationError(f"{entry['path']}: manifest-backed bundle requires manifest metadata")
    manifest_relative = _safe_relative(manifest_meta.get("path"), f"{entry['path']} manifest.path")
    manifest_path = repo_root / manifest_relative
    if not manifest_path.is_file():
        raise ValidationError(f"{entry['path']}: missing provenance manifest {manifest_relative}")
    expected_manifest_sha = _require_sha256(
        manifest_meta.get("sha256"), f"{entry['path']} manifest.sha256"
    )
    if _sha256(manifest_path) != expected_manifest_sha:
        raise ValidationError(f"{entry['path']}: provenance manifest SHA-256 mismatch")
    manifest = _load_json(manifest_path, "provenance manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValidationError(f"{entry['path']}: unsupported provenance manifest schema")

    declared_bundle = _safe_relative(manifest.get("bundle"), f"{entry['path']} manifest bundle")
    if (manifest_path.parent / declared_bundle).resolve() != bundle.resolve():
        raise ValidationError(f"{entry['path']}: manifest resolves to a different bundle")
    if manifest.get("bundle_size") != bundle.stat().st_size:
        raise ValidationError(f"{entry['path']}: manifest bundle size mismatch")
    if manifest.get("bundle_sha256") != entry["sha256"]:
        raise ValidationError(f"{entry['path']}: manifest bundle SHA-256 mismatch")

    expected_manifest_class = MANIFEST_CLASSIFICATIONS[entry["classification"]]
    if manifest.get("classification") != expected_manifest_class:
        raise ValidationError(f"{entry['path']}: manifest classification mismatch")
    refs = entry["advertised_refs"]
    if len(refs) != 1:
        raise ValidationError(f"{entry['path']}: manifest-backed bundle must advertise exactly one ref")
    if manifest.get("expected_ref") != refs[0]["ref"] or manifest.get("expected_tip") != refs[0]["tip"]:
        raise ValidationError(f"{entry['path']}: manifest expected ref/tip does not match header")
    _require_oid(manifest.get("expected_tree"), f"{entry['path']} manifest expected_tree")

    declared = manifest.get("prerequisites")
    if not isinstance(declared, list):
        raise ValidationError(f"{entry['path']}: manifest prerequisites must be a list")
    declared_commits: list[str] = []
    for index, prerequisite in enumerate(declared):
        label = f"{entry['path']} manifest prerequisites[{index}]"
        if not isinstance(prerequisite, dict):
            raise ValidationError(f"{label} must be an object")
        declared_commits.append(_require_oid(prerequisite.get("commit"), f"{label}.commit"))
        _require_oid(prerequisite.get("tree"), f"{label}.tree")
        remote = prerequisite.get("public_remote")
        remote_name = prerequisite.get("provenance_remote_name")
        remote_ref = prerequisite.get("provenance_ref")
        if not isinstance(remote, str) or not remote.startswith("https://"):
            raise ValidationError(f"{label}.public_remote must be an HTTPS URL")
        if not isinstance(remote_name, str) or not remote_name:
            raise ValidationError(f"{label}.provenance_remote_name must be non-empty")
        if not isinstance(remote_ref, str) or not remote_ref.startswith("refs/remotes/"):
            raise ValidationError(f"{label}.provenance_ref must be a remote-tracking ref")
    if declared_commits != entry["prerequisites"]:
        raise ValidationError(f"{entry['path']}: manifest prerequisite set does not match header")

    if expected_manifest_class == "self-contained":
        if declared_commits:
            raise ValidationError(f"{entry['path']}: self-contained manifest declares prerequisites")
        with tempfile.TemporaryDirectory(prefix="git-bundle-inventory-restore-") as raw:
            consumer = Path(raw) / "consumer.git"
            _run(["git", "init", "--bare", "-q", str(consumer)])
            _run(["git", "--git-dir", str(consumer), "bundle", "verify", str(bundle)])
            _run(
                [
                    "git",
                    "--git-dir",
                    str(consumer),
                    "fetch",
                    "--quiet",
                    "--no-tags",
                    str(bundle),
                    f"{refs[0]['ref']}:refs/restored/bundle-tip",
                ]
            )
            restored = _run(
                ["git", "--git-dir", str(consumer), "rev-parse", "refs/restored/bundle-tip"]
            ).stdout.strip()
            if restored != refs[0]["tip"]:
                raise ValidationError(f"{entry['path']}: empty restore returned wrong tip")
            _run(["git", "--git-dir", str(consumer), "fsck", "--connectivity-only", "--no-dangling"])
    else:
        if not declared_commits:
            raise ValidationError(f"{entry['path']}: thin manifest declares no prerequisite")
        recovery_refs = manifest.get("public_recovery_refs")
        if not isinstance(recovery_refs, list) or not recovery_refs:
            raise ValidationError(f"{entry['path']}: thin manifest requires public_recovery_refs")
        for index, recovery in enumerate(recovery_refs):
            label = f"{entry['path']} manifest public_recovery_refs[{index}]"
            if not isinstance(recovery, dict):
                raise ValidationError(f"{label} must be an object")
            remote = recovery.get("public_remote")
            ref = recovery.get("ref")
            if not isinstance(remote, str) or not remote.startswith("https://"):
                raise ValidationError(f"{label}.public_remote must be an HTTPS URL")
            if not isinstance(ref, str) or not ref.startswith("refs/"):
                raise ValidationError(f"{label}.ref must be a full refs/... name")
            _require_oid(recovery.get("commit"), f"{label}.commit")
            _require_oid(recovery.get("tree"), f"{label}.tree")
    return manifest


def _tracking_ref_to_public_ref(remote_name: str, tracking_ref: str, label: str) -> str:
    prefix = f"refs/remotes/{remote_name}/"
    if not tracking_ref.startswith(prefix) or tracking_ref == prefix:
        raise ValidationError(f"{label}: cannot derive public branch from {tracking_ref!r}")
    return f"refs/heads/{tracking_ref.removeprefix(prefix)}"


def _prove_manifest_public_restore(bundle: Path, manifest: dict[str, Any], label: str) -> None:
    """Network-prove public prerequisites and exact recovery refs."""
    expected_ref = manifest["expected_ref"]
    expected_tip = manifest["expected_tip"]
    expected_tree = manifest["expected_tree"]
    prerequisites = manifest["prerequisites"]
    included = manifest.get("included_commits", [])
    if not isinstance(included, list):
        raise ValidationError(f"{label}: included_commits must be a list")

    with tempfile.TemporaryDirectory(prefix="git-bundle-public-restore-") as raw:
        consumer = Path(raw) / "consumer.git"
        _run(["git", "init", "--bare", "-q", str(consumer)])
        fetched: set[tuple[str, str]] = set()
        for index, prerequisite in enumerate(prerequisites):
            commit = prerequisite["commit"]
            remote = prerequisite["public_remote"]
            source_ref = _tracking_ref_to_public_ref(
                prerequisite["provenance_remote_name"],
                prerequisite["provenance_ref"],
                f"{label} prerequisite {commit}",
            )
            advertised = _run(
                ["git", "ls-remote", "--refs", remote, source_ref], timeout=300
            ).stdout.splitlines()
            parsed = [line.split() for line in advertised if line.strip()]
            if len(parsed) != 1 or len(parsed[0]) != 2 or parsed[0][1] != source_ref:
                raise ValidationError(
                    f"{label}: public prerequisite ref {source_ref} is not uniquely advertised"
                )
            key = (remote, source_ref)
            destination = f"refs/provenance/{index}"
            if key not in fetched:
                _run(
                    [
                        "git",
                        "--git-dir",
                        str(consumer),
                        "fetch",
                        "--quiet",
                        "--no-tags",
                        remote,
                        f"{source_ref}:{destination}",
                    ],
                    timeout=600,
                )
                fetched.add(key)
            else:
                first = next(
                    i
                    for i, item in enumerate(prerequisites)
                    if (item["public_remote"], _tracking_ref_to_public_ref(
                        item["provenance_remote_name"], item["provenance_ref"], label
                    )) == key
                )
                destination = f"refs/provenance/{first}"
            if _run_no_check(
                ["git", "--git-dir", str(consumer), "merge-base", "--is-ancestor", commit, destination]
            ).returncode:
                raise ValidationError(
                    f"{label}: prerequisite {commit} is not reachable from public ref {source_ref}"
                )
            observed_tree = _run(
                ["git", "--git-dir", str(consumer), "show", "-s", "--format=%T", commit]
            ).stdout.strip()
            if observed_tree != prerequisite["tree"]:
                raise ValidationError(f"{label}: prerequisite {commit} tree mismatch")

        if _run_no_check(
            ["git", "--git-dir", str(consumer), "cat-file", "-e", f"{expected_tip}^{{commit}}"]
        ).returncode == 0:
            raise ValidationError(f"{label}: public prerequisite already contains bundle tip")
        for index, item in enumerate(included):
            if not isinstance(item, dict):
                raise ValidationError(f"{label}: included_commits[{index}] must be an object")
            commit = _require_oid(item.get("commit"), f"{label} included_commits[{index}].commit")
            _require_oid(item.get("tree"), f"{label} included_commits[{index}].tree")
            if item.get("must_be_absent_before_bundle") is True and _run_no_check(
                ["git", "--git-dir", str(consumer), "cat-file", "-e", f"{commit}^{{commit}}"]
            ).returncode == 0:
                raise ValidationError(f"{label}: included commit {commit} exists before bundle restore")

        _run(["git", "--git-dir", str(consumer), "bundle", "verify", str(bundle)])
        _run(
            [
                "git",
                "--git-dir",
                str(consumer),
                "fetch",
                "--quiet",
                "--no-tags",
                str(bundle),
                f"{expected_ref}:refs/restored/bundle-tip",
            ]
        )
        restored_tip = _run(
            ["git", "--git-dir", str(consumer), "rev-parse", "refs/restored/bundle-tip"]
        ).stdout.strip()
        restored_tree = _run(
            ["git", "--git-dir", str(consumer), "show", "-s", "--format=%T", restored_tip]
        ).stdout.strip()
        if restored_tip != expected_tip or restored_tree != expected_tree:
            raise ValidationError(f"{label}: public-seeded bundle restore returned wrong tip/tree")
        for index, item in enumerate(included):
            commit = item["commit"]
            observed_tree = _run(
                ["git", "--git-dir", str(consumer), "show", "-s", "--format=%T", commit]
            ).stdout.strip()
            if observed_tree != item["tree"]:
                raise ValidationError(f"{label}: restored included_commits[{index}] tree mismatch")
        _run(["git", "--git-dir", str(consumer), "fsck", "--connectivity-only", "--no-dangling"])

        recovery = Path(raw) / "recovery.git"
        _run(["git", "init", "--bare", "-q", str(recovery)])
        for index, item in enumerate(manifest["public_recovery_refs"]):
            remote = item["public_remote"]
            ref = item["ref"]
            advertised = [
                line.split()
                for line in _run(
                    ["git", "ls-remote", "--refs", remote, ref], timeout=300
                ).stdout.splitlines()
                if line.strip()
            ]
            if advertised != [[item["commit"], ref]]:
                raise ValidationError(
                    f"{label}: public recovery ref {ref} is not advertised at {item['commit']}"
                )
            destination = f"refs/recovery/{index}"
            _run(
                [
                    "git",
                    "--git-dir",
                    str(recovery),
                    "fetch",
                    "--quiet",
                    "--no-tags",
                    "--depth=1",
                    remote,
                    f"{ref}:{destination}",
                ],
                timeout=300,
            )
            observed_tree = _run(
                ["git", "--git-dir", str(recovery), "show", "-s", "--format=%T", destination]
            ).stdout.strip()
            if observed_tree != item["tree"]:
                raise ValidationError(f"{label}: public recovery ref {ref} tree mismatch")


def _run_no_check(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
    )


def validate_inventory(
    inventory_path: Path, *, repo_root: Path, verify_public_remotes: bool = False
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    inventory_path = inventory_path.resolve()
    inventory = _load_json(inventory_path, "bundle inventory")
    if inventory.get("schema") != SCHEMA:
        raise ValidationError(f"inventory schema must be {SCHEMA!r}")
    roots = inventory.get("bundle_roots")
    if not isinstance(roots, list) or not roots:
        raise ValidationError("bundle_roots must be a non-empty list")
    root_paths: list[Path] = []
    for index, value in enumerate(roots):
        relative = _safe_relative(value, f"bundle_roots[{index}]")
        root = repo_root / relative
        if not root.is_dir():
            raise ValidationError(f"bundle root does not exist: {relative}")
        root_paths.append(root)

    entries = inventory.get("bundles")
    if not isinstance(entries, list):
        raise ValidationError("bundles must be a list")
    if not all(isinstance(entry, dict) and isinstance(entry.get("path"), str) for entry in entries):
        raise ValidationError("every bundle inventory entry must be an object with a string path")
    paths = [entry["path"] for entry in entries]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValidationError("bundle inventory paths must be unique and sorted")

    actual_paths = sorted(
        path.relative_to(repo_root).as_posix()
        for root in root_paths
        for path in root.rglob("*.bundle")
        if path.is_file()
    )
    if paths != actual_paths:
        missing = sorted(set(actual_paths) - set(paths))
        stale = sorted(set(paths) - set(actual_paths))
        raise ValidationError(f"bundle census mismatch; untracked={missing}, absent={stale}")

    legacy: list[dict[str, Any]] = []
    manifest_backed = 0
    public_remote_proofs = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValidationError(f"bundles[{index}] must be an object")
        relative = _safe_relative(entry.get("path"), f"bundles[{index}].path")
        bundle = repo_root / relative
        classification = entry.get("classification")
        if classification not in LEGACY_CLASSIFICATIONS | MANIFEST_CLASSIFICATIONS.keys():
            raise ValidationError(f"{relative}: unknown classification {classification!r}")
        sha = _require_sha256(entry.get("sha256"), f"{relative}.sha256")
        size = entry.get("size")
        if not isinstance(size, int) or size <= 0:
            raise ValidationError(f"{relative}.size must be a positive integer")
        if bundle.stat().st_size != size or _sha256(bundle) != sha:
            raise ValidationError(f"{relative}: bundle bytes changed")
        signature, prerequisites, refs = _bundle_header(bundle)
        if entry.get("signature") != signature:
            raise ValidationError(f"{relative}: bundle signature mismatch")
        if entry.get("prerequisites") != prerequisites:
            raise ValidationError(f"{relative}: bundle prerequisites mismatch")
        if entry.get("advertised_refs") != refs:
            raise ValidationError(f"{relative}: bundle advertised refs mismatch")
        basis = entry.get("recovery_basis")
        if not isinstance(basis, str) or not basis:
            raise ValidationError(f"{relative}: recovery_basis must be non-empty")

        if classification in LEGACY_CLASSIFICATIONS:
            if "manifest" in entry:
                raise ValidationError(f"{relative}: legacy entry must not claim a manifest")
            legacy.append(entry)
        else:
            manifest_backed += 1
            manifest = _validate_manifest_contract(repo_root, entry, bundle)
            if classification == "manifest-backed-thin-public-prerequisite" and verify_public_remotes:
                _prove_manifest_public_restore(bundle, manifest, str(relative))
                public_remote_proofs += 1

    declared_legacy_digest = _require_sha256(
        inventory.get("legacy_allowlist_sha256"), "legacy_allowlist_sha256"
    )
    observed_legacy_digest = _canonical_legacy(legacy)
    if declared_legacy_digest != observed_legacy_digest:
        raise ValidationError("legacy allowlist content does not match its declared SHA-256")
    if observed_legacy_digest != FROZEN_LEGACY_ALLOWLIST_SHA256:
        raise ValidationError(
            "legacy allowlist is frozen; new or changed bundles require manifest-backed classification"
        )

    return {
        "status": "PASS",
        "inventory": str(inventory_path),
        "bundle_count": len(entries),
        "legacy_frozen_count": len(legacy),
        "manifest_backed_count": manifest_backed,
        "public_remote_proofs": public_remote_proofs,
        "legacy_allowlist_sha256": observed_legacy_digest,
        "network_used": verify_public_remotes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--verify-public-remotes",
        action="store_true",
        help="network-prove thin prerequisites/recovery refs and restore each bundle",
    )
    args = parser.parse_args()
    try:
        result = validate_inventory(
            args.inventory,
            repo_root=args.repo_root,
            verify_public_remotes=args.verify_public_remotes,
        )
    except (OSError, ValidationError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
