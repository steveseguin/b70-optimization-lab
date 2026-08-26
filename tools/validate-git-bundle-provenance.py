#!/usr/bin/env python3
"""Fail closed on undeclared or privately anchored Git bundles.

A bundle is accepted only when it is either:

* self-contained and restorable in a new empty bare repository; or
* thin with every prerequisite declared and proven reachable from an explicit
  public remote-tracking ref in a supplied provenance repository.

The restore test seeds a disposable repository with only the declared
prerequisite commits before fetching the bundle. It never relies on unrelated
objects from the provenance repository.

Optional ``public_recovery_refs`` are independently fetched by exact ref into
a second empty repository. This proves that published incident-recovery tags
exist at the declared remote and resolve to the frozen commits and trees.
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


SCHEMA = "neural.download.git-bundle-provenance.v1"
CLASSIFICATIONS = {"self-contained", "thin-public-prerequisite"}
OID = re.compile(r"^[0-9a-f]{40,64}$")


class ValidationError(RuntimeError):
    """A bundle or provenance contract failed."""


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode:
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


def _bundle_header(path: Path) -> tuple[list[str], dict[str, str]]:
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
    refs: dict[str, str] = {}
    for line in lines[1:]:
        if not line or line.startswith("@"):
            continue
        if line.startswith("-"):
            token = line[1:].split(" ", 1)[0]
            prerequisites.append(_require_oid(token, "bundle prerequisite"))
            continue
        token, separator, ref = line.partition(" ")
        if not separator or not ref.startswith("refs/"):
            raise ValidationError(f"{path}: invalid bundle header line: {line!r}")
        refs[ref] = _require_oid(token, f"bundle ref {ref}")
    return prerequisites, refs


def _canonical_url(value: str) -> str:
    return value.rstrip("/").removesuffix(".git")


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValidationError(f"manifest schema must be {SCHEMA!r}")
    return value


def _resolve_bundle(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    raw = manifest.get("bundle")
    if not isinstance(raw, str) or not raw:
        raise ValidationError("manifest bundle must be a non-empty relative path")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValidationError("manifest bundle must stay under the manifest directory")
    bundle = manifest_path.parent / relative
    if not bundle.is_file():
        raise ValidationError(f"bundle does not exist: {bundle}")
    expected_size = manifest.get("bundle_size")
    if not isinstance(expected_size, int) or expected_size <= 0 or bundle.stat().st_size != expected_size:
        raise ValidationError(f"bundle size mismatch: {bundle}")
    expected_sha = manifest.get("bundle_sha256")
    if not isinstance(expected_sha, str) or _sha256(bundle) != expected_sha:
        raise ValidationError(f"bundle SHA-256 mismatch: {bundle}")
    return bundle


def _validate_public_prerequisites(
    manifest: dict[str, Any],
    header_prerequisites: list[str],
    provenance_repo: Path | None,
) -> list[dict[str, str]]:
    entries = manifest.get("prerequisites")
    if not isinstance(entries, list):
        raise ValidationError("manifest prerequisites must be a list")
    classification = manifest.get("classification")
    if classification not in CLASSIFICATIONS:
        raise ValidationError(f"unknown classification: {classification!r}")

    if classification == "self-contained":
        if entries or header_prerequisites:
            raise ValidationError("self-contained bundle must declare and contain zero prerequisites")
        return []

    if not entries or not header_prerequisites:
        raise ValidationError("thin-public-prerequisite bundle must declare at least one prerequisite")
    if provenance_repo is None:
        raise ValidationError("thin bundle validation requires --provenance-repo")
    if _run(["git", "-C", str(provenance_repo), "rev-parse", "--git-dir"], check=False).returncode:
        raise ValidationError(f"not a Git provenance repository: {provenance_repo}")

    normalized: list[dict[str, str]] = []
    declared: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValidationError(f"prerequisites[{index}] must be an object")
        commit = _require_oid(entry.get("commit"), f"prerequisites[{index}].commit")
        tree = _require_oid(entry.get("tree"), f"prerequisites[{index}].tree")
        remote_name = entry.get("provenance_remote_name")
        public_remote = entry.get("public_remote")
        public_ref = entry.get("provenance_ref")
        if not all(isinstance(item, str) and item for item in (remote_name, public_remote, public_ref)):
            raise ValidationError(f"prerequisites[{index}] public provenance fields must be non-empty strings")
        if not public_ref.startswith("refs/remotes/"):
            raise ValidationError(f"prerequisites[{index}].provenance_ref must be a remote-tracking ref")

        observed_remote = _run(
            ["git", "-C", str(provenance_repo), "remote", "get-url", remote_name]
        ).stdout.strip()
        if _canonical_url(observed_remote) != _canonical_url(public_remote):
            raise ValidationError(
                f"prerequisite {commit}: public remote mismatch: {observed_remote!r} != {public_remote!r}"
            )
        _run(["git", "-C", str(provenance_repo), "rev-parse", "--verify", f"{public_ref}^{{commit}}"])
        if _run(
            ["git", "-C", str(provenance_repo), "merge-base", "--is-ancestor", commit, public_ref],
            check=False,
        ).returncode:
            raise ValidationError(f"prerequisite {commit} is not reachable from public ref {public_ref}")
        observed_tree = _run(
            ["git", "-C", str(provenance_repo), "show", "-s", "--format=%T", commit]
        ).stdout.strip()
        if observed_tree != tree:
            raise ValidationError(f"prerequisite {commit}: tree mismatch {observed_tree} != {tree}")
        declared.append(commit)
        normalized.append(
            {
                "commit": commit,
                "tree": tree,
                "public_remote": public_remote,
                "provenance_ref": public_ref,
            }
        )

    if sorted(declared) != sorted(header_prerequisites):
        raise ValidationError(
            f"bundle prerequisites {sorted(header_prerequisites)} != declared public prerequisites {sorted(declared)}"
        )
    return normalized


def _validate_public_recovery_refs(manifest: dict[str, Any]) -> list[dict[str, str]]:
    entries = manifest.get("public_recovery_refs", [])
    if not isinstance(entries, list):
        raise ValidationError("manifest public_recovery_refs must be a list")
    normalized: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        label = f"public_recovery_refs[{index}]"
        if not isinstance(entry, dict):
            raise ValidationError(f"{label} must be an object")
        remote = entry.get("public_remote")
        ref = entry.get("ref")
        role = entry.get("role")
        if not all(isinstance(value, str) and value for value in (remote, ref, role)):
            raise ValidationError(f"{label} remote, ref, and role must be non-empty strings")
        if not ref.startswith("refs/"):
            raise ValidationError(f"{label}.ref must be a full refs/... name")
        commit = _require_oid(entry.get("commit"), f"{label}.commit")
        tree = _require_oid(entry.get("tree"), f"{label}.tree")
        normalized.append(
            {"public_remote": remote, "ref": ref, "role": role, "commit": commit, "tree": tree}
        )
    return normalized


def _prove_public_recovery_refs(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    if not entries:
        return []
    verified: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="git-bundle-public-recovery-") as raw:
        consumer = Path(raw) / "consumer.git"
        _run(["git", "init", "--bare", "-q", str(consumer)])
        for index, entry in enumerate(entries):
            remote = entry["public_remote"]
            ref = entry["ref"]
            expected_commit = entry["commit"]
            advertised = _run(["git", "ls-remote", "--refs", remote, ref], timeout=300)
            lines = [line.split() for line in advertised.stdout.splitlines() if line.strip()]
            if lines != [[expected_commit, ref]]:
                raise ValidationError(
                    f"public recovery ref {ref} is not advertised as exact commit {expected_commit}: {lines}"
                )
            destination = f"refs/recovery/{index}"
            _run(
                [
                    "git",
                    "--git-dir",
                    str(consumer),
                    "fetch",
                    "--quiet",
                    "--no-tags",
                    "--depth=1",
                    remote,
                    f"{ref}:{destination}",
                ],
                timeout=300,
            )
            restored_commit = _run(
                ["git", "--git-dir", str(consumer), "rev-parse", f"{destination}^{{commit}}"]
            ).stdout.strip()
            restored_tree = _run(
                ["git", "--git-dir", str(consumer), "show", "-s", "--format=%T", restored_commit]
            ).stdout.strip()
            if restored_commit != expected_commit or restored_tree != entry["tree"]:
                raise ValidationError(
                    f"public recovery ref {ref} restored {restored_commit}/{restored_tree}, "
                    f"expected {expected_commit}/{entry['tree']}"
                )
            verified.append(entry)
        _run(["git", "--git-dir", str(consumer), "fsck", "--connectivity-only", "--no-dangling"])
    return verified


def validate(
    manifest_path: Path,
    *,
    provenance_repo: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    bundle = _resolve_bundle(manifest_path, manifest)
    header_prerequisites, refs = _bundle_header(bundle)
    expected_ref = manifest.get("expected_ref")
    if not isinstance(expected_ref, str) or not expected_ref.startswith("refs/"):
        raise ValidationError("manifest expected_ref must be a full refs/... name")
    expected_tip = _require_oid(manifest.get("expected_tip"), "expected_tip")
    expected_tree = _require_oid(manifest.get("expected_tree"), "expected_tree")
    if refs != {expected_ref: expected_tip}:
        raise ValidationError(f"bundle refs {refs} != expected ref/tip {{{expected_ref!r}: {expected_tip!r}}}")

    public = _validate_public_prerequisites(manifest, header_prerequisites, provenance_repo)
    recovery = _validate_public_recovery_refs(manifest)
    included_raw = manifest.get("included_commits", [])
    if not isinstance(included_raw, list):
        raise ValidationError("manifest included_commits must be a list")
    included: list[dict[str, object]] = []
    for index, entry in enumerate(included_raw):
        if not isinstance(entry, dict):
            raise ValidationError(f"included_commits[{index}] must be an object")
        included.append(
            {
                "commit": _require_oid(entry.get("commit"), f"included_commits[{index}].commit"),
                "tree": _require_oid(entry.get("tree"), f"included_commits[{index}].tree"),
                "must_be_absent_before_bundle": entry.get("must_be_absent_before_bundle") is True,
            }
        )
    with tempfile.TemporaryDirectory(prefix="git-bundle-restore-") as raw:
        consumer = Path(raw) / "consumer.git"
        _run(["git", "init", "--bare", "-q", str(consumer)])
        for entry in public:
            commit = entry["commit"]
            _run(
                [
                    "git",
                    "--git-dir",
                    str(consumer),
                    "fetch",
                    "--quiet",
                    "--no-tags",
                    "--depth=1",
                    str(provenance_repo),
                    f"{commit}:refs/provenance/{commit}",
                ],
                timeout=300,
            )
            restored_tree = _run(
                ["git", "--git-dir", str(consumer), "show", "-s", "--format=%T", commit]
            ).stdout.strip()
            if restored_tree != entry["tree"]:
                raise ValidationError(f"seeded prerequisite {commit} tree mismatch")

        if _run(
            ["git", "--git-dir", str(consumer), "cat-file", "-e", f"{expected_tip}^{{commit}}"],
            check=False,
        ).returncode == 0:
            raise ValidationError("public prerequisite seed unexpectedly already contains the private record tip")
        for entry in included:
            if entry["must_be_absent_before_bundle"] and _run(
                [
                    "git",
                    "--git-dir",
                    str(consumer),
                    "cat-file",
                    "-e",
                    f"{entry['commit']}^{{commit}}",
                ],
                check=False,
            ).returncode == 0:
                raise ValidationError(
                    f"included commit {entry['commit']} unexpectedly exists before bundle restoration"
                )

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
            ],
            timeout=300,
        )
        restored_tip = _run(
            ["git", "--git-dir", str(consumer), "rev-parse", "refs/restored/bundle-tip"]
        ).stdout.strip()
        restored_tree = _run(
            ["git", "--git-dir", str(consumer), "show", "-s", "--format=%T", restored_tip]
        ).stdout.strip()
        if restored_tip != expected_tip:
            raise ValidationError(f"restored tip mismatch: {restored_tip} != {expected_tip}")
        if restored_tree != expected_tree:
            raise ValidationError(f"restored tree mismatch: {restored_tree} != {expected_tree}")
        for entry in included:
            observed_tree = _run(
                [
                    "git",
                    "--git-dir",
                    str(consumer),
                    "show",
                    "-s",
                    "--format=%T",
                    str(entry["commit"]),
                ]
            ).stdout.strip()
            if observed_tree != entry["tree"]:
                raise ValidationError(
                    f"included commit {entry['commit']} tree mismatch: {observed_tree} != {entry['tree']}"
                )
        _run(["git", "--git-dir", str(consumer), "fsck", "--connectivity-only", "--no-dangling"])

    verified_recovery = _prove_public_recovery_refs(recovery)

    return {
        "status": "PASS",
        "manifest": str(manifest_path),
        "bundle": str(bundle),
        "classification": manifest["classification"],
        "prerequisites": header_prerequisites,
        "expected_ref": expected_ref,
        "restored_tip": expected_tip,
        "restored_tree": expected_tree,
        "verified_included_commits": [entry["commit"] for entry in included],
        "verified_public_recovery_refs": [
            {"role": entry["role"], "ref": entry["ref"], "commit": entry["commit"]}
            for entry in verified_recovery
        ],
        "empty_disposable_restore": True,
        "empty_disposable_public_ref_fetch": bool(verified_recovery),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--provenance-repo", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.manifest, provenance_repo=args.provenance_repo)
    except (ValidationError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
