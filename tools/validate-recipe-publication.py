#!/usr/bin/env python3
"""Validate that a published recipe is reproducible from public artifacts.

This validator intentionally separates publication from local reproducibility.
A recipe may work on the originating host while still failing this gate because
an input is untracked, a declared digest disagrees with its build script, or a
release asset is absent.  Use --check-remote for the final release audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FORMAT = "neural.download.recipe-publication.v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
SCRIPT_REFERENCE_RE = re.compile(
    r"\$\{(?P<root>repo_root|script_dir)\}/(?P<path>[A-Za-z0-9_.+/@:-]+(?:/[A-Za-z0-9_.+/@:-]+)*)"
)
HOST_LOCAL_RE = re.compile(r"/(?:home/[^/]+|mnt/fast-ai|media/[^/]+)/")
REQUIRED_RELEASE_KINDS = {
    "build-log",
    "wheel",
    "xpu-extension",
    "gdn-library",
    "toolchain-inventory",
}
REQUIRED_BINARY_SECTIONS = {".text", ".rodata", ".data", "OFFLOAD_DEVICE_CODE"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_tracked(repo: Path, path: PurePosixPath) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", "--", path.as_posix()],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _repo_path(repo: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty repository-relative path")
        return None
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        errors.append(f"{label} must stay inside the repository: {value!r}")
        return None
    path = repo / pure
    if not path.is_file():
        errors.append(f"{label} does not exist: {value}")
    elif not _is_tracked(repo, pure):
        errors.append(f"{label} is not tracked by Git: {value}")
    return path


def _read_shell_assignments(script: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in script.read_text().splitlines():
        match = ASSIGNMENT_RE.match(raw_line.strip())
        if not match:
            continue
        key, value = match.groups()
        values[key] = value.strip().strip('"\'')
    return values


def _resolve_shell_path(repo: Path, script: Path, value: str) -> Path | None:
    if value.startswith("${repo_root}/"):
        return repo / value.removeprefix("${repo_root}/")
    if value.startswith("${script_dir}/"):
        return script.parent / value.removeprefix("${script_dir}/")
    return None


def _validate_build_script(repo: Path, script: Path, errors: list[str]) -> None:
    label = script.relative_to(repo).as_posix()
    text = script.read_text()
    assignments = _read_shell_assignments(script)

    if HOST_LOCAL_RE.search(text):
        errors.append(f"{label}: contains an originating-host-only path")

    for match in SCRIPT_REFERENCE_RE.finditer(text):
        root = repo if match.group("root") == "repo_root" else script.parent
        referenced = root / match.group("path")
        try:
            relative = referenced.resolve().relative_to(repo.resolve())
        except ValueError:
            errors.append(f"{label}: referenced path escapes the repository: {referenced}")
            continue
        # Root-discovery expressions such as ${script_dir}/../.. intentionally
        # resolve to a directory. File closure is checked below; directory
        # references are navigation, not publishable artifacts.
        if referenced.is_dir():
            continue
        if not referenced.is_file():
            errors.append(f"{label}: referenced file does not exist: {relative.as_posix()}")
        elif not _is_tracked(repo, PurePosixPath(relative.as_posix())):
            errors.append(f"{label}: referenced file is not tracked: {relative.as_posix()}")

    # A digest beside a path in the same build script is an executable
    # contract. Validate the contract directly instead of duplicating it in a
    # second hand-maintained allow-list.
    for key, value in assignments.items():
        digest_key = f"{key}_sha256"
        expected = assignments.get(digest_key)
        if expected is None:
            continue
        path = _resolve_shell_path(repo, script, value)
        if path is None:
            continue
        if not SHA256_RE.fullmatch(expected):
            errors.append(f"{label}: {digest_key} is not a lowercase SHA-256 digest")
            continue
        if not path.is_file():
            errors.append(f"{label}: {key} does not resolve: {path}")
            continue
        actual = _sha256(path)
        if actual != expected:
            errors.append(
                f"{label}: {key} digest contract failed; expected {expected}, actual {actual}"
            )


def _validate_remote_asset(asset: dict[str, Any], errors: list[str]) -> None:
    name = asset["name"]
    request = Request(asset["url"], headers={"User-Agent": "neural-download-publication-audit/1"})
    digest = hashlib.sha256()
    size = 0
    try:
        with urlopen(request, timeout=60) as response:
            with tempfile.TemporaryFile() as sink:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    sink.write(block)
                    digest.update(block)
                    size += len(block)
    except (HTTPError, URLError, TimeoutError) as exc:
        errors.append(f"release asset {name}: cannot download {asset['url']}: {exc}")
        return
    if size != asset["size"]:
        errors.append(f"release asset {name}: expected {asset['size']} bytes, downloaded {size}")
    if digest.hexdigest() != asset["sha256"]:
        errors.append(
            f"release asset {name}: expected SHA-256 {asset['sha256']}, downloaded {digest.hexdigest()}"
        )


def validate_manifest(repo: Path, manifest_path: Path, check_remote: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read publication manifest {manifest_path}: {exc}"]

    label = manifest_path.relative_to(repo).as_posix()
    if not _is_tracked(repo, PurePosixPath(label)):
        errors.append(f"{label}: publication manifest is not tracked by Git")
    if manifest.get("format") != FORMAT:
        errors.append(f"{label}: format must be {FORMAT!r}")
    if manifest.get("publication_status") not in {"draft", "published"}:
        errors.append(f"{label}: publication_status must be 'draft' or 'published'")
    _repo_path(repo, manifest.get("guide"), f"{label}.guide", errors)

    repository = manifest.get("repository")
    if not isinstance(repository, dict):
        errors.append(f"{label}.repository must be an object")
        repository = {}
    scripts = repository.get("build_scripts")
    if not isinstance(scripts, list) or not scripts:
        errors.append(f"{label}.repository.build_scripts must be a non-empty list")
    else:
        for index, value in enumerate(scripts):
            path = _repo_path(repo, value, f"{label}.repository.build_scripts[{index}]", errors)
            if path is not None and path.is_file():
                _validate_build_script(repo, path, errors)

    inputs = repository.get("immutable_inputs")
    if not isinstance(inputs, list) or not inputs:
        errors.append(f"{label}.repository.immutable_inputs must be a non-empty list")
    else:
        for index, item in enumerate(inputs):
            item_label = f"{label}.repository.immutable_inputs[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{item_label} must be an object")
                continue
            path = _repo_path(repo, item.get("path"), f"{item_label}.path", errors)
            expected = item.get("sha256")
            if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
                errors.append(f"{item_label}.sha256 must be a lowercase SHA-256 digest")
            elif path is not None and path.is_file() and _sha256(path) != expected:
                errors.append(f"{item_label}: repository artifact digest mismatch")

    sources = manifest.get("source_repositories")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{label}.source_repositories must be a non-empty list")
    else:
        for index, source in enumerate(sources):
            source_label = f"{label}.source_repositories[{index}]"
            if not isinstance(source, dict):
                errors.append(f"{source_label} must be an object")
                continue
            if not isinstance(source.get("url"), str) or not source["url"].startswith("https://"):
                errors.append(f"{source_label}.url must be an HTTPS URL")
            if not isinstance(source.get("commit"), str) or not COMMIT_RE.fullmatch(source["commit"]):
                errors.append(f"{source_label}.commit must be a full 40-character Git commit")

    release = manifest.get("release")
    if not isinstance(release, dict):
        errors.append(f"{label}.release must be an object")
        release = {}
    if not isinstance(release.get("tag"), str) or not release["tag"]:
        errors.append(f"{label}.release.tag must be a non-empty immutable tag")
    if not isinstance(release.get("url"), str) or not release["url"].startswith("https://"):
        errors.append(f"{label}.release.url must be an HTTPS URL")
    assets = release.get("assets")
    found_kinds: set[str] = set()
    found_names: set[str] = set()
    if not isinstance(assets, list) or not assets:
        errors.append(f"{label}.release.assets must be a non-empty list")
    else:
        for index, asset in enumerate(assets):
            asset_label = f"{label}.release.assets[{index}]"
            if not isinstance(asset, dict):
                errors.append(f"{asset_label} must be an object")
                continue
            name = asset.get("name")
            kind = asset.get("kind")
            url = asset.get("url")
            digest = asset.get("sha256")
            size = asset.get("size")
            if not isinstance(name, str) or not name:
                errors.append(f"{asset_label}.name must be a non-empty string")
            elif name in found_names:
                errors.append(f"{asset_label}: duplicate asset name {name!r}")
            else:
                found_names.add(name)
            if not isinstance(kind, str) or not kind:
                errors.append(f"{asset_label}.kind must be a non-empty string")
            else:
                found_kinds.add(kind)
            if not isinstance(url, str) or not url.startswith("https://"):
                errors.append(f"{asset_label}.url must be an HTTPS URL")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(f"{asset_label}.sha256 must be a lowercase SHA-256 digest")
            if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                errors.append(f"{asset_label}.size must be a positive integer")
            if (
                check_remote
                and isinstance(name, str)
                and isinstance(url, str)
                and isinstance(digest, str)
                and SHA256_RE.fullmatch(digest)
                and isinstance(size, int)
                and size > 0
            ):
                _validate_remote_asset(asset, errors)

    binary_sections = manifest.get("binary_sections")
    if not isinstance(binary_sections, dict) or not binary_sections:
        errors.append(f"{label}.binary_sections must be a non-empty object")
    else:
        for asset_name, binary in binary_sections.items():
            binary_label = f"{label}.binary_sections[{asset_name!r}]"
            if asset_name not in found_names:
                errors.append(f"{binary_label}: binary is not a named release asset")
            if not isinstance(binary, dict):
                errors.append(f"{binary_label} must be an object")
                continue
            if binary.get("runpath") != "$ORIGIN":
                errors.append(f"{binary_label}.runpath must be '$ORIGIN'")
            sections = binary.get("sections")
            if not isinstance(sections, dict):
                errors.append(f"{binary_label}.sections must be an object")
                continue
            missing_sections = REQUIRED_BINARY_SECTIONS - set(sections)
            if missing_sections:
                errors.append(f"{binary_label}: missing section hashes {sorted(missing_sections)}")
            for section, digest in sections.items():
                if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                    errors.append(f"{binary_label}.sections[{section!r}] must be a SHA-256 digest")

    validation = manifest.get("validation")
    if not isinstance(validation, dict):
        errors.append(f"{label}.validation must be an object")
        validation = {}
    for field in ("clean_source_build", "runtime_smoke", "quality_gate"):
        if not isinstance(validation.get(field), bool):
            errors.append(f"{label}.validation.{field} must be boolean")
    quality_evidence = validation.get("quality_evidence")
    if not isinstance(quality_evidence, list) or not quality_evidence:
        errors.append(f"{label}.validation.quality_evidence must be a non-empty list")
    else:
        for index, value in enumerate(quality_evidence):
            _repo_path(repo, value, f"{label}.validation.quality_evidence[{index}]", errors)

    if manifest.get("publication_status") == "published":
        missing_kinds = REQUIRED_RELEASE_KINDS - found_kinds
        if missing_kinds:
            errors.append(f"{label}: published recipe lacks release kinds {sorted(missing_kinds)}")
        if not all(validation.get(field) is True for field in (
            "clean_source_build", "runtime_smoke", "quality_gate"
        )):
            errors.append(f"{label}: published recipe requires all validation gates to pass")
        remote_verified_at = release.get("remote_verified_at")
        if not isinstance(remote_verified_at, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", remote_verified_at
        ):
            errors.append(f"{label}: published release requires remote_verified_at in UTC")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="*", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-remote", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    manifests = args.manifests or sorted(repo.glob("repro/*/publication-manifest.json"))
    if not manifests:
        print("RECIPE PUBLICATION PASS manifests=0 remote=False")
        return 0
    errors: list[str] = []
    for value in manifests:
        path = value if value.is_absolute() else repo / value
        errors.extend(validate_manifest(repo, path.resolve(), args.check_remote))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"RECIPE PUBLICATION PASS manifests={len(manifests)} remote={args.check_remote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
